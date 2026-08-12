"""Document API endpoints — upload, parse, view, and auto-generate.

Endpoints:
    POST   /api/v1/documents/upload              — Upload a PDF
    GET    /api/v1/documents                     — List uploaded documents
    GET    /api/v1/documents/{id}                — Get document detail
    DELETE /api/v1/documents/{id}                — Delete a document
    POST   /api/v1/documents/{id}/parse          — Parse PDF into sections
    GET    /api/v1/documents/{id}/content        — View parsed sections (summary)
    GET    /api/v1/documents/{id}/sections/{n}   — View a single section (full text)
    POST   /api/v1/documents/{id}/generate-routes — Auto-generate routes from AI analysis
    POST   /api/v1/documents/{id}/generate-plans  — Auto-generate study plans from AI analysis
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.document import (
    DocumentListOut,
    DocumentOut,
    DocumentUploadResponse,
    ParseResultOut,
    SectionDetailOut,
    SectionOut,
)
from app.services.document_parser import DocumentParser
from app.services.document_service import DocumentService
from app.services.intelligence_service import IntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_parser(db: AsyncSession = Depends(get_db)) -> DocumentParser:
    return DocumentParser(db)


# ── Upload ────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user_id: int = Query(..., gt=0, description="上传用户 ID"),
    service: DocumentService = Depends(get_document_service),
):
    """Upload a PDF. Parsing can be triggered afterwards."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"文件超过大小限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    try:
        doc = await service.upload(
            user_id=user_id, filename=file.filename, content=content,
        )
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    return DocumentUploadResponse(
        document_id=doc.id, filename=doc.filename,
        file_size=doc.file_size, status=doc.status,
        message="上传成功，文件已保存",
    )


# ── List ─────────────────────────────────────────────────────

@router.get("", response_model=DocumentListOut)
async def list_documents(
    user_id: int | None = Query(default=None, gt=0),
    service: DocumentService = Depends(get_document_service),
):
    """List uploaded documents, newest first."""
    docs = await service.list_documents(user_id=user_id)
    return DocumentListOut(
        total=len(docs),
        items=[DocumentOut.model_validate(d) for d in docs],
    )


# ── Detail ───────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: int,
    service: DocumentService = Depends(get_document_service),
):
    """Get a single document's details."""
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(doc)


# ── Delete ───────────────────────────────────────────────────

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    service: DocumentService = Depends(get_document_service),
):
    """Delete a document and its file from disk."""
    deleted = await service.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除", "document_id": document_id}


# ── Parse ────────────────────────────────────────────────────

@router.post("/{document_id}/parse", response_model=ParseResultOut)
async def parse_document(
    document_id: int,
    parser: DocumentParser = Depends(get_parser),
):
    """Parse a PDF into structured sections.

    Uses PyMuPDF for text extraction and heading-based heuristics
    to detect Chinese section headings. No LLM is used at this stage.

    The parsed result is saved to the document record and can be
    retrieved via GET /documents/{id}/content.
    """
    try:
        parsed = await parser.parse(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="PDF 文件丢失，请重新上传")
    except Exception as e:
        logger.exception("Parse failed for document %d", document_id)
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

    sections = [
        SectionOut(
            index=s.index, title=s.title,
            content_preview=s.content[:200],
            content_length=len(s.content),
            page_start=s.page_start, page_end=s.page_end, level=s.level,
        )
        for s in parsed.sections
    ]

    return ParseResultOut(
        document_id=document_id,
        filename=parsed.filename,
        status="parsed",
        total_pages=parsed.total_pages,
        total_chars=parsed.total_chars,
        section_count=len(parsed.sections),
        sections=sections,
    )


# ── View parsed content (summary) ────────────────────────────

@router.get("/{document_id}/content", response_model=ParseResultOut)
async def get_parsed_content(
    document_id: int,
    parser: DocumentParser = Depends(get_parser),
):
    """Get the parsed section structure of a document.

    Returns all section titles, page ranges, and content previews.
    Use GET /documents/{id}/sections/{n} for full section text.
    """
    parsed = await parser.get_parsed(document_id)
    if not parsed:
        raise HTTPException(status_code=404, detail="文档尚未解析，请先 POST /parse")

    sections = [
        SectionOut(
            index=s.index, title=s.title,
            content_preview=s.content[:200],
            content_length=len(s.content),
            page_start=s.page_start, page_end=s.page_end, level=s.level,
        )
        for s in parsed.sections
    ]

    return ParseResultOut(
        document_id=document_id,
        filename=parsed.filename,
        status="parsed",
        total_pages=parsed.total_pages,
        total_chars=parsed.total_chars,
        section_count=len(parsed.sections),
        sections=sections,
    )


# ── View single section (full text) ──────────────────────────

@router.get("/{document_id}/sections/{section_index}", response_model=SectionDetailOut)
async def get_section_detail(
    document_id: int,
    section_index: int,
    parser: DocumentParser = Depends(get_parser),
):
    """Get the full content of a single section."""
    parsed = await parser.get_parsed(document_id)
    if not parsed:
        raise HTTPException(status_code=404, detail="文档尚未解析")

    if section_index < 0 or section_index >= len(parsed.sections):
        raise HTTPException(
            status_code=404,
            detail=f"Section {section_index} 不存在（共 {len(parsed.sections)} 个章节）",
        )

    s = parsed.sections[section_index]
    return SectionDetailOut(
        index=s.index, title=s.title, content=s.content,
        page_start=s.page_start, page_end=s.page_end,
        level=s.level, parent_index=s.parent_index,
    )


# ── Auto-generate Routes ────────────────────────────────────

@router.post("/{document_id}/generate-routes")
async def generate_routes(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate FieldRoute records from AI analysis results.

    Prerequisites:
    1. Document uploaded (POST /upload)
    2. Document parsed (POST /{id}/parse)
    3. AI analysis completed (POST /intelligence/analyze/{id})

    Reads the AI-extracted routes and creates entries in the
    existing field_routes table. Duplicate route names are
    automatically skipped.
    """
    service = IntelligenceService(db)
    try:
        result = await service.generate_routes(document_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Route generation failed")
        raise HTTPException(status_code=500, detail=f"路线生成失败: {str(e)}")

    return result


# ── Auto-generate Study Plans ───────────────────────────────

@router.post("/{document_id}/generate-plans")
async def generate_plans(
    document_id: int,
    user_id: int = Query(..., gt=0, description="目标用户 ID"),
    start_date: str | None = Query(default=None, description="实习开始日期 (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """Generate StudyPlan records from AI analysis results.

    Prerequisites:
    1. Document uploaded, parsed, and analyzed by AI
    2. Routes should be generated first (for linking)

    Maps AI-extracted study tasks to the study_plans table,
    calculating dates based on date_offset and start_date.
    Tasks that reference a route name are automatically linked
    to the corresponding route_id.
    """
    from datetime import date as date_type

    start = date_type.fromisoformat(start_date) if start_date else None

    service = IntelligenceService(db)
    try:
        result = await service.generate_study_plans(
            document_id=document_id, user_id=user_id, start_date=start,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Plan generation failed")
        raise HTTPException(status_code=500, detail=f"学习计划生成失败: {str(e)}")

    return result
