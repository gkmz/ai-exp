"""真实 Embedding 模型实验：统一文档向量和 Query 向量的生成方式。"""

import os
from collections.abc import Sequence
from math import sqrt
from pathlib import Path
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
    # 固定读取 04-rag/.env，并让项目配置覆盖 shell 中同名的环境变量。
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env, override=True)

    model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
    if not model_name:
        raise ValueError(
            "请在 .env 中配置 OPENAI_EMBEDDING_MODEL，例如 text-embedding-3-small"
        )

    # api_key 和 base_url 为空时，OpenAIEmbeddings 会继续尝试读取其默认环境变量。
    # 这样既支持官方 OpenAI，也支持提供 OpenAI 兼容接口的模型服务。
    api_key = os.getenv("OPENAI_API_KEY") or ""
    base_url = os.getenv("OPENAI_BASE_URL") or ""
    if not api_key.strip():
        raise ValueError("请在 .env 中配置 OPENAI_API_KEY")
    if not base_url.strip():
        raise ValueError(
            "请在 .env 中配置 OPENAI_BASE_URL，例如 https://api.openai.com/v1"
        )
    provider = OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        # 部分 OpenAI 兼容接口只接受字符串数组，不接受 LangChain 默认生成的 token 数组。
        # 如果保持默认值 True，可能收到 400：input must be an array of strings。
        check_embedding_ctx_length=False,
    )
    return EmbeddingService(provider)


def _cosine_similarity(left: Vector, right: Vector) -> float:
    """计算两个向量之间的余弦相似度。"""
    # 点积
    dot_product = sum(
        left_value * right_value for left_value, right_value in zip(left, right)
    )
    # 向量长度
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    # 余弦相似度
    return dot_product / (left_norm * right_norm)


def main() -> None:
    """调用真实 Embedding 模型并展示文档向量和语义相似度。"""
    # 准备几段语义不同的文档，用于观察模型对文档内容的向量化结果。
    documents = [
        "苹果是一种常见的水果，含有丰富的维生素和膳食纤维。",
        "北京是中国的首都，拥有故宫、长城等著名历史景点。",
        "向量数据库可以根据向量相似度快速检索相关文档。",
    ]
    query = "如何根据语义相似度查找相关资料？"

    service = create_openai_embedding_service()
    document_vectors = service.embed_documents(documents)
    query_vector = service.embed_query(query)

    print("=== 文档 Embedding 结果 ===")
    for document, vector in zip(documents, document_vectors):
        print(f"文档：{document}")
        print(f"向量维度：{len(vector)}")
        # 完整向量通常有上千个浮点数，这里只展示前 10 个值便于观察。
        print(f"向量前 10 个值：{vector[:10]}")
        print()

    print("=== Query 与文档的余弦相似度 ===")
    print(f"Query：{query}")
    for document, vector in zip(documents, document_vectors):
        # 计算查询文本的向量和检索文档的向量的余弦相似度
        # 趋近于1，表示越相关
        score = _cosine_similarity(query_vector, vector)
        print(f"{score:.4f}  {document}")


if __name__ == "__main__":
    main()

# 示例输出：
# === 文档 Embedding 结果 ===
# 文档：苹果是一种常见的水果，含有丰富的维生素和膳食纤维。
# 向量维度：1024
# 向量前 10 个值：[0.021218515932559967, 0.03725139796733856, -0.023610923439264297, -0.03930561244487
# 7625, 0.04647030681371689, -0.07154673337936401, 0.03752696141600609, 0.04421567916870117, -0.043063
# 316494226456, 0.01091613806784153]
#
# 文档：北京是中国的首都，拥有故宫、长城等著名历史景点。
# 向量维度：1024
# 向量前 10 个值：[0.019513260573148727, 0.08189254254102707, -0.031852710992097855, 0.039683274924755
# 096, 0.007925288751721382, -0.04637714475393295, 0.035616435110569, -0.09098610281944275, -0.0034353
# 442024439573, 0.035439617931842804]
#
# 文档：向量数据库可以根据向量相似度快速检索相关文档。
# 向量维度：1024
# 向量前 10 个值：[0.02314865030348301, -0.003437438979744911, 0.023058274760842323, -0.00368273979984
# 22384, -0.05226198211312294, 0.02534344606101513, -0.014730959199368954, -0.020359966903924942, 0.00
# 16735324170440435, 0.03235388547182083]
#
# === Query 与文档的余弦相似度 ===
# Query：如何根据语义相似度查找相关资料？
# 0.1878  苹果是一种常见的水果，含有丰富的维生素和膳食纤维。
# 0.1593  北京是中国的首都，拥有故宫、长城等著名历史景点。
# 0.5926  向量数据库可以根据向量相似度快速检索相关文档。
