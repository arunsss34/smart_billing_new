import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    tables = ['products', 'invoices', 'invoice_items']
    for table in tables:
        rows = await conn.fetch(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position")
        print(f"{table} columns:")
        for r in rows:
            print(f"  {r[0]} ({r[1]})")
        print()

    procs = ['sp_create_product', 'sp_update_product', 'sp_create_invoice']
    for p in procs:
        rows = await conn.fetch(f"SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname='{p}'")
        print(f"{p} signatures:")
        for r in rows:
            print(f"  ({r[0]})")
        print()

    await conn.close()

asyncio.run(check())
