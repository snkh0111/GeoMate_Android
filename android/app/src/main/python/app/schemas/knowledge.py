"""Pydantic schemas for knowledge base API — with geology metadata."""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Document ──────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: int
    title: str
    filename: str
    file_type: str
    status: str
    chunk_count: int
    file_size: int | None = None
    error_message: str | None = None
    created_at: datetime

    class Config:
        orm_mode = True


class DocumentListOut(BaseModel):
    total: int
    items: list[DocumentOut]


# ── Search ────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Semantic search request with optional metadata filters."""
    query: str = Field(..., min_length=1, max_length=1000, description="搜索查询（中文）")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    document_id: int | None = Field(default=None, description="限定搜索范围到指定文档")

    # Metadata filters (all optional — auto-detected from query if omitted)
    category: str | None = Field(
        default=None,
        description="分类筛选: 矿物|岩石|构造|路线|安全规范|考试重点|技能|地貌",
    )
    location: str | None = Field(
        default=None,
        description="地点筛选: 占甲埠村|马山|棉花山|刘公岛|鸡鸣岛|奔腾码头|黄沟村",
    )
    rock_type: str | None = Field(
        default=None,
        description="岩石类型筛选: 花岗岩|玄武岩|沉积岩|片麻岩|大理岩|榴辉岩",
    )
    mineral: str | None = Field(
        default=None,
        description="矿物筛选: 石英|斜长石|钾长石|角闪石|辉石|橄榄石",
    )
    difficulty: str | None = Field(
        default=None,
        description="重要度筛选: 重点|进阶|基础",
    )
    auto_filter: bool = Field(
        default=True,
        description="是否自动从查询中识别意图并应用过滤器",
    )


class SearchResultItem(BaseModel):
    """A single search result with geology metadata."""
    chunk_id: str
    content: str
    score: float
    document_id: int
    document_title: str
    page_number: int | None = None
    section_title: str | None = None
    chunk_index: int

    # Geology classification metadata
    category: str = "general"
    location: str | None = None
    rock_type: str | None = None
    mineral: str | None = None
    difficulty: str = "基础"
    keywords: list[str] = Field(default_factory=list)
    route_number: str | None = None


class SearchResponse(BaseModel):
    """Semantic search response."""
    query: str
    detected_intent: str = ""  # e.g. "路线查询 → 马山"
    results: list[SearchResultItem]
    total: int


# ── Upload ────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    document_id: int
    title: str
    filename: str
    status: str
    chunk_count: int
    categories_found: dict[str, int] = Field(default_factory=dict)
    message: str


# ── Filters ───────────────────────────────────────────────────

class AvailableFilters(BaseModel):
    """Available metadata filter values in the knowledge base."""
    categories: list[str]
    locations: list[str]
    rock_types: list[str]
    minerals: list[str]


# ── Stats ─────────────────────────────────────────────────────

class KnowledgeStats(BaseModel):
    document_count: int
    chunk_count: int
    vector_store_chunks: int
