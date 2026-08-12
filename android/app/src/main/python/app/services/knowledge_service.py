"""Knowledge base service — business logic with geology metadata support."""

import logging
import os
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.retriever import QueryIntent, Retriever
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import SearchResponse, SearchResultItem
from app.utils.pdf import extract_pdf_text

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Handles the full lifecycle of knowledge documents with geology metadata."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = Retriever()

    # ── Upload / Ingest ───────────────────────────────────────

    async def upload_and_ingest(
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
        await self.db.commit()
        await self.db.refresh(doc)

        try:
            # 2. Extract text
            pdf_doc = extract_pdf_text(file_path)
            pages = [(p.page_number, p.text) for p in pdf_doc.pages]

            if not pages:
                raise ValueError("PDF 中没有可提取的文本内容")

            # 3. Ingest with geology-aware chunking + metadata extraction
            chunk_count = await self.retriever.ingest_document(
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

            await self.db.commit()
            await self.db.refresh(doc)

            logger.info(
                "Document %d (%s) ingested: %d chunks from %d pages",
                doc.id, title, chunk_count, pdf_doc.total_pages,
            )
            return doc

        except Exception as e:
            logger.exception("Failed to ingest document %d", doc.id)
            doc.status = "error"
            doc.error_message = str(e)
            await self.db.commit()
            await self.db.refresh(doc)
            raise

    # ── Search ─────────────────────────────────────────────────

    async def search(
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
        results = await self.retriever.search(
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

    async def list_documents(self) -> list[KnowledgeDocument]:
        result = await self.db.execute(
            select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, document_id: int) -> KnowledgeDocument | None:
        return await self.db.get(KnowledgeDocument, document_id)

    async def delete_document(self, document_id: int) -> bool:
        doc = await self.db.get(KnowledgeDocument, document_id)
        if not doc:
            return False
        await self.retriever.delete_document(document_id)
        await self.db.delete(doc)
        await self.db.commit()
        return True

    async def get_stats(self) -> dict:
        doc_count_result = await self.db.execute(
            select(func.count(KnowledgeDocument.id))
        )
        chunk_count_result = await self.db.execute(
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
