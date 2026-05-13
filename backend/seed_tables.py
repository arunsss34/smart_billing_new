import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def seed_tables():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    # get all tenants with table_mgmt
    tenants = await conn.fetch("SELECT tenant_id FROM tenant_features WHERE feature_key = 'table_mgmt' AND enabled = true")
    
    for t in tenants:
        tid = t['tenant_id']
        # check if tables exist
        exist = await conn.fetchval("SELECT COUNT(*) FROM restaurant_tables WHERE tenant_id = $1", tid)
        if exist == 0:
            print(f"Seeding tables for tenant {tid}")
            for i in range(1, 21):
                await conn.execute("INSERT INTO restaurant_tables (tenant_id, table_number, capacity, is_occupied) VALUES ($1, $2, 4, false)", tid, str(i))

    await conn.close()

asyncio.run(seed_tables())
