"""Study Plan model — daily learning tasks for geology field practice.

Each plan item is a checkable task tied to a user, optionally linked to
a specific route or knowledge category.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StudyPlan(Base):
    """A single learning task in a student's daily study plan."""

    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ───────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        comment="所属用户"
    )
    route_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("field_routes.id", ondelete="SET NULL"), nullable=True,
        comment="关联路线（可为空，表示通用学习任务）"
    )
    source_document_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="来源文档ID（由上传PDF自动生成）"
    )

    # ── Core fields ─────────────────────────────────────────
    plan_date: Mapped[date] = mapped_column(
        "date", Date, nullable=False, comment="计划日期"
    )
    task_name: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="任务名称（简短）"
    )
    content: Mapped[str | None] = mapped_column(
        Text, comment="任务详细说明"
    )

    # ── Status & priority ───────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        comment="状态: pending | completed"
    )
    priority: Mapped[str] = mapped_column(
        String(10), default="medium",
        comment="优先级: high | medium | low"
    )

    # ── Organization ────────────────────────────────────────
    category: Mapped[str | None] = mapped_column(
        String(50), comment="分类: 技能/矿物/岩石/构造/安全/考试/路线复习/地貌"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, comment="当日排序"
    )

    # ── Timestamps ──────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<StudyPlan id={self.id} date={self.plan_date} "
            f"task='{self.task_name[:30]}' status={self.status}>"
        )
