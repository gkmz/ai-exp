# 2.7.1 Embedding 模型对比实验

对应笔记：`notes/2.7.1 Embedding 模型对比实验.md`

## 学习目标

- 对比云端模型（Qwen）和本地开源模型（bge-small-zh、MiniLM）的实际表现。
- 理解向量维度、编码速度、语义检索准确性之间的权衡。
- 体会中文专项模型与通用英文模型在中文场景下的差异。

## 文件

- `embedding_comparison_skeleton.py`：框架代码，核心逻辑留空由学习者填充。
- `embedding_comparison_reference.py`：参考实现，完成后对比。
- `test_embedding_comparison.py`：使用 Fake Provider 的离线测试。

## 编码引导

### 步骤 1：实现 SentenceTransformerProvider

- 在 `__init__` 中用 `SentenceTransformer(model_name)` 加载模型
- `dimension` 属性用模型自带的方法获取
- `embed_documents` 用 `encode()` 批量编码，注意返回类型转换
- `embed_query` 编码单条文本

**关键点**：`encode()` 返回 numpy 数组，需要 `.tolist()` 转为 Python 列表。

### 步骤 2：实现 QwenProvider

- 复用 2.2.1 中的 `.env` 读取和 `OpenAIEmbeddings` 创建逻辑
- 注意 `check_embedding_ctx_length=False`

### 步骤 3：实现 evaluate_model

- 用 `time.perf_counter()` 计时文档编码
- 逐条编码 query，计算与所有文档向量的余弦相似度
- 找 Top-1 索引，与期望索引比较
- 汇总为结果字典

### 步骤 4：实现 print_report

- 输出汇总表格（模型、维度、耗时、命中率）
- 输出逐条查询的 Top-1 命中情况

### 步骤 5：补全 main 函数

- 创建三个 Provider，逐个调用 evaluate_model
- Qwen 用 try/except 包裹，缺配置时跳过

## 运行

先跑离线测试（验证评估逻辑）：

```bash
uv run pytest ch02-vector-and-embedding/2.7.1-embedding-comparison
```

再跑真实模型对比（首次会下载本地模型）：

```bash
uv run python ch02-vector-and-embedding/2.7.1-embedding-comparison/embedding_comparison_skeleton.py
```

## 预期行为

- bge-small-zh-v1.5：512 维，中文检索命中率高
- all-MiniLM-L6-v2：384 维，速度快但中文检索可能较弱
- Qwen embedding：1024 维，命中率高但有网络延迟
