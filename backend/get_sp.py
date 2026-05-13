import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def update_sp():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    # Need to drop function first because return type changed (added columns)
    await conn.execute("DROP FUNCTION IF EXISTS public.sp_list_users(integer, integer);")

    await conn.execute("""
CREATE OR REPLACE FUNCTION public.sp_list_users(p_tenant_id integer DEFAULT NULL::integer, p_role_id integer DEFAULT NULL::integer)
 RETURNS TABLE(
    id integer, username character varying, full_name character varying, email character varying, 
    role_id integer, role_name character varying, 
    tenant_id integer, tenant_role_id integer, tenant_role_name character varying, 
    tenant_name character varying, business_type character varying, 
    is_active boolean, created_at timestamp without time zone)
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF p_role_id = 1 THEN
        -- Super admin sees all users
        RETURN QUERY
        SELECT u.id, u.username, u.full_name, u.email,
               u.role_id, r.name::VARCHAR as role_name,
               u.tenant_id, u.tenant_role_id, tr.name::VARCHAR as tenant_role_name,
               t.name::VARCHAR as tenant_name, t.business_type::VARCHAR as business_type,
               u.is_active, u.created_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN tenant_roles tr ON tr.id = u.tenant_role_id
        LEFT JOIN tenants t ON t.id = u.tenant_id
        WHERE u.role_id != 1  -- don't show super admins
        ORDER BY u.tenant_id, u.created_at DESC;
    ELSE
        -- Tenant admin sees only their tenant's users
        RETURN QUERY
        SELECT u.id, u.username, u.full_name, u.email,
               u.role_id, r.name::VARCHAR as role_name,
               u.tenant_id, u.tenant_role_id, tr.name::VARCHAR as tenant_role_name,
               t.name::VARCHAR as tenant_name, t.business_type::VARCHAR as business_type,
               u.is_active, u.created_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN tenant_roles tr ON tr.id = u.tenant_role_id
        LEFT JOIN tenants t ON t.id = u.tenant_id
        WHERE u.tenant_id = p_tenant_id AND u.role_id = 3  -- staff only
        ORDER BY u.created_at DESC;
    END IF;
END; $function$
    """)

    print("Updated sp_list_users.")
    await conn.close()

asyncio.run(update_sp())
