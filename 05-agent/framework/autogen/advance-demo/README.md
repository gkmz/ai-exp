# AutoGen 高级软件开发团队 Demo

这个版本将 Agent 对话升级为可执行的开发闭环：工程师把代码写入隔离目录，代码审查未通过会自动返工，自动检查通过后启动 Streamlit，并把真实访问地址交给用户验收。

> 名词说明：你提到的 “pandytic” 在本项目里实际是 **Pydantic**。它不是 Agent 框架，Agent 编排使用的是 **AutoGen**；Pydantic 负责定义和校验产品规格、审查结果等结构化数据。

## 工作流

```text
产品规格 -> 工程师落盘 -> 代码审查 -> 自动检查 -> 启动应用 -> 用户验收
               ^          |          |                    |
               | 审查失败 | 检查失败 |                    | 用户反馈
               +----------+----------+--------------------+
```

- 每次运行创建 `workspaces/<时间戳>/`，Agent 不能读写该目录之外的文件。
- 审查员读取磁盘上的真实文件，并返回结构化的 `approved` 和 `issues`。
- 审查或自动检查失败时，工作流把具体问题交回工程师，最多尝试 4 次。
- 服务启动后经过 HTTP 健康检查，成功才输出 `http://127.0.0.1:<port>`。
- 用户输入“通过”结束；输入问题描述会停止服务、修改代码、重新审查并再次启动。

## 核心模块

| 文件 | 职责 |
| --- | --- |
| `main.py` | 最薄的命令行入口，调用 `app.main()`。 |
| `app.py` | 组装所有角色，控制“产品规划”和“用户验收”两层外部流程。 |
| `schemas.py` | 使用 Pydantic 定义 Agent 之间传递的数据合同。 |
| `agents.py` | 创建产品经理、工程师、审查员和用户代理，并封装统一调用接口。 |
| `workflow.py` | 用普通 Python 状态机控制实现、审查、自动验证和返工。 |
| `workspace.py` | 为 Agent 提供受限文件工具，阻止 `../` 等越界访问。 |
| `verifier.py` | 检查入口、Python 语法和生成项目自带的单元测试。 |
| `process_manager.py` | 启动 Streamlit 子进程并等待健康检查通过。 |
| `model_client.py` | 从环境变量创建 AutoGen 使用的模型客户端。 |

## 一次运行的详细流程

1. `main.py` 调用 `app.main()`，后者通过 `asyncio.run()` 进入异步的 `run()`。该目录名包含连字符，不是标准 Python 包名，因此示例按脚本目录使用本地模块导入。
2. `run()` 加载 `.env`，创建带时间戳的独立 `TaskWorkspace`，然后创建共享模型客户端。
3. `ProductManagerRunner.plan()` 调用产品经理 Agent。AutoGen 要求模型按照 `ProductSpecification` 输出，Pydantic 再把结果校验并解析成 Python 对象。
4. `ProductSpecification.as_prompt()` 把结构化规格转换成工程师和审查员都能读取的文本。
5. `DevelopmentWorkflow.develop()` 启动内部返工状态机：
   - 工程师 Agent 调用 `write_file/read_file/list_files` 工具，在隔离工作区实现代码；
   - 审查员 Agent 只拥有读取工具，读取真实磁盘文件并返回 `ReviewResult`；
   - 若 `approved=false`，程序把 `issues` 交回工程师；
   - 若审查通过，`WorkspaceVerifier` 再执行入口、语法和单元测试检查；
   - 自动检查失败同样返回工程师，并从代码审查重新开始；
   - 最多尝试 4 次，超过限制会抛出明确异常。
6. 内部开发闭环通过后，`StreamlitProcess.start()` 选择本机空闲端口、启动子进程，并轮询 `/_stcore/health`。
7. 健康检查成功后，`UserAcceptanceRunner` 把真实 URL 展示给用户。
8. 用户输入“通过”时结束；输入问题时，服务先停止，反馈追加到规格，再回到第 5 步修改同一工作区。
9. 无论正常结束还是异常退出，`finally` 都会停止 Streamlit，并关闭共享模型客户端。

## Pydantic 在这里解决什么问题

如果没有 Pydantic，产品经理可能返回“需求差不多整理好了”之类的自由文本，程序很难稳定提取需求列表；审查员也可能用“总体不错，但还有一点问题”这种模糊表达，程序无法可靠判断是否应该进入下一步。

本 Demo 用 Pydantic 把这两类回复约束成固定结构：

```text
ProductSpecification
├── summary: str
├── requirements: list[str]
└── acceptance_criteria: list[str]

ReviewResult
├── approved: bool
├── summary: str
└── issues: list[str]
```

因此，**AutoGen 负责调用模型和工具，Pydantic 负责保证关键结果具有程序可读取的形状，`DevelopmentWorkflow` 负责根据这些结果决定下一步。**

## 配置与运行

在项目根目录执行：

```bash
uv sync
cp advance-demo/.env.example advance-demo/.env
```

编辑 `.env`，设置模型服务后运行：

```bash
uv run python advance-demo/main.py
```

生成的应用只监听 `127.0.0.1`，因此链接仅能从运行 Demo 的本机访问。运行过程中按 `Ctrl+C` 会进入清理逻辑并关闭 Streamlit 子进程。

## 测试

```bash
PYTHONPATH=advance-demo uv run python -m unittest discover -s advance-demo/tests -v
```

测试覆盖工作区越界保护、审查返工、自动检查返工、入口及语法检查和本地 URL 生成。真实模型调用需要有效的模型配置，不包含在离线单元测试中。
