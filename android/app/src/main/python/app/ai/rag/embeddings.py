"""Embedding generator with pluggable backends.

Backends:
- "sentence-transformers"  — 高质量语义模型（BAAI/bge-small-zh-v1.5）。
  依赖 torch，仅用于桌面 / 完整 Python 环境。
- "light"                  — 纯 Python + numpy 实现（字符 bigram 特征哈希），
  无 torch / 无模型下载，可在 Android（Chaquopy）内运行。
- "auto"（默认）           — 自动选择：Android 环境用 light，否则 sentence-transformers。

对外接口保持不变：embed_texts / embed_query / get_embedding_dimension。
"""

import logging
import os
import sys
from typing import Sequence

from app.config import settings

logger = logging.getLogger(__name__)

# Android 检测（与 android_bridge.py 一致）
IS_ANDROID = hasattr(sys, "getandroidapilevel") or "chaquopy" in sys.modules

_backend = None
_backend_name = None


def _resolve_backend_name() -> str:
    """根据配置与运行环境决定实际使用的后端。"""
    configured = settings.EMBEDDING_BACKEND or "auto"
    if configured == "light":
        return "light"
    if configured == "sentence-transformers":
        return "sentence-transformers"
    # auto
    return "light" if IS_ANDROID else "sentence-transformers"


def _get_backend():
    """Lazy-load the embedding backend (singleton)."""
    global _backend, _backend_name
    name = _resolve_backend_name()
    if _backend is not None and name == _backend_name:
        return _backend

    if name == "light":
        from app.ai.rag import light_embeddings

        _backend = light_embeddings.LightEmbedder()
        logger.info("Embedding backend: light (pure numpy, %d dim)", _backend.DIM)
    else:
        from sentence_transformers import SentenceTransformer

        logger.info(
            "Loading embedding model: %s on %s",
            settings.EMBEDDING_MODEL,
            settings.EMBEDDING_DEVICE,
        )
        _backend = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info(
            "Embedding model loaded (dim=%d)",
            _backend.get_sentence_embedding_dimension(),
        )
    _backend_name = name
    return _backend


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (each is list[float]).
    """
    backend = _get_backend()
    if _backend_name == "light":
        return backend.embed_texts(texts)

    model = backend
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
    backend = _get_backend()
    if _backend_name == "light":
        return backend.embed_query(query)

    embedding = backend.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding.tolist()


def get_embedding_dimension() -> int:
    """Return the embedding vector dimension."""
    backend = _get_backend()
    if _backend_name == "light":
        return backend.get_embedding_dimension()
    return backend.get_sentence_embedding_dimension()
