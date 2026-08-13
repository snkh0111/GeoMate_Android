"""Document Parser service — extract text and split into sections.

Uses PyMuPDF for text extraction and heading-based heuristics
for section detection. No LLM involved at this stage.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.document import AnalysisDocument
from app.utils.pdf import parse_pdf, ParsedDocument

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parses uploaded PDFs into structured sections.

    Steps:
    1. Read PDF text via PyMuPDF
    2. Detect section headings (Chinese/geology patterns)
    3. Split into hierarchical DocumentSections
    4. Save ParsedDocument JSON to the database
    """

    def __init__(self, db: Session):
        self.db = db

    def parse(self, document_id: int) -> ParsedDocument:
        """Parse a document by ID. Updates the DB record with results.

        Args:
            document_id: ID of an uploaded AnalysisDocument.

        Returns:
            ParsedDocument with all detected sections.

        Raises:
            ValueError: If the document is not found.
            FileNotFoundError: If the PDF file is missing from disk.
        """
        doc = self.db.get(AnalysisDocument, document_id)
        if not doc:
            raise ValueError(f"Document not found: id={document_id}")

        logger.info("Parsing document %d: %s", doc.id, doc.filename)

        # 1. Extract text and split into sections
        parsed = parse_pdf(doc.file_path)

        # 2. Update status
        doc.status = "parsed"

        # 3. Store result as JSON (SQLite JSON column handles serialization)
        doc.parsed_content = parsed.to_dict()
        doc.parsed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        self.db.commit()
        self.db.refresh(doc)

        logger.info(
            "Document %d parsed: %d pages, %d chars, %d sections",
            doc.id, parsed.total_pages, parsed.total_chars, len(parsed.sections),
        )
        return parsed

    def get_parsed(self, document_id: int) -> ParsedDocument | None:
        """Retrieve parsed content from a previously parsed document.

        Returns None if the document hasn't been parsed yet.
        """
        doc = self.db.get(AnalysisDocument, document_id)
        if not doc or not doc.parsed_content:
            return None
        return ParsedDocument.from_dict(doc.parsed_content)
