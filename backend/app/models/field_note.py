"""Field Note model — digital geology field notebook.

Each record represents a geological observation point, mirroring
the paper field notebook format used in the Weihai practice.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FieldNote(Base):
    """A single geological observation point record (地质点记录)."""

    __tablename__ = "field_notes"

    # ── Primary key ─────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Foreign keys ────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        comment="记录者"
    )
    route_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("field_routes.id", ondelete="SET NULL"), nullable=True,
        comment="所属路线"
    )

    # ── Observation point identity ──────────────────────────
    point_number: Mapped[str | None] = mapped_column(
        String(20), comment="地质点编号 (e.g. NO.1, D001)"
    )
    location: Mapped[str | None] = mapped_column(
        String(500), comment="点位描述 (e.g. 占甲埠村东200m公路旁)"
    )

    # ── GPS coordinates ─────────────────────────────────────
    latitude: Mapped[float | None] = mapped_column(
        Float, comment="纬度"
    )
    longitude: Mapped[float | None] = mapped_column(
        Float, comment="经度"
    )

    # ── Geological description (core content) ───────────────
    rock_type: Mapped[str | None] = mapped_column(
        String(200), comment="岩石类型 (e.g. 中粒黑云母花岗岩)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, comment="地质描述 — 野簿核心记录内容"
    )

    # ── Attitude (产状三要素) ───────────────────────────────
    strike: Mapped[float | None] = mapped_column(
        Float, comment="走向 (0-360°)"
    )
    dip_direction: Mapped[float | None] = mapped_column(
        Float, comment="倾向 (0-360°)"
    )
    dip_angle: Mapped[float | None] = mapped_column(
        Float, comment="倾角 (0-90°)"
    )

    # ── Specimen & photo ────────────────────────────────────
    sample_number: Mapped[str | None] = mapped_column(
        String(50), comment="标本编号 (e.g. SGD-01)"
    )
    photo_url: Mapped[str | None] = mapped_column(
        String(1000), comment="照片路径或URL"
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True,
        comment="客户端幂等键 (防止离线同步重复创建)",
    )

    # ── Metadata ────────────────────────────────────────────
    weather: Mapped[str | None] = mapped_column(
        String(50), comment="天气 (晴/阴/雨/雾)"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, comment="当日路线中序号"
    )

    # ── Timestamps ──────────────────────────────────────────
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="野外记录的实际时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # ── Display ─────────────────────────────────────────────
    @property
    def attitude(self) -> str:
        """Format attitude as: 280°∠20° (standard geology notation)."""
        if self.dip_direction is not None and self.dip_angle is not None:
            return f"{self.dip_direction:.0f}°∠{self.dip_angle:.0f}°"
        return ""

    @property
    def coordinates(self) -> dict | None:
        """Return {lat, lng} dict if both coordinates exist."""
        if self.latitude is not None and self.longitude is not None:
            return {"lat": self.latitude, "lng": self.longitude}
        return None

    def __repr__(self) -> str:
        return (
            f"<FieldNote id={self.id} point={self.point_number} "
            f"rock='{self.rock_type}' route={self.route_id}>"
        )
