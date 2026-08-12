"""Rule-based document analyzer — offline fallback for AI analysis.

Extracts routes, knowledge points and study tasks from parsed document
text using heading heuristics and a geology lexicon. No LLM / API key
is required, so it runs fully on-device (Android / Chaquopy).

Produces the same structured output contract as the LLM path
(AIAnalysisOutput), so route/plan generation works identically.
"""

import logging
import re
from datetime import datetime, timezone

from app.ai.schemas import (
    AIAnalysisOutput,
    AIKnowledgePoint,
    AIRouteExtraction,
    AIStudyTask,
)
from app.utils.pdf import ParsedDocument

logger = logging.getLogger(__name__)

# ── Geology lexicon ─────────────────────────────────────────────

GEOLOGY_TYPES = {
    "igneous": ["岩浆", "火山", "玄武岩", "花岗岩", "喷出", "侵入", "安山岩", "流纹岩", "辉绿岩", "熔岩", "凝灰岩"],
    "sedimentary": ["沉积", "砂岩", "页岩", "石灰岩", "灰岩", "砾岩", "地层", "层理", "泥岩", "白云岩"],
    "metamorphic": ["变质", "片岩", "片麻岩", "大理岩", "板岩", "千枚岩", "混合岩", "糜棱岩"],
    "coastal": ["海岸", "海蚀", "海滩", "浪蚀", "滨海", "潮汐", "海积", "岬角", "海岬"],
    "composite": ["综合", "复合", "剖面", "组合"],
}

PLACE_SUFFIXES = ["村", "山", "镇", "湾", "港", "岛", "峰", "岭", "坡", "沟", "滩", "岬", "河", "湖", "海"]

CATEGORY_KEYWORDS = {
    "矿物": ["矿物", "晶体", "石英", "长石", "云母", "角闪石", "辉石", "橄榄石", "方解石", "黄铁矿"],
    "岩石": ["岩石", "岩性", "玄武岩", "花岗岩", "砂岩", "灰岩", "岩体"],
    "构造": ["构造", "褶皱", "断层", "节理", "产状", "走向", "倾向", "倾角", "不整合"],
    "地貌": ["地貌", "地形", "海蚀", "阶地", "冲沟", "河谷"],
    "技能": ["罗盘", "测量", "记录", "采样", "鉴定", "编录", "地质图", "定点", "描述"],
    "安全": ["安全", "防护", "警示", "危险", "急救"],
    "考试": ["考核", "考试", "评分", "成绩", "要求"],
    "路线": ["路线", "观察点", "实习点"],
    "地质背景": ["地质背景", "区域地质", "构造背景"],
}

DIFFICULTY_EASY = ["简单", "入门", "基础", "了解"]
DIFFICULTY_HARD = ["困难", "较难", "复杂", "深入"]

ROUTE_HEADING_RE = re.compile(r"^\s*(?:路线|实习路线|观察路线)\s*[一二三四五六七八九十0-9]*\s*[：:、]\s*")


def analyze(parsed: ParsedDocument) -> AIAnalysisOutput:
    """Rule-based analysis of a parsed document.

    Args:
        parsed: ParsedDocument produced by DocumentParser.

    Returns:
        AIAnalysisOutput with routes, knowledge points and study tasks.
    """
    sections = [s for s in parsed.sections if (s.title or "").strip()]

    # 1. Detect route sections
    route_sections = []
    other_sections = []
    for s in sections:
        if _is_route_heading(s.title):
            route_sections.append(s)
        else:
            other_sections.append(s)

    # 2. Build routes
    routes = []
    for idx, s in enumerate(route_sections):
        route = _build_route(s, order_index=idx + 1)
        if route:
            routes.append(route)

    # 3. Build knowledge points from non-route section headings
    knowledge_points = _build_knowledge_points(other_sections, routes)

    # 4. Build study tasks
    study_tasks = _build_study_tasks(routes, knowledge_points)

    summary = _build_summary(parsed, len(routes), len(knowledge_points))

    output = AIAnalysisOutput(
        summary=summary,
        routes=routes,
        knowledge_points=knowledge_points,
        study_tasks=study_tasks,
    )
    logger.info(
        "Rule analysis: %d routes, %d knowledge points, %d tasks",
        len(routes), len(knowledge_points), len(study_tasks),
    )
    return output


# ── Route detection ─────────────────────────────────────────────

def _is_route_heading(title: str) -> bool:
    """True if a section heading looks like a field route."""
    title = (title or "").strip()
    if not title or len(title) > 60:
        return False
    if ROUTE_HEADING_RE.match(title):
        return True
    # Heuristic: contains a place name AND a geology keyword
    if _extract_places(title) and any(kw in title for kw in ("路线", "实习", "观察", "剖面", "地质")):
        return True
    return False


def _extract_places(text: str) -> list[str]:
    """Extract likely place names like 马山 / 占甲埠村."""
    places = []
    for match in re.finditer(r"[\u4e00-\u9fff]{2,6}(?:" + "|".join(PLACE_SUFFIXES) + r")", text):
        places.append(match.group(0))
    return places


def _classify_geological_type(text: str) -> str:
    text_lower = text.lower()
    for gtype, kws in GEOLOGY_TYPES.items():
        if any(kw in text_lower for kw in kws):
            return gtype
    return "composite"


def _classify_difficulty(text: str) -> str:
    if any(kw in text for kw in DIFFICULTY_HARD):
        return "hard"
    if any(kw in text for kw in DIFFICULTY_EASY):
        return "easy"
    return "medium"


def _detect_duration(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s*天", text)
    if match:
        return float(match.group(1)) * 8
    return None


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。；\n]+", text) if s.strip()]


def _build_route(section, order_index: int) -> AIRouteExtraction | None:
    """Build an AIRouteExtraction from a route section."""
    title = (section.title or "").strip()
    content = (section.content or "").strip()
    text = f"{title}\n{content}"

    places = _extract_places(text)
    location = places[0] if places else (title.split("：")[-1] if "：" in title else title)

    # Clean name: strip heading markers
    name = re.sub(r"^[#\s>]+", "", title)
    name = ROUTE_HEADING_RE.sub("", name).strip() or title

    # Split content into sentences for key points
    sentences = _split_sentences(content)
    key_points = [s for s in sentences if len(s) > 6][:5]
    if not key_points and sentences:
        key_points = sentences[:3]

    # Learning objectives: lines with 目标/目的/学习/掌握
    objectives = [
        s for s in sentences
        if any(kw in s for kw in ("目标", "目的", "学习", "掌握", "理解", "认识"))
    ][:4]

    # Precautions: lines with 注意/安全/小心
    precautions = [
        s for s in sentences
        if any(kw in s for kw in ("注意", "安全", "小心", "禁止"))
    ][:4]

    return AIRouteExtraction(
        name=name or f"路线{order_index}",
        location=location or "威海",
        geological_type=_classify_geological_type(text),
        description=f"{title}\n\n{content}" if content else title,
        difficulty=_classify_difficulty(text),
        duration_hours=_detect_duration(text),
        learning_objectives=objectives,
        key_points=key_points,
        precautions=precautions,
        required_tools=["罗盘", "地质锤", "记录本"],
        order_index=order_index,
    )


# ── Knowledge points ────────────────────────────────────────────

def _classify_category(text: str) -> str:
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "地质背景"


def _build_knowledge_points(
    sections, routes: list[AIRouteExtraction],
) -> list[AIKnowledgePoint]:
    """Create knowledge points from non-route section headings + key content."""
    points: list[AIKnowledgePoint] = []
    for s in sections[:40]:
        title = (s.title or "").strip()
        content = (s.content or "").strip()
        if not title or len(title) > 50:
            continue
        text = f"{title}\n{content}"
        sentences = _split_sentences(content)
        # Take the first substantive sentence as the explanation
        detail = next((x for x in sentences if len(x) > 10), content[:300] or title)
        keywords = [w for w in re.findall(r"[\u4e00-\u9fff]{2,6}", title) if len(w) >= 2][:5]
        related_route = None
        for route in routes:
            if any(kw in title for kw in (route.location, route.name[:4])):
                related_route = route.name
                break
        points.append(AIKnowledgePoint(
            category=_classify_category(text),
            title=title,
            content=detail,
            difficulty=_classify_difficulty(text),
            keywords=keywords or [title[:4]],
            related_route_name=related_route,
        ))
    return points


# ── Study tasks ─────────────────────────────────────────────────

def _build_study_tasks(
    routes: list[AIRouteExtraction],
    knowledge_points: list[AIKnowledgePoint],
) -> list[AIStudyTask]:
    """Generate a practice schedule: intro → each route → review/exam."""
    tasks: list[AIStudyTask] = []

    tasks.append(AIStudyTask(
        date_offset=0,
        task_name="实习前准备与整体了解",
        content=(
            "了解本次野外实习的整体安排，熟悉实习路线与安全须知，"
            "预习路线背景知识，准备罗盘、地质锤、记录本等工具。"
        ),
        priority="high",
        category="技能",
    ))

    for i, route in enumerate(routes):
        day = i + 1
        route_tasks = [
            (f"路线{day}：{route.name} — 实地考察",
             f"前往{route.location}，按顺序观察下列要点：{'；'.join(route.key_points) if route.key_points else '观察地层与构造现象'}。"
             f"注意安全事项：{'；'.join(route.precautions) if route.precautions else '听从老师安排'}。",
             "high", "路线"),
        ]
        if route.learning_objectives:
            route_tasks.append(
                (f"路线{day}：{route.name} — 完成学习目标",
                 "；".join(route.learning_objectives),
                 "medium", "技能"),
            )
        for name, content, priority, category in route_tasks:
            tasks.append(AIStudyTask(
                date_offset=day,
                task_name=name,
                content=content,
                priority=priority,
                category=category,
                related_route_name=route.name,
            ))

    # Add knowledge review tasks (spread across remaining days)
    review_start = len(routes) + 1
    for i, kp in enumerate(knowledge_points[:6]):
        tasks.append(AIStudyTask(
            date_offset=review_start + i,
            task_name=f"复习：{kp.title}",
            content=kp.content,
            priority="medium",
            category=kp.category,
        ))

    # Final exam review
    tasks.append(AIStudyTask(
        date_offset=review_start + min(len(knowledge_points), 6),
        task_name="综合复习与考核准备",
        content="回顾所有路线的观察要点与知识点，整理野外记录，准备实习考核。",
        priority="high",
        category="考试",
    ))

    return tasks


# ── Summary ─────────────────────────────────────────────────────

def _build_summary(parsed: ParsedDocument, route_count: int, kp_count: int) -> str:
    filename = parsed.filename or ""
    if not filename and parsed.sections:
        filename = parsed.sections[0].title or ""
    return (
        f"本材料《{filename[:60]}》共 {parsed.total_pages} 页、"
        f"{len(parsed.sections)} 个章节。通过分析自动提取出 {route_count} 条实习路线、"
        f"{kp_count} 个地质知识点，并据此生成学习计划。"
        "（本分析由设备端规则引擎生成，未调用外部大模型）"
    )
