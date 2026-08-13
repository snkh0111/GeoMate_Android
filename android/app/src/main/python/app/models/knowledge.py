"""Knowledge base models: documents and their text chunks."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeDocument(Base):
    """An uploaded document (PDF) ingested into the knowledge base."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), default="pdf")
    status: Mapped[str] = mapped_column(
        String(20), default="processing"
    )  # processing | ready | error
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int | None] = mapped_column(Integer)
    source_document_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="来源分析文档ID（由上传PDF自动生成，用于级联删除路线/计划）"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument id={self.id} title='{self.title[:30]}' status={self.status}>"


class KnowledgeChunk(Base):
    """A text chunk from a document, stored in both SQLite (metadata) and ChromaDB (vector)."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    chroma_id: Mapped[str | None] = mapped_column(
        String(100), unique=True
    )  # ID in ChromaDB
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument", back_populates="chunks"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeChunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"
