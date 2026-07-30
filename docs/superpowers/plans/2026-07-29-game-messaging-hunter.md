# 游戏消息与猎人流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立清晰的游戏消息协议并补全猎人死亡、遗言、身份公开和开枪结算流程。

**Architecture:** 新增独立消息展示模块负责统一控制台格式；主持人负责创建带类型和可见性 metadata 的消息；游戏主类负责公开广播、私密投递和玩家发言展示。猎人使用动态 Pydantic 模型约束遗言、目标和理由，并由主循环按死亡原因触发。

**Tech Stack:** Python 3.12、AgentScope 1.x、Pydantic 2

## Global Constraints

- 关键代码包含明确的中文注释。
- 公开方法包含明确的文档注释。
- 不引入新的第三方依赖或测试框架。
- 私密信息允许打印到控制台，但不得广播给无关 Agent。

---

### Task 1: 统一消息协议

**Files:**
- Create: `05-agent/framework/agentscope-v1-demo/game_messages.py`
- Modify: `05-agent/framework/agentscope-v1-demo/roles.py`

- [x] 编写消息格式和 metadata 的失败断言。
- [x] 实现消息类型、可见性和统一控制台输出。
- [x] 改造主持人公告，使其不再与默认 Agent 输出混杂。

### Task 2: 游戏消息投递

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/main.py`

- [x] 增加公开广播、私密通知和玩家消息展示方法。
- [x] 关闭玩家 Agent 默认控制台输出。
- [x] 分类打印狼人讨论、查验、用药、白天发言和投票。
- [x] 替换散落的裸 `print()`。

### Task 3: 猎人完整流程

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/output.py`
- Modify: `05-agent/framework/agentscope-v1-demo/main.py`
- Modify: `05-agent/framework/agentscope-v1-demo/prompt.py`
- Modify: `05-agent/framework/agentscope-v1-demo/roles.py`

- [x] 为猎人模型增加遗言和跨字段校验。
- [x] 实现身份公开、遗言广播、开枪理由和放弃公告。
- [x] 支持狼杀和放逐触发，禁止毒杀触发。
- [x] 对死亡列表去重并完成回归验证。
