import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def f():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    r = await conn.fetch("SELECT items FROM invoices LIMIT 2")
    for row in r:
        print(row['items'])
    await conn.close()

asyncio.run(f())
