from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/masters", tags=["Masters"])

ALLOWED_ROLES = [1, 2]  # super_admin, tenant_admin

def _check_access(current_user: dict):
    if current_user["role_id"] not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

def _tenant_id(current_user: dict) -> Optional[int]:
    """Super admin gets NULL (global), tenant admin gets their tenant_id."""
    return current_user["tenant_id"]  # None for superadmin

# ─── UOM ─────────────────────────────────────────────────────

class UOMSchema(BaseModel):
    name: str
    abbreviation: str

@router.get("/uom")
async def list_uom(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Super admin sees all global UOMs.
    Tenant admin sees global + their own tenant's UOMs.
    """
    tid = _tenant_id(current_user)
    r = await db.execute(
        text("SELECT * FROM sp_list_uom(:tenant_id)"),
        {"tenant_id": tid}
    )
    return [dict(row) for row in r.mappings().all()]

@router.post("/uom")
async def save_uom(
    data: UOMSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    try:
        r = await db.execute(
            text("SELECT * FROM sp_save_uom(:id, :name, :abbreviation, :tenant_id)"),
            {"id": 0, "name": data.name, "abbreviation": data.abbreviation.upper(), "tenant_id": tid}
        )
        await db.commit()
        return dict(r.mappings().first())
    except IntegrityError as e:
        await db.rollback()
        err = str(e.orig).lower()
        if "abbreviation" in err:
            raise HTTPException(status_code=400, detail=f"Abbreviation '{data.abbreviation}' already exists.")
        raise HTTPException(status_code=400, detail="UOM already exists.")

@router.put("/uom/{uom_id}")
async def update_uom(
    uom_id: int,
    data: UOMSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    try:
        r = await db.execute(
            text("SELECT * FROM sp_save_uom(:id, :name, :abbreviation, :tenant_id)"),
            {"id": uom_id, "name": data.name, "abbreviation": data.abbreviation.upper(), "tenant_id": tid}
        )
        await db.commit()
        return dict(r.mappings().first())
    except IntegrityError as e:
        await db.rollback()
        err = str(e.orig).lower()
        if "abbreviation" in err:
            raise HTTPException(status_code=400, detail=f"Abbreviation '{data.abbreviation}' already exists.")
        raise HTTPException(status_code=400, detail="Update failed — duplicate value.")

@router.delete("/uom/{uom_id}")
async def delete_uom(
    uom_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    # Tenant admin can only delete their own UOMs
    if tid is not None:
        check = await db.execute(
            text("SELECT tenant_id FROM uom_masters WHERE id = :id"),
            {"id": uom_id}
        )
        row = check.first()
        if row and row[0] != tid:
            raise HTTPException(status_code=403, detail="Cannot delete global/other tenant UOM")
    await db.execute(text("CALL sp_delete_uom(:id)"), {"id": uom_id})
    await db.commit()
    return {"message": "UOM removed"}

# ─── Category ────────────────────────────────────────────────

class CategorySchema(BaseModel):
    name: str
    parent_id: Optional[int] = None

@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    tid = _tenant_id(current_user)
    bt_id = current_user.get("business_type_id")
    r = await db.execute(
        text("SELECT * FROM sp_list_categories(:tenant_id, :business_type_id)"),
        {"tenant_id": tid, "business_type_id": bt_id}
    )
    return [dict(row) for row in r.mappings().all()]

@router.post("/categories")
async def save_category(
    data: CategorySchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    bt_id = current_user.get("business_type_id")
    try:
        r = await db.execute(
            text("SELECT * FROM sp_save_category(:id, :name, :parent_id, :tenant_id, :bt_id)"),
            {"id": 0, "name": data.name, "parent_id": data.parent_id,
             "tenant_id": tid, "bt_id": bt_id}
        )
        await db.commit()
        return dict(r.mappings().first())
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Category '{data.name}' might already exist.")

@router.put("/categories/{cat_id}")
async def update_category(
    cat_id: int,
    data: CategorySchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    bt_id = current_user.get("business_type_id")
    try:
        r = await db.execute(
            text("SELECT * FROM sp_save_category(:id, :name, :parent_id, :tenant_id, :bt_id)"),
            {"id": cat_id, "name": data.name, "parent_id": data.parent_id,
             "tenant_id": tid, "bt_id": bt_id}
        )
        await db.commit()
        return dict(r.mappings().first())
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Update failed — duplicate value.")

@router.delete("/categories/{cat_id}")
async def delete_category(
    cat_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    await db.execute(text("CALL sp_delete_category(:id)"), {"id": cat_id})
    await db.commit()
    return {"message": "Category removed"}

# ─── HSN ─────────────────────────────────────────────────────

class HSNSchema(BaseModel):
    hsn_code: str
    description: str
    cgst_rate: float = 0
    sgst_rate: float = 0
    igst_rate: float = 0
    cess_rate: float = 0

@router.get("/hsn")
async def list_hsn(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    tid = _tenant_id(current_user)
    r = await db.execute(
        text("SELECT * FROM sp_list_hsn(:tenant_id)"),
        {"tenant_id": tid}
    )
    return [dict(row) for row in r.mappings().all()]

@router.post("/hsn")
async def save_hsn(
    data: HSNSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    try:
        r = await db.execute(
            text("SELECT * FROM sp_save_hsn(:id,:code,:desc,:cgst,:sgst,:igst,:cess,:tenant_id)"),
            {"id": 0, "code": data.hsn_code, "desc": data.description,
             "cgst": data.cgst_rate, "sgst": data.sgst_rate,
             "igst": data.igst_rate, "cess": data.cess_rate, "tenant_id": tid}
        )
        await db.commit()
        return dict(r.mappings().first())
    except IntegrityError as e:
        await db.rollback()
        err = str(e.orig).lower()
        if "hsn_code" in err:
            raise HTTPException(status_code=400, detail=f"HSN Code '{data.hsn_code}' already exists.")
        raise HTTPException(status_code=400, detail="HSN already exists.")

@router.put("/hsn/{hsn_id}")
async def update_hsn(
    hsn_id: int,
    data: HSNSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    try:
        r = await db.execute(
            text("SELECT * FROM sp_save_hsn(:id,:code,:desc,:cgst,:sgst,:igst,:cess,:tenant_id)"),
            {"id": hsn_id, "code": data.hsn_code, "desc": data.description,
             "cgst": data.cgst_rate, "sgst": data.sgst_rate,
             "igst": data.igst_rate, "cess": data.cess_rate, "tenant_id": tid}
        )
        await db.commit()
        return dict(r.mappings().first())
    except IntegrityError as e:
        await db.rollback()
        err = str(e.orig).lower()
        if "hsn_code" in err:
            raise HTTPException(status_code=400, detail=f"HSN Code '{data.hsn_code}' already exists.")
        raise HTTPException(status_code=400, detail="Update failed — duplicate value.")

@router.delete("/hsn/{hsn_id}")
async def delete_hsn(
    hsn_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    _check_access(current_user)
    tid = _tenant_id(current_user)
    if tid is not None:
        # Ensure tenant can only delete their own HSNs
        check = await db.execute(
            text("SELECT tenant_id FROM hsn_masters WHERE id = :id"), {"id": hsn_id}
        )
        row = check.first()
        if row and row[0] != tid:
            raise HTTPException(status_code=403, detail="Cannot delete another tenant's HSN")
    await db.execute(text("CALL sp_delete_hsn(:id)"), {"id": hsn_id})
    await db.commit()
    return {"message": "HSN removed"}

