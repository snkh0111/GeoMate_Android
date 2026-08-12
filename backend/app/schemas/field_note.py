"""Pydantic schemas for Field Note API."""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────

class FieldNoteCreate(BaseModel):
    """Create a new geological observation point record."""
    user_id: int = Field(..., gt=0)
    route_id: int | None = Field(default=None, gt=0)
    point_number: str | None = Field(default=None, max_length=20, description="地质点编号")
    location: str | None = Field(default=None, max_length=500, description="点位描述")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    rock_type: str | None = Field(default=None, max_length=200, description="岩石类型")
    description: str | None = Field(default=None, description="地质描述")
    strike: float | None = Field(default=None, ge=0, le=360, description="走向")
    dip_direction: float | None = Field(default=None, ge=0, le=360, description="倾向")
    dip_angle: float | None = Field(default=None, ge=0, le=90, description="倾角")
    sample_number: str | None = Field(default=None, max_length=50, description="标本编号")
    photo_url: str | None = Field(default=None, max_length=1000, description="照片路径")
    weather: str | None = Field(default=None, max_length=50)
    order_index: int = Field(default=0, ge=0)
    recorded_at: datetime | None = Field(default=None, description="野外记录时间")


class FieldNoteUpdate(BaseModel):
    """Update a field note. All fields optional."""
    route_id: int | None = Field(default=None, gt=0)
    point_number: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    rock_type: str | None = Field(default=None, max_length=200)
    description: str | None = None
    strike: float | None = Field(default=None, ge=0, le=360)
    dip_direction: float | None = Field(default=None, ge=0, le=360)
    dip_angle: float | None = Field(default=None, ge=0, le=90)
    sample_number: str | None = Field(default=None, max_length=50)
    photo_url: str | None = Field(default=None, max_length=1000)
    weather: str | None = Field(default=None, max_length=50)
    order_index: int | None = Field(default=None, ge=0)
    recorded_at: datetime | None = None


# ── Response schemas ─────────────────────────────────────────

class FieldNoteOut(BaseModel):
    """Field note in API responses."""
    id: int
    user_id: int
    route_id: int | None = None
    point_number: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rock_type: str | None = None
    description: str | None = None
    strike: float | None = None
    dip_direction: float | None = None
    dip_angle: float | None = None
    attitude: str = ""                     # computed: "280°∠20°"
    coordinates: dict | None = None        # computed: {lat, lng}
    sample_number: str | None = None
    photo_url: str | None = None
    weather: str | None = None
    order_index: int
    recorded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FieldNoteListOut(BaseModel):
    """List of field notes."""
    total: int
    items: list[FieldNoteOut]


class FieldNoteGeoJSON(BaseModel):
    """A single feature in GeoJSON format (for map display)."""
    type: str = "Feature"
    geometry: dict
    properties: dict


class FieldNoteGeoJSONCollection(BaseModel):
    """GeoJSON FeatureCollection for map visualization."""
    type: str = "FeatureCollection"
    features: list[FieldNoteGeoJSON]


class PhotoUploadResponse(BaseModel):
    """Response after a photo upload."""
    photo_id: str
    filename: str
    url: str
    size_bytes: int
    note_id: int | None = None
    message: str
