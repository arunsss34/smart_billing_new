import asyncio
from app.database import engine
from sqlalchemy import text

async def run():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'invoices';"))
        print(res.fetchall())

if __name__ == "__main__":
    asyncio.run(run())
