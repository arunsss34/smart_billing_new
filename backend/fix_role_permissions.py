"""
Fix tenant admin Role Management permissions:
- Set can_add=FALSE, can_edit=FALSE, can_delete=FALSE (View only in menu permissions matrix)
- The actual CRUD is handled inside RoleManagementScreen itself (tenant manages their own roles)
- System roles (super_admin, tenant_admin, staff) are never exposed to tenant admin via /roles/
"""
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from app.config import settings

async def fix():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    u, h = url.split("@"); user, pw = u.split(":"); hp, db = h.split("/")
    host = hp.split(":")[0]; port = int(hp.split(":")[1]) if ":" in hp else 5432
    conn = await asyncpg.connect(host=host, port=port, user=user, password=pw, database=db)

    # Role Management menu = id 11
    # Tenant admin should only have View in the permissions matrix
    # The screen itself always allows tenant to manage THEIR OWN roles
    await conn.execute("""
        UPDATE role_permissions
        SET can_add = FALSE, can_edit = FALSE, can_delete = FALSE
        WHERE role_id = 2 AND menu_id = 11
    """)
    print("Updated Role Management (id=11): tenant_admin -> View only")

    # Verify
    rows = await conn.fetch("""
        SELECT r.name, rp.can_view, rp.can_add, rp.can_edit, rp.can_delete
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        JOIN menus m ON m.id = rp.menu_id
        WHERE m.route = 'settings/roles'
        ORDER BY rp.role_id
    """)
    print("\nRole Management permissions after fix:")
    for r in rows:
        flags = []
        if r["can_view"]:   flags.append("View")
        if r["can_add"]:    flags.append("Add")
        if r["can_edit"]:   flags.append("Edit")
        if r["can_delete"]: flags.append("Delete")
        print(f"  {r['name']}: {', '.join(flags) or 'None'}")

    await conn.close()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(fix())
