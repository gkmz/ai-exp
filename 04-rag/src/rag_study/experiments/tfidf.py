"""文本向量化实验：使用 TF-IDF 为词语分配区分度权重。"""

import math


class TfidfVectorizer:
    """将以空格分词的文本转换为 L2 归一化 TF-IDF 向量。"""

    def __init__(self) -> None:
        """初始化词表、文档频率和 IDF 权重。"""
        self.vocabulary_: dict[str, int] = {}
        self.document_frequencies_: dict[str, int] = {}
        self.idf_: dict[str, float] = {}
        self.document_count_ = 0

    def fit(self, texts: list[str]) -> None:
        """根据文本集合统计词表、文档频率和 IDF 权重。"""
        self.vocabulary_.clear()
        self.document_frequencies_.clear()
        self.idf_.clear()
        self.document_count_ = len(texts)

        for text in texts:
            for word in text.split():
                if word not in self.vocabulary_:
                    self.vocabulary_[word] = len(self.vocabulary_)

            # 同一个词在一篇文档中重复出现，也只算一篇文档。
            for word in set(text.split()):
                self.document_frequencies_[word] = (
                    self.document_frequencies_.get(word, 0) + 1
                )

        # 平滑 IDF，避免极端数据产生除零或零权重。
        for word in self.vocabulary_:
            document_frequency = self.document_frequencies_[word]
            self.idf_[word] = math.log(
                (1 + self.document_count_) / (1 + document_frequency)
            ) + 1

    def transform(self, texts: list[str]) -> list[list[float]]:
        """使用已训练的词表将文本转换为归一化 TF-IDF 向量。"""
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * len(self.vocabulary_)
            words = text.split()
            word_counts: dict[str, int] = {}
            for word in words:
                if word in self.vocabulary_:
                    word_counts[word] = word_counts.get(word, 0) + 1

            for word, count in word_counts.items():
                index = self.vocabulary_[word]
                vector[index] = count * self.idf_[word]

            # L2 归一化让不同长度的文本更容易进行余弦相似度比较。
            norm = math.sqrt(sum(value**2 for value in vector))
            if norm > 0:
                vector = [value / norm for value in vector]
            vectors.append(vector)
        return vectors

    def fit_transform(self, texts: list[str]) -> list[list[float]]:
        """统计文本集合并立即返回其 TF-IDF 向量。"""
        self.fit(texts)
        return self.transform(texts)
