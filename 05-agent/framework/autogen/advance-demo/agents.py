"""AutoGen 角色定义及其受限工作区工具。"""

from collections.abc import Callable
from typing import Any

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core.tools import FunctionTool

from schemas import ProductSpecification, ReviewResult
from workspace import TaskWorkspace


def _strict_tool(func: Callable[..., Any]) -> FunctionTool:
    """把工作区函数包装为 OpenAI 自动解析所要求的严格工具。"""
    # 结构化输出会触发 OpenAI SDK 自动解析，此时同一请求中的所有函数工具
    # 都必须声明 strict=true，不能依赖 AssistantAgent 的默认包装行为。
    return FunctionTool(func, description=func.__doc__ or "", strict=True)


def _extract_structured(result: Any, model_type: type[Any]) -> Any:
    """从 AutoGen 任务结果中提取指定类型的结构化消息。"""
    # 一次 Agent 运行可能产生工具调用、工具结果和最终回复等多条消息。
    # 从后向前查找，可以优先拿到最后生成的正式结构化结果。
    for message in reversed(result.messages):
        if isinstance(message, StructuredMessage) and isinstance(
            message.content, model_type
        ):
            return message.content
    raise RuntimeError(f"未收到 {model_type.__name__} 结构化输出")


def create_product_manager(model_client: Any) -> AssistantAgent:
    """创建只负责需求分析和验收标准的产品经理。"""
    return AssistantAgent(
        name="ProductManager",
        model_client=model_client,
        system_message=(
            "你是产品经理。把用户需求整理为可实现、可测试的规格。"
            "必须覆盖异常状态和验收标准，不编写代码。"
        ),
        # 指定 Pydantic 类型后，AutoGen 会要求模型按该 schema 输出，
        # 最终消息的 content 会被解析成 ProductSpecification 实例。
        output_content_type=ProductSpecification,
    )


def create_engineer(model_client: Any, workspace: TaskWorkspace) -> AssistantAgent:
    """创建只能操作当前任务目录的软件工程师。"""

    # 这些闭包是暴露给 Agent 的工具。Agent 只能调用这里显式提供的能力，
    # 不能直接拿到任意文件系统 API，从而把文件访问限制在 TaskWorkspace 内。
    def write_file(path: str, content: str) -> str:
        """写入工作区内的 UTF-8 文件；path 必须是相对路径。"""
        return workspace.write_text(path, content)

    def read_file(path: str) -> str:
        """读取工作区内的 UTF-8 文件。"""
        return workspace.read_text(path)

    def list_files() -> list[str]:
        """列出工作区内所有文件。"""
        return workspace.list_files()

    return AssistantAgent(
        name="Engineer",
        model_client=model_client,
        tools=[
            _strict_tool(write_file),
            _strict_tool(read_file),
            _strict_tool(list_files),
        ],
        # 一次 run 中允许模型连续执行最多 20 次工具调用，足够创建并检查多个文件，
        # 同时也避免模型陷入无限工具调用循环。
        max_tool_iterations=20,
        system_message=(
            "你是软件工程师。你必须使用工具把完整可运行代码写入工作区，不能只在回复中展示代码。"
            "入口文件必须是 app.py。返工时先读取现有文件，再按审查意见最小修改。"
            "使用 Python 标准库访问网络，确保错误处理、加载状态和刷新操作完整。"
        ),
    )


def create_code_reviewer(model_client: Any, workspace: TaskWorkspace) -> AssistantAgent:
    """创建读取真实文件并返回结构化结论的代码审查员。"""

    # 审查员只有读取能力，没有 write_file，因此不能一边审查一边偷偷修改代码。
    def read_file(path: str) -> str:
        """读取工作区内的 UTF-8 文件。"""
        return workspace.read_text(path)

    def list_files() -> list[str]:
        """列出工作区内所有文件。"""
        return workspace.list_files()

    return AssistantAgent(
        name="CodeReviewer",
        model_client=model_client,
        tools=[_strict_tool(read_file), _strict_tool(list_files)],
        max_tool_iterations=20,
        system_message=(
            "你是严格的代码审查员。必须先使用工具列出并读取工作区中的真实文件。"
            "检查需求覆盖、错误处理、安全性和可运行性。任何问题都 approved=false，"
            "issues 必须是工程师可执行的具体修改项；全部满足才 approved=true。"
        ),
        # ReviewResult 将自由文本审查转换为程序可判断的 approved/issues 字段。
        output_content_type=ReviewResult,
    )


def create_user_proxy(input_func: Callable[[str], str] | None = None) -> UserProxyAgent:
    """创建只负责最终用户验收的代理。"""
    # 未传 input_func 时，UserProxyAgent 使用默认控制台输入；测试时可以注入假函数。
    return UserProxyAgent(
        name="UserAcceptance",
        input_func=input_func,
        description="展示可访问地址并收集用户通过或问题反馈，不负责编写代码。",
    )


class ProductManagerRunner:
    """把产品经理 Agent 包装为工作流可调用对象。"""

    def __init__(self, agent: AssistantAgent) -> None:
        """保存产品经理 Agent。"""
        self.agent = agent

    async def plan(self, task: str) -> ProductSpecification:
        """分析用户任务并返回结构化产品规格。"""
        # agent.run 返回的是包含多条消息的 TaskResult，而不是直接返回业务对象。
        result = await self.agent.run(task=task)
        return _extract_structured(result, ProductSpecification)


class EngineerRunner:
    """把工程师 Agent 包装为开发工作流接口。"""

    def __init__(self, agent: AssistantAgent, workspace: TaskWorkspace) -> None:
        """保存工程师 Agent 和用于结果校验的工作区。"""
        self.agent = agent
        self.workspace = workspace

    async def implement(self, task: str) -> None:
        """要求工程师落盘实现，并检查确实产生了文件。"""
        await self.agent.run(task=task)
        # 模型可能只在最终回复里粘贴代码而忘记调用 write_file；这里进行兜底检查。
        if not self.workspace.list_files():
            raise RuntimeError("工程师没有向工作区写入任何文件")


class ReviewerRunner:
    """把审查员 Agent 包装为开发工作流接口。"""

    def __init__(self, agent: AssistantAgent) -> None:
        """保存代码审查 Agent。"""
        self.agent = agent

    async def review(self, requirements: str) -> ReviewResult:
        """审查磁盘文件并提取可机读结论。"""
        # 每次复审都传入原始规格，避免多轮对话后审查目标逐渐偏移。
        result = await self.agent.run(
            task=f"请根据以下规格审查工作区代码：\n{requirements}"
        )
        return _extract_structured(result, ReviewResult)


class UserAcceptanceRunner:
    """通过 UserProxyAgent 收集真实用户的最终验收意见。"""

    def __init__(self, agent: UserProxyAgent) -> None:
        """保存用户代理 Agent。"""
        self.agent = agent

    async def request(self, url: str) -> str:
        """展示访问地址并返回用户输入的验收结论。"""
        prompt = (
            f"应用已经启动：{url}\n"
            "请打开链接完成测试。通过请输入“通过”；发现问题请直接描述。"
        )
        result = await self.agent.run(task=prompt)
        # UserProxyAgent 的用户输入也会被包装成消息，需要从结果消息列表中取回。
        for message in reversed(result.messages):
            if isinstance(message, TextMessage) and message.source == self.agent.name:
                return message.content.strip()
        raise RuntimeError("没有收到用户验收结果")
