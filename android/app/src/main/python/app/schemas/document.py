"""Pydantic schemas for Document upload / parse / list API."""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Upload / List ─────────────────────────────────────────────

class DocumentOut(BaseModel):
    """Document info returned in API responses."""
    id: int
    user_id: int
    filename: str
    file_type: str
    file_size: int | None = None
    status: str
    section_count: int = 0
    is_parsed: bool = False
    error_message: str | None = None
    parsed_at: datetime | None = None
    created_at: datetime

    class Config:
        orm_mode = True


class DocumentListOut(BaseModel):
    """List of uploaded documents."""
    total: int
    items: list[DocumentOut]


class DocumentUploadResponse(BaseModel):
    """Response after a successful upload."""
    document_id: int
    filename: str
    file_size: int | None = None
    status: str
    message: str


# ── Parse ─────────────────────────────────────────────────────

class SectionOut(BaseModel):
    """A single parsed section."""
    index: int
    title: str | None
    content_preview: str = ""     # first 200 chars
    content_length: int = 0
    page_start: int
    page_end: int
    level: int


class ParseResultOut(BaseModel):
    """Response after parsing a document."""
    document_id: int
    filename: str
    status: str
    total_pages: int
    total_chars: int
    section_count: int
    sections: list[SectionOut]


class SectionDetailOut(BaseModel):
    """Full content of a single section."""
    index: int
    title: str | None
    content: str
    page_start: int
    page_end: int
    level: int
    parent_index: int | None
