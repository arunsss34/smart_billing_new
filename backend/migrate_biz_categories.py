"""
Migration: Link categories to business_type + seed business-specific categories
Run: python migrate_biz_categories.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

SQL_SCHEMA = """
-- Add business_type_id to categories
ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS business_type_id INT REFERENCES business_types(id);

-- Update SP: filter by business type (tenant's type) OR global (NULL business_type_id)
CREATE OR REPLACE FUNCTION sp_list_categories(
    p_tenant_id INT DEFAULT NULL,
    p_business_type_id INT DEFAULT NULL
)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM categories
    WHERE is_active = TRUE
      AND (tenant_id IS NULL OR tenant_id = p_tenant_id)
      AND (
           business_type_id IS NULL                        -- truly global
        OR business_type_id = p_business_type_id          -- matches tenant biz type
        OR p_business_type_id IS NULL                     -- superadmin sees all
      )
    ORDER BY business_type_id NULLS LAST, parent_id NULLS FIRST, name;
END; $$;

-- Update save SP to accept business_type_id
CREATE OR REPLACE FUNCTION sp_save_category(
    p_id INT,
    p_name VARCHAR,
    p_parent_id INT,
    p_tenant_id INT DEFAULT NULL,
    p_business_type_id INT DEFAULT NULL
)
RETURNS SETOF categories LANGUAGE plpgsql AS $$
DECLARE v_id INT;
BEGIN
    IF p_id IS NULL OR p_id = 0 THEN
        INSERT INTO categories(name, parent_id, tenant_id, business_type_id)
        VALUES (p_name, p_parent_id, p_tenant_id, p_business_type_id)
        RETURNING id INTO v_id;
    ELSE
        UPDATE categories
        SET name = p_name,
            parent_id = p_parent_id,
            business_type_id = COALESCE(p_business_type_id, business_type_id)
        WHERE id = p_id
          AND (tenant_id = p_tenant_id OR p_tenant_id IS NULL);
        v_id := p_id;
    END IF;
    RETURN QUERY SELECT * FROM categories WHERE id = v_id;
END; $$;
"""

# Categories per business type — seed data
BIZ_CATEGORIES = {
    'restaurant': [
        # Parent categories
        ('Starters', None),
        ('Main Course', None),
        ('Breads', None),
        ('Rice & Biryani', None),
        ('Noodles & Pasta', None),
        ('Soups', None),
        ('Salads', None),
        ('Desserts', None),
        ('Beverages', None),
        ('Combos & Meals', None),
    ],
    'bakery': [
        ('Breads & Loaves', None),
        ('Cakes', None),
        ('Pastries & Tarts', None),
        ('Cookies & Biscuits', None),
        ('Muffins & Cupcakes', None),
        ('Buns & Rolls', None),
        ('Puffs & Savouries', None),
        ('Festival Specials', None),
        ('Sugar-Free', None),
        ('Beverages', None),
    ],
    'supermarket': [
        ('Groceries & Staples', None),
        ('Dairy & Eggs', None),
        ('Snacks & Namkeen', None),
        ('Beverages', None),
        ('Personal Care', None),
        ('Household & Cleaning', None),
        ('Fresh Vegetables', None),
        ('Fresh Fruits', None),
        ('Frozen Foods', None),
        ('Baby Care', None),
    ],
    'dress_shop': [
        ('Mens Wear', None),
        ('Womens Wear', None),
        ('Kids Wear', None),
        ('Ethnic Wear', None),
        ('Western Wear', None),
        ('Sportswear', None),
        ('Innerwear & Nightwear', None),
        ('Accessories', None),
        ('Footwear', None),
        ('Seasonal Collection', None),
    ],
    'mobile_shop': [
        ('Smartphones', None),
        ('Feature Phones', None),
        ('Tablets & iPads', None),
        ('Mobile Accessories', None),
        ('Chargers & Cables', None),
        ('Cases & Covers', None),
        ('Earphones & Headphones', None),
        ('Smart Watches', None),
        ('Power Banks', None),
        ('Refurbished Devices', None),
    ],
}

async def migrate():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    print("Running schema migration...")
    await conn.execute(SQL_SCHEMA)

    # Remove old global categories (they don't have business type context)
    await conn.execute("""
        UPDATE categories SET is_active = FALSE
        WHERE business_type_id IS NULL AND tenant_id IS NULL
    """)
    print("Deactivated old global categories (no business type)")

    # Seed business-type-specific categories
    total = 0
    for biz_name, cats in BIZ_CATEGORIES.items():
        bt_id = await conn.fetchval(
            "SELECT id FROM business_types WHERE name = $1", biz_name
        )
        if not bt_id:
            print(f"  SKIP: business type '{biz_name}' not found")
            continue

        for (cat_name, parent_name) in cats:
            parent_id = None
            if parent_name:
                parent_id = await conn.fetchval(
                    "SELECT id FROM categories WHERE name=$1 AND business_type_id=$2",
                    parent_name, bt_id
                )
            existing = await conn.fetchval(
                "SELECT id FROM categories WHERE name=$1 AND business_type_id=$2",
                cat_name, bt_id
            )
            if not existing:
                await conn.execute("""
                    INSERT INTO categories(name, parent_id, business_type_id, is_active)
                    VALUES ($1, $2, $3, TRUE)
                """, cat_name, parent_id, bt_id)
                total += 1

    print(f"Seeded {total} business-type categories")

    # Show result
    rows = await conn.fetch("""
        SELECT bt.label, COUNT(c.id) as cat_count
        FROM categories c
        JOIN business_types bt ON bt.id = c.business_type_id
        WHERE c.is_active = TRUE
        GROUP BY bt.label ORDER BY bt.label
    """)
    print("\nCategories per business type:")
    for r in rows:
        print(f"  {r['label']}: {r['cat_count']} categories")

    await conn.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
