"""Fix sp_get_menus to handle NULL tenant_id for superadmin"""
import asyncio
import asyncpg
from app.config import settings

SP_SQL = """
CREATE OR REPLACE FUNCTION sp_get_menus(
    p_user_id INT, p_tenant_id INT, p_role_id INT
)
RETURNS TABLE (
    menu_id INT, menu_name VARCHAR, route VARCHAR, icon VARCHAR,
    parent_id INT, sort_order INT,
    can_view BOOLEAN, can_add BOOLEAN, can_edit BOOLEAN, can_delete BOOLEAN
)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_tenant_id IS NOT NULL THEN
        INSERT INTO audit_logs(user_id, tenant_id, action, resource)
        VALUES (p_user_id, p_tenant_id, 'GET_MENUS', 'menus');
    END IF;

    RETURN QUERY
    SELECT m.id, m.name, m.route, m.icon, m.parent_id, m.sort_order,
           rp.can_view, rp.can_add, rp.can_edit, rp.can_delete
    FROM menus m
    JOIN role_permissions rp ON rp.menu_id = m.id AND rp.role_id = p_role_id
    WHERE m.is_active = TRUE AND rp.can_view = TRUE
    ORDER BY m.sort_order, m.id;
END;
$$;
"""

async def fix():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    user_pass, host_db = url.split("@")
    username, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    host = host_port.split(":")[0]
    port = int(host_port.split(":")[1]) if ":" in host_port else 5432

    conn = await asyncpg.connect(
        host=host, port=port,
        user=username, password=password, database=dbname
    )
    await conn.execute(SP_SQL)
    print("sp_get_menus updated - NULL tenant_id handled for superadmin")

    # Test it
    rows = await conn.fetch("SELECT * FROM sp_get_menus(1, NULL, 1)")
    print(f"Menus returned for superadmin: {len(rows)}")
    for r in rows:
        print(f"  - {r['menu_name']} ({r['route']})")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix())
