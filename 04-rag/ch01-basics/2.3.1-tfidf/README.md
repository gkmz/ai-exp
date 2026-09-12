# 2.3.1 词袋与 TF-IDF 向量化实验

对应笔记：`notes/2.3.1 词袋与TF-IDF向量化实验.md`

## 学习目标

- 手写词袋模型，理解文本如何转换为词频向量。
- 理解 TF、IDF 和 L2 归一化。
- 对比稀疏词法向量与后续 Embedding 语义向量的差异。

## 文件

- `embedding.py`：词袋向量化实验。
- `tfidf.py`：TF-IDF 向量化实验。
- `test_embedding.py`、`test_tfidf.py`：对应自动化测试。

## 运行

```bash
uv run pytest 2.3.1-tfidf
```
