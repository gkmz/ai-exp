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
export LLM_PROVIDER="openai"
# 可选：开启后显示所有身份和私密行动，默认 false
export SPECTATOR_MODE="true"
```

缺少任意变量时程序会打印明确错误并返回非零退出码。

- `LLM_PROVIDER=openai`（默认）：用于 OpenAI Chat Completions 兼容接口，通常 `LLM_BASE_URL` 以 `/v1` 结尾。
- `LLM_PROVIDER=dashscope`：仅用于 DashScope 原生 Generation API，此时 `LLM_BASE_URL` 必须是 DashScope 原生根地址，例如 `https://dashscope.aliyuncs.com`。

不要把 OpenAI 兼容 `/v1` 地址交给 `dashscope` provider。DashScope SDK 会追加自己的原生 Generation 路径，从而导致 HTTP 404。

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

## 观战模式

- 默认关闭：开局身份显示为“未公开”，私密通知和私密行动在控制台显示“内容已隐藏”。
- 开启方式：设置 `SPECTATOR_MODE=true`，适合单人演示和调试。
- 风险提示：开启后会显示狼人协商、神职行动和完整身份，不适合玩家共用同一终端。
- 无论是否开启，游戏结束后都会显示最终身份表。

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
════════════════════════════════════════
          三国狼人杀 · 游戏开始
════════════════════════════════════════

┌────────────────────────────────────────┐
│ 第 1 夜 · 夜间行动
└────────────────────────────────────────┘

[主持人][公开公告] 现在开始自由讨论
[主持人][私密通知][→预言家] 内容已隐藏
[玩家][公开发言][刘备] 我认为曹操的发言存在矛盾
[玩家][猎人遗言][赵云] 我决定带走曹操
```

阶段标题和结算摘要只用于组织控制台输出，不会写入 Agent 记忆。私密消息始终只写入对应玩家或阵营的 Agent 记忆；是否在控制台展示原文由观战模式决定。

## 验证

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mypy
uv run python -m compileall -q .
```
