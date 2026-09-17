"""2.7.1 Embedding 模型对比实验 — 框架代码（核心逻辑由学习者填充）。

对比三个 Embedding 模型在同一组中文文档 + 查询上的表现：
- Qwen embedding（云端，OpenAI 兼容接口）
- bge-small-zh-v1.5（本地，中文专项）
- all-MiniLM-L6-v2（本地，英文基线）

对比维度：向量维度、编码速度、语义检索准确性。
"""

import os
import sys
import time
from math import sqrt
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from sentence_transformers import SentenceTransformer

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
    ("如何减少大模型的幻觉？", 0),  # 期望命中 doc[0]
    ("怎样快速找到语义相近的文档？", 1),  # 期望命中 doc[1]
    ("注意力机制是什么？", 2),  # 期望命中 doc[2]
    ("文本相似度怎么算？", 5),  # 期望命中 doc[5]
    ("有什么好吃的推荐？", 4),  # 期望命中 doc[4]
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
        # 加载 sentence-transformers 模型
        #   提示：from sentence_transformers import SentenceTransformer
        #         self._model = SentenceTransformer(model_name)
        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        """返回模型输出的向量维度。"""
        # 获取模型的输出维度
        #   提示：模型对象有一个方法可以获取 sentence embedding 的维度
        return self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        """批量编码文档。"""
        # 用模型批量编码 texts，返回 list[list[float]]
        #   提示：self._model.encode(texts) 返回 numpy 数组，需要 .tolist()
        return self._model.encode(texts).tolist()

    def embed_query(self, text: str) -> Vector:
        """编码单条查询。"""
        # 编码单条文本
        #   提示：encode 也可以接受单个字符串
        # self._model.encode(text) 返回的是一个 numpy 数组（numpy.ndarray），
        # 不是 Python 原生的 list[float]。需要tolist转为 Vector
        return self._model.encode(text).tolist()


class QwenProvider:
    """通过 OpenAI 兼容接口调用 Qwen embedding。"""

    def __init__(self):
        # 复用 2.2.1 中的 create_openai_embedding_service 逻辑
        #   提示：从 .env 读取 OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_EMBEDDING_MODEL
        #         用 langchain_openai.OpenAIEmbeddings 创建 provider
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
        self._provider = OpenAIEmbeddings(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            # 部分 OpenAI 兼容接口只接受字符串数组，不接受 LangChain 默认生成的 token 数组。
            # 如果保持默认值 True，可能收到 400：input must be an array of strings。
            check_embedding_ctx_length=False,
        )

    @property
    def dimension(self) -> int | None:
        """云端模型维度需要编码后才能知道，返回 None 表示稍后获取。"""
        return None

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        """批量编码文档。"""
        # 离线入库时应该批量编码，减少远程请求次数和网络开销。
        return self._provider.embed_documents(texts)

    def embed_query(self, text: str) -> Vector:
        """编码单条查询。"""
        # 在线检索只处理当前 Query，因此调用单条查询接口即可。
        return self._provider.embed_query(text)


# ---------------------------------------------------------------------------
# 对比评估
# ---------------------------------------------------------------------------

def evaluate_model(name: str, provider, documents: list[str], queries: list[tuple[str, int]]) -> dict:
    """对单个模型运行完整评估，返回结果字典。

    评估内容：
    1. 编码速度（文档批量编码耗时）
    2. 向量维度
    3. 检索准确性（每个 query 的 Top-1 是否命中期望文档）
    """
    # 实现以下步骤
    #
    # 步骤 1：计时 — 批量编码所有文档
    #   提示：用 time.perf_counter() 记录编码前后的时间差
    _start = time.perf_counter()
    doc_vectors = provider.embed_documents(documents)
    encode_time = time.perf_counter() - _start

    # 步骤 2：记录向量维度
    #   提示：取第一个文档向量的 len()
    dimensions = len(doc_vectors[0])

    # 步骤 3：逐条编码 query，计算与所有文档的余弦相似度，取 Top-1
    #   提示：对每个 (query_text, expected_index)：
    #         - 编码 query
    #         - 计算 query 向量和每个文档向量的 cosine_similarity
    #         - 找到相似度最高的文档索引
    #         - 与 expected_index 比较，判断是否命中
    hits = 0
    details = []
    for query_text, expected_index in queries:
        query_vector = provider.embed_query(query_text)
        # 计算余弦相似度
        scores = [
            cosine_similarity(query_vector, doc_vec) for doc_vec in doc_vectors
        ]
        # max() 默认比较的是 range(len(scores)) 里的值，也就是 0、1、2、3...
        #   这些索引本身，那永远返回最大的索引。
        #   key 参数告诉 max()：别比索引本身，去比这个索引对应的分数。
        # 所以actual_idx 返回的是分数最大的那个索引
        actual_idx = max(range(len(scores)), key=lambda i: scores[i])
        top1_score = scores[actual_idx]
        if actual_idx == expected_index:
            hits += 1

        details.append((query_text, expected_index, actual_idx, top1_score))

    # 步骤 4：汇总结果
    #   返回格式：
    #   {
    #       "name": name,
    #       "dimension": 向量维度,
    #       "encode_time": 编码耗时（秒）,
    #       "hits": 命中次数,
    #       "total": 总查询数,
    #       "accuracy": 命中率,
    #       "details": [(query, expected_idx, actual_idx, top1_score), ...],
    #   }

    # 占位返回，填充后替换
    return {
        "name": name,
        "dimension": dimensions,
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
    # 实现对比报告输出，建议格式：
    #
    # === Embedding 模型对比报告 ===
    #
    # 模型            维度    编码耗时    命中率
    # ─────────────────────────────────────────
    # bge-small-zh    512     0.12s       4/5 (80%)
    # MiniLM-L6       384     0.08s       2/5 (40%)
    # Qwen            1024    0.45s       5/5 (100%)
    #
    # === 逐条查询详情 ===
    # （每个 query 在各模型下的 Top-1 结果和分数）
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

    # --- 本地模型 ---
    print("加载 bge-small-zh-v1.5 ...")
    bge_provider = SentenceTransformerProvider("BAAI/bge-small-zh-v1.5")
    print("加载 all-MiniLM-L6-v2 ...")
    # 创建 SentenceTransformerProvider("sentence-transformers/all-MiniLM-L6-v2")
    minilm_provider = SentenceTransformerProvider("sentence-transformers/all-MiniLM-L6-v2")

    # --- 云端模型 ---
    # Qwen 需要 .env 中的 API 配置
    print("连接 Qwen embedding ...")
    # 创建 QwenProvider()
    try:
        qwen_provider = QwenProvider()
    except Exception as e:
        raise e

    results.append(
        evaluate_model(name="bge-small-zh-v1.5", provider=bge_provider, documents=DOCUMENTS, queries=QUERIES)
    )
    results.append(
        evaluate_model(name="all-MiniLM-L6-v2", provider=minilm_provider, documents=DOCUMENTS, queries=QUERIES))

    results.append(
        evaluate_model(name="qwen-embedding", provider=qwen_provider, documents=DOCUMENTS, queries=QUERIES))

    if not results:
        print("没有可用的模型，请检查依赖和配置。")
        sys.exit(1)

    print_report(results)


if __name__ == "__main__":
    main()

# 输出：
# === Embedding 模型对比报告 ===
#
# 模型                               维度       编码耗时          命中率
# ────────────────────────────────────────────────────────────
# bge-small-zh-v1.5               512      0.10s    4/5 (80%)
# all-MiniLM-L6-v2                384      0.01s    1/5 (20%)
# qwen-embedding                 1024      0.70s   5/5 (100%)
#
# === 逐条查询详情 ===
#
# Query：如何减少大模型的幻觉？
#   期望文档 [0]：RAG 通过检索外部知识库来增强大模型的回答，减少幻觉。...
#   ✓ bge-small-zh-v1.5        → [0] score=0.7086
#   ✗ all-MiniLM-L6-v2         → [6] score=0.7171
#   ✓ qwen-embedding           → [0] score=0.7279
#
# Query：怎样快速找到语义相近的文档？
#   期望文档 [1]：向量数据库使用近似最近邻算法实现高效的语义检索。...
#   ✓ bge-small-zh-v1.5        → [1] score=0.5463
#   ✗ all-MiniLM-L6-v2         → [5] score=0.8630
#   ✓ qwen-embedding           → [1] score=0.6582
#
# Query：注意力机制是什么？
#   期望文档 [2]：Transformer 模型通过自注意力机制捕捉文本中的长距离依赖。...
#   ✗ bge-small-zh-v1.5        → [6] score=0.5136
#   ✗ all-MiniLM-L6-v2         → [0] score=0.6613
#   ✓ qwen-embedding           → [2] score=0.6015
#
# Query：文本相似度怎么算？
#   期望文档 [5]：余弦相似度通过计算向量夹角衡量文本的语义相关性。...
#   ✓ bge-small-zh-v1.5        → [5] score=0.6926
#   ✓ all-MiniLM-L6-v2         → [5] score=0.8359
#   ✓ qwen-embedding           → [5] score=0.7152
#
# Query：有什么好吃的推荐？
#   期望文档 [4]：北京烤鸭是北京最著名的传统美食之一。...
#   ✓ bge-small-zh-v1.5        → [4] score=0.4749
#   ✗ all-MiniLM-L6-v2         → [1] score=0.6023
#   ✓ qwen-embedding           → [4] score=0.4343