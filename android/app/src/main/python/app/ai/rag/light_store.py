"""Lightweight vector store — SQLite + numpy cosine similarity.

Pure-Python replacement for ChromaDB, designed for Android/embedded use.
Maintains the exact same module-level API as the original store.py
so that all callers (retriever.py, knowledge_service.py) work unchanged.

Uses SQLite for metadata storage and numpy for vector similarity.
Suitable for datasets up to ~10,000 vectors on mobile devices.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "geology_knowledge"

# Module-level connection (Android: only one process, so this is fine)
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


@dataclass
class SearchResult:
    """A single search result from the vector store."""
    chunk_id: str
    content: str
    score: float
    document_id: int
    document_title: str
    page_number: int | None
    section_title: str | None
    chunk_index: int
    category: str = "general"
    location: str | None = None
    rock_type: str | None = None
    mineral: str | None = None
    difficulty: str = "基础"
    keywords: list[str] | None = None
    route_number: str | None = None


def _get_conn() -> sqlite3.Connection:
    """Get or create a SQLite connection (thread-safe singleton)."""
    global _conn
    if _conn is None:
        db_path = settings.LIGHT_VECTOR_DB_PATH
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                document TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                document_title TEXT DEFAULT '',
                page_number INTEGER DEFAULT 0,
                section_title TEXT DEFAULT '',
                chunk_index INTEGER DEFAULT 0,
                category TEXT DEFAULT 'general',
                location TEXT DEFAULT '',
                rock_type TEXT DEFAULT '',
                mineral TEXT DEFAULT '',
                difficulty TEXT DEFAULT '基础',
                route_number TEXT DEFAULT '',
                keywords TEXT DEFAULT ''
            )
            """
        )
        _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vectors_doc_id ON vectors(document_id)"
        )
        _conn.commit()
        logger.info("LightVectorStore initialized at %s", db_path)
    return _conn


def _serialize_embedding(emb: list[float]) -> bytes:
    """Serialize a float list to bytes via numpy."""
    arr = np.array(emb, dtype=np.float32)
    return arr.tobytes()


def _deserialize_embedding(data: bytes) -> np.ndarray:
    """Deserialize bytes back to a numpy array."""
    return np.frombuffer(data, dtype=np.float32)


def add_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
) -> list[str]:
    """Add chunks with embeddings and rich metadata.

    Each chunk dict must have:
        content, document_id, document_title,
        page_number, section_title, chunk_index
    Optional geology metadata:
        category, location, rock_type, mineral,
        difficulty, keywords, route_number
    """
    conn = _get_conn()
    ids = [str(uuid.uuid4()) for _ in chunks]

    with _lock:
        rows = []
        for i, c in enumerate(chunks):
            rows.append((
                ids[i],
                _serialize_embedding(embeddings[i]),
                c["content"],
                c["document_id"],
                c.get("document_title", ""),
                c.get("page_number") or 0,
                c.get("section_title") or "",
                c.get("chunk_index", 0),
                c.get("category") or "general",
                c.get("location") or "",
                c.get("rock_type") or "",
                c.get("mineral") or "",
                c.get("difficulty") or "基础",
                c.get("route_number") or "",
                ",".join(c.get("keywords") or []),
            ))

        conn.executemany(
            """INSERT INTO vectors (
                id, embedding, document, document_id, document_title,
                page_number, section_title, chunk_index,
                category, location, rock_type, mineral,
                difficulty, route_number, keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()

    logger.info("Added %d chunks to LightVectorStore (with geology metadata)", len(ids))
    return ids


def search(
    query_embedding: list[float],
    top_k: int = 5,
    document_id: int | None = None,
    category: str | None = None,
    location: str | None = None,
    rock_type: str | None = None,
    mineral: str | None = None,
    difficulty: str | None = None,
) -> list[SearchResult]:
    """Semantic search with optional metadata filters.

    Filters narrow results to matching metadata values.
    Multiple filters are AND-ed together.
    """
    conn = _get_conn()
    query_vec = np.array(query_embedding, dtype=np.float32)
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)

    with _lock:
        cursor = conn.execute(
            "SELECT id, embedding, document, document_id, document_title, "
            "page_number, section_title, chunk_index, "
            "category, location, rock_type, mineral, "
            "difficulty, route_number, keywords FROM vectors"
        )

        scored: list[tuple[float, dict]] = []
        for row in cursor:
            row_dict = {
                "chunk_id": row[0],
                "content": row[2],
                "document_id": row[3],
                "document_title": row[4],
                "page_number": row[5],
                "section_title": row[6],
                "chunk_index": row[7],
                "category": row[8],
                "location": row[9],
                "rock_type": row[10],
                "mineral": row[11],
                "difficulty": row[12],
                "route_number": row[13],
                "keywords": [k for k in (row[14] or "").split(",") if k],
            }

            # Metadata filtering
            if document_id is not None and row_dict["document_id"] != document_id:
                continue
            if category and row_dict["category"] != category:
                continue
            if location and row_dict["location"] != location:
                continue
            if rock_type and row_dict["rock_type"] != rock_type:
                continue
            if mineral and row_dict["mineral"] != mineral:
                continue
            if difficulty and row_dict["difficulty"] != difficulty:
                continue

            # Cosine similarity
            stored_emb = _deserialize_embedding(row[1])
            stored_norm = stored_emb / (np.linalg.norm(stored_emb) + 1e-8)
            similarity = float(np.dot(query_norm, stored_norm))

            scored.append((similarity, row_dict))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Build results
    results: list[SearchResult] = []
    for score, r in scored[:top_k]:
        pg = r["page_number"]
        results.append(SearchResult(
            chunk_id=r["chunk_id"],
            content=r["content"],
            score=round(score, 4),
            document_id=r["document_id"],
            document_title=r["document_title"],
            page_number=pg if pg else None,
            section_title=r["section_title"] or None,
            chunk_index=r["chunk_index"],
            category=r["category"],
            location=r["location"] or None,
            rock_type=r["rock_type"] or None,
            mineral=r["mineral"] or None,
            difficulty=r["difficulty"],
            keywords=r["keywords"],
            route_number=r["route_number"] or None,
        ))

    return results


def delete_document_chunks(document_id: int) -> int:
    """Delete all chunks for a document."""
    conn = _get_conn()
    with _lock:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM vectors WHERE document_id = ?", (document_id,)
        )
        count = cursor.fetchone()[0]
        conn.execute("DELETE FROM vectors WHERE document_id = ?", (document_id,))
        conn.commit()
    logger.info("Deleted %d chunks for document %d", count, document_id)
    return count


def get_collection_stats() -> dict:
    """Return collection stats."""
    conn = _get_conn()
    cursor = conn.execute("SELECT COUNT(*) FROM vectors")
    count = cursor.fetchone()[0]
    return {"name": COLLECTION_NAME, "chunk_count": count}


def get_available_filters() -> dict:
    """Return distinct metadata values available for filtering."""
    conn = _get_conn()

    def unique(column: str) -> list[str]:
        cursor = conn.execute(
            f"SELECT DISTINCT {column} FROM vectors WHERE {column} != '' "
            f"AND {column} IS NOT NULL ORDER BY {column}"
        )
        return [r[0] for r in cursor.fetchall()]

    return {
        "categories": unique("category"),
        "locations": unique("location"),
        "rock_types": unique("rock_type"),
        "minerals": unique("mineral"),
    }
