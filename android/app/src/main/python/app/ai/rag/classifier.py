"""Geology content classifier — auto-detects categories from text patterns.

No ML model needed — uses keyword + pattern matching tuned for
the Weihai geology field practice domain.
"""

import re
from dataclasses import dataclass, field


# ── Category definitions ──────────────────────────────────────

CATEGORY_PATTERNS: dict[str, list[str]] = {
    "矿物": [
        r"(石英|斜长石|钾长石|角闪石|辉石|橄榄石|黑云母|方解石|白云母)",
        r"(莫氏硬度|解理|光泽|断口|晶面|双晶|条痕)",
        r"(矿物.*鉴定|造岩矿物|矿物成分)",
    ],
    "岩石": [
        r"(花岗岩|玄武岩|沉积岩|片麻岩|大理岩|榴辉岩|闪长岩|辉长岩)",
        r"(火山角砾岩|凝灰岩|碎屑岩|石灰岩|砂岩|页岩)",
        r"(岩浆岩|火成岩|沉积岩|变质岩|侵入岩|喷出岩)",
        r"(岩石.*观察|岩石.*描述|岩性|定名)",
        r"(等粒|似斑状|块状构造|气孔构造|杏仁构造|柱状节理)",
    ],
    "构造": [
        r"(断层|节理|褶皱|劈理|片理|线理|面理)",
        r"(走向|倾向|倾角|产状|岩层)",
        r"(变形构造|石香肠|布丁构造|显微构造)",
        r"(穿切关系|侵入.*期次|相对.*年代)",
    ],
    "路线": [
        r"(路线[一二三四五六七])",
        r"(占甲埠|马山|福山|棉花山|刘公岛|鸡鸣岛|奔腾码头|黄沟村|朝阳港|那香海|龙王庙)",
        r"(教学安排|路线.*内容|路线.*任务|路线小结)",
        r"(观察点|教学内容与目标|注意事项)",
    ],
    "安全规范": [
        r"(严禁|禁止|注意安全|一票否决|成绩.*0\s*分)",
        r"(长衣.*长裤|硬底.*运动鞋|三大件|罗盘.*放大镜.*地质锤)",
        r"(下海游泳|中暑|陡崖|滚石|交通安全)",
        r"(安全.*规定|安全.*管理|野外.*规范)",
    ],
    "考试重点": [
        r"(考核|考试|评分|成绩|及格|满分)",
        r"(高频.*考点|易错|难点|重点掌握|必须掌握)",
        r"(一票否决|基本技能.*考核)",
        r"(备考|复习|知识点.*总结)",
    ],
    "技能": [
        r"(罗盘.*使用|产状.*测量|磁偏角|水准器)",
        r"(野簿.*记录|地质素描|素描图|记录格式)",
        r"(放大镜.*使用|标本.*采集|样品.*编号)",
        r"(地质.*基本技能|野外.*工作.*方法)",
    ],
    "地貌": [
        r"(风化|侵蚀|搬运|沉积|海蚀|海浪)",
        r"(海岸|沙滩|沙坝|海蚀崖|海蚀穴|海蚀平台)",
        r"(外动力|内动力|地质作用|水动力)",
        r"(基岩海岸|沙质海岸|生物海岸)",
    ],
}


# ── Location patterns ─────────────────────────────────────────

LOCATIONS: dict[str, list[str]] = {
    "占甲埠村": ["占甲埠", "路线一"],
    "烟台福山马山": ["马山", "福山", "路线二", "古火山"],
    "乳山棉花山": ["棉花山", "路线三", "龙旺庄"],
    "刘公岛": ["刘公岛", "路线四", "甲午"],
    "鸡鸣岛": ["鸡鸣岛", "路线五", "朝阳港", "那香海"],
    "奔腾码头": ["奔腾码头", "路线六", "龙王庙"],
    "黄沟村": ["黄沟村", "路线七", "伟德山"],
}


# ── Rock type patterns ────────────────────────────────────────

ROCK_TYPES: dict[str, list[str]] = {
    "花岗岩": ["花岗岩", "花岗", "玲珑岩体", "伟德山岩体", "钾长石.*花岗"],
    "玄武岩": ["玄武岩", "玄武", "柱状节理", "气孔构造", "杏仁构造"],
    "沉积岩": ["沉积岩", "碎屑岩", "龙旺庄组", "层理", "波痕", "泥裂", "化石"],
    "片麻岩": ["片麻岩", "花岗片麻岩", "长英质片麻岩"],
    "大理岩": ["大理岩", "大理"],
    "榴辉岩": ["榴辉岩", "榴辉"],
}


# ── Mineral patterns ──────────────────────────────────────────

MINERALS: dict[str, list[str]] = {
    "石英": ["石英", "油脂光泽", "贝壳状断口"],
    "斜长石": ["斜长石", "聚片双晶", "灰白.*长石"],
    "钾长石": ["钾长石", "卡氏双晶", "肉红.*长石"],
    "角闪石": ["角闪石", "56.*124", "长柱状.*闪石"],
    "辉石": ["辉石", "87.*93", "短柱状.*辉石"],
    "橄榄石": ["橄榄石", "蛇纹石", "橄榄绿"],
    "黑云母": ["黑云母", "云母"],
}


# ── Difficulty ────────────────────────────────────────────────

DIFFICULTY_PATTERNS: dict[str, list[str]] = {
    "重点": ["重点", "必考", "高频", "一票否决", "必须掌握", "核心"],
    "进阶": ["理解", "分析", "对比", "区别", "判断"],
    "基础": ["认识", "了解", "识别", "观察", "描述"],
}


@dataclass
class ChunkMetadata:
    """Rich metadata extracted from a geology text chunk."""

    category: str = "general"         # 矿物 | 岩石 | 构造 | 路线 | 安全规范 | 考试重点 | 技能 | 地貌
    location: str | None = None       # 占甲埠村 | 马山 | 棉花山 | ...
    rock_type: str | None = None      # 花岗岩 | 玄武岩 | 沉积岩 | ...
    mineral: str | None = None        # 石英 | 斜长石 | 角闪石 | ...
    difficulty: str = "基础"          # 重点 | 进阶 | 基础
    keywords: list[str] = field(default_factory=list)
    route_number: str | None = None   # 路线一 | 路线二 | ...


class GeologyClassifier:
    """Classifies geology text chunks using keyword pattern matching.

    Designed for the specific Weihai field practice domain —
    the patterns are tuned to the two course PDFs.
    """

    def classify(self, text: str) -> ChunkMetadata:
        """Extract structured metadata from a chunk of geology text.

        Args:
            text: The text content to classify.

        Returns:
            ChunkMetadata with category, location, rock_type, etc.
        """
        text_lower = text.lower()  # not strictly needed for Chinese, but harmless
        text_200 = text[:200]  # first 200 chars carry most signal

        return ChunkMetadata(
            category=self._detect_category(text, text_200),
            location=self._detect_location(text),
            rock_type=self._detect_rock_type(text),
            mineral=self._detect_mineral(text),
            difficulty=self._detect_difficulty(text),
            keywords=self._extract_keywords(text),
            route_number=self._detect_route_number(text),
        )

    def _detect_category(self, text: str, text_200: str) -> str:
        """Detect the primary category. First 200 chars weighted higher."""
        scores: dict[str, int] = {}

        for category, patterns in CATEGORY_PATTERNS.items():
            score = 0
            for pat in patterns:
                # Full text matches
                full_matches = len(re.findall(pat, text))
                # First-200-char matches (weighted 3x)
                head_matches = len(re.findall(pat, text_200))
                score += full_matches + head_matches * 2
            scores[category] = score

        if not scores or max(scores.values()) == 0:
            return "general"

        return max(scores, key=scores.get)

    def _detect_location(self, text: str) -> str | None:
        """Detect which field location this chunk refers to."""
        scores: dict[str, int] = {}
        for location, patterns in LOCATIONS.items():
            score = 0
            for pat in patterns:
                score += len(re.findall(pat, text))
            if score > 0:
                scores[location] = score

        if not scores:
            return None
        return max(scores, key=scores.get)

    def _detect_rock_type(self, text: str) -> str | None:
        """Detect rock type mentioned."""
        for rock, patterns in ROCK_TYPES.items():
            for pat in patterns:
                if re.search(pat, text):
                    return rock
        return None

    def _detect_mineral(self, text: str) -> str | None:
        """Detect mineral mentioned."""
        for mineral, patterns in MINERALS.items():
            for pat in patterns:
                if re.search(pat, text):
                    return mineral
        return None

    def _detect_difficulty(self, text: str) -> str:
        """Detect difficulty/importance level."""
        for level, patterns in DIFFICULTY_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text):
                    return level
        return "基础"

    def _detect_route_number(self, text: str) -> str | None:
        """Detect route number (路线一 ~ 路线七)."""
        match = re.search(r"路线([一二三四五六七])", text)
        if match:
            num_map = {"一": "1", "二": "2", "三": "3", "四": "4",
                       "五": "5", "六": "6", "七": "7"}
            cn = match.group(1)
            return f"路线{cn} (Route {num_map.get(cn, cn)})"
        return None

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract key geology terms for enhanced search."""
        keyword_sources = [
            r"((?:花岗|玄武|沉积|变质|岩浆|火山|侵入|喷出)(?:岩))",
            r"((?:石英|斜长石|钾长石|角闪石|辉石|橄榄石|黑云母|方解石))",
            r"((?:断层|节理|褶皱|劈理|片理|产状|走向|倾向|倾角))",
            r"((?:罗盘|野簿|放大镜|地质锤|三大件))",
            r"((?:海蚀|风化|侵蚀|搬运|沉积|柱状节理|气孔构造|杏仁构造))",
            r"((?:路线[一二三四五六七]))",
            r"((?:占甲埠|马山|棉花山|刘公岛|鸡鸣岛|奔腾码头|黄沟村))",
            r"((?:一票否决|安全|严禁|考核|考试))",
        ]

        keywords: set[str] = set()
        for pat in keyword_sources:
            for m in re.finditer(pat, text):
                kw = m.group(1).strip()
                if len(kw) >= 2:
                    keywords.add(kw)

        return list(keywords)[:10]  # Cap at 10 keywords


# Singleton
_classifier: GeologyClassifier | None = None


def get_classifier() -> GeologyClassifier:
    global _classifier
    if _classifier is None:
        _classifier = GeologyClassifier()
    return _classifier
