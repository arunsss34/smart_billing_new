from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/roles", tags=["Role Management"])

def _require_tenant_admin(current_user: dict):
    if current_user["role_id"] not in [1, 2]:
        raise HTTPException(status_code=403, detail="Admin access required")
    if current_user["role_id"] == 2 and not current_user["tenant_id"]:
        raise HTTPException(status_code=403, detail="No tenant context")

class RoleSchema(BaseModel):
    name: str
    description: Optional[str] = None

@router.get("/")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Tenant admin: returns ONLY their own custom tenant_roles (never system roles).
    Super admin: returns system roles minus super_admin itself.
    """
    if current_user["role_id"] == 2:
        # Tenant admin — ONLY their custom roles, never system roles
        if not current_user["tenant_id"]:
            return []
        r = await db.execute(
            text("SELECT * FROM sp_list_tenant_roles(:tenant_id)"),
            {"tenant_id": current_user["tenant_id"]}
        )
        rows = r.mappings().all()
        # Double-guard: only return rows that belong to this tenant
        return [
            dict(row) for row in rows
            if row["tenant_id"] == current_user["tenant_id"]
        ]
    else:
        # Super admin — return system roles (tenant_admin only, not super_admin)
        r = await db.execute(
            text("SELECT * FROM roles WHERE name = 'tenant_admin' ORDER BY id")
        )
        return [dict(row) for row in r.mappings().all()]

@router.post("/")
async def create_role(
    data: RoleSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _require_tenant_admin(current_user)
    if current_user["role_id"] != 2:
        raise HTTPException(status_code=403, detail="Only tenant admins can create custom roles")

    r = await db.execute(
        text("SELECT * FROM sp_save_tenant_role(:id, :tenant_id, :name, :desc)"),
        {"id": 0, "tenant_id": current_user["tenant_id"],
         "name": data.name, "desc": data.description}
    )
    await db.commit()
    return dict(r.mappings().first())

@router.put("/{role_id}")
async def update_role(
    role_id: int,
    data: RoleSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _require_tenant_admin(current_user)
    if current_user["role_id"] != 2:
        raise HTTPException(status_code=403, detail="Only tenant admins can edit custom roles")

    r = await db.execute(
        text("SELECT * FROM sp_save_tenant_role(:id, :tenant_id, :name, :desc)"),
        {"id": role_id, "tenant_id": current_user["tenant_id"],
         "name": data.name, "desc": data.description}
    )
    await db.commit()
    return dict(r.mappings().first())

@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _require_tenant_admin(current_user)
    if current_user["role_id"] != 2:
        raise HTTPException(status_code=403, detail="Only tenant admins can delete custom roles")

    # Ensure no active users have this role
    count = await db.execute(
        text("SELECT COUNT(*) FROM users WHERE tenant_role_id = :id AND is_active = TRUE"),
        {"id": role_id}
    )
    if count.scalar() > 0:
        raise HTTPException(status_code=400, detail="Cannot delete role — users are assigned to it")

    await db.execute(
        text("CALL sp_delete_tenant_role(:id, :tenant_id)"),
        {"id": role_id, "tenant_id": current_user["tenant_id"]}
    )
    await db.commit()
    return {"message": "Role removed"}
