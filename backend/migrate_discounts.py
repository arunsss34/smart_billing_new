import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def migrate():
    url = settings.DATABASE_URL.replace('postgresql+asyncpg://', '')
    u, h = url.split('@'); user, pw = u.split(':'); hp, db = h.split('/')
    host = hp.split(':')[0]; port = int(hp.split(':')[1]) if ':' in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Altering invoices table to add bill_discount...")
    await conn.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS bill_discount NUMERIC DEFAULT 0
    """)

    print("Updating sp_create_invoice to handle line-item and bill-level discounts...")
    await conn.execute("""
        DROP FUNCTION IF EXISTS public.sp_create_invoice;
        CREATE OR REPLACE FUNCTION public.sp_create_invoice(
            p_tenant_id integer, p_user_id integer, p_customer_id integer, p_items jsonb, 
            p_payment_method character varying, p_notes text, p_paid_amount numeric, 
            p_invoice_status character varying, p_metadata jsonb, 
            p_table_id integer DEFAULT NULL, p_kot_id integer DEFAULT NULL
        )
        RETURNS SETOF invoices LANGUAGE plpgsql AS $function$
        DECLARE
            v_invoice_id INT;
            v_subtotal NUMERIC := 0;
            v_item_discount_total NUMERIC := 0;
            v_bill_discount NUMERIC := 0;
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
            -- Extract bill-level discount from metadata if provided, otherwise 0
            v_bill_discount := COALESCE((p_metadata->>'bill_discount')::NUMERIC, 0);

            FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
            LOOP
                v_line_total := (v_item->>'unit_price')::NUMERIC * (v_item->>'quantity')::NUMERIC;
                
                -- Handle Item-level discount (can be fixed or percentage)
                v_discount := COALESCE((v_item->>'discount')::NUMERIC, 0);
                v_item_discount_type := COALESCE((v_item->>'discount_type')::VARCHAR, 'fixed');
                
                IF v_item_discount_type = 'percent' THEN
                    v_discount := (v_line_total * v_discount) / 100;
                END IF;
                
                v_tax := COALESCE((v_item->>'tax_percent')::NUMERIC, 0);
                v_subtotal := v_subtotal + v_line_total;
                v_item_discount_total := v_item_discount_total + v_discount;
                v_tax_total := v_tax_total + ((v_line_total - v_discount) * v_tax / 100);
            END LOOP;

            -- Grand Total = (Items Subtotal - Item Discounts) - Bill Level Discount + Taxes
            v_grand_total := (v_subtotal - v_item_discount_total) - v_bill_discount + v_tax_total;
            v_grand_total := GREATEST(0, v_grand_total);
            
            v_balance := v_grand_total - p_paid_amount;

            -- Generate Invoice Number
            SELECT 'INV-' || p_tenant_id || '-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
                   LPAD((COUNT(*) + 1)::TEXT, 4, '0')
            INTO v_invoice_number
            FROM invoices
            WHERE tenant_id = p_tenant_id AND DATE(created_at) = CURRENT_DATE;

            INSERT INTO invoices(
                tenant_id, invoice_number, customer_id, user_id, items,
                subtotal, discount_total, tax_total, grand_total,
                payment_method, notes, table_id, kot_id,
                paid_amount, balance, invoice_status, metadata, bill_discount
            )
            VALUES (
                p_tenant_id, v_invoice_number, p_customer_id, p_user_id, p_items,
                v_subtotal, (v_item_discount_total + v_bill_discount), v_tax_total, v_grand_total,
                p_payment_method, p_notes, p_table_id, p_kot_id,
                p_paid_amount, v_balance, p_invoice_status, COALESCE(p_metadata, '{}'::jsonb), v_bill_discount
            )
            RETURNING id INTO v_invoice_id;

            -- Update Stock
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
    print("Migration complete!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
