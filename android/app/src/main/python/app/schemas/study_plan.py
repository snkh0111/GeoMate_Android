"""Pydantic schemas for Study Plan API.

Note: field names use `plan_date` (not `date`) to avoid shadowing
the Python `datetime.date` type.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────

class PlanCreate(BaseModel):
    """Create a new study plan item."""
    user_id: int = Field(..., gt=0)
    route_id: int | None = Field(default=None, gt=0)
    plan_date: date = Field(..., alias="date", description="计划日期 (YYYY-MM-DD)")
    task_name: str = Field(..., min_length=1, max_length=300)
    content: str | None = Field(default=None, description="详细说明")
    status: str = Field(default="pending", regex="^(pending|completed)$")
    priority: str = Field(default="medium", regex="^(high|medium|low)$")
    category: str | None = Field(
        default=None,
        description="分类: 技能/矿物/岩石/构造/安全/考试/路线复习/地貌"
    )
    order_index: int = Field(default=0, ge=0)


class PlanUpdate(BaseModel):
    """Update a study plan item. All fields optional."""
    route_id: int | None = Field(default=None, gt=0)
    plan_date: date | None = Field(default=None, alias="date")
    task_name: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = None
    status: str | None = Field(default=None, regex="^(pending|completed)$")
    priority: str | None = Field(default=None, regex="^(high|medium|low)$")
    category: str | None = None
    order_index: int | None = Field(default=None, ge=0)


class PlanToggleStatus(BaseModel):
    """Toggle task completion status."""
    status: str = Field(..., regex="^(pending|completed)$")


# ── Response schemas ─────────────────────────────────────────

class PlanOut(BaseModel):
    """Study plan item in API responses."""
    id: int
    user_id: int
    route_id: int | None = None
    plan_date: date = Field(..., alias="date")
    task_name: str
    content: str | None = None
    status: str
    priority: str
    category: str | None = None
    order_index: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class PlanListOut(BaseModel):
    """List of study plan items."""
    total: int
    items: list[PlanOut]


class DailyPlanOut(BaseModel):
    """Study plan grouped by day — the checkbox list view."""
    plan_date: date = Field(..., alias="date")
    total_tasks: int
    completed_tasks: int
    completion_rate: float
    items: list[PlanOut]


class PlanStatsOut(BaseModel):
    """Study progress statistics."""
    total_tasks: int
    completed_tasks: int
    completion_rate: float
    by_category: dict[str, dict]
    by_priority: dict[str, dict]
