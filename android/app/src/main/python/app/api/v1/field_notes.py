"""Field Note API endpoints — digital geology field notebook.

Endpoints:
    GET    /api/v1/notes              — List field notes (with filters)
    GET    /api/v1/notes/geojson      — GeoJSON for map display
    GET    /api/v1/notes/{id}         — Get a single note
    POST   /api/v1/notes              — Create a new observation point
    PUT    /api/v1/notes/{id}         — Update a note
    DELETE /api/v1/notes/{id}         — Delete a note
    POST   /api/v1/notes/seed         — Seed demo data
    POST   /api/v1/notes/upload-photo — Upload a photo for field notes
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.field_note import (
    FieldNoteCreate,
    FieldNoteGeoJSONCollection,
    FieldNoteListOut,
    FieldNoteOut,
    FieldNoteUpdate,
    PhotoUploadResponse,
)
from app.services.field_note_service import FieldNoteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["Field Notes"])


def get_note_service(db: AsyncSession = Depends(get_db)) -> FieldNoteService:
    return FieldNoteService(db)


# ── List ─────────────────────────────────────────────────────

@router.get("", response_model=FieldNoteListOut)
async def list_notes(
    user_id: int | None = Query(default=None, gt=0, description="按用户筛选"),
    route_id: int | None = Query(default=None, gt=0, description="按路线筛选"),
    rock_type: str | None = Query(default=None, description="按岩石类型筛选"),
    service: FieldNoteService = Depends(get_note_service),
):
    """List field notes with optional filters, newest first.

    Examples:
    - GET /notes — all notes
    - GET /notes?user_id=1&route_id=1 — Route 1 notes for user 1
    - GET /notes?rock_type=花岗岩 — all granite observations
    """
    notes = await service.list_notes(
        user_id=user_id, route_id=route_id, rock_type=rock_type,
    )
    return FieldNoteListOut(
        total=len(notes),
        items=[FieldNoteOut.from_orm(n) for n in notes],
    )


# ── GeoJSON (map layer) ─────────────────────────────────────

@router.get("/geojson")
async def get_notes_geojson(
    user_id: int | None = Query(default=None, gt=0),
    route_id: int | None = Query(default=None, gt=0),
    service: FieldNoteService = Depends(get_note_service),
):
    """Return field notes as GeoJSON FeatureCollection.

    Only includes points with GPS coordinates.
    Use this endpoint to display observation points on a map.
    """
    features = await service.list_geojson(user_id=user_id, route_id=route_id)
    return {"type": "FeatureCollection", "features": features}


# ── Detail ───────────────────────────────────────────────────

@router.get("/{note_id}", response_model=FieldNoteOut)
async def get_note(
    note_id: int,
    service: FieldNoteService = Depends(get_note_service),
):
    """Get a single field note by ID.

    Returns full geological description, attitude data,
    GPS coordinates, specimen number, and photo URL.
    """
    note = await service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="记录不存在")
    return FieldNoteOut.from_orm(note)


# ── Create ───────────────────────────────────────────────────

@router.post("", response_model=FieldNoteOut, status_code=201)
async def create_note(
    data: FieldNoteCreate,
    request: Request,
    service: FieldNoteService = Depends(get_note_service),
):
    """Create a new geological observation point record.

    Supports X-Idempotency-Key header for offline sync deduplication.
    If a note with the same idempotency key already exists,
    returns 200 with the existing note instead of creating a duplicate.
    """
    idempotency_key = request.headers.get("X-Idempotency-Key")

    # Check for duplicate (offline sync retry)
    if idempotency_key:
        existing = await service.find_by_idempotency_key(idempotency_key)
        if existing:
            return FieldNoteOut.from_orm(existing)

    note = await service.create_note(data, idempotency_key=idempotency_key)
    return FieldNoteOut.from_orm(note)


# ── Update ───────────────────────────────────────────────────

@router.put("/{note_id}", response_model=FieldNoteOut)
async def update_note(
    note_id: int,
    data: FieldNoteUpdate,
    service: FieldNoteService = Depends(get_note_service),
):
    """Update a field note. Only provided fields are changed."""
    note = await service.update_note(note_id, data)
    if not note:
        raise HTTPException(status_code=404, detail="记录不存在")
    return FieldNoteOut.from_orm(note)


# ── Delete ───────────────────────────────────────────────────

@router.delete("/{note_id}")
async def delete_note(
    note_id: int,
    service: FieldNoteService = Depends(get_note_service),
):
    """Delete a field note record."""
    deleted = await service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"message": "记录已删除", "note_id": note_id}


# ── Seed ─────────────────────────────────────────────────────

@router.post("/seed")
async def seed_notes(
    user_id: int = Query(..., gt=0, description="为指定用户创建演示数据"),
    force: bool = Query(default=False, description="强制重新生成"),
    service: FieldNoteService = Depends(get_note_service),
):
    """Create demo field notes for user 1 (Route 1: 占甲埠村).

    Creates 3 realistic geological observation point records
    with GPS coordinates, attitude measurements, and specimen numbers.
    """
    result = await service.seed_notes(user_id=user_id, force=force)
    if result["created"] > 0:
        return {
            "message": f"成功创建 {result['created']} 条演示野外记录",
            "created": result["created"],
            "user_id": user_id,
        }
    else:
        return {
            "message": f"该用户已有 {result['skipped']} 条记录，跳过。使用 force=true 强制重新生成",
            "skipped": result["skipped"],
        }


# ── Photo Upload ─────────────────────────────────────────────

@router.post("/upload-photo", response_model=PhotoUploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    note_id: int | None = Query(default=None, description="关联的野外记录 ID（可选）"),
):
    """Upload a photo for a field note or general use.

    Supported formats: jpg, jpeg, png, webp.
    Max size: 10MB.
    Returns the URL path that can be saved to field_notes.photo_url or photos[].
    """
    # Validate file type
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {ext}。支持: {', '.join(allowed)}",
        )

    # Validate size (10MB)
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > 10:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    # Save
    photo_dir = Path(settings.UPLOAD_DIR) / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)

    photo_id = uuid.uuid4().hex[:12]
    safe_name = f"{photo_id}{ext}"
    file_path = photo_dir / safe_name

    with open(file_path, "wb") as f:
        f.write(content)

    url = f"/uploads/photos/{safe_name}"

    logger.info("Photo uploaded: %s (%.1f MB) -> %s", file.filename, size_mb, safe_name)

    # Optionally link to a note
    if note_id:
        # Can be extended to auto-append to the note's photos array
        pass

    return PhotoUploadResponse(
        photo_id=photo_id,
        filename=file.filename,
        url=url,
        size_bytes=len(content),
        note_id=note_id,
        message="上传成功",
    )
