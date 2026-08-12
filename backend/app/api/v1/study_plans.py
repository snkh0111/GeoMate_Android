"""Study Plan API endpoints.

Endpoints:
    GET    /api/v1/plans              — List plans (optional filters)
    GET    /api/v1/plans/daily        — Plans grouped by day (checkbox view)
    GET    /api/v1/plans/stats        — Study statistics
    POST   /api/v1/plans              — Create a plan item
    POST   /api/v1/plans/seed         — Generate 7-day plan for a user
    PATCH  /api/v1/plans/{id}/toggle  — Toggle completion status
    PUT    /api/v1/plans/{id}         — Update a plan item
    DELETE /api/v1/plans/{id}         — Delete a plan item
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.study_plan import (
    DailyPlanOut,
    PlanCreate,
    PlanListOut,
    PlanOut,
    PlanStatsOut,
    PlanUpdate,
)
from app.services.study_plan_service import StudyPlanService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Study Plans"])


def get_plan_service(db: AsyncSession = Depends(get_db)) -> StudyPlanService:
    return StudyPlanService(db)


# ── List ─────────────────────────────────────────────────────

@router.get("", response_model=PlanListOut)
async def list_plans(
    user_id: int = Query(..., gt=0, description="用户ID"),
    plan_date: date | None = Query(default=None, description="筛选日期"),
    status: str | None = Query(default=None, regex="^(pending|completed)$"),
    category: str | None = Query(default=None, description="筛选分类"),
    service: StudyPlanService = Depends(get_plan_service),
):
    """List study plan items with optional filters.

    Examples:
    - GET /plans?user_id=1 — all plans for user 1
    - GET /plans?user_id=1&date=2026-07-01 — plans for a specific day
    - GET /plans?user_id=1&status=pending — only incomplete tasks
    """
    plans = await service.list_plans(
        user_id=user_id, plan_date=plan_date,
        status=status, category=category,
    )
    return PlanListOut(
        total=len(plans),
        items=[PlanOut.model_validate(p) for p in plans],
    )


# ── Daily grouped view ───────────────────────────────────────

@router.get("/daily", response_model=list[DailyPlanOut])
async def get_daily_plans(
    user_id: int = Query(..., gt=0),
    plan_date: date | None = Query(default=None),
    service: StudyPlanService = Depends(get_plan_service),
):
    """Get study plans grouped by day.

    Returns a checkbox-list view: each day shows total/completed tasks
    and all items. This is the primary UI view for the study plan page.

    Example output:
    [
      {
        "date": "2026-07-01",
        "total_tasks": 5,
        "completed_tasks": 3,
        "completion_rate": 0.6,
        "items": [...]
      },
      ...
    ]
    """
    daily = await service.get_daily_plans(user_id=user_id, plan_date=plan_date)
    return [
        DailyPlanOut(
            date=d["date"],
            total_tasks=d["total_tasks"],
            completed_tasks=d["completed_tasks"],
            completion_rate=d["completion_rate"],
            items=[PlanOut.model_validate(p) for p in d["items"]],
        )
        for d in daily
    ]


# ── Stats ────────────────────────────────────────────────────

@router.get("/stats", response_model=PlanStatsOut)
async def get_stats(
    user_id: int = Query(..., gt=0),
    service: StudyPlanService = Depends(get_plan_service),
):
    """Get study progress statistics for a user.

    Includes overall completion rate, breakdown by category,
    and breakdown by priority level.
    """
    stats = await service.get_stats(user_id=user_id)
    return PlanStatsOut(**stats)


# ── Create ───────────────────────────────────────────────────

@router.post("", response_model=PlanOut, status_code=201)
async def create_plan(
    data: PlanCreate,
    service: StudyPlanService = Depends(get_plan_service),
):
    """Create a new study plan item."""
    plan = await service.create_plan(data)
    return PlanOut.model_validate(plan)


# ── Toggle status (快捷完成/取消完成) ───────────────────────

@router.patch("/{plan_id}/toggle", response_model=PlanOut)
async def toggle_plan_status(
    plan_id: int,
    service: StudyPlanService = Depends(get_plan_service),
):
    """Toggle a plan between pending and completed.

    Convenience endpoint for the checkbox UI —
    one click to mark done, another to undo.
    """
    plan = await service.toggle_status(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return PlanOut.model_validate(plan)


# ── Update ───────────────────────────────────────────────────

@router.put("/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    service: StudyPlanService = Depends(get_plan_service),
):
    """Update a plan item. Only provided fields are changed."""
    plan = await service.update_plan(plan_id, data)
    if not plan:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return PlanOut.model_validate(plan)


# ── Delete ───────────────────────────────────────────────────

@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: int,
    service: StudyPlanService = Depends(get_plan_service),
):
    """Delete a plan item."""
    deleted = await service.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="计划项不存在")
    return {"message": "计划项已删除", "plan_id": plan_id}


# ── Seed ─────────────────────────────────────────────────────

@router.post("/seed")
async def seed_plans(
    user_id: int = Query(..., gt=0, description="为用户生成7天学习计划"),
    force: bool = Query(default=False, description="是否强制重新生成"),
    service: StudyPlanService = Depends(get_plan_service),
):
    """Generate a 7-day study plan for a user.

    The plan follows the actual Weihai field practice schedule:
    Day 1: Station training + safety + mineral preview
    Day 2: Route 1 (占甲埠村 granite)
    Day 3: Route 2 (马山 basalt volcano)
    Day 4: Route 3 (棉花山 sedimentary)
    Day 5: Route 4 (刘公岛 metamorphic + coastal)
    Day 6: Route 5 (鸡鸣岛 weathering + beach)
    Day 7: Route 6+7 + comprehensive exam review

    Each day includes route prep, field tasks, mineral/rock review,
    and exam key points. Total: ~32 tasks across 7 days.
    """
    result = await service.seed_plans(user_id=user_id, force=force)
    if result["created"] > 0:
        return {
            "message": f"成功生成 {result['created']} 项学习任务（7天计划）",
            "created": result["created"],
            "user_id": user_id,
        }
    else:
        return {
            "message": f"该用户已有 {result['skipped']} 项学习计划，跳过生成。使用 force=true 强制重新生成",
            "skipped": result["skipped"],
        }
