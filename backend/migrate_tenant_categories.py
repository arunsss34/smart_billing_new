"""
Migration: Add tenant_id to categories so each tenant manages their own.
UOM and HSN remain global (shared across all tenants).
Run: python migrate_tenant_categories.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

SQL = """
-- Add tenant_id to categories (NULL = global/system-level)
ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS tenant_id INT REFERENCES tenants(id);

-- Update category SPs to filter by tenant
CREATE OR REPLACE FUNCTION sp_list_categories(p_tenant_id INT DEFAULT NULL)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM categories
    WHERE is_active = TRUE
      AND (tenant_id IS NULL OR tenant_id = p_tenant_id)
    ORDER BY tenant_id NULLS FIRST, parent_id NULLS FIRST, name;
END; $$;

-- Save category with tenant scope
CREATE OR REPLACE FUNCTION sp_save_category(
    p_id INT, p_name VARCHAR, p_parent_id INT, p_tenant_id INT DEFAULT NULL
)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO categories(name, parent_id, tenant_id)
        VALUES (p_name, p_parent_id, p_tenant_id)
        RETURNING id INTO v_id;
    ELSE
        -- Only allow editing own tenant's categories
        UPDATE categories
        SET name = p_name, parent_id = p_parent_id
        WHERE id = p_id
          AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM categories WHERE id = v_id;
END; $$;

-- Similarly for UOM: keep global but allow tenant admins to ADD custom UOM
ALTER TABLE uom_masters
    ADD COLUMN IF NOT EXISTS tenant_id INT REFERENCES tenants(id);

CREATE OR REPLACE FUNCTION sp_list_uom(p_tenant_id INT DEFAULT NULL)
RETURNS SETOF uom_masters LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM uom_masters
    WHERE is_active = TRUE
      AND (tenant_id IS NULL OR tenant_id = p_tenant_id)
    ORDER BY tenant_id NULLS FIRST, name;
END; $$;

CREATE OR REPLACE FUNCTION sp_save_uom(
    p_id INT, p_name VARCHAR, p_abbreviation VARCHAR, p_tenant_id INT DEFAULT NULL
)
RETURNS SETOF uom_masters LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO uom_masters(name, abbreviation, tenant_id)
        VALUES (p_name, p_abbreviation, p_tenant_id)
        RETURNING id INTO v_id;
    ELSE
        UPDATE uom_masters
        SET name = p_name, abbreviation = p_abbreviation
        WHERE id = p_id
          AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM uom_masters WHERE id = v_id;
END; $$;

-- HSN: keep fully global (government standard codes)
-- Tenant admins CAN add custom HSN codes but they're shared
-- (HSN codes are universal — no tenant_id needed)
"""

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432

    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)
    await conn.execute(SQL)

    # Verify
    cat_cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'categories' ORDER BY ordinal_position
    """)
    print("Categories columns:", [r[0] for r in cat_cols])

    uom_cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'uom_masters' ORDER BY ordinal_position
    """)
    print("UOM columns:", [r[0] for r in uom_cols])

    # Test SPs
    cats = await conn.fetch("SELECT * FROM sp_list_categories(NULL)")
    print(f"Global categories visible to superadmin: {len(cats)}")

    await conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
