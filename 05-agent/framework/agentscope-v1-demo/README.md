# AgentScope 三国狼人杀 Demo

这是一个基于 AgentScope 1.x 的多智能体狼人杀演示。每名玩家由独立的 `ReActAgent` 驱动，主持人负责公开公告和私密信息投递。

## 环境要求

- Python 3.12+
- uv
- 支持 OpenAI 兼容 HTTP API 的模型服务

## 安装

```bash
uv sync --dev
```

## 模型配置

启动前必须设置以下环境变量：

```bash
export LLM_API_KEY="your-api-key"
export LLM_MODEL_ID="your-model-id"
export LLM_BASE_URL="https://your-model-service.example.com/v1"
```

缺少任意变量时程序会打印明确错误并返回非零退出码。

## 启动

默认运行包含猎人的八人局：

```bash
uv run python main.py
```

可用参数：

```bash
uv run python main.py \
  --players 9 \
  --max-rounds 12 \
  --discussion-rounds 3 \
  --agent-attempts 2
```

- `--players`：支持 `6`、`8`、`9`，默认 `8`。
- `--max-rounds`：达到该轮数仍未分出胜负时判定平局。
- `--discussion-rounds`：狼人每夜讨论轮数。
- `--agent-attempts`：单次 Agent 调用失败时的最大尝试次数。

## 角色规则

- 狼人只能击杀当前存活的非狼人玩家。
- 预言家不能查验自己。
- 女巫一晚最多使用一瓶药，不能毒自己。
- 猎人被狼人击杀或被放逐时可以发表遗言并开枪；被毒杀时不能开枪。
- 守护者可以守护自己，但不能连续两晚守护同一名玩家；守护抵挡狼刀，不抵挡毒药。
- 白天投票不能投自己；平票或全员弃票时本轮无人出局。

## 消息格式

控制台输出区分发送方、消息类型和可见范围：

```text
[系统][阶段] 第1轮游戏开始
[主持人][公开公告] 现在开始自由讨论
[主持人][私密通知][→预言家] 查验结果：曹操是狼人
[玩家][公开发言][刘备] 我认为曹操的发言存在矛盾
[玩家][猎人遗言][赵云] 我决定带走曹操
```

私密夜间信息会保留在控制台以便调试，但只写入对应玩家或阵营的 Agent 记忆。

## 验证

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mypy
uv run python -m compileall -q .
```
