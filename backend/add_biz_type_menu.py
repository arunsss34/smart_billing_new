"""Add Business Types menu item under Settings for Super Admin"""
import asyncio
import asyncpg
import sys
sys.path.insert(0, '.')
from app.config import settings

async def add_menu():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    user_pass, host_db = url.split("@")
    username, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    host = host_port.split(":")[0]
    port = int(host_port.split(":")[1]) if ":" in host_port else 5432

    conn = await asyncpg.connect(host=host, port=port, user=username, password=password, database=dbname)

    # Get Settings menu ID
    settings_id = await conn.fetchval("SELECT id FROM menus WHERE route = 'settings'")
    if not settings_id:
        print("Settings menu not found!")
        await conn.close()
        return

    print(f"Settings menu ID: {settings_id}")

    # Insert Business Types menu under Settings
    await conn.execute("""
        INSERT INTO menus(name, route, icon, parent_id, sort_order)
        VALUES ('Business Types', 'settings/business-types', 'building', $1, 0)
        ON CONFLICT DO NOTHING
    """, settings_id)

    # Get the new menu ID
    bt_menu_id = await conn.fetchval("SELECT id FROM menus WHERE route = 'settings/business-types'")
    print(f"Business Types menu ID: {bt_menu_id}")

    # Give Super Admin permission
    await conn.execute("""
        INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
        VALUES (1, $1, TRUE, TRUE, TRUE, TRUE)
        ON CONFLICT (role_id, menu_id) DO NOTHING
    """, bt_menu_id)

    print("Business Types menu added to sidebar for Super Admin!")

    # Verify all settings sub-menus
    rows = await conn.fetch("SELECT name, route FROM menus WHERE parent_id = $1 ORDER BY sort_order", settings_id)
    print("\nSettings sub-menus:")
    for r in rows:
        print(f"  - {r['name']} -> {r['route']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(add_menu())
