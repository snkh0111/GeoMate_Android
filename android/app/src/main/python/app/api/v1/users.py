"""User API — minimal registration / profile for development.

Endpoints:
    POST /api/v1/users/register — Register a new account
    GET  /api/v1/users/me       — Get current user (dev: first user)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new GeoMate account."""
    # Check duplicate username
    existing = await db.scalar(select(User).where(User.username == data.username))
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # Simple hash — production should use passlib
    import hashlib
    password_hash = hashlib.sha256(data.password.encode()).hexdigest()

    user = User(
        username=data.username,
        email=data.email,
        password_hash=password_hash,
        display_name=data.display_name or data.username,
        class_name=data.class_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Registered user: %s (id=%d)", user.username, user.id)
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile. Dev mode: pass ?user_id=N or defaults to first user."""
    if user_id:
        user = await db.get(User, user_id)
    else:
        user = (await db.execute(select(User).limit(1))).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在，请先注册")
    return UserOut.model_validate(user)
