import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    sa = await conn.fetchrow("SELECT id FROM users WHERE username = 'superadmin'")
    if sa:
        rows = await conn.fetch("SELECT * FROM sp_get_menus($1, NULL, 1)", sa["id"])
        print(f"sp_get_menus returns {len(rows)} rows for superadmin:")
        for r in rows:
            name = r["menu_name"]
            route = r["route"]
            print(f"  {name} -> {route}")
    else:
        print("superadmin user not found")
    await conn.close()

asyncio.run(check())
