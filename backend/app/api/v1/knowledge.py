"""Knowledge base API endpoints — with geology metadata support.

Endpoints:
    POST   /api/v1/knowledge/upload       — Upload & ingest a PDF
    POST   /api/v1/knowledge/search       — Semantic search (auto intent detection)
    GET    /api/v1/knowledge/documents    — List all documents
    GET    /api/v1/knowledge/documents/{id} — Get document detail
    DELETE /api/v1/knowledge/documents/{id} — Delete a document
    GET    /api/v1/knowledge/stats        — Knowledge base stats
    GET    /api/v1/knowledge/filters      — Available filter values (for UI)
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.knowledge import (
    AvailableFilters,
    DocumentListOut,
    DocumentOut,
    KnowledgeStats,
    SearchRequest,
    SearchResponse,
    UploadResponse,
)
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def get_knowledge_service(db: AsyncSession = Depends(get_db)) -> KnowledgeService:
    return KnowledgeService(db)


# ── Upload ────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_pdf(
    file: UploadFile = File(...),
    title: str | None = None,
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Upload a PDF and ingest into the geology knowledge base.

    The PDF is automatically:
    1. Text-extracted with PyMuPDF
    2. Geology-aware chunked (by routes, minerals, structures, etc.)
    3. Classified with metadata (category, location, rock_type, keywords)
    4. Embedded and stored in ChromaDB.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"文件超过大小限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    file_id = uuid.uuid4().hex[:12]
    safe_filename = f"{file_id}_{file.filename}"
    file_path = Path(settings.UPLOAD_DIR) / safe_filename

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("Saved upload: %s (%.1f MB)", safe_filename, size_mb)

    try:
        doc = await service.upload_and_ingest(
            file_path=str(file_path),
            filename=file.filename,
            title=title,
        )
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=f"知识库处理失败: {str(e)}")

    return UploadResponse(
        document_id=doc.id,
        title=doc.title,
        filename=doc.filename,
        status=doc.status,
        chunk_count=doc.chunk_count,
        categories_found={},  # Would need extra query to fill
        message=f"成功处理 {doc.chunk_count} 个文本块",
    )


# ── Search ────────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    req: SearchRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Semantic search with auto intent detection.

    Examples:
    - "马山路线需要看什么？" → auto-detects location=马山, category=路线
    - "花岗岩和玄武岩有什么区别？" → auto-detects rock_type=花岗岩, category=岩石
    - "石英的解理特征" → auto-detects mineral=石英, category=矿物
    - "一票否决有哪些？" → auto-detects category=考试重点
    """
    return await service.search(
        query=req.query,
        top_k=req.top_k,
        document_id=req.document_id,
        category=req.category,
        location=req.location,
        rock_type=req.rock_type,
        mineral=req.mineral,
        difficulty=req.difficulty,
        auto_filter=req.auto_filter,
    )


# ── Quick Search (GET, for convenience) ──────────────────────

@router.get("/search", response_model=SearchResponse)
async def quick_search(
    q: str = Query(..., min_length=1, description="搜索查询"),
    top_k: int = Query(default=5, ge=1, le=20),
    category: str | None = Query(default=None),
    location: str | None = Query(default=None),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Convenience GET endpoint for quick searches.

    Example: GET /api/v1/knowledge/search?q=马山路线&location=马山
    """
    return await service.search(
        query=q,
        top_k=top_k,
        category=category,
        location=location,
        auto_filter=True,
    )


# ── Document CRUD ─────────────────────────────────────────────

@router.get("/documents", response_model=DocumentListOut)
async def list_documents(
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """List all ingested documents, newest first."""
    docs = await service.list_documents()
    return DocumentListOut(
        total=len(docs),
        items=[DocumentOut.from_orm(d) for d in docs],
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: int,
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Get a single document's details."""
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.from_orm(doc)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Delete a document and all its knowledge chunks."""
    deleted = await service.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除", "document_id": document_id}


# ── Stats ─────────────────────────────────────────────────────

@router.get("/stats", response_model=KnowledgeStats)
async def get_stats(
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Get knowledge base statistics."""
    stats = await service.get_stats()
    return KnowledgeStats(
        document_count=stats["document_count"],
        chunk_count=stats["chunk_count_sqlite"],
        vector_store_chunks=stats["chunk_count_chroma"],
    )


# ── Filters ───────────────────────────────────────────────────

@router.get("/filters", response_model=AvailableFilters)
async def get_filters(
    service: KnowledgeService = Depends(get_knowledge_service),
):
    """Get available metadata filter values.

    Useful for building filter dropdowns in the UI.
    Returns distinct categories, locations, rock types, and minerals.
    """
    filters = service.get_available_filters()
    return AvailableFilters(
        categories=filters["categories"],
        locations=filters["locations"],
        rock_types=filters["rock_types"],
        minerals=filters["minerals"],
    )
