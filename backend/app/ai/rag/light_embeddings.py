"""Android-compatible lightweight embedding backend.

Pure Python + numpy implementation — NO torch / sentence-transformers /
network model download required. Suitable for running inside Chaquopy.

Method: character bigram feature hashing + TF weighting (L2 normalized).
- 中文文本按连续汉字串切分为二元字符组（bigram），兼顾单字边界
- 连续字母/数字串作为整体 token
- 每个 token 经 FNV-1a 哈希映射到固定维度（与 BGE-small-zh 一致为 512 维）
- 词频累加后 L2 归一化，输出与 sentence-transformers 相同接口

精度低于 BGE 语义模型，但足以支撑地质领域术语的词汇级匹配检索。
"""

import logging
import re
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# 固定向量维度，与 BAAI/bge-small-zh-v1.5 的 512 维保持一致
DIM = 512

# 连续汉字串 或 连续字母数字串
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+")

# FNV-1a 参数
_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193


def _fnv1a(text: str) -> int:
    """FNV-1a 哈希，将 token 映射到 [0, DIM) 索引。"""
    h = _FNV_OFFSET
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & 0xFFFFFFFF
    return h % DIM


def _bigrams(chinese: str) -> list[str]:
    """将连续汉字串拆分为 bigram（不足两个字符时保留单字）。"""
    grams = []
    for i in range(len(chinese) - 1):
        grams.append(chinese[i : i + 2])
    if len(chinese) == 1:
        grams.append(chinese)
    return grams


def tokenize(text: str) -> list[str]:
    """切分文本为 token 列表（汉字 bigram + 字母数字词）。"""
    tokens = []
    for seg in _TOKEN_RE.findall(text.lower()):
        if "\u4e00" <= seg[0] <= "\u9fff":
            tokens.extend(_bigrams(seg))
        else:
            tokens.append(seg)
    return tokens


class LightEmbedder:
    """轻量嵌入器：TF 词频向量 + 特征哈希 + L2 归一化。"""

    DIM = DIM

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """批量生成文本向量。"""
        return [self._embed(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """生成查询向量（与文档使用同一空间）。"""
        return self._embed(query)

    def get_embedding_dimension(self) -> int:
        return DIM

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(DIM, dtype=np.float32)
        for gram in tokenize(text or ""):
            vec[_fnv1a(gram)] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.tolist()


# 模块级单例，供 embeddings.py 复用
_light_embedder = LightEmbedder()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _light_embedder.embed_texts(texts)


def embed_query(query: str) -> list[float]:
    return _light_embedder.embed_query(query)


def get_embedding_dimension() -> int:
    return _light_embedder.get_embedding_dimension()
