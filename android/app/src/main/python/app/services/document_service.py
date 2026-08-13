"""Document service — upload, list, delete analysis documents."""

import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import AnalysisDocument

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

    def delete_document(self, document_id: int) -> bool:
        """Delete a document record and its file from disk."""
        doc = self.db.get(AnalysisDocument, document_id)
        if not doc:
            return False

        # Remove file from disk
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except OSError as e:
            logger.warning("Failed to delete file %s: %s", doc.file_path, e)

        self.db.delete(doc)
        self.db.commit()
        logger.info("Document deleted: id=%d", document_id)
        return True
