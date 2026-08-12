"""Vector store wrapper — Android-compatible (LightVectorStore).

Re-exports the exact same module-level API as the original ChromaDB-backed store.
All services (retriever.py, knowledge_service.py) continue to work unchanged.
"""

# Re-export everything from the light store
from app.ai.rag.light_store import (
    COLLECTION_NAME,
    SearchResult,
    add_chunks,
    delete_document_chunks,
    get_available_filters,
    get_collection_stats,
    search,
)

__all__ = [
    "COLLECTION_NAME",
    "SearchResult",
    "add_chunks",
    "delete_document_chunks",
    "get_available_filters",
    "get_collection_stats",
    "search",
]
