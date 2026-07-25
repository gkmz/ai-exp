"""代码实现、审查返工和自动验证的显式工作流。"""

from typing import Protocol

from schemas import DevelopmentResult, ReviewResult, VerificationResult


class Engineer(Protocol):
    """工程师角色需要实现的接口。"""

    async def implement(self, task: str) -> None:
        """实现新需求或按照反馈修改已有文件。"""


class Reviewer(Protocol):
    """代码审查角色需要实现的接口。"""

    async def review(self, requirements: str) -> ReviewResult:
        """审查工作区文件并返回结构化结论。"""


class Verifier(Protocol):
    """自动验证角色需要实现的接口。"""

    async def verify(self) -> VerificationResult:
        """执行自动化检查并返回结果。"""


class ReviewLimitExceeded(RuntimeError):
    """达到最大审查次数但代码仍未通过。"""


class VerificationFailed(RuntimeError):
    """代码审查通过，但自动化检查失败。"""


class DevelopmentWorkflow:
    """通过明确状态转换保证审查失败后必须返工。"""

    def __init__(
        self,
        engineer: Engineer,
        reviewer: Reviewer,
        verifier: Verifier,
        max_review_attempts: int = 4,
    ) -> None:
        """配置角色和最大审查次数。"""
        # Protocol 让工作流只依赖 implement/review/verify 接口，
        # 既能接入真实 AutoGen Agent，也方便测试时传入 Fake 对象。
        if max_review_attempts < 1:
            raise ValueError("最大审查次数必须大于零")
        self.engineer = engineer
        self.reviewer = reviewer
        self.verifier = verifier
        self.max_review_attempts = max_review_attempts

    async def develop(self, requirements: str) -> DevelopmentResult:
        """持续执行工程实现和代码复审，直至通过或达到次数上限。"""
        # engineering_task 是本轮发给工程师的提示词：首轮等于原始需求，
        # 后续轮次会替换为“原始需求 + 审查/验证失败原因”。
        engineering_task = requirements
        last_review: ReviewResult | None = None
        last_verification: VerificationResult | None = None

        # 返工由程序状态机控制，不能依赖模型在自然语言中自觉选择下一角色。
        for attempt in range(1, self.max_review_attempts + 1):
            # 1. 工程师首次实现，或根据上一轮反馈修改工作区中的已有文件。
            await self.engineer.implement(engineering_task)

            # 2. 审查员始终根据原始完整需求检查磁盘上的真实代码。
            last_review = await self.reviewer.review(requirements)
            if last_review.approved:
                # 3. 大模型审查通过后，再执行不依赖模型判断的确定性检查。
                last_verification = await self.verifier.verify()
                if last_verification.passed:
                    # 审查和自动检查都通过，本次开发闭环才算成功。
                    return DevelopmentResult(
                        review=last_review,
                        verification=last_verification,
                        review_attempts=attempt,
                    )

                details = "\n".join(
                    f"- {detail}" for detail in last_verification.details
                )
                # 自动检查失败时，把真实命令输出交回工程师，下一轮仍需重新审查。
                engineering_task = (
                    f"请修改工作区中的现有实现，原始需求如下：\n{requirements}\n\n"
                    f"自动化检查失败：{last_verification.summary}\n{details}"
                )
                continue

            issues = "\n".join(f"- {issue}" for issue in last_review.issues)
            # 审查不通过时，将结构化 issues 转成工程师可直接执行的返工清单。
            engineering_task = (
                f"请修改工作区中的现有实现，原始需求如下：\n{requirements}\n\n"
                f"第 {attempt} 次代码审查未通过，必须修复：\n{issues}"
            )

        # 循环耗尽后区分“审查始终不通过”和“审查通过但自动检查始终失败”，
        # 便于调用者显示更准确的错误原因。
        if last_review and last_review.approved and last_verification:
            raise VerificationFailed(
                f"经过 {self.max_review_attempts} 次修改，自动检查仍失败：{last_verification.summary}"
            )
        summary = last_review.summary if last_review else "没有获得审查结果"
        raise ReviewLimitExceeded(
            f"经过 {self.max_review_attempts} 次审查仍未通过：{summary}"
        )
