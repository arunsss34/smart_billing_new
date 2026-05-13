"""Add Masters menu under Settings for Super Admin"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def run():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    sid = await conn.fetchval("SELECT id FROM menus WHERE route = 'settings'")
    await conn.execute("""
        INSERT INTO menus(name, route, icon, parent_id, sort_order)
        VALUES ('Masters', 'settings/masters', 'package', $1, 1)
        ON CONFLICT DO NOTHING
    """, sid)

    mid = await conn.fetchval("SELECT id FROM menus WHERE route = 'settings/masters'")
    await conn.execute("""
        INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
        VALUES (1, $1, TRUE, TRUE, TRUE, TRUE),(2, $1, TRUE, TRUE, TRUE, TRUE)
        ON CONFLICT (role_id, menu_id) DO NOTHING
    """, mid)

    print(f"Masters menu added (id={mid}) — accessible to Super Admin and Tenant Admin")
    await conn.close()

asyncio.run(run())
