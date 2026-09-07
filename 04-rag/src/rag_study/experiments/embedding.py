"""文本向量化实验：使用词袋模型把文本转换为数字向量。"""


class BagOfWordsVectorizer:
    """将以空格分词的文本转换为词频向量。"""

    def __init__(self) -> None:
        """初始化空词表。"""
        self.vocabulary_: dict[str, int] = {}

    def fit(self, texts: list[str]) -> None:
        """根据文本集合建立词到向量下标的映射。"""
        self.vocabulary_.clear()
        for text in texts:
            for word in text.split():
                if word not in self.vocabulary_:
                    self.vocabulary_[word] = len(self.vocabulary_)

    def transform(self, texts: list[str]) -> list[list[int]]:
        """使用已建立的词表把文本转换为词频向量。"""
        vectors: list[list[int]] = []
        for text in texts:
            vector = [0] * len(self.vocabulary_)
            for word in text.split():
                index = self.vocabulary_.get(word)
                if index is not None:
                    vector[index] += 1
            vectors.append(vector)
        return vectors

    def fit_transform(self, texts: list[str]) -> list[list[int]]:
        """建立词表并立即将同一批文本转换为词频向量。"""
        self.fit(texts)
        return self.transform(texts)
