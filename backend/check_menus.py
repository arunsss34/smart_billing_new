import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check_menus():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("--- MENUS ---")
    menus = await conn.fetch("SELECT * FROM menus ORDER BY id")
    for m in menus: print(dict(m))

    print("\n--- TENANT ROLE PERMISSIONS ---")
    perms = await conn.fetch("SELECT * FROM role_permissions WHERE role_id = 2")
    for p in perms: print(dict(p))

    await conn.close()

asyncio.run(check_menus())
