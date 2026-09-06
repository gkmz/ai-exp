import pytest

from rag_study.experiments.vector_similarity import (
    cosine_similarity,
    dot_product,
    euclidean_distance,
    numpy_cosine_similarity,
    numpy_dot_product,
    numpy_euclidean_distance,
)


def test_handwritten_similarity_functions_match_known_values():
    """验证手写实现的三个指标符合已知数学结果。"""
    first = [3.0, 4.0]
    second = [4.0, 3.0]

    assert dot_product(first, second) == pytest.approx(24.0)
    assert euclidean_distance(first, second) == pytest.approx(\
        2**0.5
    )
    assert cosine_similarity(first, second) == pytest.approx(0.96)


def test_numpy_similarity_functions_match_handwritten_functions():
    """验证 NumPy 实现与手写实现结果一致。"""
    first = [3.0, 4.0]
    second = [4.0, 3.0]

    assert numpy_dot_product(first, second) == pytest.approx(dot_product(first, second))
    assert numpy_euclidean_distance(first, second) == pytest.approx(
        euclidean_distance(first, second)
    )
    assert numpy_cosine_similarity(first, second) == pytest.approx(
        cosine_similarity(first, second)
    )


def test_similarity_functions_reject_vectors_with_different_dimensions():
    """验证不同维度的向量不能进行比较。"""
    with pytest.raises(ValueError, match="维度"):
        dot_product([1.0, 2.0], [1.0])

    with pytest.raises(ValueError, match="维度"):
        numpy_cosine_similarity([1.0, 2.0], [1.0])


def test_cosine_similarity_rejects_zero_vector():
    """验证零向量没有可定义的余弦相似度。"""
    with pytest.raises(ValueError, match="零向量"):
        cosine_similarity([0.0, 0.0], [1.0, 2.0])
