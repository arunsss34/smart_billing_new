from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/menus", tags=["Dynamic Menus"])

class MenuResponse(BaseModel):
    menus: list[dict[str, Any]]
    features: dict[str, Any]
    theme_color: Optional[str] = "#6366F1"
    tenant_name: Optional[str] = "Smart Billing"

class PermissionUpdate(BaseModel):
    role_id: int
    menu_id: int
    can_view: bool
    can_add: bool
    can_edit: bool
    can_delete: bool

# ─── Dynamic menus for logged-in user ─────────────────────────
@router.get("/get-menus", response_model=MenuResponse)
async def get_menus(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_get_menus(:user_id, :tenant_id, :role_id)"),
        {
            "user_id": current_user["user_id"],
            "tenant_id": current_user["tenant_id"],
            "role_id": current_user["role_id"]
        }
    )
    rows = result.mappings().all()
    menus = [{
        "id": row["menu_id"],
        "name": row["menu_name"],
        "route": row["route"],
        "icon": row["icon"],
        "parent_id": row["parent_id"],
        "sort_order": row.get("sort_order", 0),
        "can_view": row["can_view"],
        "can_add": row["can_add"],
        "can_delete": row["can_delete"],
    } for row in rows]

    features = {}
    theme_color = "#6366F1"
    tenant_name = "Smart Billing"
    if current_user["tenant_id"] is not None:
        # Fetch features
        feat_result = await db.execute(
            text("SELECT * FROM sp_get_tenant_features(:tenant_id)"),
            {"tenant_id": current_user["tenant_id"]}
        )
        features = {row["feature_key"]: row["enabled"] for row in feat_result.mappings().all()}

        # Fetch theme and name
        tenant_result = await db.execute(
            text("SELECT name, theme_color FROM tenants WHERE id = :tenant_id"),
            {"tenant_id": current_user["tenant_id"]}
        )
        t_row = tenant_result.mappings().first()
        if t_row:
            if t_row["theme_color"]: theme_color = t_row["theme_color"]
            if t_row["name"]: tenant_name = t_row["name"]

    return MenuResponse(menus=menus, features=features, theme_color=theme_color, tenant_name=tenant_name)

# ─── Menu Config Admin Endpoints (Super Admin only) ───────────

@router.get("/all")
async def list_all_menus(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return full menu tree with per-role permissions"""
    if current_user["role_id"] != 1:
        raise HTTPException(status_code=403, detail="Super Admin only")

    # Get all menus
    menus_result = await db.execute(
        text("SELECT * FROM menus WHERE is_active = TRUE ORDER BY parent_id NULLS FIRST, sort_order, name")
    )
    menus = [dict(r) for r in menus_result.mappings().all()]

    # Get all roles
    roles_result = await db.execute(text("SELECT * FROM roles ORDER BY id"))
    roles = [dict(r) for r in roles_result.mappings().all()]

    # Get all role_permissions
    perms_result = await db.execute(
        text("SELECT * FROM role_permissions")
    )
    perms = [dict(r) for r in perms_result.mappings().all()]

    # Index permissions as {(role_id, menu_id): perm}
    perm_index = {(p["role_id"], p["menu_id"]): p for p in perms}

    # Attach permissions to each menu
    for menu in menus:
        menu["permissions"] = []
        for role in roles:
            key = (role["id"], menu["id"])
            perm = perm_index.get(key)
            menu["permissions"].append({
                "role_id": role["id"],
                "role_name": role["name"],
                "role_label": role["name"].replace("_", " ").title(),
                "can_view":   perm["can_view"]   if perm else False,
                "can_add":    perm["can_add"]    if perm else False,
                "can_edit":   perm["can_edit"]   if perm else False,
                "can_delete": perm["can_delete"] if perm else False,
            })

    return {"menus": menus, "roles": roles}

@router.put("/permissions")
async def update_permission(
    data: PermissionUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upsert role permission for a menu"""
    if current_user["role_id"] != 1:
        raise HTTPException(status_code=403, detail="Super Admin only")

    await db.execute(
        text("""
            INSERT INTO role_permissions(role_id, menu_id, can_view, can_add, can_edit, can_delete)
            VALUES (:role_id, :menu_id, :can_view, :can_add, :can_edit, :can_delete)
            ON CONFLICT (role_id, menu_id) DO UPDATE SET
                can_view   = EXCLUDED.can_view,
                can_add    = EXCLUDED.can_add,
                can_edit   = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete
        """),
        {
            "role_id":    data.role_id,
            "menu_id":    data.menu_id,
            "can_view":   data.can_view,
            "can_add":    data.can_add,
            "can_edit":   data.can_edit,
            "can_delete": data.can_delete,
        }
    )
    await db.commit()
    return {"message": "Permission updated"}

# ─── Tenant Role Permission Config (Tenant Admin only) ─────────

class TenantRolePermissionUpdate(BaseModel):
    menu_id:    int
    can_view:   bool
    can_add:    bool
    can_edit:   bool
    can_delete: bool

@router.get("/tenant-role-permissions/{tenant_role_id}")
async def get_tenant_role_menus(
    tenant_role_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns all menus with their current permissions for a given tenant_role."""
    if current_user["role_id"] != 2:
        raise HTTPException(status_code=403, detail="Tenant Admin only")

    # Verify this tenant_role belongs to this tenant
    check = await db.execute(
        text("SELECT id FROM tenant_roles WHERE id = :id AND tenant_id = :tid"),
        {"id": tenant_role_id, "tid": current_user["tenant_id"]}
    )
    if not check.first():
        raise HTTPException(status_code=404, detail="Role not found in your tenant")

    result = await db.execute(
        text("SELECT * FROM sp_list_menus_for_tenant_role(:role_id)"),
        {"role_id": tenant_role_id}
    )
    return [dict(r) for r in result.mappings().all()]

@router.put("/tenant-role-permissions/{tenant_role_id}")
async def update_tenant_role_permission(
    tenant_role_id: int,
    data: TenantRolePermissionUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upsert a menu permission for a tenant_role."""
    if current_user["role_id"] != 2:
        raise HTTPException(status_code=403, detail="Tenant Admin only")

    check = await db.execute(
        text("SELECT id FROM tenant_roles WHERE id = :id AND tenant_id = :tid"),
        {"id": tenant_role_id, "tid": current_user["tenant_id"]}
    )
    if not check.first():
        raise HTTPException(status_code=404, detail="Role not found in your tenant")

    await db.execute(
        text("""
            SELECT sp_save_tenant_role_permission(
                :role_id, :menu_id, :can_view, :can_add, :can_edit, :can_delete
            )
        """),
        {
            "role_id":    tenant_role_id,
            "menu_id":    data.menu_id,
            "can_view":   data.can_view,
            "can_add":    data.can_add,
            "can_edit":   data.can_edit,
            "can_delete": data.can_delete,
        }
    )
    await db.commit()
    return {"message": "Permission updated"}
