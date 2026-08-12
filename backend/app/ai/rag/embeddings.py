"""Embedding generator using sentence-transformers.

Uses a local model (BAAI/bge-small-zh-v1.5 by default) — free, no API calls.
The model is loaded once as a module-level singleton.
"""

import logging
from typing import Sequence

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — loaded on first use
_embedding_model = None


def _get_model():
    """Lazy-load the sentence-transformers model (singleton)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        logger.info(
            "Loading embedding model: %s on %s",
            settings.EMBEDDING_MODEL,
            settings.EMBEDDING_DEVICE,
        )
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info("Embedding model loaded (dim=%d)", _embedding_model.get_sentence_embedding_dimension())
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (each is list[float]).
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Generate embedding for a single query string.

    For BGE models, prepend "为这个句子生成表示以用于检索相关文章："
    which is the recommended query instruction.
    """
    model = _get_model()
    embedding = model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding.tolist()


def get_embedding_dimension() -> int:
    """Return the embedding vector dimension."""
    model = _get_model()
    return model.get_sentence_embedding_dimension()
