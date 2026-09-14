# 2.2.1 真实 Embedding 向量化实验

对应笔记：`notes/2.2.1 真实Embedding向量化实验.md`

## 学习目标

- 区分 Document 向量和 Query 向量。
- 理解批量文档向量化与单条 Query 向量化。
- 通过 `EmbeddingProvider` 保持模型服务可替换。

## 文件

- `embedding_model.py`：Embedding 服务封装。
- `test_embedding_model.py`：使用 Fake Provider 的离线测试。

## 运行

```bash
uv run pytest 2.2.1-real-embedding
```

运行真实 Embedding 示例：

```bash
uv run python ch02-vector-and-embedding/2.2.1-real-embedding/embedding_model.py
```

真实调用需要先在 `04-rag/.env` 中配置 Embedding 模型相关环境变量。
