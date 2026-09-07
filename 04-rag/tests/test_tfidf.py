import math

import pytest

from rag_study.experiments.tfidf import TfidfVectorizer


def test_fit_builds_vocabulary_and_document_frequencies():
    """验证 TF-IDF 会记录词表和每个词出现于多少篇文档。"""
    vectorizer = TfidfVectorizer()

    vectorizer.fit(["苹果 很好吃", "香蕉 很好吃", "苹果 很甜"])

    assert vectorizer.vocabulary_ == {
        "苹果": 0,
        "很好吃": 1,
        "香蕉": 2,
        "很甜": 3,
    }
    assert vectorizer.document_frequencies_ == {
        "苹果": 2,
        "很好吃": 2,
        "香蕉": 1,
        "很甜": 1,
    }


def test_rare_words_receive_higher_idf_than_common_words():
    """验证只出现在少数文档中的词具有更高 IDF。"""
    vectorizer = TfidfVectorizer()
    vectorizer.fit(["苹果 很好吃", "香蕉 很好吃", "苹果 很甜"])

    assert vectorizer.idf_["香蕉"] > vectorizer.idf_["很好吃"]
    assert vectorizer.idf_["很甜"] > vectorizer.idf_["很好吃"]


def test_transform_returns_l2_normalized_tfidf_vectors():
    """验证 TF-IDF 向量会进行 L2 归一化。"""
    vectorizer = TfidfVectorizer()
    vectorizer.fit(["苹果 很好吃", "香蕉 很好吃"])

    vector = vectorizer.transform(["苹果 很好吃"])[0]

    assert math.sqrt(sum(value**2 for value in vector)) == pytest.approx(1.0)
    assert vector[0] > 0
    assert vector[1] > 0
    assert vector[2] == 0


def test_transform_ignores_unknown_words_and_returns_zero_for_empty_text():
    """验证未登录词被忽略，空文本返回零向量。"""
    vectorizer = TfidfVectorizer()
    vectorizer.fit(["苹果 很好吃"])

    vectors = vectorizer.transform(["苹果 香蕉", "香蕉"])

    assert vectors[0][0] == pytest.approx(1.0)
    assert vectors[0][1] == pytest.approx(0.0)
    assert vectors[0] == pytest.approx([1.0, 0.0])
    assert vectors[1] == [0.0, 0.0]
