"""
Migration: Isolate tenant masters + auto-provision when tenant created
- Tenant admin sees ONLY their own records (tenant_id = their_id)
- On tenant creation, auto-copy business-type templates as tenant-specific records
- Super admin sees all global/system templates
Run: python migrate_isolated_masters.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

SQL = """
-- Add tenant_id to hsn_masters (so tenants have their own HSN list)
ALTER TABLE hsn_masters
    ADD COLUMN IF NOT EXISTS tenant_id INT REFERENCES tenants(id);

-- =============================================
-- UPDATE SPs: Strict tenant isolation
-- =============================================

-- Categories: tenant admin sees ONLY their own
CREATE OR REPLACE FUNCTION sp_list_categories(
    p_tenant_id INT DEFAULT NULL,
    p_business_type_id INT DEFAULT NULL
)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
BEGIN
    IF p_tenant_id IS NULL THEN
        -- Super admin: see system templates (tenant_id IS NULL)
        RETURN QUERY
        SELECT * FROM categories
        WHERE is_active = TRUE
          AND tenant_id IS NULL
          AND (business_type_id = p_business_type_id OR p_business_type_id IS NULL)
        ORDER BY business_type_id NULLS FIRST, parent_id NULLS FIRST, name;
    ELSE
        -- Tenant admin: see ONLY their own records
        RETURN QUERY
        SELECT * FROM categories
        WHERE is_active = TRUE
          AND tenant_id = p_tenant_id
        ORDER BY parent_id NULLS FIRST, name;
    END IF;
END; $$;

-- UOM: tenant admin sees ONLY their own
CREATE OR REPLACE FUNCTION sp_list_uom(p_tenant_id INT DEFAULT NULL)
RETURNS SETOF uom_masters LANGUAGE plpgsql AS $$
BEGIN
    IF p_tenant_id IS NULL THEN
        RETURN QUERY SELECT * FROM uom_masters
        WHERE is_active = TRUE AND tenant_id IS NULL ORDER BY name;
    ELSE
        RETURN QUERY SELECT * FROM uom_masters
        WHERE is_active = TRUE AND tenant_id = p_tenant_id ORDER BY name;
    END IF;
END; $$;

-- HSN: tenant admin sees ONLY their own
CREATE OR REPLACE FUNCTION sp_list_hsn(p_tenant_id INT DEFAULT NULL)
RETURNS SETOF hsn_masters LANGUAGE plpgsql AS $$
BEGIN
    IF p_tenant_id IS NULL THEN
        RETURN QUERY SELECT * FROM hsn_masters
        WHERE is_active = TRUE AND tenant_id IS NULL ORDER BY hsn_code;
    ELSE
        RETURN QUERY SELECT * FROM hsn_masters
        WHERE is_active = TRUE AND tenant_id = p_tenant_id ORDER BY hsn_code;
    END IF;
END; $$;

-- Save Category with strict tenant scope
CREATE OR REPLACE FUNCTION sp_save_category(
    p_id INT,
    p_name VARCHAR,
    p_parent_id INT,
    p_tenant_id INT DEFAULT NULL,
    p_business_type_id INT DEFAULT NULL
)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO categories(name, parent_id, tenant_id, business_type_id)
        VALUES (p_name, p_parent_id, p_tenant_id, p_business_type_id)
        RETURNING id INTO v_id;
    ELSE
        UPDATE categories
        SET name = p_name, parent_id = p_parent_id
        WHERE id = p_id
          AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM categories WHERE id = v_id;
END; $$;

-- Save UOM with tenant scope
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
        UPDATE uom_masters SET name = p_name, abbreviation = p_abbreviation
        WHERE id = p_id AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM uom_masters WHERE id = v_id;
END; $$;

-- Save HSN with tenant scope
CREATE OR REPLACE FUNCTION sp_save_hsn(
    p_id INT, p_hsn_code VARCHAR, p_description TEXT,
    p_cgst NUMERIC, p_sgst NUMERIC, p_igst NUMERIC, p_cess NUMERIC,
    p_tenant_id INT DEFAULT NULL
)
RETURNS SETOF hsn_masters LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO hsn_masters(hsn_code, description, cgst_rate, sgst_rate, igst_rate, cess_rate, tenant_id)
        VALUES (p_hsn_code, p_description, p_cgst, p_sgst, p_igst, p_cess, p_tenant_id)
        RETURNING id INTO v_id;
    ELSE
        UPDATE hsn_masters SET
            hsn_code = p_hsn_code, description = p_description,
            cgst_rate = p_cgst, sgst_rate = p_sgst, igst_rate = p_igst, cess_rate = p_cess
        WHERE id = p_id AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM hsn_masters WHERE id = v_id;
END; $$;

-- =============================================
-- AUTO-PROVISIONING SP (called on tenant create)
-- Copies business-type templates as tenant-specific records
-- =============================================
CREATE OR REPLACE PROCEDURE sp_provision_tenant_masters(
    p_tenant_id INT,
    p_business_type_id INT
)
LANGUAGE plpgsql AS $$
BEGIN
    -- Copy categories from business-type templates
    INSERT INTO categories(name, parent_id, tenant_id, business_type_id, is_active)
    SELECT
        c.name,
        NULL,  -- parent_id reset (re-link below if needed)
        p_tenant_id,
        c.business_type_id,
        TRUE
    FROM categories c
    WHERE c.business_type_id = p_business_type_id
      AND c.tenant_id IS NULL
      AND c.is_active = TRUE
      AND c.parent_id IS NULL  -- top-level first
    ON CONFLICT DO NOTHING;

    -- Copy sub-categories (parent_id linked to the newly inserted ones)
    INSERT INTO categories(name, parent_id, tenant_id, business_type_id, is_active)
    SELECT
        sub.name,
        new_parent.id,
        p_tenant_id,
        sub.business_type_id,
        TRUE
    FROM categories sub
    JOIN categories tmpl_parent ON tmpl_parent.id = sub.parent_id
    JOIN categories new_parent ON new_parent.name = tmpl_parent.name
        AND new_parent.tenant_id = p_tenant_id
    WHERE sub.business_type_id = p_business_type_id
      AND sub.tenant_id IS NULL
      AND sub.is_active = TRUE
      AND sub.parent_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    -- Copy standard UOMs (all global UOMs)
    INSERT INTO uom_masters(name, abbreviation, tenant_id, is_active)
    SELECT name, abbreviation, p_tenant_id, TRUE
    FROM uom_masters
    WHERE tenant_id IS NULL AND is_active = TRUE
    ON CONFLICT DO NOTHING;

    -- Copy common HSN codes (all global HSNs)
    INSERT INTO hsn_masters(hsn_code, description, cgst_rate, sgst_rate, igst_rate, cess_rate, tenant_id, is_active)
    SELECT hsn_code, description, cgst_rate, sgst_rate, igst_rate, cess_rate, p_tenant_id, TRUE
    FROM hsn_masters
    WHERE tenant_id IS NULL AND is_active = TRUE
    ON CONFLICT DO NOTHING;
END;
$$;
"""

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Applying schema changes...")
    await conn.execute(SQL)
    print("SPs updated!")

    # Now provision masters for any existing tenants
    tenants = await conn.fetch("""
        SELECT t.id, t.name, t.business_type_id, bt.name as biz_name
        FROM tenants t
        JOIN business_types bt ON bt.id = t.business_type_id
        WHERE t.is_active = TRUE AND t.business_type_id IS NOT NULL
    """)

    print(f"\nProvisioning masters for {len(tenants)} existing tenants...")
    for t in tenants:
        # Check if already provisioned
        cat_count = await conn.fetchval(
            "SELECT COUNT(*) FROM categories WHERE tenant_id = $1", t['id']
        )
        if cat_count == 0:
            await conn.execute(
                "CALL sp_provision_tenant_masters($1, $2)",
                t['id'], t['business_type_id']
            )
            cats = await conn.fetchval("SELECT COUNT(*) FROM categories WHERE tenant_id=$1", t['id'])
            uoms = await conn.fetchval("SELECT COUNT(*) FROM uom_masters WHERE tenant_id=$1", t['id'])
            hsns = await conn.fetchval("SELECT COUNT(*) FROM hsn_masters WHERE tenant_id=$1", t['id'])
            print(f"  Tenant [{t['name']}] ({t['biz_name']}): {cats} cats, {uoms} UOMs, {hsns} HSNs")
        else:
            print(f"  Tenant [{t['name']}]: already provisioned ({cat_count} categories)")

    # Verify global records still intact
    g_uom = await conn.fetchval("SELECT COUNT(*) FROM uom_masters WHERE tenant_id IS NULL")
    g_cat = await conn.fetchval("SELECT COUNT(*) FROM categories WHERE tenant_id IS NULL AND is_active = TRUE")
    g_hsn = await conn.fetchval("SELECT COUNT(*) FROM hsn_masters WHERE tenant_id IS NULL")
    print(f"\nGlobal templates: {g_cat} categories, {g_uom} UOMs, {g_hsn} HSNs")
    print("Migration complete!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
