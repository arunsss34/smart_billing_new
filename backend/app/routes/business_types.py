from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/business-types", tags=["Business Types"])

SUPERADMIN_ROLE = 1

class BusinessTypeCreate(BaseModel):
    name: str                          # slug key e.g. "pharmacy"
    label: str                         # display name e.g. "Pharmacy"
    icon: str = "🏢"
    description: Optional[str] = None
    default_features: List[str] = []   # e.g. ["barcode", "expiry_tracking"]

class BusinessTypeUpdate(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    default_features: Optional[List[str]] = None
    is_active: Optional[bool] = None

def _sa(current_user: dict):
    if current_user["role_id"] != SUPERADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Super Admin access required")

@router.get("/")
async def list_business_types(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all active business types — available to all logged-in users"""
    result = await db.execute(text("SELECT * FROM sp_list_business_types()"))
    rows = result.mappings().all()
    return [dict(r) for r in rows]

@router.post("/")
async def create_business_type(
    data: BusinessTypeCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new business type — Super Admin only"""
    _sa(current_user)
    # Validate slug: lowercase, no spaces
    slug = data.name.lower().replace(" ", "_")
    result = await db.execute(
        text("SELECT * FROM sp_create_business_type(:name, :label, :icon, :description, :default_features)"),
        {
            "name": slug,
            "label": data.label,
            "icon": data.icon,
            "description": data.description,
            "default_features": data.default_features,
        }
    )
    await db.commit()
    return dict(result.mappings().first())

@router.put("/{bt_id}")
async def update_business_type(
    bt_id: int,
    data: BusinessTypeUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a business type — Super Admin only"""
    _sa(current_user)
    payload = data.model_dump(exclude_none=True)
    if "name" in payload:
        payload["name"] = payload["name"].lower().replace(" ", "_")
    result = await db.execute(
        text("""SELECT * FROM sp_update_business_type(
            :id, :name, :label, :icon, :description, :default_features, :is_active
        )"""),
        {
            "id": bt_id,
            "name": payload.get("name"),
            "label": payload.get("label"),
            "icon": payload.get("icon"),
            "description": payload.get("description"),
            "default_features": payload.get("default_features"),
            "is_active": payload.get("is_active"),
        }
    )
    await db.commit()
    return dict(result.mappings().first())

@router.delete("/{bt_id}")
async def deactivate_business_type(
    bt_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete a business type — Super Admin only"""
    _sa(current_user)
    await db.execute(
        text("UPDATE business_types SET is_active = FALSE WHERE id = :id"),
        {"id": bt_id}
    )
    await db.commit()
    return {"message": "Business type deactivated"}
