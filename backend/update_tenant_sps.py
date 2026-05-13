import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def update_sps():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Updating sp_create_tenant...")
    await conn.execute("""
CREATE OR REPLACE FUNCTION public.sp_create_tenant(p_name character varying, p_business_type character varying, p_email character varying, p_phone character varying, p_subscription_expiry date, p_is_active boolean, p_theme_color character varying DEFAULT '#6366F1')
 RETURNS SETOF tenants
 LANGUAGE plpgsql
AS $function$
DECLARE v_tenant_id INT;
BEGIN
    INSERT INTO tenants(name, business_type, email, phone, subscription_expiry, is_active, theme_color)
    VALUES (p_name, p_business_type, p_email, p_phone, p_subscription_expiry, p_is_active, p_theme_color)
    RETURNING id INTO v_tenant_id;

    -- Auto-seed default feature flags based on business type
    IF p_business_type = 'restaurant' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'kot', TRUE),
            (v_tenant_id, 'table_mgmt', TRUE),
            (v_tenant_id, 'barcode', FALSE) ON CONFLICT DO NOTHING;
    ELSIF p_business_type = 'bakery' OR p_business_type = 'bakery_shop' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'expiry_tracking', TRUE),
            (v_tenant_id, 'barcode', FALSE) ON CONFLICT DO NOTHING;
    ELSIF p_business_type = 'supermarket' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'barcode', TRUE),
            (v_tenant_id, 'kot', FALSE) ON CONFLICT DO NOTHING;
    ELSIF p_business_type = 'dress_shop' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'size_color_variants', TRUE),
            (v_tenant_id, 'barcode', FALSE) ON CONFLICT DO NOTHING;
    ELSIF p_business_type = 'mobile_shop' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'imei_tracking', TRUE),
            (v_tenant_id, 'barcode', TRUE) ON CONFLICT DO NOTHING;
    ELSIF p_business_type = 'retail_shop' OR p_business_type = 'retail' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'size_color_variants', TRUE),
            (v_tenant_id, 'barcode', TRUE) ON CONFLICT DO NOTHING;
    END IF;

    RETURN QUERY SELECT * FROM tenants WHERE id = v_tenant_id;
END;
$function$;
""")

    print("Updating sp_update_tenant...")
    await conn.execute("""
CREATE OR REPLACE FUNCTION public.sp_update_tenant(p_tenant_id integer, p_name character varying, p_business_type character varying, p_email character varying, p_phone character varying, p_subscription_expiry date, p_is_active boolean, p_theme_color character varying DEFAULT NULL)
 RETURNS SETOF tenants
 LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE tenants SET
        name = COALESCE(p_name, name),
        business_type = COALESCE(p_business_type, business_type),
        email = COALESCE(p_email, email),
        phone = COALESCE(p_phone, phone),
        subscription_expiry = COALESCE(p_subscription_expiry, subscription_expiry),
        is_active = COALESCE(p_is_active, is_active),
        theme_color = COALESCE(p_theme_color, theme_color)
    WHERE id = p_tenant_id;
    RETURN QUERY SELECT * FROM tenants WHERE id = p_tenant_id;
END;
$function$;
""")

    print("Updates complete.")
    await conn.close()

asyncio.run(update_sps())
