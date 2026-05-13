from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/sales-summary")
async def sales_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    customer_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_report_sales_summary(:tenant_id, :start, :end, :cust)"),
        {"tenant_id": current_user["tenant_id"], "start": start_date, "end": end_date, "cust": customer_id}
    )
    return result.mappings().all()

@router.get("/daily-sales")
async def daily_sales(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    customer_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_report_daily_sales(:tenant_id, :start, :end, :cust)"),
        {"tenant_id": current_user["tenant_id"], "start": start_date, "end": end_date, "cust": customer_id}
    )
    return result.mappings().all()

@router.get("/top-products")
async def top_products(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    customer_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_report_top_products(:tenant_id, :start, :end, :cust)"),
        {"tenant_id": current_user["tenant_id"], "start": start_date, "end": end_date, "cust": customer_id}
    )
    return result.mappings().all()

@router.get("/payment-methods")
async def payment_method_report(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    customer_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_report_payment_methods(:tenant_id, :start, :end, :cust)"),
        {"tenant_id": current_user["tenant_id"], "start": start_date, "end": end_date, "cust": customer_id}
    )
    return result.mappings().all()
