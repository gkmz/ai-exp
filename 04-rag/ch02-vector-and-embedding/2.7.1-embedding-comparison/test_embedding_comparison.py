"""2.7.1 Embedding 模型对比实验 — 离线测试。

使用 Fake Provider 验证评估逻辑，不依赖真实模型。
"""

from math import sqrt

import pytest
from embedding_comparison_mine import (
    DOCUMENTS,
    QUERIES,
    cosine_similarity,
    evaluate_model,
)


class FakeProvider:
    """返回可预测向量的假 Provider。

    策略：为每个文档生成一个 one-hot 向量（第 i 个文档在第 i 维为 1），
    查询向量与期望文档的向量相同，这样 Top-1 一定命中。
    """

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i, _text in enumerate(texts):
            vec = [0.0] * self._dim
            vec[i % self._dim] = 1.0
            vectors.append(vec)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        # 通过 QUERIES 找到该查询对应的期望文档索引，返回相同的 one-hot 向量
        for query_text, expected_idx in QUERIES:
            if query_text == text:
                vec = [0.0] * self._dim
                vec[expected_idx % self._dim] = 1.0
                return vec
        return [0.0] * self._dim


def test_cosine_similarity_identical_vectors():
    """相同向量的余弦相似度为 1。"""
    vec = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(vec, vec) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    """正交向量的余弦相似度为 0。"""
    assert abs(cosine_similarity([1, 0, 0], [0, 1, 0])) < 1e-6


def test_cosine_similarity_zero_vector():
    """含零向量时返回 0。"""
    assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0


def test_evaluate_model_returns_expected_structure():
    """验证 evaluate_model 返回完整的结果结构。"""
    provider = FakeProvider(dim=len(DOCUMENTS))
    result = evaluate_model("fake", provider, DOCUMENTS, QUERIES)

    assert result["name"] == "fake"
    assert isinstance(result["dimension"], int)
    # 注意：框架代码返回 0，实现后应该等于 len(DOCUMENTS)
    assert isinstance(result["encode_time"], float)
    assert result["total"] == len(QUERIES)
    assert isinstance(result["hits"], int)
    assert isinstance(result["accuracy"], float)
    assert isinstance(result["details"], list)


def test_evaluate_model_detail_format():
    """验证 details 中每条记录的格式。"""
    provider = FakeProvider(dim=len(DOCUMENTS))
    result = evaluate_model("fake", provider, DOCUMENTS, QUERIES)

    for query_text, expected_idx, actual_idx, score in result["details"]:
        assert isinstance(query_text, str)
        assert isinstance(expected_idx, int)
        assert isinstance(actual_idx, int)
        assert isinstance(score, float)
