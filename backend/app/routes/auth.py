from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from jose import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.database import get_db
from app.config import settings
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    tenant_id: Optional[int]
    business_type: Optional[str]       # e.g. "restaurant", "dress_shop"
    business_type_id: Optional[int]    # FK for category filtering

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_login(:username)"),
        {"username": form_data.username}
    )
    user = result.mappings().first()

    if not user or not pwd_context.verify(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Fetch tenant's business type (NULL for superadmin)
    business_type = None
    business_type_id = None
    if user["tenant_id"]:
        bt = await db.execute(
            text("""
                SELECT bt.name, bt.id
                FROM tenants t
                JOIN business_types bt ON bt.id = t.business_type_id
                WHERE t.id = :tid
            """),
            {"tid": user["tenant_id"]}
        )
        bt_row = bt.first()
        if bt_row:
            business_type = bt_row[0]
            business_type_id = bt_row[1]

    token_data = {
        "sub": str(user["id"]),
        "tenant_id": user["tenant_id"],
        "role_id": user["role_id"],
        "role": user["role_name"],
        "business_type_id": business_type_id,
    }
    token = create_access_token(token_data)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user["role_name"],
        tenant_id=user["tenant_id"],
        business_type=business_type,
        business_type_id=business_type_id,
    )

@router.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}
