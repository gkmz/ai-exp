# RAG 学习实验

本目录按 `notes` 中的学习顺序组织。每个实验目录都包含对应源码、测试和运行说明，先理解原理，再运行实验。

## 学习顺序

### 第一章：基础实验

- `ch01-basics/2.2.1-real-embedding`：真实 Embedding 模型调用，以及 Document/Query 两条向量化流程。
- `ch01-basics/2.3.1-tfidf`：词袋模型和 TF-IDF 的文本向量化。
- `ch01-basics/2.5.1-vector-similarity`：点积、欧氏距离和余弦相似度。

后续章节将在完成基础实验后继续添加，例如文档处理、向量数据库和最小 RAG。框架示例单独放在 `frameworks/`，避免框架封装掩盖底层原理。

## 运行测试

在本目录执行：

```bash
uv run pytest
```

真实 Embedding 实验的自动化测试使用 Fake Provider，不会调用远程 API。运行真实模型前，请参考 `.env.example` 配置服务商 API Key、Base URL 和模型名。
