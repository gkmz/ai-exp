"""高级软件开发团队演示的命令行入口。"""

import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agents import (
    EngineerRunner,
    ProductManagerRunner,
    ReviewerRunner,
    UserAcceptanceRunner,
    create_code_reviewer,
    create_engineer,
    create_product_manager,
    create_user_proxy,
)
from model_client import create_model_client
from process_manager import StreamlitProcess
from verifier import WorkspaceVerifier
from workflow import DevelopmentWorkflow
from workspace import TaskWorkspace


DEFAULT_TASK = """开发一个比特币价格显示应用：
- 使用 Streamlit，入口文件为 app.py
- 实时显示比特币 USD 当前价格
- 显示 24 小时涨跌幅和涨跌额
- 提供手动刷新功能
- 包含加载状态、网络超时和错误提示
- 界面简洁，用户可以直接运行和测试
"""


def _accepted(feedback: str) -> bool:
    """判断用户输入是否表示验收通过。"""
    # 同时兼容中文和常见英文输入，避免用户必须记住唯一的结束口令。
    return feedback.strip().lower() in {"通过", "pass", "passed", "terminate"}


async def run(task: str = DEFAULT_TASK) -> None:
    """运行从需求分析到真实用户验收的完整开发闭环。"""
    # demo_root 指向 advance-demo 目录。配置、生成工作区都统一放在这里，
    # 这样无论从哪个当前目录启动程序，路径计算都不会发生变化。
    demo_root = Path(__file__).resolve().parent
    load_dotenv(demo_root / ".env")

    # 每次运行使用独立时间戳目录，防止不同任务生成的代码互相覆盖。
    task_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    workspace = TaskWorkspace(demo_root / "workspaces" / task_id)

    # 所有需要调用大模型的 Agent 共享同一个客户端；程序结束时统一关闭。
    model_client = create_model_client()
    service: StreamlitProcess | None = None

    try:
        print(f"任务工作区：{workspace.root}")

        # 第 1 阶段：产品经理只负责把自然语言需求转换为结构化规格，
        # 不直接写代码。Pydantic 会验证模型输出是否符合 ProductSpecification。
        product_manager = ProductManagerRunner(create_product_manager(model_client))
        specification = await product_manager.plan(task)
        requirements = specification.as_prompt()
        print("产品规格已生成，工程师开始实现。")

        # 第 2 阶段：组装开发闭环所需的角色和确定性验证器。
        # Engineer/Reviewer 是大模型 Agent，WorkspaceVerifier 是普通 Python 程序。
        engineer = EngineerRunner(create_engineer(model_client, workspace), workspace)
        reviewer = ReviewerRunner(create_code_reviewer(model_client, workspace))
        verifier = WorkspaceVerifier(workspace)
        workflow = DevelopmentWorkflow(engineer, reviewer, verifier)
        user_acceptance = UserAcceptanceRunner(create_user_proxy())

        # 第 3 阶段：用户验收循环。
        # 用户发现问题后继续复用同一个工作区，工程师会读取现有文件并做增量修改。
        while True:
            # develop() 内部还包含一层“实现 -> 审查 -> 自动验证”的返工循环。
            result = await workflow.develop(requirements)
            print(f"代码审查已通过，共审查 {result.review_attempts} 次。")
            print(result.verification.summary)

            # 只有审查和自动验证都通过，才会真正启动生成的 Streamlit 应用。
            service = StreamlitProcess(workspace.root)
            url = service.start()
            feedback = await user_acceptance.request(url)

            # 每轮验收后先关闭服务，避免返工时旧进程仍占用端口或读取旧代码。
            service.stop()
            service = None

            if _accepted(feedback):
                print(f"用户验收通过。最终代码目录：{workspace.root}")
                return

            print("收到用户反馈，返回工程师修改并重新审查。")
            # 将用户反馈追加到原始规格中。下一轮仍会经过完整代码审查和自动验证，
            # 而不是让工程师修改后直接交付。
            requirements = f"{requirements}\n\n用户验收反馈（必须修复）：\n- {feedback}"
    finally:
        # finally 保证正常结束、异常退出或 Ctrl+C 时都尽量清理子进程和网络连接。
        if service:
            service.stop()
        await model_client.close()


def main() -> None:
    """启动命令行演示并统一展示可理解的错误。"""
    try:
        # AutoGen 的 Agent 调用是异步接口，命令行入口用 asyncio.run 创建事件循环。
        asyncio.run(run())
    except (ValueError, RuntimeError, TimeoutError) as error:
        # 将底层异常转换为简洁的命令行错误，同时保留异常链便于调试。
        raise SystemExit(f"运行失败：{error}") from error
