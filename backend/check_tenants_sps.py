import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("--- sp_update_tenant ---")
    r1 = await conn.fetchrow("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='sp_update_tenant'")
    if r1: print(r1[0])

    print("\n--- sp_list_tenants ---")
    r2 = await conn.fetchrow("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='sp_list_tenants'")
    if r2: print(r2[0])

    await conn.close()

asyncio.run(check())
