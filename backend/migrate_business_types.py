"""
Migration: Create business_types table with feature config
Run: python migrate_business_types.py
"""
import asyncio
import asyncpg
import sys
sys.path.insert(0, '.')
from app.config import settings

SQL = """
-- =============================================
-- Business Types Master Table
-- =============================================
CREATE TABLE IF NOT EXISTS business_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,        -- e.g. "restaurant"
    label VARCHAR(100) NOT NULL,              -- e.g. "Restaurant"
    icon VARCHAR(10) DEFAULT '🏢',
    description TEXT,
    default_features TEXT[] DEFAULT '{}',     -- array of feature keys
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- Stored Procedures for Business Types
-- =============================================

CREATE OR REPLACE FUNCTION sp_list_business_types()
RETURNS SETOF business_types
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT * FROM business_types WHERE is_active = TRUE ORDER BY label;
END;
$$;

CREATE OR REPLACE FUNCTION sp_create_business_type(
    p_name VARCHAR, p_label VARCHAR, p_icon VARCHAR,
    p_description TEXT, p_default_features TEXT[]
)
RETURNS SETOF business_types
LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO business_types(name, label, icon, description, default_features)
    VALUES (p_name, p_label, p_icon, p_description, p_default_features)
    RETURNING id INTO v_id;
    RETURN QUERY SELECT * FROM business_types WHERE id = v_id;
END;
$$;

CREATE OR REPLACE FUNCTION sp_update_business_type(
    p_id INT, p_name VARCHAR, p_label VARCHAR, p_icon VARCHAR,
    p_description TEXT, p_default_features TEXT[], p_is_active BOOLEAN
)
RETURNS SETOF business_types
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE business_types SET
        name = COALESCE(p_name, name),
        label = COALESCE(p_label, label),
        icon = COALESCE(p_icon, icon),
        description = COALESCE(p_description, description),
        default_features = COALESCE(p_default_features, default_features),
        is_active = COALESCE(p_is_active, is_active)
    WHERE id = p_id;
    RETURN QUERY SELECT * FROM business_types WHERE id = p_id;
END;
$$;

-- =============================================
-- Add business_type_id FK to tenants (if not already exists)
-- =============================================
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS business_type_id INT REFERENCES business_types(id);

-- =============================================
-- Seed: Insert the 5 default business types
-- =============================================
INSERT INTO business_types(name, label, icon, description, default_features) VALUES
(
    'restaurant', 'Restaurant', '🍽️',
    'Full-service dining with table and kitchen management',
    ARRAY['kot', 'table_mgmt']
),
(
    'bakery', 'Bakery', '🥐',
    'Bakery and confectionery with expiry date tracking',
    ARRAY['expiry_tracking']
),
(
    'supermarket', 'Supermarket', '🛒',
    'Retail supermarket with barcode scanning and inventory',
    ARRAY['barcode']
),
(
    'dress_shop', 'Dress Shop', '👗',
    'Clothing and apparel with size and color variant tracking',
    ARRAY['size_color_variants']
),
(
    'mobile_shop', 'Mobile Shop', '📱',
    'Electronics and mobile store with IMEI tracking',
    ARRAY['imei_tracking', 'barcode']
)
ON CONFLICT (name) DO UPDATE SET
    label = EXCLUDED.label,
    icon = EXCLUDED.icon,
    description = EXCLUDED.description,
    default_features = EXCLUDED.default_features;

-- Update existing tenants to link business_type_id
UPDATE tenants t
SET business_type_id = bt.id
FROM business_types bt
WHERE t.business_type = bt.name AND t.business_type_id IS NULL;
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
    print("Migration complete!")

    # Verify
    rows = await conn.fetch("SELECT id, name, label, icon, default_features FROM business_types ORDER BY id")
    print(f"\n{len(rows)} business types seeded:")
    for r in rows:
        print(f"  [{r['id']}] {r['icon']} {r['label']} ({r['name']}) -> {list(r['default_features'])}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
