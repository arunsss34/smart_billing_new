from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # JWT 'sub' is always stored as string — cast to int for SP calls
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id: int = int(sub)
        tenant_id = payload.get("tenant_id")   # None for superadmin
        role_id: int = int(payload.get("role_id", 0))
        business_type_id = payload.get("business_type_id")  # None for superadmin
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role_id": role_id,
        "business_type_id": business_type_id,
    }
