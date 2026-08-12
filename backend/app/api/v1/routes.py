"""Route API endpoints.

Endpoints:
    GET    /api/v1/routes          — List all routes
    GET    /api/v1/routes/{id}     — Get route detail
    POST   /api/v1/routes          — Create a route (admin)
    PUT    /api/v1/routes/{id}     — Update a route (admin)
    DELETE /api/v1/routes/{id}     — Delete a route (admin)
    POST   /api/v1/routes/seed     — Seed default 7 routes
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.route import (
    RouteCreate,
    RouteListOut,
    RouteOut,
    RouteUpdate,
)
from app.services.route_service import RouteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routes", tags=["Routes"])


def get_route_service(db: AsyncSession = Depends(get_db)) -> RouteService:
    return RouteService(db)


# ── List ─────────────────────────────────────────────────────

@router.get("", response_model=RouteListOut)
async def list_routes(
    service: RouteService = Depends(get_route_service),
):
    """List all routes, ordered by route number (order_index).

    Returns all 7 Weihai field practice routes.
    """
    routes = await service.list_routes()
    return RouteListOut(
        total=len(routes),
        items=[RouteOut.model_validate(r) for r in routes],
    )


# ── Detail ───────────────────────────────────────────────────

@router.get("/{route_id}", response_model=RouteOut)
async def get_route(
    route_id: int,
    service: RouteService = Depends(get_route_service),
):
    """Get a single route by ID, with full detail.

    Returns learning objectives, key observation points,
    precautions, required tools, and geological background.
    """
    route = await service.get_route(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")
    return RouteOut.model_validate(route)


# ── Create ───────────────────────────────────────────────────

@router.post("", response_model=RouteOut, status_code=201)
async def create_route(
    data: RouteCreate,
    service: RouteService = Depends(get_route_service),
):
    """Create a new route. (Admin endpoint)

    All list fields (learning_objectives, key_points, etc.)
    should be provided as JSON arrays of strings.
    """
    try:
        route = await service.create_route(data)
        return RouteOut.model_validate(route)
    except Exception as e:
        logger.exception("Failed to create route")
        raise HTTPException(status_code=400, detail=f"创建路线失败: {str(e)}")


# ── Update ───────────────────────────────────────────────────

@router.put("/{route_id}", response_model=RouteOut)
async def update_route(
    route_id: int,
    data: RouteUpdate,
    service: RouteService = Depends(get_route_service),
):
    """Update a route. Only provided fields will be changed. (Admin endpoint)"""
    route = await service.update_route(route_id, data)
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")
    return RouteOut.model_validate(route)


# ── Delete ───────────────────────────────────────────────────

@router.delete("/{route_id}")
async def delete_route(
    route_id: int,
    service: RouteService = Depends(get_route_service),
):
    """Delete a route. (Admin endpoint)"""
    deleted = await service.delete_route(route_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="路线不存在")
    return {"message": "路线已删除", "route_id": route_id}


# ── Seed ─────────────────────────────────────────────────────

@router.post("/seed")
async def seed_routes(
    force: bool = Query(default=False, description="是否强制重新导入（会删除已有数据）"),
    service: RouteService = Depends(get_route_service),
):
    """Import the 7 default Weihai field routes from seed data.

    By default, skips seeding if routes already exist.
    Set `force=true` to delete existing routes and re-import.

    Each route includes geological background, learning objectives,
    key observation points, precautions, and required tools.
    """
    result = await service.seed_routes(force=force)
    if result["created"] > 0:
        return {
            "message": f"成功导入 {result['created']} 条路线",
            "created": result["created"],
        }
    else:
        return {
            "message": f"路线数据已存在（{result['skipped']} 条），跳过导入。使用 force=true 强制重新导入",
            "skipped": result["skipped"],
        }
