from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/customers", tags=["Customers"])

class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None

@router.get("/")
async def list_customers(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_list_customers(:tenant_id)"),
        {"tenant_id": current_user["tenant_id"]}
    )
    return result.mappings().all()

@router.post("/")
async def create_customer(
    customer: CustomerCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = customer.model_dump()
    data["tenant_id"] = current_user["tenant_id"]
    result = await db.execute(
        text("SELECT * FROM sp_create_customer(:tenant_id, :name, :phone, :email, :address, :gstin)"),
        data
    )
    await db.commit()
    return result.mappings().first()

@router.put("/{customer_id}")
async def update_customer(
    customer_id: int,
    customer: CustomerCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = customer.model_dump()
    data["tenant_id"] = current_user["tenant_id"]
    data["customer_id"] = customer_id
    result = await db.execute(
        text("SELECT * FROM sp_update_customer(:customer_id, :tenant_id, :name, :phone, :email, :address, :gstin)"),
        data
    )
    await db.commit()
    return result.mappings().first()
