"""Analysis Document model — uploaded PDFs for Document Intelligence Agent.

Distinct from KnowledgeDocument (RAG knowledge base).
These documents are raw uploads waiting for LLM analysis.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisDocument(Base):
    """An uploaded PDF awaiting AI analysis."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="上传者"
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False, comment="原始文件名")
    file_path: Mapped[str] = mapped_column(
        String(1000), nullable=False, comment="服务器存储路径"
    )
    file_type: Mapped[str] = mapped_column(
        String(20), default="pdf", comment="文件类型"
    )
    file_size: Mapped[int | None] = mapped_column(Integer, comment="文件大小(bytes)")
    status: Mapped[str] = mapped_column(
        String(20), default="uploaded",
        comment="uploaded|parsed|analyzing|completed|failed"
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # ── Parsing results ────────────────────────────────────
    parsed_content: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="解析结果 (ParsedDocument.to_dict())"
    )
    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="解析完成时间"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    @property
    def section_count(self) -> int:
        """Number of parsed sections."""
        if self.parsed_content:
            return len(self.parsed_content.get("sections", []))
        return 0

    @property
    def is_parsed(self) -> bool:
        return self.parsed_content is not None

    def __repr__(self) -> str:
        return f"<AnalysisDocument id={self.id} filename='{self.filename[:30]}' status={self.status}>"
