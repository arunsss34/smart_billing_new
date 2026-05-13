"""
Migration: Create UOM, Category, HSN master tables with SPs
Run: python migrate_masters.py
"""
import asyncio
import asyncpg
import sys
sys.path.insert(0, '.')
from app.config import settings

SQL = """
-- =============================================
-- UOM (Unit of Measure) Master
-- =============================================
CREATE TABLE IF NOT EXISTS uom_masters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,          -- e.g. Kilogram
    abbreviation VARCHAR(20) NOT NULL,   -- e.g. KG
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(abbreviation)
);

CREATE OR REPLACE FUNCTION sp_list_uom()
RETURNS SETOF uom_masters LANGUAGE plpgsql AS $$
BEGIN RETURN QUERY SELECT * FROM uom_masters WHERE is_active = TRUE ORDER BY name; END; $$;

CREATE OR REPLACE FUNCTION sp_save_uom(p_id INT, p_name VARCHAR, p_abbreviation VARCHAR)
RETURNS SETOF uom_masters LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO uom_masters(name, abbreviation) VALUES (p_name, p_abbreviation) RETURNING id INTO v_id;
    ELSE
        UPDATE uom_masters SET name = p_name, abbreviation = p_abbreviation WHERE id = p_id;
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM uom_masters WHERE id = v_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_delete_uom(p_id INT) LANGUAGE plpgsql AS $$
BEGIN UPDATE uom_masters SET is_active = FALSE WHERE id = p_id; END; $$;

-- =============================================
-- Category Master
-- =============================================
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INT REFERENCES categories(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION sp_list_categories()
RETURNS SETOF categories LANGUAGE plpgsql AS $$
BEGIN RETURN QUERY SELECT * FROM categories WHERE is_active = TRUE ORDER BY parent_id NULLS FIRST, name; END; $$;

CREATE OR REPLACE FUNCTION sp_save_category(p_id INT, p_name VARCHAR, p_parent_id INT)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO categories(name, parent_id) VALUES (p_name, p_parent_id) RETURNING id INTO v_id;
    ELSE
        UPDATE categories SET name = p_name, parent_id = p_parent_id WHERE id = p_id;
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM categories WHERE id = v_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_delete_category(p_id INT) LANGUAGE plpgsql AS $$
BEGIN UPDATE categories SET is_active = FALSE WHERE id = p_id; END; $$;

-- =============================================
-- HSN Master (with GST rates)
-- =============================================
CREATE TABLE IF NOT EXISTS hsn_masters (
    id SERIAL PRIMARY KEY,
    hsn_code VARCHAR(20) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    cgst_rate NUMERIC(5,2) DEFAULT 0,   -- e.g. 9.00
    sgst_rate NUMERIC(5,2) DEFAULT 0,   -- e.g. 9.00
    igst_rate NUMERIC(5,2) DEFAULT 0,   -- e.g. 18.00
    cess_rate NUMERIC(5,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION sp_list_hsn()
RETURNS SETOF hsn_masters LANGUAGE plpgsql AS $$
BEGIN RETURN QUERY SELECT * FROM hsn_masters WHERE is_active = TRUE ORDER BY hsn_code; END; $$;

CREATE OR REPLACE FUNCTION sp_save_hsn(
    p_id INT, p_hsn_code VARCHAR, p_description TEXT,
    p_cgst NUMERIC, p_sgst NUMERIC, p_igst NUMERIC, p_cess NUMERIC
)
RETURNS SETOF hsn_masters LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO hsn_masters(hsn_code, description, cgst_rate, sgst_rate, igst_rate, cess_rate)
        VALUES (p_hsn_code, p_description, p_cgst, p_sgst, p_igst, p_cess)
        RETURNING id INTO v_id;
    ELSE
        UPDATE hsn_masters SET
            hsn_code = p_hsn_code, description = p_description,
            cgst_rate = p_cgst, sgst_rate = p_sgst,
            igst_rate = p_igst, cess_rate = p_cess
        WHERE id = p_id;
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM hsn_masters WHERE id = v_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_delete_hsn(p_id INT) LANGUAGE plpgsql AS $$
BEGIN UPDATE hsn_masters SET is_active = FALSE WHERE id = p_id; END; $$;

-- =============================================
-- Seed: Common UOM values
-- =============================================
INSERT INTO uom_masters(name, abbreviation) VALUES
('Piece',      'PCS'),
('Kilogram',   'KG'),
('Gram',       'GM'),
('Litre',      'LTR'),
('Millilitre', 'ML'),
('Metre',      'MTR'),
('Centimetre', 'CM'),
('Box',        'BOX'),
('Dozen',      'DOZ'),
('Pack',       'PCK'),
('Bag',        'BAG'),
('Bottle',     'BTL')
ON CONFLICT (abbreviation) DO NOTHING;

-- =============================================
-- Seed: Common Categories
-- =============================================
INSERT INTO categories(name, parent_id) VALUES
('Food & Beverages', NULL),
('Electronics',      NULL),
('Clothing',         NULL),
('Health & Beauty',  NULL),
('Home & Kitchen',   NULL),
('Stationery',       NULL)
ON CONFLICT DO NOTHING;

-- =============================================
-- Seed: Common HSN Codes with GST rates
-- =============================================
INSERT INTO hsn_masters(hsn_code, description, cgst_rate, sgst_rate, igst_rate) VALUES
('0101', 'Live horses, asses, mules',          0, 0, 0),
('1001', 'Wheat and meslin',                   0, 0, 0),
('2106', 'Food preparations not elsewhere specified', 9, 9, 18),
('3004', 'Medicaments for retail sale',        6, 6, 12),
('6101', 'Mens overcoats and similar articles',6, 6, 12),
('6201', 'Mens or boys overcoats',             9, 9, 18),
('8471', 'Automatic data processing machines', 9, 9, 18),
('8517', 'Telephone sets including smartphones',9,9, 18),
('9403', 'Other furniture',                    9, 9, 18),
('9619', 'Sanitary towels and napkins',        6, 6, 12)
ON CONFLICT (hsn_code) DO NOTHING;
"""

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    user_pass, host_db = url.split("@")
    username, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    host = host_port.split(":")[0]
    port = int(host_port.split(":")[1]) if ":" in host_port else 5432

    print(f"Connecting to {host}:{port}/{dbname}...")
    conn = await asyncpg.connect(host=host, port=port, user=username, password=password, database=dbname)
    await conn.execute(SQL)

    uom_count = await conn.fetchval("SELECT COUNT(*) FROM uom_masters")
    cat_count = await conn.fetchval("SELECT COUNT(*) FROM categories")
    hsn_count = await conn.fetchval("SELECT COUNT(*) FROM hsn_masters")
    print(f"Migration complete! UOM: {uom_count} | Categories: {cat_count} | HSN: {hsn_count}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
