"""PDF text extraction using PyMuPDF (fitz).

Extracts plain text with page numbers, detects section headings,
and splits content into hierarchical sections.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


# ── Data classes ──────────────────────────────────────────────

@dataclass
class PDFPage:
    """A single page of extracted PDF content."""
    page_number: int
    text: str


@dataclass
class PDFDocument:
    """Extracted PDF content ready for chunking."""
    filename: str
    total_pages: int
    pages: list[PDFPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


@dataclass
class DocumentSection:
    """A single section within a parsed document."""
    index: int
    title: str | None          # detected heading
    content: str               # full text of this section
    page_start: int            # first page of this section
    page_end: int              # last page of this section
    level: int = 1             # heading level (1=top, 2=sub, 3=detail)
    parent_index: int | None = None  # index of parent section


@dataclass
class ParsedDocument:
    """Complete parsed result of a PDF."""
    filename: str
    total_pages: int
    total_chars: int
    sections: list[DocumentSection] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict for database storage."""
        return {
            "filename": self.filename,
            "total_pages": self.total_pages,
            "total_chars": self.total_chars,
            "sections": [
                {
                    "index": s.index,
                    "title": s.title,
                    "content": s.content,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                    "level": s.level,
                    "parent_index": s.parent_index,
                }
                for s in self.sections
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedDocument":
        """Deserialize from database JSON."""
        return cls(
            filename=data["filename"],
            total_pages=data["total_pages"],
            total_chars=data["total_chars"],
            sections=[
                DocumentSection(
                    index=s["index"],
                    title=s.get("title"),
                    content=s["content"],
                    page_start=s["page_start"],
                    page_end=s["page_end"],
                    level=s.get("level", 1),
                    parent_index=s.get("parent_index"),
                )
                for s in data["sections"]
            ],
        )


# ── Heading patterns ──────────────────────────────────────────

# Level 1: Major chapter/section markers
LEVEL1_PATTERNS = [
    r"^[一二三四五六七八九十]+[、．.]\s*\S",     # 一、野外基本技能
    r"^第[一二三四五六七八九十\d]+[章节]\s",      # 第一章 / 第1节
    r"^路线[一二三四五六七][：:]\s*",             # 路线一：占甲埠村
    r"^#{1,3}\s+",                                 # Markdown heading
]

# Level 2: Sub-section markers
LEVEL2_PATTERNS = [
    r"^\d+[\.、．]\s+\S",                          # 1. 罗盘使用
    r"^[（(][一二三四五六七八九十\d]+[）)]\s*",    # (一) (1)
    r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*",                    # ①
]

# Level 3: Detail markers (inline labels, bold terms)
LEVEL3_PATTERNS = [
    r"^[\w一-鿿]{2,10}[：:]\s*\S",         # 走向：/Strike:
    r"^⚠️\s*",                                      # ⚠️ warning
    r"^💡\s*",                                      # 💡 tip
    r"^►\s*",                                       # ► bullet
]

def _detect_heading_level(line: str) -> int:
    """Detect heading level of a single line. Returns 0 if not a heading."""
    line = line.strip()
    if not line or len(line) > 80:
        return 0

    for pat in LEVEL1_PATTERNS:
        if re.match(pat, line):
            return 1
    for pat in LEVEL2_PATTERNS:
        if re.match(pat, line):
            return 2
    for pat in LEVEL3_PATTERNS:
        if re.match(pat, line):
            return 3

    # Heuristic: short lines (<30 chars) that don't end with punctuation
    # and contain geology keywords are likely headings
    if len(line) < 30 and not re.search(r"[。，、；：！？\)]$", line):
        geology_kw = [
            "路线", "观察", "鉴定", "识别", "规范", "注意", "考核",
            "矿物", "岩石", "构造", "地貌", "安全", "技能", "总结",
            "教学", "目的", "背景", "任务", "要求", "方法", "特征",
            "实习", "野外", "记录", "测量", "使用",
        ]
        if any(kw in line for kw in geology_kw):
            return 2

    return 0


# ── Extraction ────────────────────────────────────────────────

def extract_pdf_text(file_path: str | Path) -> PDFDocument:
    """Extract all text from a PDF file, preserving page structure."""
    import fitz

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(str(file_path))
    total_pages = doc.page_count
    pages: list[PDFPage] = []

    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        if text:
            pages.append(PDFPage(page_number=i, text=text))

    doc.close()

    return PDFDocument(
        filename=file_path.name,
        total_pages=total_pages,
        pages=pages,
    )


def extract_section_headings(text: str) -> list[str]:
    """Detect probable section/chapter headings from text."""
    headings = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) > 60:
            continue
        if _detect_heading_level(line) > 0:
            headings.append(line)
    return headings


# ── Section splitting ─────────────────────────────────────────

def split_into_sections(pages: list[PDFPage]) -> ParsedDocument:
    """Split extracted PDF pages into hierarchical sections.

    Strategy:
    1. Scan all lines across all pages to find heading boundaries.
    2. Split text at each heading, assigning a level and page range.
    3. Handle orphan content (text before the first heading).

    Args:
        pages: List of PDFPage from extract_pdf_text().

    Returns:
        ParsedDocument with structured sections.
    """
    sections: list[DocumentSection] = []
    current_section: dict | None = None  # {title, level, content_lines, page_start, page_end}
    total_chars = 0

    for page in pages:
        lines = page.text.split("\n")
        total_chars += len(page.text)

        for line in lines:
            stripped = line.strip()
            level = _detect_heading_level(stripped) if stripped else 0

            if level > 0 and level <= 2:
                # Save previous section
                if current_section and current_section["content_lines"]:
                    _finalize_section(current_section, sections)

                # Start new section
                current_section = {
                    "title": stripped,
                    "level": level,
                    "content_lines": [],
                    "page_start": page.page_number,
                    "page_end": page.page_number,
                }
            elif current_section is not None:
                current_section["content_lines"].append(line)
                current_section["page_end"] = page.page_number
            else:
                # Text before first heading → create a preamble section
                if stripped:
                    if current_section is None:
                        current_section = {
                            "title": None,
                            "level": 0,
                            "content_lines": [],
                            "page_start": page.page_number,
                            "page_end": page.page_number,
                        }
                    current_section["content_lines"].append(line)
                    current_section["page_end"] = page.page_number

    # Save final section
    if current_section and current_section["content_lines"]:
        _finalize_section(current_section, sections)

    # Filter out empty sections and re-index
    sections = [s for s in sections if s.content.strip()]
    for i, s in enumerate(sections):
        s.index = i

    filename = pages[0].text[:50] if pages else ""
    return ParsedDocument(
        filename=filename,
        total_pages=len(pages),
        total_chars=total_chars,
        sections=sections,
    )


def _finalize_section(sec: dict, sections: list[DocumentSection]) -> None:
    """Convert a raw section dict to a DocumentSection and append."""
    content = "\n".join(sec["content_lines"]).strip()
    if not content and not sec["title"]:
        return

    # Determine parent: previous section at a higher level
    parent_index = None
    for prev in reversed(sections):
        if prev.level < sec["level"]:
            parent_index = prev.index
            break

    sections.append(DocumentSection(
        index=len(sections),
        title=sec.get("title"),
        content=content,
        page_start=sec["page_start"],
        page_end=sec["page_end"],
        level=sec.get("level", 1),
        parent_index=parent_index,
    ))


# ── Convenience ───────────────────────────────────────────────

def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """One-shot: extract + split a PDF into sections."""
    doc = extract_pdf_text(file_path)
    return split_into_sections(doc.pages)
