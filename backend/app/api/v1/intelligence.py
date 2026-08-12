"""Document Intelligence & AI Tutor API.

Endpoints:
    POST /api/v1/intelligence/analyze/{document_id}  — Run AI analysis
    GET  /api/v1/intelligence/result/{document_id}   — Get analysis results
    POST /api/v1/intelligence/chat                    — AI tutor chat (SSE stream)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.intelligence_service import IntelligenceService
from app.services.tutor_service import TutorService

logger = logging.getLogger(__name__)


# ── Request schemas ──────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message", min_length=1, max_length=4000)
    history: list[dict] | None = Field(
        default=None,
        description="Previous conversation turns: [{\"role\":\"user\",\"content\":\"...\"}, ...]",
    )
    api_key: str | None = Field(default=None, description="Optional Anthropic API key")


class ChatResponse(BaseModel):
    reply: str
    mode: str = "llm"  # "llm" or "knowledge"

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


def get_intelligence_service(db: AsyncSession = Depends(get_db)) -> IntelligenceService:
    return IntelligenceService(db)


def get_tutor_service(db: AsyncSession = Depends(get_db)) -> TutorService:
    return TutorService(db)


# ── Analyze ──────────────────────────────────────────────────

@router.post("/analyze/{document_id}")
async def analyze_document(
    document_id: int,
    api_key: str | None = Query(default=None, description="Anthropic API Key（可选，留空则使用 .env 配置）"),
    service: IntelligenceService = Depends(get_intelligence_service),
):
    """Run AI analysis on a parsed document.

    Prerequisites:
    1. Document must be uploaded (POST /documents/upload)
    2. Document must be parsed (POST /documents/{id}/parse)

    API Key can be provided via:
    - Environment variable: ANTHROPIC_API_KEY in backend/.env
    - Query parameter: ?api_key=sk-ant-...

    The LLM will extract routes, knowledge points, and study tasks.
    Results are saved and retrievable via GET /intelligence/result/{document_id}.
    """
    try:
        result = await service.analyze(document_id, api_key=api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Analysis failed for document %d", document_id)
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")

    analysis = result["analysis"]
    return {
        "document_id": document_id,
        "status": "completed",
        "summary": analysis.summary,
        "routes_found": len(analysis.routes),
        "knowledge_points_found": len(analysis.knowledge_points),
        "study_tasks_found": len(analysis.study_tasks),
        "routes": [r.model_dump() for r in analysis.routes],
        "knowledge_points": [k.model_dump() for k in analysis.knowledge_points],
        "study_tasks": [t.model_dump() for t in analysis.study_tasks],
    }


# ── Get result ───────────────────────────────────────────────

@router.get("/result/{document_id}")
async def get_analysis_result(
    document_id: int,
    service: IntelligenceService = Depends(get_intelligence_service),
):
    """Get the stored AI analysis result for a document.

    Returns the structured JSON extracted by the LLM,
    plus metadata about the analysis run.
    """
    from app.models.document import AnalysisDocument

    db = service.db
    doc = await db.get(AnalysisDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not doc.parsed_content:
        raise HTTPException(status_code=404, detail="文档尚未解析")
    if doc.status not in ("completed", "analyzing"):
        raise HTTPException(
            status_code=400,
            detail=f"文档状态为 '{doc.status}'，请先运行 AI 分析",
        )

    analysis_data = doc.parsed_content.get("analysis") if doc.parsed_content else None
    if not analysis_data:
        raise HTTPException(status_code=404, detail="未找到分析结果，请先 POST /analyze")

    # Parse the raw JSON back into structured output
    import json
    raw = analysis_data.get("raw_json", "{}")

    return {
        "document_id": document_id,
        "status": doc.status,
        "summary": analysis_data.get("summary", ""),
        "route_count": analysis_data.get("route_count", 0),
        "knowledge_point_count": analysis_data.get("knowledge_point_count", 0),
        "study_task_count": analysis_data.get("study_task_count", 0),
        "analyzed_at": analysis_data.get("analyzed_at"),
        "raw_json": raw,
    }


# ── AI Tutor Chat (SSE streaming) ───────────────────────────

@router.post("/chat")
async def tutor_chat(
    req: ChatRequest,
    service: TutorService = Depends(get_tutor_service),
):
    """AI tutor chat with RAG + streaming.

    Send a message and optional conversation history, receive
    a Server-Sent Events stream with the AI tutor's response.

    Stream format:
        data: {"content": "text chunk", "type": "llm"}
        data: {"type": "meta", "mode": "knowledge"}
        data: {"error": "message", "type": "error"}
        data: [DONE]

    Falls back to knowledge search results if no Anthropic API key
    is configured.
    """
    return StreamingResponse(
        service.chat_stream(
            message=req.message,
            history=req.history,
            api_key=req.api_key,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
