"""Fix: Create single clean sp_create_user (8 params)"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

SQL = """
CREATE OR REPLACE FUNCTION sp_create_user(
    p_username      VARCHAR,
    p_password_hash TEXT,
    p_full_name     VARCHAR,
    p_email         VARCHAR,
    p_role_id       INT,
    p_tenant_id     INT     DEFAULT NULL,
    p_is_active     BOOLEAN DEFAULT TRUE,
    p_tenant_role_id INT    DEFAULT NULL
)
RETURNS SETOF users LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO users(username, password_hash, full_name, email, role_id, tenant_id, is_active, tenant_role_id)
    VALUES (p_username, p_password_hash, p_full_name, p_email, p_role_id, p_tenant_id, p_is_active, p_tenant_role_id)
    RETURNING id INTO v_id;
    RETURN QUERY SELECT * FROM users WHERE id = v_id;
END;
$$;
"""

async def fix():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    # Verify old versions are gone
    rows = await conn.fetch("SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname = 'sp_create_user'")
    print(f"sp_create_user versions before: {len(rows)}")
    for r in rows: print(f"  ({r[0]})")

    # Drop any remaining versions
    await conn.execute("DROP FUNCTION IF EXISTS sp_create_user(VARCHAR,TEXT,VARCHAR,VARCHAR,INT,INT,BOOLEAN)")
    await conn.execute("DROP FUNCTION IF EXISTS sp_create_user(VARCHAR,TEXT,VARCHAR,VARCHAR,INT,INT,BOOLEAN,INT)")

    # Create the clean single version
    await conn.execute(SQL)

    rows = await conn.fetch("SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname = 'sp_create_user'")
    print(f"sp_create_user versions after: {len(rows)}")
    for r in rows: print(f"  ({r[0]})")

    await conn.close()
    print("Done! sp_create_user is now unambiguous.")

if __name__ == "__main__":
    asyncio.run(fix())
