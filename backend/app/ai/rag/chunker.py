"""Semantic text chunking for Chinese geology field-practice documents.

Enhanced for Weihai geology PDFs:
- Recognizes route headers, mineral tables, safety warnings
- Auto-classifies each chunk (category, location, rock_type, etc.)
- Preserves table structures as coherent chunks
"""

import re
from dataclasses import dataclass, field

from app.ai.rag.classifier import ChunkMetadata, get_classifier


@dataclass
class Chunk:
    """A single text chunk with content + classification metadata."""

    content: str
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    content_type: str = "text"
    metadata: ChunkMetadata | None = None

    @property
    def token_count(self) -> int:
        chinese_chars = len(re.findall(r"[一-鿿]", self.content))
        english_words = len(re.findall(r"[a-zA-Z]+", self.content))
        return int(chinese_chars * 1.5 + english_words * 1.3)


# ── Patterns ──────────────────────────────────────────────────

# Standard academic headings
HEADING_PATTERNS = [
    r"^#{1,3}\s+",
    r"^第[一二三四五六七八九十\d]+[章节]",
    r"^\d+(\.\d+)+\s+",
    r"^[一二三四五六七八九十]+[、．.]",
    r"^[（(][一二三四五六七八九十\d]+[）)]",
]

# Geology-specific structural markers (weighted as "always split here")
GEOLOGY_MARKERS = [
    # Route headers: "路线一：占甲埠村岩浆岩路线"
    r"^路线[一二三四五六七][：:]\s*",
    # Station teaching: "站内教学："
    r"^站内教学[：:]",
    # Major sections from the knowledge summary
    r"^[一二三四五六七八九十]、\s*(野外基本技能|核心造岩矿物|三大类岩石|外动力|.*海岸|七条实习|考核规则)",
    # Safety section: "一些重要注意点"
    r"^(一些重要|注意[事项点]|安全.*规范)",
    # Mineral tables: "矿物名称"
    r"^(矿物名称|主要物理特征|野外易混淆)",
    # Route detail: "路线编号"
    r"^(路线编号|路线名称)",
    # Skill section
    r"^(罗盘.*使用|野簿.*记录|地质素描|放大镜.*使用)",
]

HEADING_RE = re.compile("|".join(HEADING_PATTERNS), re.MULTILINE)
GEOLOGY_MARKER_RE = re.compile("|".join(GEOLOGY_MARKERS), re.MULTILINE)
SENTENCE_END_RE = re.compile(r"[。！？；](?![」』】）\)])")


class DocumentChunker:
    """Splits geology PDFs into semantically coherent, classified chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.classifier = get_classifier()

    def chunk_pages(
        self, pages: list[tuple[int, str]], document_title: str = ""
    ) -> list[Chunk]:
        """Chunk a list of (page_number, text) into classified chunks.

        Uses document_title as extra signal for metadata extraction.
        """
        chunks: list[Chunk] = []
        chunk_index = 0

        full_text = "\n".join(text for _, text in pages)

        for page_num, page_text in pages:
            # Split by headings (standard + geology-specific)
            sections = self._split_by_headings(page_text)

            for section_title, section_text in sections:
                sub_chunks = self._split_oversized(section_text)
                for sub in sub_chunks:
                    # Classify with metadata
                    meta = self.classifier.classify(sub)

                    # Boost: if document_title contains route/location info, propagate
                    if not meta.location:
                        meta.location = self._extract_location_from_title(document_title)

                    chunks.append(Chunk(
                        content=sub,
                        chunk_index=chunk_index,
                        page_number=page_num,
                        section_title=section_title,
                        metadata=meta,
                    ))
                    chunk_index += 1

        return chunks

    # ── Heading splitting ──────────────────────────────────

    def _split_by_headings(self, text: str) -> list[tuple[str | None, str]]:
        """Split text by both standard and geology-specific headings."""
        lines = text.split("\n")
        sections: list[tuple[str | None, str]] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            is_heading = False
            # Check geology markers first (higher priority)
            if GEOLOGY_MARKER_RE.match(stripped) and len(stripped) < 100:
                is_heading = True
            # Then standard headings
            elif HEADING_RE.match(stripped) and len(stripped) < 80:
                is_heading = True
            # Bold-like short lines (often section titles in PDFs)
            elif len(stripped) < 40 and (
                "：" not in stripped and
                "。" not in stripped and
                any(kw in stripped for kw in [
                    "路线", "观察", "鉴定", "识别", "规范", "注意", "考核",
                    "矿物", "岩石", "构造", "地貌", "安全", "技能", "总结",
                ])
            ):
                is_heading = True

            if is_heading:
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content and len(content) > 10:
                        sections.append((current_heading, content))
                current_heading = stripped
                current_lines = []
            else:
                current_lines.append(line)

        # Last section
        if current_lines:
            content = "\n".join(current_lines).strip()
            if content and len(content) > 10:
                sections.append((current_heading, content))

        if not sections:
            text = text.strip()
            if text and len(text) > 10:
                sections.append((None, text))

        return sections

    # ── Size splitting ─────────────────────────────────────

    def _split_oversized(self, text: str) -> list[str]:
        """Split oversized text at sentence boundaries."""
        if not text.strip():
            return []

        chinese = len(re.findall(r"[一-鿿]", text)) * 1.5
        english = len(re.findall(r"[a-zA-Z]+", text)) * 1.3
        est_tokens = int(chinese + english)

        if est_tokens <= self.chunk_size:
            return [text]

        sentences = SENTENCE_END_RE.split(text)
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            sent_chinese = len(re.findall(r"[一-鿿]", sent)) * 1.5
            sent_english = len(re.findall(r"[a-zA-Z]+", sent)) * 1.3
            sent_tokens = int(sent_chinese + sent_english)

            if current_tokens + sent_tokens > self.chunk_size and current:
                chunks.append("。".join(current) + "。")
                # Overlap
                if current:
                    overlap_sent = current[-1]
                    current = [overlap_sent]
                    ov_chinese = len(re.findall(r"[一-鿿]", overlap_sent)) * 1.5
                    ov_english = len(re.findall(r"[a-zA-Z]+", overlap_sent)) * 1.3
                    current_tokens = int(ov_chinese + ov_english)
                else:
                    current = []
                    current_tokens = 0

            current.append(sent)
            current_tokens += sent_tokens

        if current:
            chunks.append("。".join(current) + "。")

        return chunks

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_location_from_title(title: str) -> str | None:
        """Extract location name from document title."""
        locations = [
            "占甲埠", "马山", "福山", "棉花山", "刘公岛",
            "鸡鸣岛", "奔腾码头", "黄沟村", "朝阳港", "那香海", "龙王庙",
        ]
        for loc in locations:
            if loc in title:
                return loc
        return None


def create_chunker(chunk_size: int = 500, chunk_overlap: int = 50) -> DocumentChunker:
    return DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
