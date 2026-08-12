"""Pydantic schemas for AI structured output.

These define the JSON contract between the LLM and the database.
The AI must output data that exactly matches these schemas so it
can be directly written to field_routes and study_plans tables.
"""

from pydantic import BaseModel, Field


# ── Route extraction ─────────────────────────────────────────

class AIRouteExtraction(BaseModel):
    """A route extracted from a PDF by the AI."""
    name: str = Field(..., min_length=1, max_length=200, description="路线名称")
    location: str = Field(..., min_length=1, max_length=200, description="地理位置")
    geological_type: str = Field(
        ..., description="igneous|sedimentary|metamorphic|coastal|composite"
    )
    description: str = Field(
        ..., min_length=1, description="路线概述（Markdown，含地质背景和教学内容）"
    )
    difficulty: str = Field(default="medium", description="easy|medium|hard")
    duration_hours: float | None = Field(default=None, ge=0, description="预计用时")
    learning_objectives: list[str] = Field(default_factory=list, description="学习目标")
    key_points: list[str] = Field(default_factory=list, description="关键观察点")
    precautions: list[str] = Field(default_factory=list, description="注意事项")
    required_tools: list[str] = Field(default_factory=list, description="所需工具")
    order_index: int | None = Field(default=None, description="建议路线编号")


# ── Knowledge point extraction ───────────────────────────────

class AIKnowledgePoint(BaseModel):
    """A key geology knowledge point extracted from the PDF."""
    category: str = Field(
        ..., description="分类: 矿物|岩石|构造|地貌|技能|安全|考试|路线"
    )
    title: str = Field(..., min_length=1, max_length=200, description="知识点标题")
    content: str = Field(..., min_length=1, description="知识点详细说明")
    difficulty: str = Field(default="medium", description="基础|进阶|重点")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    related_route_name: str | None = Field(
        default=None, description="关联的路线名称（如适用）"
    )


# ── Study task extraction ────────────────────────────────────

class AIStudyTask(BaseModel):
    """A study task extracted from the PDF."""
    date_offset: int = Field(
        default=0, ge=0, le=14, description="建议实习第几天（0=站内教学日）"
    )
    task_name: str = Field(..., min_length=1, max_length=300, description="任务名称")
    content: str = Field(..., min_length=1, description="任务详细说明")
    priority: str = Field(default="medium", description="high|medium|low")
    category: str = Field(
        ..., description="技能|矿物|岩石|构造|地貌|安全|考试|路线复习"
    )
    related_route_name: str | None = Field(
        default=None, description="关联的路线名称（如适用）"
    )


# ── Top-level AI output ──────────────────────────────────────

class AIAnalysisOutput(BaseModel):
    """Complete structured output from the Document Intelligence Agent.

    This is the JSON contract the LLM must produce. The fields map
    directly to:
      - routes → field_routes table
      - study_tasks → study_plans table
      - knowledge_points → new knowledge_points table (future)
    """
    summary: str = Field(
        default="", description="200字中文摘要，概述这份PDF的主要内容"
    )
    routes: list[AIRouteExtraction] = Field(
        default_factory=list, description="提取的路线信息"
    )
    knowledge_points: list[AIKnowledgePoint] = Field(
        default_factory=list, description="提取的知识点"
    )
    study_tasks: list[AIStudyTask] = Field(
        default_factory=list, description="提取的学习任务"
    )

    @property
    def total_extracted(self) -> int:
        return len(self.routes) + len(self.knowledge_points) + len(self.study_tasks)
