"""Document Intelligence Service — AI analysis + auto-generation.

Orchestrates: parsed text → LLM → structured JSON → validation
         → auto-generate routes → auto-generate study plans
"""

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import chat_json
from app.ai.prompts.document_analyst import SYSTEM_PROMPT
from app.ai.schemas import AIAnalysisOutput
from app.models.document import AnalysisDocument
from app.models.route import FieldRoute
from app.models.study_plan import StudyPlan
from app.utils.pdf import ParsedDocument

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 40_000


class IntelligenceService:
    """Analyzes parsed documents and generates routes + study plans."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── AI Analysis ─────────────────────────────────────────

    async def analyze(self, document_id: int, api_key: str | None = None) -> dict:
        """Run AI analysis on a parsed document.

        Args:
            document_id: Document to analyze.
            api_key: Optional per-call Anthropic API key. Falls back to .env.
        """
        doc = await self._get_document(document_id)
        if not doc.parsed_content:
            raise ValueError("请先解析文档（POST /documents/{id}/parse）")

        parsed = ParsedDocument.from_dict(doc.parsed_content)
        user_message = self._build_message(parsed)
        if not user_message.strip():
            raise ValueError("文档中没有可分析的文字内容")

        # Validate API key availability
        from app.config import settings
        key = api_key or settings.ANTHROPIC_API_KEY
        if not key or key == "your-api-key-here":
            raise ValueError(
                "请提供 Anthropic API Key。\n"
                "方式一: 在 backend/.env 中设置 ANTHROPIC_API_KEY=sk-ant-...\n"
                "方式二: 通过 API 参数传入 api_key=sk-ant-..."
            )

        logger.info("Analyzing doc %d: %d sections, %d chars", doc.id, len(parsed.sections), len(user_message))

        doc.status = "analyzing"
        await self.db.commit()

        try:
            raw_json = await chat_json(
                system_prompt=SYSTEM_PROMPT, user_message=user_message, api_key=api_key,
            )
        except Exception as e:
            doc.status = "failed"
            doc.error_message = f"LLM 调用失败: {str(e)}"
            await self.db.commit()
            raise

        analysis = self._parse_and_validate(raw_json)

        doc.status = "completed"
        doc.parsed_content = {
            **doc.parsed_content,
            "analysis": {
                "summary": analysis.summary,
                "route_count": len(analysis.routes),
                "knowledge_point_count": len(analysis.knowledge_points),
                "study_task_count": len(analysis.study_tasks),
                "raw_json": raw_json,
                "analyzed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            },
        }
        await self.db.commit()

        logger.info("Analysis complete: %d routes, %d points, %d tasks",
                    len(analysis.routes), len(analysis.knowledge_points), len(analysis.study_tasks))

        return {"analysis": analysis, "raw_json": raw_json, "document_id": doc.id}

    # ── Auto-generate Routes ────────────────────────────────

    async def generate_routes(self, document_id: int) -> dict:
        """Generate FieldRoute records from AI analysis results.

        Reads the stored AI analysis, validates against existing routes
        to avoid duplicates, and creates new FieldRoute records.

        Returns:
            {created: int, skipped: int, routes: [{id, name}]}
        """
        doc = await self._get_document(document_id)
        analysis = self._get_analysis(doc)

        if not analysis.routes:
            return {"created": 0, "skipped": 0, "routes": [], "message": "AI 未识别出路线信息"}

        # Get existing route names for dedup
        existing_names = await self._get_existing_route_names()

        created, skipped = 0, 0
        result_routes = []

        for ai_route in analysis.routes:
            # Check for duplicates by name similarity
            if self._is_duplicate(ai_route.name, existing_names):
                logger.info("Skipping duplicate route: %s", ai_route.name)
                skipped += 1
                continue

            # Create FieldRoute
            route = FieldRoute(
                name=ai_route.name,
                location=ai_route.location,
                geological_type=ai_route.geological_type,
                description=ai_route.description,
                difficulty=ai_route.difficulty,
                duration_hours=ai_route.duration_hours,
                learning_objectives=ai_route.learning_objectives or [],
                key_points=ai_route.key_points or [],
                precautions=ai_route.precautions or [],
                required_tools=ai_route.required_tools or [],
                order_index=ai_route.order_index,
            )
            self.db.add(route)
            await self.db.flush()
            result_routes.append({"id": route.id, "name": route.name})
            existing_names.add(ai_route.name)
            created += 1

        await self.db.commit()

        logger.info("Generated %d routes (skipped %d duplicates) from doc %d",
                    created, skipped, document_id)

        return {
            "created": created,
            "skipped": skipped,
            "routes": result_routes,
            "message": f"成功创建 {created} 条路线" + (f"，跳过 {skipped} 条重复" if skipped else ""),
        }

    # ── Auto-generate Study Plans ───────────────────────────

    async def generate_study_plans(
        self, document_id: int, user_id: int, start_date: date | None = None
    ) -> dict:
        """Generate StudyPlan records from AI analysis results.

        Maps AIStudyTask fields to existing StudyPlan model.
        Uses date_offset to calculate actual dates from a start_date.

        Args:
            document_id: Source document ID.
            user_id: User to create plans for.
            start_date: First day of field practice. Defaults to today.

        Returns:
            {created: int, plans: [{id, task_name, date}]}
        """
        doc = await self._get_document(document_id)
        analysis = self._get_analysis(doc)

        if not analysis.study_tasks:
            return {"created": 0, "plans": [], "message": "AI 未识别出学习任务"}

        if start_date is None:
            start_date = date.today()

        # Get route name → ID mapping for linking
        route_map = await self._get_route_name_map()

        created = 0
        result_plans = []

        for task in analysis.study_tasks:
            plan_date = start_date + timedelta(days=task.date_offset)

            # Try to link to a route by name
            route_id = None
            if task.related_route_name:
                route_id = route_map.get(task.related_route_name)

            plan = StudyPlan(
                user_id=user_id,
                route_id=route_id,
                plan_date=plan_date,
                task_name=task.task_name,
                content=task.content,
                status="pending",
                priority=task.priority,
                category=task.category,
                order_index=created,
            )
            self.db.add(plan)
            await self.db.flush()
            result_plans.append({
                "id": plan.id,
                "task_name": plan.task_name,
                "date": plan.plan_date.isoformat(),
            })
            created += 1

        await self.db.commit()

        logger.info("Generated %d study plans for user %d from doc %d",
                    created, user_id, document_id)

        return {
            "created": created,
            "plans": result_plans,
            "message": f"成功创建 {created} 项学习任务",
        }

    # ── Helpers ─────────────────────────────────────────────

    async def _get_document(self, document_id: int) -> AnalysisDocument:
        doc = await self.db.get(AnalysisDocument, document_id)
        if not doc:
            raise ValueError(f"Document not found: id={document_id}")
        return doc

    def _get_analysis(self, doc: AnalysisDocument) -> AIAnalysisOutput:
        """Extract AIAnalysisOutput from document's stored analysis."""
        if not doc.parsed_content:
            raise ValueError("请先解析文档（POST /documents/{id}/parse）")
        analysis_data = doc.parsed_content.get("analysis")
        if not analysis_data:
            raise ValueError("请先运行 AI 分析（POST /intelligence/analyze/{id}）")

        raw_json = analysis_data.get("raw_json", "{}")
        return self._parse_and_validate(raw_json)

    async def _get_existing_route_names(self) -> set[str]:
        """Get all existing route names for duplicate detection."""
        result = await self.db.execute(select(FieldRoute.name))
        return {row[0] for row in result}

    async def _get_route_name_map(self) -> dict[str, int]:
        """Get mapping of route name → route id."""
        result = await self.db.execute(select(FieldRoute.id, FieldRoute.name))
        return {row[1]: row[0] for row in result}

    @staticmethod
    def _is_duplicate(name: str, existing: set[str]) -> bool:
        """Check if a route name is already in the existing set."""
        name_clean = name.strip()
        if name_clean in existing:
            return True
        # Fuzzy: check if existing name contains this name or vice versa
        for en in existing:
            if len(name_clean) > 4 and (name_clean in en or en in name_clean):
                return True
        return False

    def _build_message(self, parsed: ParsedDocument) -> str:
        parts = []
        total = 0
        for s in parsed.sections:
            header = f"## {s.title}" if s.title else "## (无标题)"
            part = f"{header}\n{s.content}\n"
            if total + len(part) > MAX_INPUT_CHARS:
                remaining = MAX_INPUT_CHARS - total - 100
                if remaining > 200:
                    parts.append(f"{header}\n{s.content[:remaining]}...\n")
                break
            parts.append(part)
            total += len(part)
        return "\n".join(parts)

    def _parse_and_validate(self, raw_json: str) -> AIAnalysisOutput:
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned)
            cleaned = re.sub(r"\n```\s*$", "", cleaned)

        errors = []
        for _ in range(3):
            try:
                data = json.loads(cleaned)
                return AIAnalysisOutput.model_validate(data)
            except json.JSONDecodeError as e:
                errors.append(f"JSON解析错误: {e}")
                cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            except Exception as e:
                errors.append(f"Schema校验错误: {e}")
                break

        raise ValueError(
            f"LLM 返回的内容无法解析为有效 JSON。\n"
            f"错误: {'; '.join(errors)}\n"
            f"原始输出前500字: {raw_json[:500]}"
        )
