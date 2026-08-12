"""Pydantic schemas for User API — minimal for development."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Register a new user."""
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    email: str | None = None
    display_name: str | None = None
    class_name: str | None = None


class UserOut(BaseModel):
    """Public user profile (never includes password hash)."""
    id: int
    username: str
    email: str | None = None
    display_name: str | None = None
    class_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
