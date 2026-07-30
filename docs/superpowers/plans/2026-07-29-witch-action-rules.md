# 女巫行动规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正女巫行动字段语义，确保每晚最多使用一瓶药、毒药目标有效且不能是女巫自己，并允许平安夜使用毒药。

**Architecture:** 使用动态 Pydantic 模型根据当前存活玩家、女巫身份和药品状态约束结构化输出。业务层保留独立防御校验，避免异常 metadata 绕过模型约束或错误消耗药品。

**Tech Stack:** Python 3.12、Pydantic 2、AgentScope 1.x

## Global Constraints

- 关键代码使用明确的中文注释。
- 公开方法使用明确的文档注释。
- 不引入新的测试框架或额外依赖。
- 不提交用户当前工作区中的无关改动。

---

### Task 1: 动态女巫行动模型

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/output.py`

**Interfaces:**
- Consumes: 当前存活 Agent、女巫姓名、解药和毒药的可用状态。
- Produces: `get_witch_action_model(...) -> type[BaseModel]`。

- [x] 编写临时失败断言，确认动态模型接口尚不存在。
- [x] 实现 `poison_target` 字段和跨字段校验。
- [x] 验证同时用药、毒自己、无目标和无效目标都会失败。
- [x] 验证合法救人、合法毒人和不行动能够通过。

### Task 2: 女巫阶段业务校验

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/main.py`

**Interfaces:**
- Consumes: 动态女巫行动模型输出的 `Msg.metadata`。
- Produces: `(final_killed, poisoned_player)` 夜间结算结果。

- [x] 移除平安夜提前返回，使女巫仍可使用毒药。
- [x] 调用动态模型并传入药品状态。
- [x] 增加一晚一瓶药和毒药目标的运行时防御校验。
- [x] 确保非法行动不会消耗药品。

### Task 3: 角色规则提示与验证

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/prompt.py`
- Modify: `05-agent/framework/agentscope-v1-demo/roles.py`

**Interfaces:**
- Consumes: 女巫角色规则。
- Produces: 与程序约束一致的系统提示和角色能力说明。

- [x] 补充每晚最多使用一瓶药和不能毒自己的规则。
- [x] 运行动态模型断言和 Python 编译检查。
- [x] 检查 `git diff` 与 `git status`，确认无意外改动。
