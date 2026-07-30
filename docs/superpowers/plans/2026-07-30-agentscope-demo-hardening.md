# AgentScope 狼人杀 Demo 完整修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复已审查出的全部功能、规则、可靠性和工程质量问题，并提交一组可验证的模块化改动。

**Architecture:** 将 800 行主文件拆成 CLI、游戏引擎、夜间阶段和白天阶段；使用动态 Pydantic 模型限制不同玩家的合法目标；使用纯函数处理平票、弃票和胜负；通过统一 Agent 调用重试和显式配置校验提高可恢复性。

**Tech Stack:** Python 3.12、AgentScope 1.x、Pydantic 2、Pytest、Ruff、Pyright、Mypy

## Global Constraints

- 关键代码包含中文注释，公开方法包含中文文档注释。
- 默认 8 人局；仅支持 6、8、9 人。
- 白天平票或全员弃票无人出局。
- 守护者可守自己但不能连续守同一人，只抵挡狼刀。
- 保留当前工作区 `util.py` 的用户修改意图，在修复后纳入最终提交。

---

### Task 1: 测试基线与配置

**Files:**
- Create: `tests/test_config.py`
- Create: `tests/test_rules.py`
- Modify: `pyproject.toml`
- Create: `config.py`

- [x] 编写环境变量、CLI、投票和平票失败测试。
- [x] 实现 `GameConfig`、参数解析和非零退出码。
- [x] 修复投票返回类型和角色映射缺失处理。

### Task 2: 动态目标模型

**Files:**
- Create: `tests/test_output_models.py`
- Modify: `output.py`
- Modify: `prompt.py`

- [x] 编写狼人、预言家、投票和守护者目标失败测试。
- [x] 移除固定 JSON 系统提示冲突。
- [x] 实现按行动者动态排除非法目标的模型。

### Task 3: 阶段模块和守护者

**Files:**
- Create: `night_phases.py`
- Create: `day_phases.py`
- Create: `tests/test_night_phases.py`
- Create: `tests/test_day_phases.py`
- Modify: `roles.py`

- [x] 实现守护者状态、连续守护限制和狼刀抵挡。
- [x] 将夜间与白天逻辑从主文件拆出。
- [x] 验证猎人狼杀/放逐触发、毒杀禁用和遗言广播。

### Task 4: 游戏引擎与恢复

**Files:**
- Create: `game.py`
- Replace: `main.py`
- Create: `tests/test_game.py`

- [x] 实现统一 Agent 调用重试和阶段降级。
- [x] 使用配置中的人数、轮数和讨论轮数。
- [x] 实现最大轮数平局公告和明确返回结果。

### Task 5: 文档与 CI

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `.github/workflows/agentscope-v1-demo.yml`

- [x] 补齐安装、配置、规则和运行文档。
- [x] 配置 Ruff、Pyright、Mypy、Pytest 和 GitHub Actions。
- [x] 运行全量测试、静态检查、编译和差异检查。
- [x] 复核工作区并按 Conventional Commits 提交。
