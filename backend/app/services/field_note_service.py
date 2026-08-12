"""Field Note service — CRUD, geo queries, and demo seed data.

Geological field notebook records with GPS coordinates and
attitude measurements (strike/dip_direction/dip_angle).
"""

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field_note import FieldNote
from app.schemas.field_note import FieldNoteCreate, FieldNoteUpdate

logger = logging.getLogger(__name__)


class FieldNoteService:
    """CRUD and query operations for geological field notes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CRUD ────────────────────────────────────────────────

    async def list_notes(
        self,
        user_id: int | None = None,
        route_id: int | None = None,
        rock_type: str | None = None,
    ) -> list[FieldNote]:
        """List field notes with optional filters, newest first."""
        stmt = select(FieldNote).order_by(FieldNote.recorded_at.desc())

        if user_id is not None:
            stmt = stmt.where(FieldNote.user_id == user_id)
        if route_id is not None:
            stmt = stmt.where(FieldNote.route_id == route_id)
        if rock_type is not None:
            stmt = stmt.where(FieldNote.rock_type == rock_type)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_note(self, note_id: int) -> FieldNote | None:
        """Get a single field note by ID."""
        return await self.db.get(FieldNote, note_id)

    async def find_by_idempotency_key(self, key: str) -> FieldNote | None:
        """Find an existing note by idempotency key (offline sync dedup)."""
        result = await self.db.execute(
            select(FieldNote).where(FieldNote.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def create_note(
        self, data: FieldNoteCreate, idempotency_key: str | None = None,
    ) -> FieldNote:
        """Create a new geological observation point record."""
        note = FieldNote(**data.model_dump())
        if idempotency_key:
            note.idempotency_key = idempotency_key
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        logger.info("Created field note: id=%d point=%s", note.id, note.point_number)
        return note

    async def update_note(self, note_id: int, data: FieldNoteUpdate) -> FieldNote | None:
        """Update a field note. Only provided fields are changed."""
        note = await self.db.get(FieldNote, note_id)
        if not note:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(note, key, value)
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def delete_note(self, note_id: int) -> bool:
        """Delete a field note."""
        note = await self.db.get(FieldNote, note_id)
        if not note:
            return False
        await self.db.delete(note)
        await self.db.commit()
        return True

    # ── Geo queries ─────────────────────────────────────────

    async def list_geojson(
        self,
        user_id: int | None = None,
        route_id: int | None = None,
    ) -> list[dict]:
        """Return field notes as GeoJSON FeatureCollection.

        Only includes notes that have GPS coordinates.
        """
        stmt = select(FieldNote).order_by(FieldNote.recorded_at.desc())
        if user_id is not None:
            stmt = stmt.where(FieldNote.user_id == user_id)
        if route_id is not None:
            stmt = stmt.where(FieldNote.route_id == route_id)

        result = await self.db.execute(stmt)
        notes = result.scalars().all()

        features = []
        for note in notes:
            if note.latitude is None or note.longitude is None:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [note.longitude, note.latitude],
                },
                "properties": {
                    "id": note.id,
                    "point_number": note.point_number,
                    "rock_type": note.rock_type,
                    "attitude": note.attitude,
                    "description": (note.description or "")[:100],
                    "recorded_at": note.recorded_at.isoformat() if note.recorded_at else None,
                },
            })

        return features

    # ── Seed ────────────────────────────────────────────────

    async def seed_notes(self, user_id: int, force: bool = False) -> dict:
        """Create demo field notes for Route 1 (占甲埠村).

        These are realistic examples following the standard
        field notebook format taught in the Weihai practice.

        Args:
            user_id: The user to create notes for.
            force: If True, delete existing notes for this user first.
        """
        existing = await self.db.scalar(
            select(func.count(FieldNote.id)).where(FieldNote.user_id == user_id)
        )
        if existing and existing > 0:
            if not force:
                return {"created": 0, "skipped": existing}
            else:
                await self.db.execute(
                    FieldNote.__table__.delete().where(FieldNote.user_id == user_id)
                )
                await self.db.commit()

        now = datetime.utcnow()

        notes_data = [
            {
                "user_id": user_id,
                "route_id": 1,
                "order_index": 1,
                "point_number": "NO.1",
                "location": "占甲埠村东200m公路旁采石场",
                "latitude": 37.3850,
                "longitude": 122.1100,
                "rock_type": "中粒黑云母花岗岩",
                "description": (
                    "岩石呈灰白色，中粒等粒结构，块状构造。\n"
                    "主要矿物成分：\n"
                    "- 钾长石（~35%）：肉红色，半自形板状，可见卡氏双晶\n"
                    "- 斜长石（~30%）：灰白色，半自形板状，可见聚片双晶\n"
                    "- 石英（~25%）：烟灰色，他形粒状，油脂光泽\n"
                    "- 黑云母（~8%）：黑色片状，珍珠光泽\n"
                    "- 角闪石（~2%）：黑色长柱状\n\n"
                    "岩石新鲜面坚硬，裂隙不发育。"
                ),
                "strike": None,
                "dip_direction": None,
                "dip_angle": None,
                "sample_number": "SGD-01",
                "weather": "晴",
                "recorded_at": now,
            },
            {
                "user_id": user_id,
                "route_id": 1,
                "order_index": 2,
                "point_number": "NO.2",
                "location": "采石场北侧陡崖下",
                "latitude": 37.3852,
                "longitude": 122.1103,
                "rock_type": "花岗伟晶岩脉",
                "description": (
                    "伟晶岩脉呈浅肉红色，宽约30cm，走向NE-SW，近直立。\n"
                    "矿物晶体粗大，钾长石晶体可达3-5cm，石英呈烟灰色块状。\n"
                    "脉体切穿主岩体（中粒花岗岩），边界清晰。\n"
                    "接触面附近花岗岩有轻微蚀变（绿泥石化）。\n\n"
                    "→ 判断该伟晶岩脉形成晚于主岩体（穿切关系）。"
                ),
                "strike": 45.0,
                "dip_direction": 315.0,
                "dip_angle": 82.0,
                "sample_number": "SGD-02",
                "weather": "晴",
                "recorded_at": now,
            },
            {
                "user_id": user_id,
                "route_id": 1,
                "order_index": 3,
                "point_number": "NO.3",
                "location": "采石场西侧平台",
                "latitude": 37.3848,
                "longitude": 122.1095,
                "rock_type": "辉绿岩脉",
                "description": (
                    "辉绿岩脉呈暗绿色至墨绿色，宽约50cm，走向NW-SE。\n"
                    "细粒辉绿结构，主要矿物为辉石和斜长石。\n"
                    "脉体切穿中粒花岗岩和伟晶岩脉，是区域内最晚的岩浆活动。\n"
                    "辉绿岩脉边缘可见冷凝边（细粒化），宽约2-3cm。\n\n"
                    "→ 岩浆侵入期次：中粒花岗岩（最早）→ 伟晶岩脉 → 辉绿岩脉（最晚）"
                ),
                "strike": 140.0,
                "dip_direction": 230.0,
                "dip_angle": 75.0,
                "sample_number": "SGD-03",
                "weather": "晴转多云",
                "recorded_at": now,
            },
        ]

        created = 0
        for data in notes_data:
            note = FieldNote(**data)
            self.db.add(note)
            created += 1

        await self.db.commit()
        logger.info("Seeded %d demo field notes for user %d", created, user_id)
        return {"created": created, "skipped": 0}
