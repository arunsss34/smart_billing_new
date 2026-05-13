import asyncio
import asyncpg
import random
import sys
import os

# Add root to sys.path
sys.path.insert(0, '.')
from app.config import settings

async def seed_retail_data(tenant_id: int):
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@")
    user, pw = u.split(":")
    hp, db_name = h.split("/")
    host = hp.split(":")[0]
    port = int(hp.split(":")[1]) if ":" in hp else 5432
    
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db_name)
    
    print(f"Seeding 100 products for tenant_id: {tenant_id}")

    # 1. Ensure we have some Categories for this tenant
    categories = [
        "Electronics", "Clothing", "Groceries", "Household", "Stationery",
        "Beverages", "Snacks", "Personal Care", "Dairy", "Frozen Food"
    ]
    
    cat_ids = []
    for cat_name in categories:
        # Check if exists
        row = await conn.fetchrow("SELECT id FROM categories WHERE name = $1 AND (tenant_id = $2 OR tenant_id IS NULL)", cat_name, tenant_id)
        if row:
            cat_ids.append(row['id'])
        else:
            # We don't have tenant_id in categories table based on migrate_masters.py, 
            # let's check if we should add it or just use existing.
            # Looking at migrate_masters.py, categories table doesn't have tenant_id.
            # But the SP sp_list_categories in ProductsScreen uses tenant_id.
            # I will assume the table has it based on your multi-tenant requirement.
            try:
                nid = await conn.fetchval("INSERT INTO categories (name, tenant_id) VALUES ($1, $2) RETURNING id", cat_name, tenant_id)
                cat_ids.append(nid)
            except:
                nid = await conn.fetchval("INSERT INTO categories (name) VALUES ($1) RETURNING id", cat_name)
                cat_ids.append(nid)

    # 2. Ensure we have some UOMs
    uoms = [("Piece", "PCS"), ("Kilogram", "KG"), ("Liter", "LTR"), ("Box", "BOX")]
    uom_names = []
    for u_name, u_abbv in uoms:
        # Check if abbreviation exists in uom_masters
        row = await conn.fetchrow("SELECT name FROM uom_masters WHERE abbreviation = $1", u_abbv)
        if row:
            uom_names.append(row['name'])
        else:
            await conn.execute("INSERT INTO uom_masters (name, abbreviation) VALUES ($1, $2)", u_name, u_abbv)
            uom_names.append(u_name)

    # 3. Ensure we have HSN Codes
    hsn_codes = ["8412", "8517", "6101", "1001", "2106"]
    for h_code in hsn_codes:
        row = await conn.fetchrow("SELECT hsn_code FROM hsn_masters WHERE hsn_code = $1", h_code)
        if not row:
            await conn.execute("INSERT INTO hsn_masters (hsn_code, description, igst_rate) VALUES ($1, $2, 18.0)", h_code, f"Tax code {h_code}")

    # 4. Generate 100 Products
    product_prefixes = ["Ultra", "Smart", "Eco", "Pro", "Classic", "Premium", "Daily", "Fast", "Super", "Mega"]
    product_bases = ["Phone", "Bottle", "Shirt", "Snack", "Charger", "Napkin", "Pen", "Notebook", "Milk", "Bread", "Oil", "Soap", "Brush", "Towel", "Light", "Fan"]
    
    count = 0
    for i in range(1, 101):
        name = f"{random.choice(product_prefixes)} {random.choice(product_bases)} {i}"
        category = random.choice(categories)
        price = round(random.uniform(10.0, 2000.0), 2)
        stock = random.randint(10, 500)
        unit = random.choice(uom_names)
        barcode = f"8901234{str(i).zfill(6)}"
        sku = f"SKU-{tenant_id}-{str(i).zfill(4)}"
        hsn = random.choice(hsn_codes)
        
        # Check if exists
        exists = await conn.fetchval("SELECT id FROM products WHERE sku = $1 AND tenant_id = $2", sku, tenant_id)
        if not exists:
            await conn.execute("""
                SELECT public.sp_create_product(
                    $1, $2, $3, NULL, NULL, $4, $5, $6, 0.0, 'percent', 18.0, $7, 5.0, 10.0, $8, $9, $10, $11, NULL, NULL, NULL, '{}'::jsonb, '{}'::jsonb
                )
            """, tenant_id, name, category, price, price*0.8, price*1.2, float(stock), unit, barcode, sku, hsn)
            count += 1
            if count % 20 == 0:
                print(f"Inserted {count} products...")

    print(f"Finished! Seeded {count} new products for tenant {tenant_id}.")
    await conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_retail_data.py <tenant_id>")
    else:
        tid = int(sys.argv[1])
        asyncio.run(seed_retail_data(tid))
