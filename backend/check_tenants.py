import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    r = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='tenants'")
    print([dict(x) for x in r])
    await conn.close()

asyncio.run(check())
