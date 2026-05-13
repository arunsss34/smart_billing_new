import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def migrate():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Adding theme_color column to tenants table...")
    await conn.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS theme_color VARCHAR(20) DEFAULT '#6366F1'")
    
    print("Migration complete.")
    await conn.close()

asyncio.run(migrate())
