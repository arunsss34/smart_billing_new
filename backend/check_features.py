import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def check_t():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("--- TENANT FEATURES FOR RESTAURANT ---")
    rows = await conn.fetch("SELECT t.name as tenant_name, t.business_type, tf.* FROM tenants t LEFT JOIN tenant_features tf ON tf.tenant_id = t.id WHERE t.business_type='restaurant'")
    for r in rows: print(dict(r))

    print("\n--- ALL TENANTS ---")
    rows = await conn.fetch("SELECT id, name, business_type FROM tenants")
    for r in rows: print(dict(r))

    await conn.close()

asyncio.run(check_t())
