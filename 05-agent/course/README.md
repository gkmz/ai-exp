# Agent 开发学习实践

按照 `notebook/B-Area/010-AI/Agent开发/0. Agent开发学习大纲.md` 的章节顺序组织，配合 `学习规范.md` 使用。

## 目录结构

```
course/
├── ch01-basics/            # 第一章：Agent 开发基础
├── ch02-llm-decision/      # 第二章：LLM 驱动的决策
├── ch03-tool-calling/      # 第三章：工具调用
├── ch04-patterns/          # 第四章：Agent 经典范式
├── ch05-state-memory/      # 第五章：状态与记忆
├── ch06-workflow/          # 第六章：Agent 工作流编排
├── ch07-human-in-loop/     # 第七章：Human-in-the-loop
├── ch08-external/          # 第八章：Agent 与外部能力
├── ch09-multi-agent/       # 第九章：多 Agent 系统
├── ch10-frameworks/        # 第十章：Agent 框架与实现
├── ch11-evaluation/        # 第十一章：Agent 评测与可靠性
├── ch12-security/          # 第十二章：Agent 安全
├── ch13-engineering/       # 第十三章：Agent 工程化
├── ch14-productization/    # 第十四章：Agent 产品化
├── ch15-projects/          # 第十五章：Agent 综合实践
└── ch16-advanced/          # 第十六章：Agent 高级方向
```

## 技术栈

| 阶段 | 语言 | 方式 | 依赖 |
|------|------|------|------|
| 第 1-4 章 | Python | 手写 | openai, pydantic |
| 第 5-9 章 | Python | 手写 + pydantic | + sqlite |
| 第 10 章 | Python | 框架学习 | + langgraph |
| 第 11-16 章 | Python | 框架为主 | + fastapi, docker |

## 章节内文件约定

```
ch03-tool-calling/
├── 3.2-tool-schema/          # 按小节编号
│   ├── skeleton.py           # AI 提供的代码框架（[示例] 类型）
│   ├── mine.py               # 我的实现
│   └── reference.py          # 参考实现（完成后查看）
├── 3.5-multi-tool/           # [实践] 类型
│   ├── task.md               # 实践任务描述
│   ├── mine.py               # 我的实现
│   └── reference.py          # 参考实现
└── README.md                 # 本章学习笔记和进度
```

## 学习类型标记

- `[理论]` — 只写笔记，不编码
- `[示例]` — AI 提供框架，我填核心逻辑
- `[实践]` — AI 提供任务，我独立实现
- `[项目]` — AI 提供需求，我独立完成

## 与旧代码的关系

项目根目录下的 `first-agent-py/`、`handwrite/`、`framework/`、`simple-plan/`、`travel-planning/` 是之前按书籍学习的代码，独立保留。本目录按大纲重新组织，两条学习线并行。
