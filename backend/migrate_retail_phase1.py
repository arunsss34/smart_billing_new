import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def migrate():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Altering products table...")
    await conn.execute("""
        ALTER TABLE products 
        ADD COLUMN IF NOT EXISTS subcategory VARCHAR,
        ADD COLUMN IF NOT EXISTS brand VARCHAR,
        ADD COLUMN IF NOT EXISTS hsn_code VARCHAR,
        ADD COLUMN IF NOT EXISTS purchase_price NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS mrp NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS discount NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS discount_type VARCHAR DEFAULT 'percent',
        ADD COLUMN IF NOT EXISTS tax_percent NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS min_stock NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS reorder_level NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS batch_number VARCHAR,
        ADD COLUMN IF NOT EXISTS mfg_date DATE,
        ADD COLUMN IF NOT EXISTS variants JSONB DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS additional_attributes JSONB DEFAULT '{}'::jsonb
    """)

    print("Altering invoices table...")
    await conn.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS paid_amount NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS balance NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS invoice_status VARCHAR DEFAULT 'Paid',
        ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb
    """)

    print("Updating products SPs...")
    await conn.execute("""
        DROP FUNCTION IF EXISTS public.sp_create_product;
        CREATE OR REPLACE FUNCTION public.sp_create_product(
            p_tenant_id integer, p_name character varying, p_category character varying, p_subcategory character varying, p_brand character varying, p_price numeric, p_purchase_price numeric, p_mrp numeric, p_discount numeric, p_discount_type character varying, p_tax_percent numeric, p_stock_qty numeric, p_min_stock numeric, p_reorder_level numeric, p_unit character varying, p_barcode character varying, p_sku character varying, p_hsn_code character varying, p_batch_number character varying, p_mfg_date date, p_expiry_date date, p_variants jsonb, p_additional_attributes jsonb, p_size character varying DEFAULT NULL, p_color character varying DEFAULT NULL, p_imei character varying DEFAULT NULL
        )
        RETURNS SETOF products LANGUAGE plpgsql AS $function$
        DECLARE v_id INT;
        BEGIN
            INSERT INTO products(
                tenant_id, name, category, subcategory, brand, price, purchase_price, mrp, discount, discount_type, tax_percent, stock_qty, min_stock, reorder_level, unit, barcode, sku, hsn_code, batch_number, mfg_date, expiry_date, variants, additional_attributes, size, color, imei
            )
            VALUES (
                p_tenant_id, p_name, p_category, p_subcategory, p_brand, p_price, p_purchase_price, p_mrp, p_discount, p_discount_type, p_tax_percent, p_stock_qty, p_min_stock, p_reorder_level, p_unit, p_barcode, p_sku, p_hsn_code, p_batch_number, p_mfg_date, p_expiry_date, COALESCE(p_variants, '{}'::jsonb), COALESCE(p_additional_attributes, '{}'::jsonb), p_size, p_color, p_imei
            )
            RETURNING id INTO v_id;
            RETURN QUERY SELECT * FROM products WHERE id = v_id;
        END;
        $function$;
    """)

    await conn.execute("""
        DROP FUNCTION IF EXISTS public.sp_update_product;
        CREATE OR REPLACE FUNCTION public.sp_update_product(
            p_product_id integer, p_tenant_id integer, p_name character varying, p_category character varying, p_subcategory character varying, p_brand character varying, p_price numeric, p_purchase_price numeric, p_mrp numeric, p_discount numeric, p_discount_type character varying, p_tax_percent numeric, p_stock_qty numeric, p_min_stock numeric, p_reorder_level numeric, p_unit character varying, p_barcode character varying, p_sku character varying, p_hsn_code character varying, p_batch_number character varying, p_mfg_date date, p_expiry_date date, p_variants jsonb, p_additional_attributes jsonb, p_size character varying DEFAULT NULL, p_color character varying DEFAULT NULL, p_imei character varying DEFAULT NULL
        )
        RETURNS SETOF products LANGUAGE plpgsql AS $function$
        BEGIN
            UPDATE products SET
                name = COALESCE(p_name, name), 
                category = COALESCE(p_category, category),
                subcategory = COALESCE(p_subcategory, subcategory),
                brand = COALESCE(p_brand, brand),
                price = COALESCE(p_price, price), 
                purchase_price = COALESCE(p_purchase_price, purchase_price),
                mrp = COALESCE(p_mrp, mrp),
                discount = COALESCE(p_discount, discount),
                discount_type = COALESCE(p_discount_type, discount_type),
                tax_percent = COALESCE(p_tax_percent, tax_percent),
                stock_qty = COALESCE(p_stock_qty, stock_qty),
                min_stock = COALESCE(p_min_stock, min_stock),
                reorder_level = COALESCE(p_reorder_level, reorder_level),
                unit = COALESCE(p_unit, unit), 
                barcode = COALESCE(p_barcode, barcode),
                sku = COALESCE(p_sku, sku), 
                hsn_code = COALESCE(p_hsn_code, hsn_code),
                batch_number = COALESCE(p_batch_number, batch_number),
                mfg_date = COALESCE(p_mfg_date, mfg_date),
                expiry_date = COALESCE(p_expiry_date, expiry_date),
                variants = COALESCE(p_variants, variants),
                additional_attributes = COALESCE(p_additional_attributes, additional_attributes),
                size = COALESCE(p_size, size),
                color = COALESCE(p_color, color), 
                imei = COALESCE(p_imei, imei)
            WHERE id = p_product_id AND tenant_id = p_tenant_id;
            RETURN QUERY SELECT * FROM products WHERE id = p_product_id;
        END;
        $function$;
    """)

    print("Updating invoices SPs...")
    await conn.execute("""
        DROP FUNCTION IF EXISTS public.sp_create_invoice;
        CREATE OR REPLACE FUNCTION public.sp_create_invoice(
            p_tenant_id integer, p_user_id integer, p_customer_id integer, p_items jsonb, p_payment_method character varying, p_notes text, p_paid_amount numeric, p_invoice_status character varying, p_metadata jsonb, p_table_id integer DEFAULT NULL, p_kot_id integer DEFAULT NULL
        )
        RETURNS SETOF invoices LANGUAGE plpgsql AS $function$
        DECLARE
            v_invoice_id INT;
            v_subtotal NUMERIC := 0;
            v_discount_total NUMERIC := 0;
            v_tax_total NUMERIC := 0;
            v_grand_total NUMERIC := 0;
            v_balance NUMERIC := 0;
            v_item JSONB;
            v_invoice_number VARCHAR;
            v_line_total NUMERIC;
            v_discount NUMERIC;
            v_tax NUMERIC;
            v_item_discount_type VARCHAR;
        BEGIN
            FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
            LOOP
                v_line_total := (v_item->>'unit_price')::NUMERIC * (v_item->>'quantity')::NUMERIC;
                v_discount := COALESCE((v_item->>'discount')::NUMERIC, 0);
                v_item_discount_type := COALESCE((v_item->>'discount_type')::VARCHAR, 'percent');
                IF v_item_discount_type = 'percent' THEN
                    v_discount := (v_line_total * v_discount) / 100;
                END IF;
                
                v_tax := COALESCE((v_item->>'tax_percent')::NUMERIC, 0);
                v_subtotal := v_subtotal + v_line_total;
                v_discount_total := v_discount_total + v_discount;
                v_tax_total := v_tax_total + ((v_line_total - v_discount) * v_tax / 100);
            END LOOP;

            v_grand_total := v_subtotal - v_discount_total + v_tax_total;
            v_balance := v_grand_total - p_paid_amount;

            SELECT 'INV-' || p_tenant_id || '-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
                   LPAD((COUNT(*) + 1)::TEXT, 4, '0')
            INTO v_invoice_number
            FROM invoices
            WHERE tenant_id = p_tenant_id AND DATE(created_at) = CURRENT_DATE;

            INSERT INTO invoices(
                tenant_id, invoice_number, customer_id, user_id, items,
                subtotal, discount_total, tax_total, grand_total,
                payment_method, notes, table_id, kot_id,
                paid_amount, balance, invoice_status, metadata
            )
            VALUES (
                p_tenant_id, v_invoice_number, p_customer_id, p_user_id, p_items,
                v_subtotal, v_discount_total, v_tax_total, v_grand_total,
                p_payment_method, p_notes, p_table_id, p_kot_id,
                p_paid_amount, v_balance, p_invoice_status, COALESCE(p_metadata, '{}'::jsonb)
            )
            RETURNING id INTO v_invoice_id;

            FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
            LOOP
                UPDATE products
                SET stock_qty = stock_qty - (v_item->>'quantity')::NUMERIC
                WHERE id = (v_item->>'product_id')::INT AND tenant_id = p_tenant_id;
            END LOOP;

            RETURN QUERY SELECT * FROM invoices WHERE id = v_invoice_id;
        END;
        $function$;
    """)
    print("Done!")
    await conn.close()

asyncio.run(migrate())
