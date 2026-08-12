"""Generic file upload API.

Endpoints:
    POST /api/v1/upload   — Upload an image file
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings

router = APIRouter(prefix="/upload", tags=["Upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("")
async def upload_image(
    file: UploadFile = File(..., description="Image file (jpg, png, webp, max 10MB)"),
):
    """Upload an image for use anywhere in GeoMate.

    Returns the public URL that can be used in route thumbnail_image,
    key_points[].image_url, field_note.photo_url, or knowledge documents.
    """
    # Validate extension
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format: {ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validate size
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")

    # Save to uploads directory
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}{ext}"
    file_path = upload_dir / safe_name

    file_path.write_bytes(content)

    url = f"/uploads/{safe_name}"

    return {
        "file_id": file_id,
        "filename": safe_name,
        "url": url,
        "size_bytes": len(content),
        "message": "Image uploaded successfully",
    }
