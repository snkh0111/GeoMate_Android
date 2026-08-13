"""Route service — business logic for geology field route management."""

import json
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.route import FieldRoute
from app.schemas.route import RouteCreate, RouteUpdate

logger = logging.getLogger(__name__)

# Path to seed data
SEED_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "seed_data" / "routes.json"


class RouteService:
    """CRUD and seed operations for field routes."""

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ────────────────────────────────────────────────

    def list_routes(self) -> list[FieldRoute]:
        """List all routes, ordered by order_index."""
        result = self.db.execute(
            select(FieldRoute).order_by(FieldRoute.order_index)
        )
        return list(result.scalars().all())

    def get_route(self, route_id: int) -> FieldRoute | None:
        """Get a single route by ID."""
        return self.db.get(FieldRoute, route_id)

    def create_route(self, data: RouteCreate) -> FieldRoute:
        """Create a new route."""
        route = FieldRoute(**data.dict())
        self.db.add(route)
        self.db.commit()
        self.db.refresh(route)
        logger.info("Created route: %s (id=%d)", route.name, route.id)
        return route

    def update_route(self, route_id: int, data: RouteUpdate) -> FieldRoute | None:
        """Update an existing route. Only updates provided fields."""
        route = self.db.get(FieldRoute, route_id)
        if not route:
            return None

        # Only update fields that were explicitly provided (not None)
        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(route, key, value)

        self.db.commit()
        self.db.refresh(route)
        logger.info("Updated route: %s (id=%d)", route.name, route.id)
        return route

    def delete_route(self, route_id: int) -> bool:
        """Delete a route. Returns True if deleted, False if not found."""
        route = self.db.get(FieldRoute, route_id)
        if not route:
            return False
        self.db.delete(route)
        self.db.commit()
        logger.info("Deleted route id=%d", route_id)
        return True

    # ── Seed ────────────────────────────────────────────────

    def seed_routes(self, force: bool = False) -> dict:
        """Load routes from seed_data/routes.json and insert into DB.

        Args:
            force: If True, delete existing routes before seeding.

        Returns:
            Dict with 'created' count and 'skipped' count.
        """
        # Check if data already exists
        existing_count = self.db.scalar(
            select(func.count(FieldRoute.id))
        )
        if existing_count and existing_count > 0:
            if not force:
                logger.info("Routes already seeded (%d routes), skipping", existing_count)
                return {"created": 0, "skipped": existing_count}
            else:
                # Delete all existing routes first
                self.db.execute(FieldRoute.__table__.delete())
                self.db.commit()
                logger.info("Cleared %d existing routes for re-seed", existing_count)

        # Load seed data
        if not SEED_DATA_PATH.exists():
            logger.warning("Seed data file not found: %s", SEED_DATA_PATH)
            return {"created": 0, "skipped": 0}

        with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
            routes_data = json.load(f)

        created = 0
        for data in routes_data:
            route = FieldRoute(**data)
            self.db.add(route)
            created += 1

        self.db.commit()
        logger.info("Seeded %d routes from %s", created, SEED_DATA_PATH)
        return {"created": created, "skipped": 0}
