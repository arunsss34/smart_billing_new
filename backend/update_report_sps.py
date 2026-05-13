import asyncio
from app.database import engine
from sqlalchemy import text

async def update_sps():
    async with engine.begin() as conn:
        # 1. Sales Summary SP
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION sp_report_sales_summary(
                p_tenant_id INTEGER,
                p_start_date DATE DEFAULT NULL,
                p_end_date DATE DEFAULT NULL,
                p_customer_id INTEGER DEFAULT NULL
            )
            RETURNS TABLE (
                total_revenue NUMERIC,
                total_invoices BIGINT,
                total_tax NUMERIC,
                total_discount NUMERIC
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT 
                    COALESCE(SUM(grand_total), 0),
                    COUNT(id),
                    COALESCE(SUM(tax_total), 0),
                    COALESCE(SUM(discount_total), 0)
                FROM invoices
                WHERE tenant_id = p_tenant_id
                  AND (p_start_date IS NULL OR created_at >= p_start_date)
                  AND (p_end_date IS NULL OR created_at <= (p_end_date + interval '1 day'))
                  AND (p_customer_id IS NULL OR customer_id = p_customer_id);
            END;
            $$ LANGUAGE plpgsql;
        """))

        # 2. Daily Sales SP
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION sp_report_daily_sales(
                p_tenant_id INTEGER,
                p_start_date DATE DEFAULT NULL,
                p_end_date DATE DEFAULT NULL,
                p_customer_id INTEGER DEFAULT NULL
            )
            RETURNS TABLE (
                sale_date DATE,
                total_revenue NUMERIC,
                total_invoices BIGINT
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT 
                    created_at::DATE,
                    SUM(grand_total),
                    COUNT(id)
                FROM invoices
                WHERE tenant_id = p_tenant_id
                  AND (p_start_date IS NULL OR created_at >= p_start_date)
                  AND (p_end_date IS NULL OR created_at <= (p_end_date + interval '1 day'))
                  AND (p_customer_id IS NULL OR customer_id = p_customer_id)
                GROUP BY 1
                ORDER BY 1 DESC;
            END;
            $$ LANGUAGE plpgsql;
        """))

        # 3. Top Products SP
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION sp_report_top_products(
                p_tenant_id INTEGER,
                p_start_date DATE DEFAULT NULL,
                p_end_date DATE DEFAULT NULL,
                p_customer_id INTEGER DEFAULT NULL
            )
            RETURNS TABLE (
                product_name VARCHAR,
                total_qty NUMERIC,
                total_revenue NUMERIC
            ) AS $$
            BEGIN
                RETURN QUERY
                WITH expanded_items AS (
                    SELECT 
                        (item->>'product_id')::INT as product_id,
                        (item->>'quantity')::NUMERIC as quantity,
                        (item->>'unit_price')::NUMERIC as unit_price,
                        (item->>'discount')::NUMERIC as discount
                    FROM invoices i,
                    jsonb_array_elements(i.items) AS item
                    WHERE i.tenant_id = p_tenant_id
                      AND (p_start_date IS NULL OR i.created_at >= p_start_date)
                      AND (p_end_date IS NULL OR i.created_at <= (p_end_date + interval '1 day'))
                      AND (p_customer_id IS NULL OR i.customer_id = p_customer_id)
                )
                SELECT 
                    p.name::VARCHAR,
                    SUM(ei.quantity),
                    SUM(ei.quantity * ei.unit_price - COALESCE(ei.discount, 0))
                FROM expanded_items ei
                JOIN products p ON p.id = ei.product_id
                GROUP BY p.name
                ORDER BY 3 DESC
                LIMIT 10;
            END;
            $$ LANGUAGE plpgsql;
        """))

        # 4. Payment Methods SP
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION sp_report_payment_methods(
                p_tenant_id INTEGER,
                p_start_date DATE DEFAULT NULL,
                p_end_date DATE DEFAULT NULL,
                p_customer_id INTEGER DEFAULT NULL
            )
            RETURNS TABLE (
                payment_method VARCHAR,
                total_invoices BIGINT,
                total_revenue NUMERIC
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT 
                    i.payment_method,
                    COUNT(i.id),
                    SUM(i.grand_total)
                FROM invoices i
                WHERE i.tenant_id = p_tenant_id
                  AND (p_start_date IS NULL OR i.created_at >= p_start_date)
                  AND (p_end_date IS NULL OR i.created_at <= (p_end_date + interval '1 day'))
                  AND (p_customer_id IS NULL OR i.customer_id = p_customer_id)
                GROUP BY i.payment_method
                ORDER BY 3 DESC;
            END;
            $$ LANGUAGE plpgsql;
        """))

if __name__ == "__main__":
    asyncio.run(update_sps())
