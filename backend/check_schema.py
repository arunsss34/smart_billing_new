import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    rows = await conn.fetch("SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname='sp_get_menus'")
    print("sp_get_menus signatures:")
    for r in rows: print(f"  ({r[0]})")

    rows2 = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
    print("users columns:", [r[0] for r in rows2])

    rows3 = await conn.fetch("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='tenant_role_permissions'")
    print("tenant_role_permissions exists:", rows3[0][0] > 0)

    # Check auth SP to see if tenant_role_id is in JWT
    rows4 = await conn.fetch("SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname='sp_login'")
    print("sp_login signatures:")
    for r in rows4: print(f"  ({r[0]})")

    await conn.close()

asyncio.run(check())
