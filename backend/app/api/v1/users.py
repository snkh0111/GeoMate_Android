"""User API — minimal registration / login / profile for development.

Endpoints:
    POST /api/v1/users/register — Register a new account
    POST /api/v1/users/login    — Log in with username + password
    GET  /api/v1/users/me       — Get current user (dev: first user)
"""

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


class LoginRequest(BaseModel):
    """Username + password login."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash — matches register() implementation."""
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Register a new GeoMate account."""
    # Check duplicate username
    existing = db.scalar(select(User).where(User.username == data.username))
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # Check duplicate email if provided
    if data.email:
        existing_email = db.scalar(select(User).where(User.email == data.email))
        if existing_email:
            raise HTTPException(status_code=409, detail="邮箱已被使用")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=_hash_password(data.password),
        display_name=data.display_name or data.username,
        class_name=data.class_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered user: %s (id=%d)", user.username, user.id)
    return UserOut.from_orm(user)


@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Log in with username + password."""
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.password_hash != _hash_password(data.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    logger.info("User logged in: %s (id=%d)", user.username, user.id)
    return UserOut.from_orm(user)


@router.get("/me", response_model=UserOut)
def get_me(
    user_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Get current user profile. Dev mode: pass ?user_id=N or defaults to first user."""
    if user_id:
        user = db.get(User, user_id)
    else:
        user = (db.execute(select(User).limit(1))).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在，请先注册")
    return UserOut.from_orm(user)
