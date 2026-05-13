"""
Fix superadmin password hash directly in the database.
Run: python fix_password.py
"""
import asyncio
import asyncpg
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def fix_password():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    user_pass, host_db = url.split("@")
    username, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    host = host_port.split(":")[0]
    port = int(host_port.split(":")[1]) if ":" in host_port else 5432

    print(f"Connecting to DB: {host}:{port}/{dbname} as {username}")

    conn = await asyncpg.connect(
        host=host, port=port,
        user=username, password=password,
        database=dbname
    )

    # Check current stored hash
    row = await conn.fetchrow("SELECT username, password_hash FROM users WHERE username = 'superadmin'")
    if not row:
        print("ERROR: superadmin user NOT found in database!")
        print("Run the schema.sql first to seed the data.")
        await conn.close()
        return

    print(f"Found user: {row['username']}")
    print(f"Current hash: {row['password_hash'][:50]}...")

    # Generate correct hash for admin123
    new_hash = pwd_context.hash("admin123")
    print(f"New hash:     {new_hash[:50]}...")

    # Verify the new hash works before saving
    assert pwd_context.verify("admin123", new_hash), "Hash verification failed!"
    print("Hash verified OK")

    # Update in DB
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE username = 'superadmin'",
        new_hash
    )
    print("\nDONE: Password updated in database!")
    print("Login with: superadmin / admin123")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_password())
