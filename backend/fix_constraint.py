import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def fix_constraint():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Dropping and recreating constraint...")
    try:
        await conn.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_business_type_check;")
    except Exception as e:
        print(f"Error dropping: {e}")

    await conn.execute("ALTER TABLE tenants ADD CONSTRAINT tenants_business_type_check CHECK (business_type IN ('restaurant', 'bakery', 'bakery_shop', 'supermarket', 'dress_shop', 'mobile_shop', 'retail_shop', 'retail', 'service', 'wholesale', 'manufacturing'));")
    
    print("Done!")
    await conn.close()

asyncio.run(fix_constraint())
