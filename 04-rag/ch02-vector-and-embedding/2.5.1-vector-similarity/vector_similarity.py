"""向量基础实验：用手写公式和 NumPy 对照计算相似度。"""

import math
from collections.abc import Sequence

import numpy as np

Vector = Sequence[float]


def _validate_dimensions(first: Vector, second: Vector) -> None:
    """验证两个向量维度一致。"""
    if len(first) != len(second):
        raise ValueError("两个向量的维度必须一致")


def dot_product(first: Vector, second: Vector) -> float:
    """使用纯 Python 计算两个向量的点积。"""
    _validate_dimensions(first, second)
    # 点积是对应维度相乘后求和。
    return float(sum(left * right for left, right in zip(first, second)))


def euclidean_distance(first: Vector, second: Vector) -> float:
    """使用纯 Python 计算两个向量的欧氏距离。"""
    _validate_dimensions(first, second)
    # 欧氏距离是各维差值平方和的平方根。
    squared_distance = sum((left - right) ** 2 for left, right in zip(first, second))
    return math.sqrt(squared_distance)


def cosine_similarity(first: Vector, second: Vector) -> float:
    """使用纯 Python 计算两个向量的余弦相似度。"""
    _validate_dimensions(first, second)
    first_norm = math.sqrt(sum(value**2 for value in first))
    second_norm = math.sqrt(sum(value**2 for value in second))
    if first_norm == 0 or second_norm == 0:
        raise ValueError("零向量没有可定义的余弦相似度")
    # 余弦相似度等于点积除以两个向量模长的乘积。
    return dot_product(first, second) / (first_norm * second_norm)


def numpy_dot_product(first: Vector, second: Vector) -> float:
    """使用 NumPy 计算两个向量的点积。"""
    _validate_dimensions(first, second)
    return float(np.dot(np.asarray(first), np.asarray(second)))


def numpy_euclidean_distance(first: Vector, second: Vector) -> float:
    """使用 NumPy 计算两个向量的欧氏距离。"""
    _validate_dimensions(first, second)
    first_array = np.asarray(first)
    second_array = np.asarray(second)
    return float(np.linalg.norm(first_array - second_array))


def numpy_cosine_similarity(first: Vector, second: Vector) -> float:
    """使用 NumPy 计算两个向量的余弦相似度。"""
    _validate_dimensions(first, second)
    first_array = np.asarray(first)
    second_array = np.asarray(second)
    first_norm = np.linalg.norm(first_array)
    second_norm = np.linalg.norm(second_array)
    if first_norm == 0 or second_norm == 0:
        raise ValueError("零向量没有可定义的余弦相似度")
    return float(np.dot(first_array, second_array) / (first_norm * second_norm))
