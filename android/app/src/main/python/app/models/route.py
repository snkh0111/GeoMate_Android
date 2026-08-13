"""Route model: Weihai geology field practice routes.

Seven standard routes covering igneous, sedimentary, metamorphic rocks,
coastal geomorphology, and structural geology in the Weihai area.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FieldRoute(Base):
    """A geology field practice route in the Weihai area."""

    __tablename__ = "field_routes"

    # ── Primary fields ──────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="来源文档ID（由上传PDF自动生成）"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="路线名称")
    location: Mapped[str] = mapped_column(String(200), nullable=False, comment="地理位置")
    geological_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="地质类型: igneous/sedimentary/metamorphic/coastal/composite"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="路线概述（Markdown）"
    )
    difficulty: Mapped[str] = mapped_column(
        String(20), default="easy", comment="难度: easy/medium/hard"
    )

    # ── Structured content (JSON arrays) ────────────────────
    learning_objectives: Mapped[list | None] = mapped_column(
        JSON, comment="学习目标列表"
    )
    key_points: Mapped[list | None] = mapped_column(
        JSON, comment="关键观察点列表"
    )
    precautions: Mapped[list | None] = mapped_column(
        JSON, comment="注意事项列表"
    )
    required_tools: Mapped[list | None] = mapped_column(
        JSON, comment="需要携带的工具"
    )

    # ── Optional metadata ───────────────────────────────────
    order_index: Mapped[int | None] = mapped_column(
        Integer, comment="路线编号（1-7）"
    )
    duration_hours: Mapped[float | None] = mapped_column(
        Float, comment="预计用时（小时）"
    )
    thumbnail_image: Mapped[str | None] = mapped_column(
        String(500), comment="路线缩略图路径"
    )

    # ── Timestamps ──────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<FieldRoute id={self.id} name='{self.name}' difficulty={self.difficulty}>"
