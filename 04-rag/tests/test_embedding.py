from rag_study.experiments.embedding import BagOfWordsVectorizer


def test_fit_builds_vocabulary_in_first_seen_order():
    """验证词表按文本中首次出现的顺序建立。"""
    vectorizer = BagOfWordsVectorizer()

    vectorizer.fit(["苹果 很好吃", "香蕉 也很好吃"])

    assert vectorizer.vocabulary_ == {
        "苹果": 0,
        "很好吃": 1,
        "香蕉": 2,
        "也很好吃": 3,
    }


def test_transform_returns_word_count_vectors():
    """验证文本会被转换为词频向量。"""
    vectorizer = BagOfWordsVectorizer()
    vectorizer.fit(["苹果 很好吃", "香蕉 也很好吃"])

    vectors = vectorizer.transform(["苹果 很好吃 苹果", "香蕉"])

    assert vectors == [[2, 1, 0, 0], [0, 0, 1, 0]]


def test_transform_ignores_words_not_in_vocabulary():
    """验证转换新文本时会忽略词表之外的词。"""
    vectorizer = BagOfWordsVectorizer()
    vectorizer.fit(["苹果 很好吃"])

    assert vectorizer.transform(["苹果 香蕉"])[0] == [1, 0]


def test_fit_transform_fits_vocabulary_and_returns_vectors():
    """验证 fit_transform 会先建立词表，再返回向量。"""
    vectorizer = BagOfWordsVectorizer()

    vectors = vectorizer.fit_transform(["苹果 很好吃", "苹果 很甜"])

    assert vectors == [[1, 1, 0], [1, 0, 1]]
