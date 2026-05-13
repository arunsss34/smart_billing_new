-- =============================================
-- Smart Billing App - PostgreSQL Schema
-- Full multi-tenant SaaS database with SPs
-- =============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- CORE TABLES
-- =============================================

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,  -- super_admin, tenant_admin, staff
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    business_type VARCHAR(50) NOT NULL CHECK (
        business_type IN ('restaurant','bakery','supermarket','dress_shop','mobile_shop')
    ),
    email VARCHAR(200),
    phone VARCHAR(20),
    subscription_expiry DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(200),
    email VARCHAR(200),
    role_id INT REFERENCES roles(id),
    tenant_id INT REFERENCES tenants(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- DYNAMIC MENU SYSTEM
-- =============================================

-- All menus in the system
CREATE TABLE IF NOT EXISTS menus (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    route VARCHAR(100) NOT NULL,
    icon VARCHAR(50),
    parent_id INT REFERENCES menus(id),
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- Role-based permission per menu
CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INT NOT NULL REFERENCES roles(id),
    menu_id INT NOT NULL REFERENCES menus(id),
    can_view BOOLEAN DEFAULT FALSE,
    can_add BOOLEAN DEFAULT FALSE,
    can_edit BOOLEAN DEFAULT FALSE,
    can_delete BOOLEAN DEFAULT FALSE,
    UNIQUE(role_id, menu_id)
);

-- Feature flags per tenant
CREATE TABLE IF NOT EXISTS tenant_features (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    feature_key VARCHAR(100) NOT NULL,  -- kot, barcode, imei, expiry_tracking, table_mgmt
    enabled BOOLEAN DEFAULT FALSE,
    UNIQUE(tenant_id, feature_key)
);

-- =============================================
-- BILLING TABLES
-- =============================================

-- Customers per tenant
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    name VARCHAR(200) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(200),
    address TEXT,
    gstin VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Products per tenant
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    price NUMERIC(12,2) NOT NULL,
    stock_qty NUMERIC(12,3) DEFAULT 0,
    unit VARCHAR(20),
    barcode VARCHAR(100),
    sku VARCHAR(100),
    -- Business-specific fields
    size VARCHAR(50),          -- Dress shop
    color VARCHAR(50),         -- Dress shop
    imei VARCHAR(20),          -- Mobile shop
    expiry_date DATE,          -- Bakery
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Restaurant tables
CREATE TABLE IF NOT EXISTS restaurant_tables (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    table_number VARCHAR(20) NOT NULL,
    capacity INT,
    is_occupied BOOLEAN DEFAULT FALSE
);

-- KOT (Kitchen Order Tickets)
CREATE TABLE IF NOT EXISTS kot (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    table_id INT REFERENCES restaurant_tables(id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','preparing','ready','served')),
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Invoices (header)
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id),
    invoice_number VARCHAR(50) NOT NULL,
    customer_id INT REFERENCES customers(id),
    user_id INT REFERENCES users(id),
    items JSONB NOT NULL,               -- Full line items stored as JSON
    subtotal NUMERIC(12,2) DEFAULT 0,
    discount_total NUMERIC(12,2) DEFAULT 0,
    tax_total NUMERIC(12,2) DEFAULT 0,
    grand_total NUMERIC(12,2) DEFAULT 0,
    payment_method VARCHAR(20) CHECK (payment_method IN ('cash','upi','card')),
    payment_status VARCHAR(20) DEFAULT 'paid' CHECK (payment_status IN ('paid','pending','cancelled')),
    notes TEXT,
    table_id INT REFERENCES restaurant_tables(id),
    kot_id INT REFERENCES kot(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log for menu access
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    tenant_id INT REFERENCES tenants(id),
    action VARCHAR(100),
    resource VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- STORED PROCEDURES & FUNCTIONS
-- =============================================

-- ---- AUTH ----

-- SP: Login - returns user row with role name
CREATE OR REPLACE FUNCTION sp_login(p_username VARCHAR)
RETURNS TABLE (
    id INT, username VARCHAR, password_hash TEXT, full_name VARCHAR,
    email VARCHAR, role_id INT, role_name VARCHAR, tenant_id INT, is_active BOOLEAN
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.username, u.password_hash, u.full_name,
           u.email, u.role_id, r.name AS role_name, u.tenant_id, u.is_active
    FROM users u
    JOIN roles r ON r.id = u.role_id
    WHERE u.username = p_username;
END;
$$;

-- ---- MENUS ----

-- SP: Get menus for a user based on role and tenant
CREATE OR REPLACE FUNCTION sp_get_menus(
    p_user_id INT, p_tenant_id INT, p_role_id INT
)
RETURNS TABLE (
    menu_id INT, menu_name VARCHAR, route VARCHAR, icon VARCHAR,
    parent_id INT, sort_order INT,
    can_view BOOLEAN, can_add BOOLEAN, can_edit BOOLEAN, can_delete BOOLEAN
)
LANGUAGE plpgsql AS $$
BEGIN
    -- Log menu access (skip if superadmin with NULL tenant)
    IF p_tenant_id IS NOT NULL THEN
        INSERT INTO audit_logs(user_id, tenant_id, action, resource)
        VALUES (p_user_id, p_tenant_id, 'GET_MENUS', 'menus');
    END IF;

    RETURN QUERY
    SELECT m.id, m.name, m.route, m.icon, m.parent_id, m.sort_order,
           rp.can_view, rp.can_add, rp.can_edit, rp.can_delete
    FROM menus m
    JOIN role_permissions rp ON rp.menu_id = m.id AND rp.role_id = p_role_id
    WHERE m.is_active = TRUE AND rp.can_view = TRUE
    ORDER BY m.sort_order, m.id;
END;
$$;

-- SP: Get tenant feature flags
CREATE OR REPLACE FUNCTION sp_get_tenant_features(p_tenant_id INT)
RETURNS TABLE (feature_key VARCHAR, enabled BOOLEAN)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT tf.feature_key, tf.enabled
    FROM tenant_features tf
    WHERE tf.tenant_id = p_tenant_id;
END;
$$;

-- ---- TENANTS ----

-- SP: List all tenants (Super Admin)
CREATE OR REPLACE FUNCTION sp_list_tenants()
RETURNS SETOF tenants
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT * FROM tenants ORDER BY id;
END;
$$;

-- SP: Create tenant
CREATE OR REPLACE FUNCTION sp_create_tenant(
    p_name VARCHAR, p_business_type VARCHAR, p_email VARCHAR,
    p_phone VARCHAR, p_subscription_expiry DATE, p_is_active BOOLEAN
)
RETURNS SETOF tenants
LANGUAGE plpgsql AS $$
DECLARE v_tenant_id INT;
BEGIN
    INSERT INTO tenants(name, business_type, email, phone, subscription_expiry, is_active)
    VALUES (p_name, p_business_type, p_email, p_phone, p_subscription_expiry, p_is_active)
    RETURNING id INTO v_tenant_id;

    -- Auto-seed default feature flags based on business type
    IF p_business_type = 'restaurant' THEN
        INSERT INTO tenant_features(tenant_id, feature_key, enabled) VALUES
            (v_tenant_id, 'kot', TRUE),
            (v_tenant_id, 'table_mgmt', TRUE),
            (v_tenant_id, 'barcode', FALSE) ON CONFLICT DO NOTHING;
    ELSIF p_business_type = 'bakery' THEN
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
    END IF;

    RETURN QUERY SELECT * FROM tenants WHERE id = v_tenant_id;
END;
$$;

-- SP: Update tenant
CREATE OR REPLACE FUNCTION sp_update_tenant(
    p_tenant_id INT, p_name VARCHAR, p_business_type VARCHAR, p_email VARCHAR,
    p_phone VARCHAR, p_subscription_expiry DATE, p_is_active BOOLEAN
)
RETURNS SETOF tenants
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE tenants SET
        name = COALESCE(p_name, name),
        business_type = COALESCE(p_business_type, business_type),
        email = COALESCE(p_email, email),
        phone = COALESCE(p_phone, phone),
        subscription_expiry = COALESCE(p_subscription_expiry, subscription_expiry),
        is_active = COALESCE(p_is_active, is_active)
    WHERE id = p_tenant_id;
    RETURN QUERY SELECT * FROM tenants WHERE id = p_tenant_id;
END;
$$;

-- SP: Deactivate tenant
CREATE OR REPLACE PROCEDURE sp_deactivate_tenant(p_tenant_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE tenants SET is_active = FALSE WHERE id = p_tenant_id;
    UPDATE users SET is_active = FALSE WHERE tenant_id = p_tenant_id;
END;
$$;

-- ---- PRODUCTS ----

-- SP: List products by tenant
CREATE OR REPLACE FUNCTION sp_list_products(p_tenant_id INT)
RETURNS SETOF products
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT * FROM products WHERE tenant_id = p_tenant_id AND is_active = TRUE ORDER BY id;
END;
$$;

-- SP: Create product
CREATE OR REPLACE FUNCTION sp_create_product(
    p_tenant_id INT, p_name VARCHAR, p_category VARCHAR, p_price NUMERIC,
    p_stock_qty NUMERIC, p_unit VARCHAR, p_barcode VARCHAR, p_sku VARCHAR,
    p_size VARCHAR, p_color VARCHAR, p_imei VARCHAR, p_expiry_date DATE
)
RETURNS SETOF products
LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO products(tenant_id, name, category, price, stock_qty, unit, barcode, sku, size, color, imei, expiry_date)
    VALUES (p_tenant_id, p_name, p_category, p_price, p_stock_qty, p_unit, p_barcode, p_sku, p_size, p_color, p_imei, p_expiry_date)
    RETURNING id INTO v_id;
    RETURN QUERY SELECT * FROM products WHERE id = v_id;
END;
$$;

-- SP: Update product
CREATE OR REPLACE FUNCTION sp_update_product(
    p_product_id INT, p_tenant_id INT, p_name VARCHAR, p_category VARCHAR, p_price NUMERIC,
    p_stock_qty NUMERIC, p_unit VARCHAR, p_barcode VARCHAR, p_sku VARCHAR,
    p_size VARCHAR, p_color VARCHAR, p_imei VARCHAR, p_expiry_date DATE
)
RETURNS SETOF products
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE products SET
        name = COALESCE(p_name, name), category = COALESCE(p_category, category),
        price = COALESCE(p_price, price), stock_qty = COALESCE(p_stock_qty, stock_qty),
        unit = COALESCE(p_unit, unit), barcode = COALESCE(p_barcode, barcode),
        sku = COALESCE(p_sku, sku), size = COALESCE(p_size, size),
        color = COALESCE(p_color, color), imei = COALESCE(p_imei, imei),
        expiry_date = COALESCE(p_expiry_date, expiry_date)
    WHERE id = p_product_id AND tenant_id = p_tenant_id;
    RETURN QUERY SELECT * FROM products WHERE id = p_product_id;
END;
$$;

-- SP: Delete (soft) product
CREATE OR REPLACE PROCEDURE sp_delete_product(p_product_id INT, p_tenant_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE products SET is_active = FALSE WHERE id = p_product_id AND tenant_id = p_tenant_id;
END;
$$;

-- ---- CUSTOMERS ----

-- SP: List customers
CREATE OR REPLACE FUNCTION sp_list_customers(p_tenant_id INT)
RETURNS SETOF customers
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT * FROM customers WHERE tenant_id = p_tenant_id AND is_active = TRUE ORDER BY id;
END;
$$;

-- SP: Create customer
CREATE OR REPLACE FUNCTION sp_create_customer(
    p_tenant_id INT, p_name VARCHAR, p_phone VARCHAR,
    p_email VARCHAR, p_address TEXT, p_gstin VARCHAR
)
RETURNS SETOF customers
LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO customers(tenant_id, name, phone, email, address, gstin)
    VALUES (p_tenant_id, p_name, p_phone, p_email, p_address, p_gstin)
    RETURNING id INTO v_id;
    RETURN QUERY SELECT * FROM customers WHERE id = v_id;
END;
$$;

-- SP: Update customer
CREATE OR REPLACE FUNCTION sp_update_customer(
    p_customer_id INT, p_tenant_id INT, p_name VARCHAR, p_phone VARCHAR,
    p_email VARCHAR, p_address TEXT, p_gstin VARCHAR
)
RETURNS SETOF customers
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE customers SET
        name = COALESCE(p_name, name), phone = COALESCE(p_phone, phone),
        email = COALESCE(p_email, email), address = COALESCE(p_address, address),
        gstin = COALESCE(p_gstin, gstin)
    WHERE id = p_customer_id AND tenant_id = p_tenant_id;
    RETURN QUERY SELECT * FROM customers WHERE id = p_customer_id;
END;
$$;

-- ---- BILLING / INVOICES ----

-- SP: Create invoice (calculates totals from JSONB items)
CREATE OR REPLACE FUNCTION sp_create_invoice(
    p_tenant_id INT, p_user_id INT, p_customer_id INT,
    p_items JSONB, p_payment_method VARCHAR,
    p_notes TEXT, p_table_id INT, p_kot_id INT
)
RETURNS SETOF invoices
LANGUAGE plpgsql AS $$
DECLARE
    v_invoice_id INT;
    v_subtotal NUMERIC := 0;
    v_discount_total NUMERIC := 0;
    v_tax_total NUMERIC := 0;
    v_grand_total NUMERIC := 0;
    v_item JSONB;
    v_invoice_number VARCHAR;
    v_line_total NUMERIC;
    v_discount NUMERIC;
    v_tax NUMERIC;
BEGIN
    -- Calculate totals from items JSON array
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
    LOOP
        v_line_total := (v_item->>'unit_price')::NUMERIC * (v_item->>'quantity')::NUMERIC;
        v_discount := COALESCE((v_item->>'discount')::NUMERIC, 0);
        v_tax := COALESCE((v_item->>'tax_percent')::NUMERIC, 0);
        v_subtotal := v_subtotal + v_line_total;
        v_discount_total := v_discount_total + v_discount;
        v_tax_total := v_tax_total + ((v_line_total - v_discount) * v_tax / 100);
    END LOOP;

    v_grand_total := v_subtotal - v_discount_total + v_tax_total;

    -- Auto-generate invoice number: INV-TENANTID-YYYYMMDD-SEQ
    SELECT 'INV-' || p_tenant_id || '-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
           LPAD((COUNT(*) + 1)::TEXT, 4, '0')
    INTO v_invoice_number
    FROM invoices
    WHERE tenant_id = p_tenant_id AND DATE(created_at) = CURRENT_DATE;

    INSERT INTO invoices(
        tenant_id, invoice_number, customer_id, user_id, items,
        subtotal, discount_total, tax_total, grand_total,
        payment_method, notes, table_id, kot_id
    )
    VALUES (
        p_tenant_id, v_invoice_number, p_customer_id, p_user_id, p_items,
        v_subtotal, v_discount_total, v_tax_total, v_grand_total,
        p_payment_method, p_notes, p_table_id, p_kot_id
    )
    RETURNING id INTO v_invoice_id;

    -- Update product stock
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
    LOOP
        UPDATE products
        SET stock_qty = stock_qty - (v_item->>'quantity')::NUMERIC
        WHERE id = (v_item->>'product_id')::INT AND tenant_id = p_tenant_id;
    END LOOP;

    RETURN QUERY SELECT * FROM invoices WHERE id = v_invoice_id;
END;
$$;

-- SP: List invoices
CREATE OR REPLACE FUNCTION sp_list_invoices(p_tenant_id INT)
RETURNS SETOF invoices
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT * FROM invoices WHERE tenant_id = p_tenant_id ORDER BY created_at DESC;
END;
$$;

-- SP: Get single invoice
CREATE OR REPLACE FUNCTION sp_get_invoice(p_invoice_id INT, p_tenant_id INT)
RETURNS SETOF invoices
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT * FROM invoices WHERE id = p_invoice_id AND tenant_id = p_tenant_id;
END;
$$;

-- ---- USERS ----

-- SP: List users
CREATE OR REPLACE FUNCTION sp_list_users(p_tenant_id INT, p_role_id INT)
RETURNS TABLE (
    id INT, username VARCHAR, full_name VARCHAR, email VARCHAR,
    role_id INT, role_name VARCHAR, tenant_id INT, is_active BOOLEAN, created_at TIMESTAMP
)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_role_id = 1 THEN
        -- Super admin sees all
        RETURN QUERY
        SELECT u.id, u.username, u.full_name, u.email, u.role_id, r.name::VARCHAR, u.tenant_id, u.is_active, u.created_at
        FROM users u JOIN roles r ON r.id = u.role_id ORDER BY u.id;
    ELSE
        -- Others see own tenant only
        RETURN QUERY
        SELECT u.id, u.username, u.full_name, u.email, u.role_id, r.name::VARCHAR, u.tenant_id, u.is_active, u.created_at
        FROM users u JOIN roles r ON r.id = u.role_id
        WHERE u.tenant_id = p_tenant_id ORDER BY u.id;
    END IF;
END;
$$;

-- SP: Create user
CREATE OR REPLACE FUNCTION sp_create_user(
    p_username VARCHAR, p_password_hash TEXT, p_full_name VARCHAR,
    p_email VARCHAR, p_role_id INT, p_tenant_id INT, p_is_active BOOLEAN
)
RETURNS SETOF users
LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO users(username, password_hash, full_name, email, role_id, tenant_id, is_active)
    VALUES (p_username, p_password_hash, p_full_name, p_email, p_role_id, p_tenant_id, p_is_active)
    RETURNING id INTO v_id;
    RETURN QUERY SELECT * FROM users WHERE id = v_id;
END;
$$;

-- SP: Toggle user active status
CREATE OR REPLACE FUNCTION sp_toggle_user_active(p_user_id INT, p_tenant_id INT)
RETURNS SETOF users
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE users SET is_active = NOT is_active
    WHERE id = p_user_id AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
    RETURN QUERY SELECT * FROM users WHERE id = p_user_id;
END;
$$;

-- ---- REPORTS ----

-- SP: Sales summary
CREATE OR REPLACE FUNCTION sp_report_sales_summary(p_tenant_id INT)
RETURNS TABLE (
    total_invoices BIGINT, total_revenue NUMERIC,
    total_discount NUMERIC, total_tax NUMERIC
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT COUNT(*), SUM(grand_total), SUM(discount_total), SUM(tax_total)
    FROM invoices
    WHERE tenant_id = p_tenant_id AND payment_status = 'paid';
END;
$$;

-- SP: Daily sales
CREATE OR REPLACE FUNCTION sp_report_daily_sales(p_tenant_id INT)
RETURNS TABLE (sale_date DATE, total_invoices BIGINT, total_revenue NUMERIC)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT DATE(created_at), COUNT(*), SUM(grand_total)
    FROM invoices
    WHERE tenant_id = p_tenant_id AND payment_status = 'paid'
    GROUP BY DATE(created_at)
    ORDER BY DATE(created_at) DESC;
END;
$$;

-- SP: Top selling products
CREATE OR REPLACE FUNCTION sp_report_top_products(p_tenant_id INT)
RETURNS TABLE (product_id INT, product_name TEXT, total_qty NUMERIC, total_revenue NUMERIC)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        (item->>'product_id')::INT,
        p.name::TEXT,
        SUM((item->>'quantity')::NUMERIC),
        SUM((item->>'unit_price')::NUMERIC * (item->>'quantity')::NUMERIC)
    FROM invoices i,
         jsonb_array_elements(i.items) AS item
    JOIN products p ON p.id = (item->>'product_id')::INT
    WHERE i.tenant_id = p_tenant_id AND i.payment_status = 'paid'
    GROUP BY (item->>'product_id')::INT, p.name
    ORDER BY 3 DESC
    LIMIT 10;
END;
$$;

-- SP: Payment method breakdown
CREATE OR REPLACE FUNCTION sp_report_payment_methods(p_tenant_id INT)
RETURNS TABLE (payment_method VARCHAR, total_invoices BIGINT, total_revenue NUMERIC)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT i.payment_method, COUNT(*), SUM(i.grand_total)
    FROM invoices i
    WHERE i.tenant_id = p_tenant_id AND i.payment_status = 'paid'
    GROUP BY i.payment_method;
END;
$$;

-- =============================================
-- SEED DATA
-- =============================================

-- Roles
INSERT INTO roles(name) VALUES ('super_admin'), ('tenant_admin'), ('staff')
ON CONFLICT (name) DO NOTHING;

-- Menus
INSERT INTO menus(name, route, icon, parent_id, sort_order) VALUES
('Dashboard',    'dashboard',   'grid',          NULL, 1),
('Billing',      'billing',     'file-text',     NULL, 2),
('Products',     'products',    'package',        NULL, 3),
('Customers',    'customers',   'users',          NULL, 4),
('Reports',      'reports',     'bar-chart',      NULL, 5),
('Settings',     'settings',    'settings',       NULL, 6),
('Users',        'users-mgmt',  'user',           NULL, 7),

-- Billing sub-menus
('New Invoice',  'billing/new', 'plus',           2, 1),
('Invoice List', 'billing/list','list',           2, 2),

-- Settings sub-menus
('Tenants',      'settings/tenants', 'building', 6, 1),
('Roles',        'settings/roles',   'shield',   6, 2),
('Menu Config',  'settings/menus',   'menu',     6, 3)
ON CONFLICT DO NOTHING;

-- Role permissions: Super Admin gets all
INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
SELECT 1, id, TRUE, TRUE, TRUE, TRUE FROM menus ON CONFLICT DO NOTHING;

-- Tenant Admin gets operational menus
INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
SELECT 2, id, TRUE, TRUE, TRUE, FALSE FROM menus
WHERE route IN ('dashboard','billing','billing/new','billing/list','products','customers','reports','users-mgmt')
ON CONFLICT DO NOTHING;

-- Staff gets billing and product view
INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
SELECT 3, id, TRUE, TRUE, FALSE, FALSE FROM menus
WHERE route IN ('dashboard','billing','billing/new','billing/list','products','customers')
ON CONFLICT DO NOTHING;

-- Sample Super Admin User (password: admin123 - hashed with bcrypt 4.0.1 + passlib 1.7.4)
INSERT INTO users(username, password_hash, full_name, email, role_id, tenant_id, is_active)
VALUES (
    'superadmin',
    '$2b$12$2xYhEFIwUFCQLXNadt8Jgumy9/R7eolo7D2uD1dsGwR7qjdCyMfDe',  -- admin123
    'Super Administrator', 'admin@smartbilling.com', 1, NULL, TRUE
) ON CONFLICT (username) DO NOTHING;
