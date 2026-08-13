"""Enhanced RAG retriever with query understanding and metadata filtering.

Key improvements:
1. Query analysis: auto-detect category/location from the question
2. Metadata-filtered search: narrow results to relevant categories
3. Multi-strategy: semantic + metadata-aware retrieval
"""

import logging
import re

from app.ai.rag.chunker import DocumentChunker, create_chunker
from app.ai.rag.embeddings import embed_query, embed_texts
from app.ai.rag.store import (
    SearchResult,
    add_chunks,
    delete_document_chunks,
    get_available_filters,
    get_collection_stats,
    search,
)
from app.ai.rag.classifier import get_classifier

logger = logging.getLogger(__name__)


class QueryIntent:
    """Parsed intent from a user's natural language query."""

    def __init__(self, query: str):
        self.raw = query
        self.category: str | None = None
        self.location: str | None = None
        self.rock_type: str | None = None
        self.mineral: str | None = None
        self.difficulty: str | None = None
        self._parse()

    def _parse(self):
        """Extract structured intent from the query using pattern matching."""
        # Location detection: "马山路线需要看什么？" → location="马山"
        location_map = {
            "占甲埠": "占甲埠村",
            "马山": "烟台福山马山",
            "福山": "烟台福山马山",
            "棉花山": "乳山棉花山",
            "乳山": "乳山棉花山",
            "刘公岛": "刘公岛",
            "鸡鸣岛": "鸡鸣岛",
            "朝阳港": "鸡鸣岛",
            "那香海": "鸡鸣岛",
            "奔腾码头": "奔腾码头",
            "龙王庙": "奔腾码头",
            "黄沟村": "黄沟村",
        }
        for keyword, location in location_map.items():
            if keyword in self.raw:
                self.location = location
                break

        # Rock type detection
        rock_map = {
            "花岗岩": "花岗岩", "花岗": "花岗岩",
            "玄武岩": "玄武岩", "玄武": "玄武岩",
            "沉积岩": "沉积岩", "沉积": "沉积岩",
            "片麻岩": "片麻岩",
            "大理岩": "大理岩", "大理": "大理岩",
            "榴辉岩": "榴辉岩",
        }
        for keyword, rock in rock_map.items():
            if keyword in self.raw:
                self.rock_type = rock
                break

        # Mineral detection
        mineral_map = {
            "石英": "石英", "斜长石": "斜长石", "钾长石": "钾长石",
            "角闪石": "角闪石", "辉石": "辉石", "橄榄石": "橄榄石",
            "黑云母": "黑云母",
        }
        for keyword, mineral in mineral_map.items():
            if keyword in self.raw:
                self.mineral = mineral
                break

        # Category detection from query keywords
        category_patterns = [
            (r"(什么矿物|矿物.*鉴定|矿物.*区别|造岩矿物)", "矿物"),
            (r"(什么岩石|岩石.*鉴定|岩石.*类型|.*岩.*特征)", "岩石"),
            (r"(构造|断层|节理|褶皱|产状|走向|倾向)", "构造"),
            (r"(路线|马山|占甲埠|棉花山|刘公岛|鸡鸣岛|奔腾码头|黄沟村)", "路线"),
            (r"(安全|严禁|禁止|注意|规范|要求|必须)", "安全规范"),
            (r"(考试|考核|复习|重点|一票否决|及格|评分)", "考试重点"),
            (r"(技能|罗盘|野簿|素描|测量|方法|怎么用)", "技能"),
            (r"(地貌|海岸|风化|侵蚀|海蚀|沙滩)", "地貌"),
        ]
        for pat, cat in category_patterns:
            if re.search(pat, self.raw):
                self.category = cat
                break

        # Difficulty
        if any(w in self.raw for w in ["重点", "必考", "核心", "高频", "一票否决"]):
            self.difficulty = "重点"
        elif any(w in self.raw for w in ["区别", "对比", "分析", "理解"]):
            self.difficulty = "进阶"

    @property
    def filter_description(self) -> str:
        parts = []
        if self.category: parts.append(f"分类={self.category}")
        if self.location: parts.append(f"地点={self.location}")
        if self.rock_type: parts.append(f"岩石={self.rock_type}")
        if self.mineral: parts.append(f"矿物={self.mineral}")
        return ", ".join(parts) if parts else "无过滤器"


class Retriever:
    """Main entry point for RAG operations with geology metadata support."""

    def __init__(self, chunker: DocumentChunker | None = None):
        self.chunker = chunker or create_chunker()
        self.classifier = get_classifier()

    # ── Ingestion ──────────────────────────────────────────────

    def ingest_document(
        self,
        pages: list[tuple[int, str]],
        document_id: int,
        document_title: str,
    ) -> int:
        """Ingest a document with full geology metadata extraction.

        1. Chunk text (geology-aware chunking)
        2. Classify each chunk (metadata extraction)
        3. Generate embeddings
        4. Store in ChromaDB with metadata
        """
        # 1. Chunk with geology-aware splitting + auto-classification
        raw_chunks = self.chunker.chunk_pages(pages, document_title=document_title)

        if not raw_chunks:
            logger.warning("No chunks produced for document %d: %s", document_id, document_title)
            return 0

        # 2. Build chunk dicts with metadata from classifier
        chunk_dicts = []
        for c in raw_chunks:
            meta = c.metadata or self.classifier.classify(c.content)

            chunk_dicts.append({
                "content": c.content,
                "document_id": document_id,
                "document_title": document_title,
                "page_number": c.page_number,
                "section_title": c.section_title,
                "chunk_index": c.chunk_index,
                # Geology metadata
                "category": meta.category,
                "location": meta.location or "",
                "rock_type": meta.rock_type or "",
                "mineral": meta.mineral or "",
                "difficulty": meta.difficulty,
                "route_number": meta.route_number or "",
                "keywords": meta.keywords,
            })

        # 3. Generate embeddings
        texts = [c["content"] for c in chunk_dicts]
        logger.info("Generating embeddings for %d chunks...", len(texts))
        embeddings = embed_texts(texts)

        # 4. Store in ChromaDB
        chroma_ids = add_chunks(chunk_dicts, embeddings)

        # Log metadata distribution
        categories = {}
        for c in chunk_dicts:
            cat = c["category"]
            categories[cat] = categories.get(cat, 0) + 1
        logger.info(
            "Ingested doc %d (%s): %d chunks. Categories: %s",
            document_id, document_title, len(chroma_ids), categories,
        )
        return len(chroma_ids)

    # ── Search ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: int | None = None,
        category: str | None = None,
        location: str | None = None,
        rock_type: str | None = None,
        mineral: str | None = None,
        difficulty: str | None = None,
        auto_filter: bool = True,
    ) -> list[SearchResult]:
        """Semantic search with automatic query understanding.

        Args:
            query: Natural language query (Chinese).
            top_k: Number of results.
            document_id: Optional: restrict to a specific document.
            category/location/rock_type/mineral/difficulty: Explicit metadata filters.
            auto_filter: If True (default), auto-detect filters from the query.

        Returns:
            Ranked search results with metadata.

        Strategy:
            When auto_filter is enabled:
            1. Parse query intent (location? rock type? category?)
            2. First try: filtered search with detected intent
            3. Fallback: unfiltered search if filtered returns too few results
        """
        # Parse query intent
        intent = QueryIntent(query)

        # Merge explicit filters with auto-detected ones
        # (explicit params override auto-detected)
        final_category = category or intent.category
        final_location = location or intent.location
        final_rock_type = rock_type or intent.rock_type
        final_mineral = mineral or intent.mineral
        final_difficulty = difficulty or intent.difficulty

        has_filters = any([
            document_id, final_category, final_location,
            final_rock_type, final_mineral, final_difficulty,
        ])

        logger.info(
            "Search: '%s' → intent: %s, filters: cat=%s loc=%s rock=%s mineral=%s",
            query[:80], intent.filter_description,
            final_category, final_location, final_rock_type, final_mineral,
        )

        # Generate query embedding
        query_embedding = embed_query(query)

        # Strategy: Try filtered search first, fall back to unfiltered
        results = search(
            query_embedding=query_embedding,
            top_k=top_k,
            document_id=document_id,
            category=final_category,
            location=final_location,
            rock_type=final_rock_type,
            mineral=final_mineral,
            difficulty=final_difficulty,
        )

        # If filtered search returns too few results, fall back
        if has_filters and auto_filter and len(results) < 3:
            logger.info(
                "Filtered search returned only %d results, falling back to unfiltered",
                len(results),
            )
            fallback_results = search(
                query_embedding=query_embedding,
                top_k=top_k,
                document_id=document_id,
                # No category/location filters
            )
            # Merge: filtered results first, then unique fallback results
            seen_ids = {r.chunk_id for r in results}
            for r in fallback_results:
                if r.chunk_id not in seen_ids:
                    results.append(r)
                    seen_ids.add(r.chunk_id)
            results = results[:top_k]

        logger.info(
            "Search '%s': %d results (top score: %.3f)",
            query[:60], len(results),
            results[0].score if results else 0,
        )

        return results

    # ── Management ─────────────────────────────────────────────

    def delete_document(self, document_id: int) -> int:
        return delete_document_chunks(document_id)

    def stats(self) -> dict:
        return get_collection_stats()

    def available_filters(self) -> dict:
        return get_available_filters()
