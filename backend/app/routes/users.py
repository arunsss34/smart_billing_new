from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext

router = APIRouter(prefix="/users", tags=["User Management"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: str = ""
    role_id: int = 3
    tenant_id: Optional[int] = None
    is_active: bool = True
    tenant_role_id: Optional[int] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None       # optional — only hash if provided
    is_active: Optional[bool] = None
    tenant_role_id: Optional[int] = None

def _check_admin(current_user: dict):
    if current_user["role_id"] not in [1, 2]:
        raise HTTPException(status_code=403, detail="Admin access required")

def _owns_user(current_user: dict, user_tenant_id):
    """Tenant admin can only manage users in their own tenant."""
    if current_user["role_id"] == 2 and user_tenant_id != current_user["tenant_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

# ─── List ────────────────────────────────────────────────────
@router.get("/")
async def list_users(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        text("SELECT * FROM sp_list_users(:tenant_id, :role_id)"),
        {"tenant_id": current_user["tenant_id"], "role_id": current_user["role_id"]}
    )
    return result.mappings().all()

# ─── Create ──────────────────────────────────────────────────
@router.post("/")
async def create_user(
    user: UserCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    _check_admin(current_user)
    hashed_pw = pwd_context.hash(user.password)
    tenant_id = user.tenant_id
    if current_user["role_id"] == 2:
        tenant_id = current_user["tenant_id"]

    try:
        result = await db.execute(
            text("""
                SELECT * FROM sp_create_user(
                    :username, :password_hash, :full_name, :email,
                    :role_id, :tenant_id, :is_active, :tenant_role_id
                )
            """),
            {
                "username":       user.username,
                "password_hash":  hashed_pw,
                "full_name":      user.full_name,
                "email":          user.email,
                "role_id":        user.role_id,
                "tenant_id":      tenant_id,
                "is_active":      user.is_active,
                "tenant_role_id": user.tenant_role_id,
            }
        )
        await db.commit()
        return result.mappings().first()
    except IntegrityError as e:
        await db.rollback()
        err = str(e.orig).lower()
        if "username" in err:
            raise HTTPException(status_code=400, detail=f"Username '{user.username}' is already taken. Please choose a different one.")
        if "email" in err:
            raise HTTPException(status_code=400, detail=f"Email '{user.email}' is already registered.")
        raise HTTPException(status_code=400, detail="User creation failed — duplicate value detected.")

# ─── Edit ────────────────────────────────────────────────────
@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    _check_admin(current_user)

    # Verify user exists and belongs to correct tenant
    existing = await db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
    u = existing.mappings().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    _owns_user(current_user, u["tenant_id"])

    # Build dynamic update
    updates = {}
    if data.full_name is not None:  updates["full_name"]      = data.full_name
    if data.email is not None:      updates["email"]          = data.email
    if data.is_active is not None:  updates["is_active"]      = data.is_active
    if data.tenant_role_id is not None: updates["tenant_role_id"] = data.tenant_role_id
    if data.password:               updates["password_hash"]  = pwd_context.hash(data.password)

    if not updates:
        return dict(u)

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = user_id

    try:
        result = await db.execute(
            text(f"UPDATE users SET {set_clause} WHERE id = :id RETURNING *"),
            updates
        )
        await db.commit()
        return result.mappings().first()
    except IntegrityError as e:
        await db.rollback()
        if "email" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail=f"Email '{data.email}' is already registered.")
        raise HTTPException(status_code=400, detail="Update failed.")

# ─── Delete ──────────────────────────────────────────────────
@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    _check_admin(current_user)

    existing = await db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
    u = existing.mappings().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    _owns_user(current_user, u["tenant_id"])

    # Prevent self-deletion
    if u["id"] == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    await db.commit()
    return {"message": f"User '{u['username']}' deleted successfully."}

# ─── Toggle Active ───────────────────────────────────────────
@router.put("/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    _check_admin(current_user)
    result = await db.execute(
        text("SELECT * FROM sp_toggle_user_active(:user_id, :tenant_id)"),
        {"user_id": user_id, "tenant_id": current_user["tenant_id"]}
    )
    await db.commit()
    return result.mappings().first()
