"""工作流中使用的结构化数据模型。"""

from pydantic import BaseModel, Field


class ProductSpecification(BaseModel):
    """产品经理生成的实现规格和验收标准。"""

    # Field(description=...) 会成为结构化输出 schema 的字段说明，
    # 模型据此知道每个字段应该填写什么内容。
    summary: str = Field(description="需求摘要")
    requirements: list[str] = Field(description="功能和技术要求")
    acceptance_criteria: list[str] = Field(description="可验证的验收标准")

    def as_prompt(self) -> str:
        """将结构化规格转换为供其他智能体使用的文本。"""
        # Pydantic 模型适合程序读取；工程师和审查员更容易理解分段的自然语言提示词。
        requirements = "\n".join(f"- {item}" for item in self.requirements)
        criteria = "\n".join(f"- {item}" for item in self.acceptance_criteria)
        return f"需求摘要：{self.summary}\n\n实现要求：\n{requirements}\n\n验收标准：\n{criteria}"


class ReviewResult(BaseModel):
    """代码审查员返回的可机读审查结论。"""

    # 使用结构化字段代替“看起来像通过了”的自然语言判断，
    # 工作流可以稳定地根据 approved 决定继续验证还是返回返工。
    approved: bool = Field(description="代码是否可以进入自动验证")
    summary: str = Field(description="审查结论摘要")
    issues: list[str] = Field(description="必须修复的问题；通过时为空")


class VerificationResult(BaseModel):
    """自动化检查的执行结果。"""

    # 该结果不是大模型生成的，而是普通 Python 验证器生成的；
    # 仍使用 Pydantic，是为了让整个工作流的数据结构保持一致。
    passed: bool
    summary: str
    details: list[str]


class DevelopmentResult(BaseModel):
    """一次开发和审查循环的最终结果。"""

    # 将最终审查、验证结果和尝试次数一起返回，便于入口统一展示和记录。
    review: ReviewResult
    verification: VerificationResult
    review_attempts: int
