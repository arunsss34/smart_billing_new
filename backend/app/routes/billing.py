from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional, List, Any
import json

router = APIRouter(prefix="/billing", tags=["Billing"])

class InvoiceItem(BaseModel):
    product_id: int
    quantity: float
    unit_price: float
    discount: float = 0.0
    discount_type: str = 'percent'
    tax_percent: float = 0.0

class InvoiceCreate(BaseModel):
    customer_id: Optional[int] = None
    items: List[InvoiceItem]
    payment_method: str  # cash, upi, card, split
    paid_amount: float = 0.0
    invoice_status: str = 'Paid'  # Draft, Paid, Cancelled
    notes: Optional[str] = None
    metadata_fields: Optional[dict] = {}
    table_id: Optional[int] = None   # Restaurant
    kot_id: Optional[int] = None     # Restaurant KOT

@router.get("/invoices")
async def list_invoices(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_list_invoices(:tenant_id)"),
        {"tenant_id": current_user["tenant_id"]}
    )
    return result.mappings().all()

@router.get("/tables")
async def list_tables(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT id, table_number, capacity, is_occupied FROM restaurant_tables WHERE tenant_id = :tenant_id ORDER BY id"),
        {"tenant_id": current_user["tenant_id"]}
    )
    return result.mappings().all()

@router.post("/invoices")
async def create_invoice(
    invoice: InvoiceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    items_json = json.dumps([item.model_dump() for item in invoice.items])
    metadata_json = json.dumps(invoice.metadata_fields or {})
    result = await db.execute(
        text("""SELECT * FROM sp_create_invoice(
            :tenant_id, :user_id, :customer_id, CAST(:items_json AS JSONB),
            :payment_method, :notes, :paid_amount, :invoice_status, CAST(:metadata_json AS JSONB), :table_id, :kot_id
        )"""),
        {
            "tenant_id": current_user["tenant_id"],
            "user_id": current_user["user_id"],
            "customer_id": invoice.customer_id,
            "items_json": items_json,
            "payment_method": invoice.payment_method,
            "notes": invoice.notes,
            "paid_amount": invoice.paid_amount,
            "invoice_status": invoice.invoice_status,
            "metadata_json": metadata_json,
            "table_id": invoice.table_id,
            "kot_id": invoice.kot_id,
        }
    )
    await db.commit()
    return result.mappings().first()

@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_get_invoice(:invoice_id, :tenant_id)"),
        {"invoice_id": invoice_id, "tenant_id": current_user["tenant_id"]}
    )
    invoice = result.mappings().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.put("/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify invoice belongs to tenant
    result = await db.execute(
        text("SELECT * FROM invoices WHERE id = :invoice_id AND tenant_id = :tenant_id"),
        {"invoice_id": invoice_id, "tenant_id": current_user["tenant_id"]}
    )
    invoice = result.mappings().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    await db.execute(
        text("UPDATE invoices SET invoice_status = 'Paid', paid_amount = grand_total, balance = 0 WHERE id = :invoice_id"),
        {"invoice_id": invoice_id}
    )
    await db.commit()
    return {"message": "Invoice marked as paid"}
