"""
Migration: Tenant Role Permissions System
=========================================
1. Creates `tenant_role_permissions` table
2. Updates `sp_get_menus` to use tenant_role_permissions for staff users
3. Updates `sp_login` to return tenant_role_id in payload
4. Creates SP for Tenant Admin to manage tenant_role_permissions
5. Creates SP to list menus for a specific tenant_role (for config UI)

Run: python migrate_tenant_role_permissions.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, ".")
from app.config import settings

SQL = """
-- =============================================
-- 1. tenant_role_permissions table
-- =============================================
CREATE TABLE IF NOT EXISTS tenant_role_permissions (
    id              SERIAL PRIMARY KEY,
    tenant_role_id  INT NOT NULL REFERENCES tenant_roles(id) ON DELETE CASCADE,
    menu_id         INT NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
    can_view        BOOLEAN DEFAULT FALSE,
    can_add         BOOLEAN DEFAULT FALSE,
    can_edit        BOOLEAN DEFAULT FALSE,
    can_delete      BOOLEAN DEFAULT FALSE,
    UNIQUE(tenant_role_id, menu_id)
);

-- =============================================
-- 2. Updated sp_login to include tenant_role_id
-- =============================================
DROP FUNCTION IF EXISTS sp_login(VARCHAR);
CREATE OR REPLACE FUNCTION sp_login(p_username VARCHAR)
RETURNS TABLE(
    id INT, username VARCHAR, password_hash TEXT,
    full_name VARCHAR, email VARCHAR,
    role_id INT, role_name VARCHAR,
    tenant_id INT, tenant_role_id INT,
    is_active BOOLEAN
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id, u.username, u.password_hash,
        u.full_name, u.email,
        u.role_id, r.name::VARCHAR AS role_name,
        u.tenant_id, u.tenant_role_id,
        u.is_active
    FROM users u
    JOIN roles r ON r.id = u.role_id
    WHERE u.username = p_username AND u.is_active = TRUE;
END;
$$;

-- =============================================
-- 3. Updated sp_get_menus: checks tenant_role_permissions for staff
-- =============================================
DROP FUNCTION IF EXISTS sp_get_menus(INT, INT, INT);
CREATE OR REPLACE FUNCTION sp_get_menus(p_user_id INT, p_tenant_id INT, p_role_id INT)
RETURNS TABLE(
    menu_id INT, menu_name VARCHAR, route VARCHAR, icon VARCHAR,
    parent_id INT, sort_order INT,
    can_view BOOLEAN, can_add BOOLEAN, can_edit BOOLEAN, can_delete BOOLEAN
)
LANGUAGE plpgsql AS $$
DECLARE
    v_tenant_role_id INT;
BEGIN
    -- Get tenant_role_id for this user (staff users only)
    SELECT tenant_role_id INTO v_tenant_role_id FROM users WHERE id = p_user_id;

    IF v_tenant_role_id IS NOT NULL THEN
        -- Staff user with tenant role: use tenant_role_permissions
        RETURN QUERY
        SELECT
            m.id, m.name::VARCHAR, m.route::VARCHAR,
            COALESCE(m.icon, 'circle')::VARCHAR,
            m.parent_id, COALESCE(m.sort_order, 0),
            trp.can_view, trp.can_add, trp.can_edit, trp.can_delete
        FROM tenant_role_permissions trp
        JOIN menus m ON m.id = trp.menu_id
        WHERE trp.tenant_role_id = v_tenant_role_id
          AND trp.can_view = TRUE
          AND m.is_active = TRUE
        ORDER BY m.parent_id NULLS FIRST, COALESCE(m.sort_order, 0), m.name;
    ELSE
        -- Super admin / Tenant admin: use role_permissions
        RETURN QUERY
        SELECT
            m.id, m.name::VARCHAR, m.route::VARCHAR,
            COALESCE(m.icon, 'circle')::VARCHAR,
            m.parent_id, COALESCE(m.sort_order, 0),
            rp.can_view, rp.can_add, rp.can_edit, rp.can_delete
        FROM role_permissions rp
        JOIN menus m ON m.id = rp.menu_id
        WHERE rp.role_id = p_role_id
          AND rp.can_view = TRUE
          AND m.is_active = TRUE
        ORDER BY m.parent_id NULLS FIRST, COALESCE(m.sort_order, 0), m.name;
    END IF;
END;
$$;

-- =============================================
-- 4. SP: Save/upsert tenant_role_permission
-- =============================================
CREATE OR REPLACE FUNCTION sp_save_tenant_role_permission(
    p_tenant_role_id INT,
    p_menu_id        INT,
    p_can_view       BOOLEAN,
    p_can_add        BOOLEAN,
    p_can_edit       BOOLEAN,
    p_can_delete     BOOLEAN
)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO tenant_role_permissions(tenant_role_id, menu_id, can_view, can_add, can_edit, can_delete)
    VALUES (p_tenant_role_id, p_menu_id, p_can_view, p_can_add, p_can_edit, p_can_delete)
    ON CONFLICT (tenant_role_id, menu_id) DO UPDATE SET
        can_view   = EXCLUDED.can_view,
        can_add    = EXCLUDED.can_add,
        can_edit   = EXCLUDED.can_edit,
        can_delete = EXCLUDED.can_delete;
END;
$$;

-- =============================================
-- 5. SP: List menus + permissions for a tenant_role (for config UI)
-- =============================================
CREATE OR REPLACE FUNCTION sp_list_menus_for_tenant_role(p_tenant_role_id INT)
RETURNS TABLE(
    menu_id INT, menu_name VARCHAR, route VARCHAR, icon VARCHAR,
    parent_id INT, sort_order INT,
    can_view BOOLEAN, can_add BOOLEAN, can_edit BOOLEAN, can_delete BOOLEAN
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id, m.name::VARCHAR, m.route::VARCHAR,
        COALESCE(m.icon, 'circle')::VARCHAR,
        m.parent_id, COALESCE(m.sort_order, 0),
        COALESCE(trp.can_view,   FALSE),
        COALESCE(trp.can_add,    FALSE),
        COALESCE(trp.can_edit,   FALSE),
        COALESCE(trp.can_delete, FALSE)
    FROM menus m
    LEFT JOIN tenant_role_permissions trp
        ON trp.menu_id = m.id AND trp.tenant_role_id = p_tenant_role_id
    WHERE m.is_active = TRUE
      -- Exclude super-admin only menus (settings/tenants, settings/business-types, settings/menus)
      AND m.route NOT IN ('settings/tenants', 'settings/business-types', 'settings/menus', 'settings/roles')
    ORDER BY m.parent_id NULLS FIRST, COALESCE(m.sort_order, 0), m.name;
END;
$$;
"""

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Running tenant role permissions migration...")
    await conn.execute(SQL)
    print("Done!")

    # Verify
    count = await conn.fetchval("SELECT COUNT(*) FROM tenant_role_permissions")
    print(f"tenant_role_permissions rows: {count}")

    rows = await conn.fetch("SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname IN ('sp_get_menus','sp_login','sp_save_tenant_role_permission','sp_list_menus_for_tenant_role')")
    print("Updated SPs:")
    for r in rows: print(f"  ({r[0]})")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
