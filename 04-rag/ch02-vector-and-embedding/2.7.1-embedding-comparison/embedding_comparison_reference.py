"""2.7.1 Embedding 模型对比实验 — 参考实现。

完成框架代码后再查看，用于对比你的实现思路。
"""

import os
import sys
import time
from math import sqrt
from pathlib import Path

from dotenv import load_dotenv

Vector = list[float]

# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

DOCUMENTS = [
    "RAG 通过检索外部知识库来增强大模型的回答，减少幻觉。",
    "向量数据库使用近似最近邻算法实现高效的语义检索。",
    "Transformer 模型通过自注意力机制捕捉文本中的长距离依赖。",
    "Python 的 GIL 限制了多线程的并行计算能力。",
    "北京烤鸭是北京最著名的传统美食之一。",
    "余弦相似度通过计算向量夹角衡量文本的语义相关性。",
    "机器学习模型需要大量标注数据进行训练。",
    "Docker 容器技术简化了应用的部署和环境一致性问题。",
]

QUERIES = [
    ("如何减少大模型的幻觉？", 0),
    ("怎样快速找到语义相近的文档？", 1),
    ("注意力机制是什么？", 2),
    ("文本相似度怎么算？", 5),
    ("有什么好吃的推荐？", 4),
]


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def cosine_similarity(left: Vector, right: Vector) -> float:
    """计算两个向量的余弦相似度。"""
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = sqrt(sum(a * a for a in left))
    norm_right = sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)


# ---------------------------------------------------------------------------
# Provider 实现
# ---------------------------------------------------------------------------

class SentenceTransformerProvider:
    """使用 sentence-transformers 加载本地模型。"""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        return self._model.encode(texts).tolist()

    def embed_query(self, text: str) -> Vector:
        return self._model.encode(text).tolist()


class QwenProvider:
    """通过 OpenAI 兼容接口调用 Qwen embedding。"""

    def __init__(self) -> None:
        from langchain_openai import OpenAIEmbeddings

        project_env = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(project_env, override=True)

        model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip()

        if not model_name:
            raise ValueError("请在 .env 中配置 OPENAI_EMBEDDING_MODEL")
        if not api_key:
            raise ValueError("请在 .env 中配置 OPENAI_API_KEY")
        if not base_url:
            raise ValueError("请在 .env 中配置 OPENAI_BASE_URL")

        self._provider = OpenAIEmbeddings(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            check_embedding_ctx_length=False,
        )

    @property
    def dimension(self) -> int | None:
        return None

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        return self._provider.embed_documents(texts)

    def embed_query(self, text: str) -> Vector:
        return self._provider.embed_query(text)


# ---------------------------------------------------------------------------
# 对比评估
# ---------------------------------------------------------------------------

def evaluate_model(
        name: str,
        provider,
        documents: list[str],
        queries: list[tuple[str, int]],
) -> dict:
    """对单个模型运行完整评估。"""
    # 步骤 1：计时编码文档
    start = time.perf_counter()
    doc_vectors = provider.embed_documents(documents)
    encode_time = time.perf_counter() - start

    # 步骤 2：向量维度
    dimension = len(doc_vectors[0])

    # 步骤 3：逐条查询评估
    hits = 0
    details = []

    for query_text, expected_idx in queries:
        query_vector = provider.embed_query(query_text)

        scores = [
            cosine_similarity(query_vector, doc_vec) for doc_vec in doc_vectors
        ]
        actual_idx = max(range(len(scores)), key=lambda i: scores[i])
        top1_score = scores[actual_idx]

        if actual_idx == expected_idx:
            hits += 1

        details.append((query_text, expected_idx, actual_idx, top1_score))

    return {
        "name": name,
        "dimension": dimension,
        "encode_time": encode_time,
        "hits": hits,
        "total": len(queries),
        "accuracy": hits / len(queries),
        "details": details,
    }


# ---------------------------------------------------------------------------
# 结果展示
# ---------------------------------------------------------------------------

def print_report(results: list[dict]) -> None:
    """打印对比报告。"""
    print("\n=== Embedding 模型对比报告 ===\n")
    print(f"{'模型':<28s} {'维度':>6s} {'编码耗时':>10s} {'命中率':>12s}")
    print("─" * 60)

    for r in results:
        accuracy_str = f"{r['hits']}/{r['total']} ({r['accuracy']:.0%})"
        print(
            f"{r['name']:<28s} {r['dimension']:>6d} {r['encode_time']:>9.2f}s {accuracy_str:>12s}"
        )

    print("\n=== 逐条查询详情 ===\n")
    for query_text, expected_idx in QUERIES:
        print(f"Query：{query_text}")
        print(f"  期望文档 [{expected_idx}]：{DOCUMENTS[expected_idx][:40]}...")
        for r in results:
            for detail in r["details"]:
                if detail[0] == query_text:
                    hit_mark = "✓" if detail[1] == detail[2] else "✗"
                    print(
                        f"  {hit_mark} {r['name']:<24s} → [{detail[2]}] score={detail[3]:.4f}"
                    )
        print()


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    """加载模型、运行评估、输出报告。"""
    results = []

    print("加载 bge-small-zh-v1.5 ...")
    bge_provider = SentenceTransformerProvider("BAAI/bge-small-zh-v1.5")
    results.append(evaluate_model("bge-small-zh-v1.5", bge_provider, DOCUMENTS, QUERIES))

    print("加载 all-MiniLM-L6-v2 ...")
    minilm_provider = SentenceTransformerProvider("sentence-transformers/all-MiniLM-L6-v2")
    results.append(evaluate_model("all-MiniLM-L6-v2", minilm_provider, DOCUMENTS, QUERIES))

    try:
        print("连接 Qwen embedding ...")
        qwen_provider = QwenProvider()
        results.append(evaluate_model("Qwen embedding", qwen_provider, DOCUMENTS, QUERIES))
    except (ValueError, Exception) as err:
        print(f"跳过 Qwen：{err}")

    if not results:
        print("没有可用的模型，请检查依赖和配置。")
        sys.exit(1)

    print_report(results)


if __name__ == "__main__":
    main()
