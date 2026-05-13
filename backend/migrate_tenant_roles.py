"""
Migration: Tenant Roles system
- tenant_roles table: each tenant manages their own custom roles (e.g. Cashier, Manager, Cook)
- users table: add tenant_role_id FK
- Add Role Management menu for tenant_admin
Run: python migrate_tenant_roles.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

SQL = """
-- =============================================
-- Tenant Roles table
-- =============================================
CREATE TABLE IF NOT EXISTS tenant_roles (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Add tenant_role_id to users (optional FK)
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS tenant_role_id INT REFERENCES tenant_roles(id);

-- =============================================
-- SPs for Tenant Roles
-- =============================================
CREATE OR REPLACE FUNCTION sp_list_tenant_roles(p_tenant_id INT)
RETURNS SETOF tenant_roles LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM tenant_roles
    WHERE tenant_id = p_tenant_id AND is_active = TRUE
    ORDER BY name;
END; $$;

CREATE OR REPLACE FUNCTION sp_save_tenant_role(
    p_id INT, p_tenant_id INT, p_name VARCHAR, p_description TEXT
)
RETURNS SETOF tenant_roles LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO tenant_roles(tenant_id, name, description)
        VALUES (p_tenant_id, p_name, p_description)
        RETURNING id INTO v_id;
    ELSE
        UPDATE tenant_roles
        SET name = p_name, description = p_description
        WHERE id = p_id AND tenant_id = p_tenant_id;
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM tenant_roles WHERE id = v_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_delete_tenant_role(p_id INT, p_tenant_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE tenant_roles SET is_active = FALSE
    WHERE id = p_id AND tenant_id = p_tenant_id;
END; $$;

-- =============================================
-- Update sp_list_users to include tenant_role_name
-- =============================================
DROP FUNCTION IF EXISTS sp_list_users(INT, INT);
CREATE OR REPLACE FUNCTION sp_list_users(p_tenant_id INT DEFAULT NULL, p_role_id INT DEFAULT NULL)
RETURNS TABLE(
    id INT, username VARCHAR, full_name VARCHAR, email VARCHAR,
    role_id INT, role_name VARCHAR,
    tenant_id INT, tenant_role_id INT, tenant_role_name VARCHAR,
    is_active BOOLEAN, created_at TIMESTAMP
) LANGUAGE plpgsql AS $$
BEGIN
    IF p_role_id = 1 THEN
        -- Super admin sees all users
        RETURN QUERY
        SELECT u.id, u.username, u.full_name, u.email,
               u.role_id, r.name::VARCHAR as role_name,
               u.tenant_id, u.tenant_role_id, tr.name::VARCHAR as tenant_role_name,
               u.is_active, u.created_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN tenant_roles tr ON tr.id = u.tenant_role_id
        WHERE u.role_id != 1  -- don't show super admins
        ORDER BY u.tenant_id, u.created_at DESC;
    ELSE
        -- Tenant admin sees only their tenant's users
        RETURN QUERY
        SELECT u.id, u.username, u.full_name, u.email,
               u.role_id, r.name::VARCHAR as role_name,
               u.tenant_id, u.tenant_role_id, tr.name::VARCHAR as tenant_role_name,
               u.is_active, u.created_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN tenant_roles tr ON tr.id = u.tenant_role_id
        WHERE u.tenant_id = p_tenant_id AND u.role_id = 3  -- staff only
        ORDER BY u.created_at DESC;
    END IF;
END; $$;

-- =============================================
-- Update sp_create_user to accept tenant_role_id
-- =============================================
CREATE OR REPLACE FUNCTION sp_create_user(
    p_username VARCHAR, p_password_hash TEXT, p_full_name VARCHAR,
    p_email VARCHAR, p_role_id INT, p_tenant_id INT DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT TRUE, p_tenant_role_id INT DEFAULT NULL
)
RETURNS SETOF users LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO users(username, password_hash, full_name, email, role_id, tenant_id, is_active, tenant_role_id)
    VALUES (p_username, p_password_hash, p_full_name, p_email, p_role_id, p_tenant_id, p_is_active, p_tenant_role_id)
    RETURNING id INTO v_id;
    RETURN QUERY SELECT * FROM users WHERE id = v_id;
END; $$;
"""

MENU_SQL = """
-- Add Role Management menu under Settings for tenant_admin
INSERT INTO menus(name, route, icon, parent_id, sort_order)
SELECT 'Role Management', 'settings/roles', 'shield', id, 2
FROM menus WHERE route = 'settings'
ON CONFLICT DO NOTHING;

-- Grant permission to tenant_admin (role_id=2)
INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
SELECT 2, id, TRUE, TRUE, TRUE, TRUE
FROM menus WHERE route = 'settings/roles'
ON CONFLICT (role_id, menu_id) DO NOTHING;
"""

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Creating tenant_roles table + SPs...")
    await conn.execute(SQL)

    print("Adding Role Management menu...")
    await conn.execute(MENU_SQL)

    # Verify
    menu = await conn.fetchrow("SELECT id, name FROM menus WHERE route='settings/roles'")
    perms = await conn.fetch(
        "SELECT r.name FROM role_permissions rp JOIN roles r ON r.id=rp.role_id WHERE rp.menu_id=$1",
        menu["id"]
    )
    print(f"  Menu: {menu['name']} (id={menu['id']})")
    print(f"  Roles with access: {[r['name'] for r in perms]}")

    # Check users table has tenant_role_id
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='users' ORDER BY ordinal_position
    """)
    print(f"  Users columns: {[c['column_name'] for c in cols]}")

    await conn.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
