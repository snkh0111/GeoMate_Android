"""Pydantic schemas for Route API."""

from datetime import datetime

from pydantic import BaseModel, Field, validator


# ── KeyPoint schema (supports both string and object) ──────────

class KeyPointOut(BaseModel):
    """A key observation point, always output as object."""
    text: str = Field(..., description="观察点描述")
    image_url: str | None = Field(default=None, description="观察点配图路径")


class KeyPointInput(BaseModel):
    """Input format: string or object with optional image."""
    text: str = Field(..., min_length=1, max_length=2000)
    image_url: str | None = Field(default=None, max_length=500)


def normalize_key_points(raw: list | None) -> list[KeyPointOut] | None:
    """Normalize key_points to always be list[KeyPointOut].

    Accepts both legacy string format and new object format.
    """
    if raw is None:
        return None
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(KeyPointOut(text=item, image_url=None))
        elif isinstance(item, dict):
            result.append(KeyPointOut(
                text=item.get("text", ""),
                image_url=item.get("image_url"),
            ))
        else:
            result.append(KeyPointOut(text=str(item), image_url=None))
    return result


# ── Helper: accept string or KeyPointInput in lists ────────────

KeyPointList = list[str | KeyPointInput | dict] | None


# ── Request schemas ──────────────────────────────────────────

class RouteCreate(BaseModel):
    """Create a new route."""
    name: str = Field(..., min_length=1, max_length=200)
    location: str = Field(..., min_length=1, max_length=200)
    geological_type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    difficulty: str = Field(default="easy", regex="^(easy|medium|hard)$")
    learning_objectives: list[str] | None = None
    key_points: list[str | KeyPointInput] | None = None
    precautions: list[str] | None = None
    required_tools: list[str] | None = None
    order_index: int | None = Field(default=None, ge=1, le=20)
    duration_hours: float | None = Field(default=None, ge=0)
    thumbnail_image: str | None = Field(default=None, max_length=500)


class RouteUpdate(BaseModel):
    """Update an existing route. All fields optional."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    geological_type: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1)
    difficulty: str | None = Field(default=None, regex="^(easy|medium|hard)$")
    learning_objectives: list[str] | None = None
    key_points: list[str | KeyPointInput] | None = None
    precautions: list[str] | None = None
    required_tools: list[str] | None = None
    order_index: int | None = Field(default=None, ge=1, le=20)
    duration_hours: float | None = Field(default=None, ge=0)
    thumbnail_image: str | None = Field(default=None, max_length=500)


# ── Response schemas ─────────────────────────────────────────

class RouteOut(BaseModel):
    """Route returned in API responses. key_points always normalized to objects."""
    id: int
    name: str
    location: str
    geological_type: str
    description: str
    difficulty: str
    learning_objectives: list[str] | None = None
    key_points: list[KeyPointOut] | None = None
    precautions: list[str] | None = None
    required_tools: list[str] | None = None
    order_index: int | None = None
    duration_hours: float | None = None
    thumbnail_image: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

    @validator("key_points", pre=True)
    @classmethod
    def _normalize_key_points(cls, v):
        return normalize_key_points(v)


class RouteListOut(BaseModel):
    """List of routes."""
    total: int
    items: list[RouteOut]


class RouteSummary(BaseModel):
    """Lightweight route summary for list views."""
    id: int
    name: str
    location: str
    geological_type: str
    difficulty: str
    order_index: int | None = None
    duration_hours: float | None = None

    class Config:
        orm_mode = True
