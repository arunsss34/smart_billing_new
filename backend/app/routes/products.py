from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/products", tags=["Products"])

class ProductCreate(BaseModel):
    name: str
    category: str
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    price: float  # Selling Price
    purchase_price: Optional[float] = 0
    mrp: Optional[float] = 0
    discount: Optional[float] = 0
    discount_type: Optional[str] = 'percent'
    tax_percent: Optional[float] = 0
    stock_qty: float
    min_stock: Optional[float] = 0
    reorder_level: Optional[float] = 0
    unit: str
    barcode: Optional[str] = None
    sku: Optional[str] = None
    hsn_code: Optional[str] = None
    batch_number: Optional[str] = None
    mfg_date: Optional[str] = None
    expiry_date: Optional[str] = None
    variants: Optional[dict] = {}
    additional_attributes: Optional[dict] = {}
    # Legacy / specific attributes
    size: Optional[str] = None      
    color: Optional[str] = None     
    imei: Optional[str] = None      

class ProductUpdate(ProductCreate):
    pass

@router.get("/")
async def list_products(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_list_products(:tenant_id)"),
        {"tenant_id": current_user["tenant_id"]}
    )
    return result.mappings().all()

@router.post("/")
async def create_product(
    product: ProductCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = product.model_dump()
    data["tenant_id"] = current_user["tenant_id"]
    import json
    data["variants"] = json.dumps(data["variants"] or {})
    data["additional_attributes"] = json.dumps(data["additional_attributes"] or {})
    
    result = await db.execute(
        text("""SELECT * FROM sp_create_product(
            :tenant_id, :name, :category, :subcategory, :brand, :price, :purchase_price, :mrp, :discount, :discount_type, :tax_percent, :stock_qty, :min_stock, :reorder_level, :unit,
            :barcode, :sku, :hsn_code, :batch_number, CAST(:mfg_date AS DATE), CAST(:expiry_date AS DATE), CAST(:variants AS JSONB), CAST(:additional_attributes AS JSONB), :size, :color, :imei
        )"""),
        data
    )
    await db.commit()
    return result.mappings().first()

@router.put("/{product_id}")
async def update_product(
    product_id: int,
    product: ProductUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = product.model_dump()
    data["tenant_id"] = current_user["tenant_id"]
    data["product_id"] = product_id
    import json
    data["variants"] = json.dumps(data["variants"] or {})
    data["additional_attributes"] = json.dumps(data["additional_attributes"] or {})
    
    result = await db.execute(
        text("""SELECT * FROM sp_update_product(
            :product_id, :tenant_id, :name, :category, :subcategory, :brand, :price, :purchase_price, :mrp, :discount, :discount_type, :tax_percent, :stock_qty, :min_stock, :reorder_level, :unit,
            :barcode, :sku, :hsn_code, :batch_number, CAST(:mfg_date AS DATE), CAST(:expiry_date AS DATE), CAST(:variants AS JSONB), CAST(:additional_attributes AS JSONB), :size, :color, :imei
        )"""),
        data
    )
    await db.commit()
    return result.mappings().first()

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        text("CALL sp_delete_product(:product_id, :tenant_id)"),
        {"product_id": product_id, "tenant_id": current_user["tenant_id"]}
    )
    await db.commit()
    return {"message": "Product deleted"}
