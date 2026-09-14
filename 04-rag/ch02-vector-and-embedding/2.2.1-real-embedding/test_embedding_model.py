import pytest
from embedding_model import (
    EmbeddingService,
    create_openai_embedding_service,
)


class FakeEmbedder:
    """用固定结果模拟远程 Embedding 服务，避免测试依赖网络。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """为每段文本返回一个固定维度的测试向量。"""
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """为单条查询返回一个测试向量。"""
        return [float(len(text)), 1.0]


def test_service_embeds_documents_in_batch():
    """验证文档可以批量转换为向量，并保持输入顺序。"""
    service = EmbeddingService(FakeEmbedder())

    vectors = service.embed_documents(["苹果", "香蕉"])

    assert vectors == [[2.0, 1.0], [2.0, 1.0]]


def test_service_embeds_one_query():
    """验证用户 Query 可以转换为单个向量。"""
    service = EmbeddingService(FakeEmbedder())

    vector = service.embed_query("北京住宿")

    assert vector == [4.0, 1.0]


def test_service_rejects_empty_inputs():
    """验证空文档列表和空查询不会发起无意义的模型调用。"""
    service = EmbeddingService(FakeEmbedder())

    with pytest.raises(ValueError, match="文档列表不能为空"):
        service.embed_documents([])

    with pytest.raises(ValueError, match="Query 不能为空"):
        service.embed_query("  ")


def test_openai_service_requires_embedding_model_configuration(monkeypatch):
    """验证缺少模型名时给出可理解的配置错误。"""
    # 禁止测试读取本地 .env，避免开发机配置影响缺少配置的测试。
    monkeypatch.setattr("embedding_model.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "")

    with pytest.raises(ValueError, match="OPENAI_EMBEDDING_MODEL"):
        create_openai_embedding_service()
