from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional
from datetime import date

router = APIRouter(prefix="/tenants", tags=["Tenant Management"])

class TenantCreate(BaseModel):
    name: str
    business_type: str  # restaurant, bakery, supermarket, dress_shop, mobile_shop
    email: str
    phone: str
    subscription_expiry: date
    is_active: bool = True
    theme_color: str = "#6366F1"

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    subscription_expiry: Optional[date] = None
    is_active: Optional[bool] = None
    theme_color: Optional[str] = None

@router.get("/")
async def list_tenants(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user["role_id"] != 1:  # Super Admin only
        raise HTTPException(status_code=403, detail="Access denied")
    result = await db.execute(text("SELECT * FROM sp_list_tenants()"))
    return result.mappings().all()

@router.post("/")
async def create_tenant(
    tenant: TenantCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user["role_id"] != 1:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        text("SELECT * FROM sp_create_tenant(:name, :business_type, :email, :phone, :subscription_expiry, :is_active, :theme_color)"),
        tenant.model_dump()
    )
    new_tenant = result.mappings().first()
    await db.commit()

    if not new_tenant:
        raise HTTPException(status_code=400, detail="Tenant creation failed")

    # Auto-provision business-type masters for the new tenant
    bt = await db.execute(
        text("SELECT id FROM business_types WHERE name = :name"),
        {"name": tenant.business_type}
    )
    bt_row = bt.first()
    if bt_row:
        await db.execute(
            text("CALL sp_provision_tenant_masters(:tenant_id, :bt_id)"),
            {"tenant_id": new_tenant["id"], "bt_id": bt_row[0]}
        )
        await db.commit()

    return {
        **dict(new_tenant),
        "masters_provisioned": bt_row is not None,
    }

@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    tenant: TenantUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user["role_id"] != 1:
        raise HTTPException(status_code=403, detail="Access denied")
    data = tenant.model_dump(exclude_none=True)
    data["tenant_id"] = tenant_id
    result = await db.execute(
        text("SELECT * FROM sp_update_tenant(:tenant_id, :name, :business_type, :email, :phone, :subscription_expiry, :is_active, :theme_color)"),
        data
    )
    await db.commit()
    return result.mappings().first()

@router.delete("/{tenant_id}")
async def deactivate_tenant(
    tenant_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user["role_id"] != 1:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.execute(
        text("CALL sp_deactivate_tenant(:tenant_id)"),
        {"tenant_id": tenant_id}
    )
    await db.commit()
    return {"message": "Tenant deactivated"}
