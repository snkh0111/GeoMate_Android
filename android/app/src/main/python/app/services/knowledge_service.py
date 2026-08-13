"""Knowledge base service — business logic with geology metadata support."""

import logging
import os
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai.rag.retriever import QueryIntent, Retriever
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import SearchResponse, SearchResultItem
from app.utils.pdf import extract_pdf_text

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Handles the full lifecycle of knowledge documents with geology metadata."""

    def __init__(self, db: Session):
        self.db = db
        self.retriever = Retriever()

    # ── Upload / Ingest ───────────────────────────────────────

    def upload_and_ingest(
        self,
        file_path: str,
        filename: str,
        title: str | None = None,
    ) -> KnowledgeDocument:
        """Upload a PDF, extract text, chunk with geology classification, store in vector DB."""
        title = title or Path(filename).stem
        file_size = os.path.getsize(file_path)

        # 1. Create document record
        doc = KnowledgeDocument(
            title=title,
            filename=filename,
            file_path=file_path,
            file_type="pdf",
            status="processing",
            file_size=file_size,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        try:
            # 2. Extract text
            pdf_doc = extract_pdf_text(file_path)
            pages = [(p.page_number, p.text) for p in pdf_doc.pages]

            if not pages:
                raise ValueError("PDF 中没有可提取的文本内容")

            # 3. Ingest with geology-aware chunking + metadata extraction
            chunk_count = self.retriever.ingest_document(
                pages=pages,
                document_id=doc.id,
                document_title=title,
            )

            # 4. Update document
            doc.status = "ready"
            doc.chunk_count = chunk_count

            # 5. Persist chunk metadata to SQLite
            for i in range(chunk_count):
                chunk = KnowledgeChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content="",  # Actual content lives in ChromaDB
                )
                self.db.add(chunk)

            self.db.commit()
            self.db.refresh(doc)

            logger.info(
                "Document %d (%s) ingested: %d chunks from %d pages",
                doc.id, title, chunk_count, pdf_doc.total_pages,
            )
            return doc

        except Exception as e:
            logger.exception("Failed to ingest document %d", doc.id)
            doc.status = "error"
            doc.error_message = str(e)
            self.db.commit()
            self.db.refresh(doc)
            raise

    # ── Search ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: int | None = None,
        category: str | None = None,
        location: str | None = None,
        rock_type: str | None = None,
        mineral: str | None = None,
        difficulty: str | None = None,
        auto_filter: bool = True,
    ) -> SearchResponse:
        """Semantic search with geology metadata filtering.

        When auto_filter=True, the system automatically detects intent
        from the query (e.g. "马山路线" → location=马山, category=路线).
        """
        results = self.retriever.search(
            query=query,
            top_k=top_k,
            document_id=document_id,
            category=category,
            location=location,
            rock_type=rock_type,
            mineral=mineral,
            difficulty=difficulty,
            auto_filter=auto_filter,
        )

        intent = QueryIntent(query)

        items = [
            SearchResultItem(
                chunk_id=r.chunk_id,
                content=r.content,
                score=r.score,
                document_id=r.document_id,
                document_title=r.document_title,
                page_number=r.page_number,
                section_title=r.section_title,
                chunk_index=r.chunk_index,
                category=r.category,
                location=r.location,
                rock_type=r.rock_type,
                mineral=r.mineral,
                difficulty=r.difficulty,
                keywords=r.keywords or [],
                route_number=r.route_number,
            )
            for r in results
        ]

        return SearchResponse(
            query=query,
            detected_intent=intent.filter_description,
            results=items,
            total=len(items),
        )

    # ── CRUD ───────────────────────────────────────────────────

    def list_documents(self) -> list[KnowledgeDocument]:
        result = self.db.execute(
            select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    def get_document(self, document_id: int) -> KnowledgeDocument | None:
        return self.db.get(KnowledgeDocument, document_id)

    def delete_document(self, document_id: int) -> bool:
        doc = self.db.get(KnowledgeDocument, document_id)
        if not doc:
            return False

        # Resolve the source analysis document (uploaded PDF) that spawned this
        # knowledge document, so routes/study-plans generated from it are
        # cascade-deleted together with this document.
        from app.models.document import AnalysisDocument

        source_doc_id = getattr(doc, "source_document_id", None)
        source_doc = None
        if not source_doc_id:
            row = self.db.execute(
                select(AnalysisDocument.id).where(
                    AnalysisDocument.file_path == doc.file_path
                )
            ).first()
            if row:
                source_doc_id = row[0]
        if source_doc_id:
            source_doc = self.db.get(AnalysisDocument, source_doc_id)

        if source_doc:
            from app.models.route import FieldRoute
            from app.models.study_plan import StudyPlan
            from app.services.document_service import DocumentService

            # Collect route/plan IDs from every available source so legacy rows
            # (created before source_document_id tracking existed) are removed too:
            #   1. IDs persisted in parsed_content["generated"] during auto-generate
            #   2. source_document_id back-reference (rows created after tracking)
            #   3. name-based fallback (rows created before generated tracking)
            generated = (source_doc.parsed_content or {}).get("generated") or {}
            plan_ids = {int(i) for i in (generated.get("plan_ids") or [])}
            route_ids = {int(i) for i in (generated.get("route_ids") or [])}

            plan_ids |= {row[0] for row in self.db.execute(
                select(StudyPlan.id).where(StudyPlan.source_document_id == source_doc_id)
            )}
            route_ids |= {row[0] for row in self.db.execute(
                select(FieldRoute.id).where(FieldRoute.source_document_id == source_doc_id)
            )}

            if not route_ids:
                route_names = DocumentService._analysis_route_names(source_doc)
                if route_names:
                    route_ids |= {row[0] for row in self.db.execute(
                        select(FieldRoute.id).where(FieldRoute.name.in_(route_names))
                    )}
            if not plan_ids:
                task_names = DocumentService._analysis_study_task_names(source_doc)
                if task_names:
                    plan_ids |= {row[0] for row in self.db.execute(
                        select(StudyPlan.id).where(StudyPlan.task_name.in_(task_names))
                    )}

            # Study plans reference routes, so delete plans first.
            if plan_ids:
                self.db.execute(delete(StudyPlan).where(StudyPlan.id.in_(plan_ids)))
            if route_ids:
                self.db.execute(delete(FieldRoute).where(FieldRoute.id.in_(route_ids)))

            # Remove the source analysis document too.
            self.db.delete(source_doc)

        # Delete vector chunks from the vector store.
        self.retriever.delete_document(document_id)

        # Remove the shared PDF file from disk once.
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except OSError as e:
            logger.warning("Failed to delete file %s: %s", doc.file_path, e)

        self.db.delete(doc)
        self.db.commit()
        return True

    def get_stats(self) -> dict:
        doc_count_result = self.db.execute(
            select(func.count(KnowledgeDocument.id))
        )
        chunk_count_result = self.db.execute(
            select(func.count(KnowledgeChunk.id))
        )
        vector_stats = self.retriever.stats()
        return {
            "document_count": doc_count_result.scalar() or 0,
            "chunk_count_sqlite": chunk_count_result.scalar() or 0,
            "chunk_count_chroma": vector_stats["chunk_count"],
        }

    def get_available_filters(self) -> dict:
        """Return distinct metadata values for UI filter dropdowns."""
        return self.retriever.available_filters()
