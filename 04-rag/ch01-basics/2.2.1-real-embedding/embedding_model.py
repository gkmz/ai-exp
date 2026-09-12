"""真实 Embedding 模型实验：统一文档向量和 Query 向量的生成方式。"""

import os
from collections.abc import Sequence
from typing import Protocol

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

Vector = list[float]


class EmbeddingProvider(Protocol):
    """定义 Embedding 服务必须提供的最小接口。"""

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        """批量生成文档向量。"""

    def embed_query(self, text: str) -> Vector:
        """生成单条 Query 向量。"""


class EmbeddingService:
    """封装文档和用户 Query 的向量化流程。"""

    def __init__(self, provider: EmbeddingProvider) -> None:
        """接收一个具体的 Embedding 提供者。"""
        # 这里依赖抽象接口，而不是直接依赖某一家模型服务，方便替换模型和测试。
        self._provider = provider

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """批量将知识库文档转换为向量。"""
        normalized_texts = list(texts)
        if not normalized_texts:
            raise ValueError("文档列表不能为空")
        if any(not text.strip() for text in normalized_texts):
            raise ValueError("文档内容不能为空")

        # 离线入库时应该批量编码，减少远程请求次数和网络开销。
        return self._provider.embed_documents(normalized_texts)

    def embed_query(self, text: str) -> Vector:
        """将用户问题转换为查询向量。"""
        if not text.strip():
            raise ValueError("Query 不能为空")

        # 在线检索只处理当前 Query，因此调用单条查询接口即可。
        return self._provider.embed_query(text)


def create_openai_embedding_service() -> EmbeddingService:
    """从环境变量创建 OpenAI 兼容的 Embedding 服务。"""
    # 允许从项目根目录的 .env 读取 API Key、Base URL 和模型名。
    load_dotenv()

    model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
    if not model_name:
        raise ValueError(
            "请在 .env 中配置 OPENAI_EMBEDDING_MODEL，例如 text-embedding-3-small"
        )

    # api_key 和 base_url 为空时，OpenAIEmbeddings 会继续尝试读取其默认环境变量。
    # 这样既支持官方 OpenAI，也支持提供 OpenAI 兼容接口的模型服务。
    provider = OpenAIEmbeddings(
        model=model_name,
        api_key=os.getenv("OPENAI_API_KEY") or None,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    return EmbeddingService(provider)
