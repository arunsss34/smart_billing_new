"""
Fix: 
1. Add Settings parent (id=6) permission for tenant_admin so the Settings section appears
2. Remove duplicate Role Management menu (id=15, same route as id=11)
3. Clean up menus for tenant_admin - should see: Settings, Role Management, Masters, Users
Run: python fix_tenant_menus.py
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def fix():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    # 1. Remove duplicate menu (id=15, same route as id=11)
    dup = await conn.fetchval("SELECT COUNT(*) FROM menus WHERE route='settings/roles'")
    print(f"Menus with route 'settings/roles': {dup}")
    if dup > 1:
        # Keep id=11, delete id=15
        await conn.execute("DELETE FROM role_permissions WHERE menu_id = 15")
        await conn.execute("DELETE FROM menus WHERE id = 15")
        print("Removed duplicate menu id=15 (Role Management)")

    # 2. Add Settings parent (id=6) permission for tenant_admin
    await conn.execute("""
        INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
        VALUES (2, 6, TRUE, FALSE, FALSE, FALSE)
        ON CONFLICT (role_id, menu_id) DO UPDATE SET can_view = TRUE
    """)
    print("Added Settings parent (id=6) for tenant_admin")

    # 3. Rename menu id=11 to "Role Management" for clarity
    await conn.execute("UPDATE menus SET name='Role Management', icon='shield' WHERE id=11")
    print("Renamed menu id=11 to 'Role Management'")

    # 4. Verify final tenant_admin menus
    rows = await conn.fetch("""
        SELECT m.id, m.name, m.route, m.parent_id, rp.can_view, rp.can_add, rp.can_edit, rp.can_delete
        FROM role_permissions rp
        JOIN menus m ON m.id = rp.menu_id
        WHERE rp.role_id = 2
        ORDER BY m.parent_id NULLS FIRST, m.id
    """)
    print("\nTenant Admin menus after fix:")
    for r in rows:
        indent = "  " if r["parent_id"] else ""
        perms = [k for k, v in {"View": r["can_view"],"Add": r["can_add"],"Edit": r["can_edit"],"Del": r["can_delete"]}.items() if v]
        print(f"  {indent}[{r['id']}] {r['name']} ({r['route']}) -> {', '.join(perms)}")

    await conn.close()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(fix())
