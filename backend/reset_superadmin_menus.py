"""
Reset Super Admin menu permissions to only the 4 required menus:
- Business Types (id=13)
- Tenants       (id=10)
- Users         (id=7)
- Menu Config   (id=12)
- Settings      (id=6)  ← parent, needed for navigation
Run: python reset_superadmin_menus.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

# menu_id → (can_view, can_add, can_edit, can_delete)
SA_MENUS = {
    6:  (True,  False, False, False),  # Settings (parent nav shell)
    7:  (True,  True,  True,  True),   # Users
    10: (True,  True,  True,  True),   # Tenants
    12: (True,  True,  True,  True),   # Menu Config
    13: (True,  True,  True,  True),   # Business Types
}

async def run():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    # 1. Restore any permissions we just deleted (they may have already been removed)
    deleted = await conn.fetchval("SELECT COUNT(*) FROM role_permissions WHERE role_id = 1")
    await conn.execute("DELETE FROM role_permissions WHERE role_id = 1")
    print(f"Cleared {deleted} existing super admin permissions")

    # 2. Insert only the 4 allowed menus
    for menu_id, (cv, ca, ce, cd) in SA_MENUS.items():
        await conn.execute("""
            INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
            VALUES (1, $1, $2, $3, $4, $5)
        """, menu_id, cv, ca, ce, cd)

    # 3. Verify
    rows = await conn.fetch("""
        SELECT m.name, m.route, rp.can_view, rp.can_add, rp.can_edit, rp.can_delete
        FROM role_permissions rp
        JOIN menus m ON m.id = rp.menu_id
        WHERE rp.role_id = 1
        ORDER BY rp.menu_id
    """)

    print("\nSuper Admin menus after reset:")
    for r in rows:
        perms = []
        if r["can_view"]:   perms.append("View")
        if r["can_add"]:    perms.append("Add")
        if r["can_edit"]:   perms.append("Edit")
        if r["can_delete"]: perms.append("Delete")
        print(f"  {r['name']:20s} ({r['route']}) -> {', '.join(perms)}")

    await conn.close()
    print("\nDone! Super Admin now sees only: Business Types, Tenants, Users, Menu Config")

if __name__ == "__main__":
    asyncio.run(run())
