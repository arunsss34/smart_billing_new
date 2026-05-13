import asyncio, asyncpg, sys
sys.path.insert(0, ".")
from app.config import settings

SQL = """
-- 1. Insert the new menu under 'Settings' (assuming Settings has route 'settings' or similar)
DO $$
DECLARE
    v_parent_id INT;
    v_menu_id INT;
BEGIN
    -- Find the 'Settings' parent menu
    SELECT id INTO v_parent_id FROM menus WHERE name = 'Settings' AND parent_id IS NULL LIMIT 1;
    
    -- Insert 'Role Permissions' if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM menus WHERE route = 'settings/role-permissions') THEN
        INSERT INTO menus (name, route, icon, parent_id, sort_order)
        VALUES ('Role Permissions', 'settings/role-permissions', 'key', v_parent_id, 4)
        RETURNING id INTO v_menu_id;
    ELSE
        SELECT id INTO v_menu_id FROM menus WHERE route = 'settings/role-permissions';
    END IF;

    -- Give tenant admin (role_id=2) full access to this menu
    INSERT INTO role_permissions (role_id, menu_id, can_view, can_add, can_edit, can_delete)
    VALUES (2, v_menu_id, TRUE, TRUE, TRUE, TRUE)
    ON CONFLICT (role_id, menu_id) DO UPDATE SET
        can_view = TRUE, can_add = TRUE, can_edit = TRUE, can_delete = TRUE;
        
    -- Give super admin (role_id=1) view access if they need to see it (optional, usually super admin doesn't manage tenant roles directly, but good to have)
    INSERT INTO role_permissions (role_id, menu_id, can_view, can_add, can_edit, can_delete)
    VALUES (1, v_menu_id, TRUE, TRUE, TRUE, TRUE)
    ON CONFLICT (role_id, menu_id) DO UPDATE SET
        can_view = TRUE, can_add = TRUE, can_edit = TRUE, can_delete = TRUE;
END;
$$;
"""

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Adding Role Permissions menu to database...")
    await conn.execute(SQL)
    print("Done!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
