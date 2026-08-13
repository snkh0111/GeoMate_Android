"""Document service — upload, list, delete analysis documents."""

import json
import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import AnalysisDocument
from app.models.route import FieldRoute
from app.models.study_plan import StudyPlan

logger = logging.getLogger(__name__)


class DocumentService:
    """Handles document upload and listing for the Intelligence Agent."""

    def __init__(self, db: Session):
        self.db = db

    def upload(
        self, user_id: int, filename: str, content: bytes
    ) -> AnalysisDocument:
        """Save an uploaded PDF and create a database record.

        Args:
            user_id: The uploading user.
            filename: Original filename.
            content: Raw file bytes.

        Returns:
            The created AnalysisDocument record.
        """
        # Save to disk
        file_id = uuid.uuid4().hex[:12]
        safe_filename = f"{file_id}_{filename}"
        file_path = Path(settings.UPLOAD_DIR) / safe_filename

        with open(file_path, "wb") as f:
            f.write(content)

        file_size = len(content)

        # Create DB record
        doc = AnalysisDocument(
            user_id=user_id,
            filename=filename,
            file_path=str(file_path),
            file_type="pdf",
            file_size=file_size,
            status="uploaded",
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        logger.info(
            "Document uploaded: id=%d user=%d file=%s size=%d",
            doc.id, user_id, filename, file_size,
        )
        return doc

    def list_documents(self, user_id: int | None = None) -> list[AnalysisDocument]:
        """List uploaded documents, newest first.

        Args:
            user_id: Optional filter by user.
        """
        stmt = select(AnalysisDocument).order_by(AnalysisDocument.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(AnalysisDocument.user_id == user_id)
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def get_document(self, document_id: int) -> AnalysisDocument | None:
        """Get a single document by ID."""
        return self.db.get(AnalysisDocument, document_id)

    @staticmethod
    def _analysis_route_names(doc: AnalysisDocument) -> list[str]:
        """Extract route names from the document's stored AI analysis.

        Supports both rule mode (``analysis.data``) and LLM mode
        (``analysis.raw_json``).
        """
        analysis = (doc.parsed_content or {}).get("analysis") or {}
        data = analysis.get("data")
        routes = None
        if data:
            routes = data.get("routes")
        elif analysis.get("raw_json"):
            try:
                routes = json.loads(analysis["raw_json"]).get("routes")
            except Exception:
                routes = None

        names = []
        for r in routes or []:
            if isinstance(r, dict) and r.get("name"):
                names.append(r["name"])
        return names

    @staticmethod
    def _analysis_study_task_names(doc: AnalysisDocument) -> list[str]:
        """Extract study-task names from the document's stored AI analysis.

        Supports both rule mode (``analysis.data``) and LLM mode
        (``analysis.raw_json``).
        """
        analysis = (doc.parsed_content or {}).get("analysis") or {}
        data = analysis.get("data")
        tasks = None
        if data:
            tasks = data.get("study_tasks")
        elif analysis.get("raw_json"):
            try:
                tasks = json.loads(analysis["raw_json"]).get("study_tasks")
            except Exception:
                tasks = None

        names = []
        for t in tasks or []:
            if isinstance(t, dict) and t.get("task_name"):
                names.append(t["task_name"])
        return names

    def delete_document(self, document_id: int) -> bool:
        """Delete a document and everything generated from it.

        Removes the routes, study plans, and knowledge-base entries that were
        auto-generated from this document (tracked via ``parsed_content["generated"]``).
        """
        doc = self.db.get(AnalysisDocument, document_id)
        if not doc:
            return False

        generated = (doc.parsed_content or {}).get("generated") or {}
        plan_ids = {int(i) for i in (generated.get("plan_ids") or [])}
        route_ids = {int(i) for i in (generated.get("route_ids") or [])}
        knowledge_ids = [int(i) for i in (generated.get("knowledge_document_ids") or [])]

        # Primary source tracking: records generated from this document carry a
        # ``source_document_id`` back-reference, so delete them reliably.
        plan_ids |= {row[0] for row in self.db.execute(
            select(StudyPlan.id).where(StudyPlan.source_document_id == document_id)
        )}
        route_ids |= {row[0] for row in self.db.execute(
            select(FieldRoute.id).where(FieldRoute.source_document_id == document_id)
        )}

        # Fallback for documents generated before source tracking existed:
        # recover route IDs by name from the stored analysis. Routes only ever
        # come from uploaded PDFs, so there are no seeded routes to collide with.
        if not route_ids:
            route_names = self._analysis_route_names(doc)
            if route_names:
                route_ids |= {row[0] for row in self.db.execute(
                    select(FieldRoute.id).where(FieldRoute.name.in_(route_names))
                )}

        # Fallback for study plans generated before source tracking existed.
        if not plan_ids:
            task_names = self._analysis_study_task_names(doc)
            if task_names:
                plan_ids |= {row[0] for row in self.db.execute(
                    select(StudyPlan.id).where(StudyPlan.task_name.in_(task_names))
                )}

        # Study plans reference routes, so delete them first.
        if plan_ids:
            self.db.execute(delete(StudyPlan).where(StudyPlan.id.in_(plan_ids)))
        if route_ids:
            self.db.execute(delete(FieldRoute).where(FieldRoute.id.in_(route_ids)))

        # Knowledge-base documents + their vector chunks.
        # Deleted inline (not via KnowledgeService.delete_document) to avoid
        # recursion: KnowledgeService.delete_document would try to delete this
        # analysis document again.
        if knowledge_ids:
            from app.ai.rag.retriever import Retriever
            from app.models.knowledge import KnowledgeDocument

            retriever = Retriever()
            for kid in knowledge_ids:
                kdoc = self.db.get(KnowledgeDocument, kid)
                if not kdoc:
                    continue
                try:
                    retriever.delete_document(kid)
                except Exception as e:
                    logger.warning("Failed to delete vector chunks for kb doc %d: %s", kid, e)
                self.db.delete(kdoc)

        # Remove file from disk
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except OSError as e:
            logger.warning("Failed to delete file %s: %s", doc.file_path, e)

        self.db.delete(doc)
        self.db.commit()
        logger.info(
            "Document deleted: id=%d (routes=%d, plans=%d, kb=%d)",
            document_id, len(route_ids), len(plan_ids), len(knowledge_ids),
        )
        return True
