"""2.5 结构化输出与状态更新示例框架。"""

import json
from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Decision(BaseModel):
    """描述模型提出的下一步决策。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["tool_call", "finish"]
    reason: str = Field(min_length=1)
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> "Decision":
        """检查不同动作所需的专属字段。"""
        # TODO: 校验必填字段，并拒绝另一个动作的专属字段
        raise NotImplementedError


@dataclass(frozen=True)
class AgentState:
    """保存由运行时维护的 Agent 进度。"""

    step: int = 0
    status: str = "running"
    pending_tool: str | None = None
    final_answer: str | None = None


def parse_decision(raw: str) -> Decision:
    """解析 JSON 并返回经过业务校验的决策。"""
    # TODO: 捕获 JSONDecodeError，并将 JSON 对象交给 Decision.model_validate
    raise NotImplementedError


def apply_decision(state: AgentState, decision: Decision) -> AgentState:
    """根据决策返回新状态，不修改传入的旧状态。"""
    # TODO: 分别处理 tool_call 和 finish，并将 step 加一
    raise NotImplementedError


def process_model_output(state: AgentState, raw: str) -> AgentState:
    """完成模型输出解析和状态更新。"""
    # TODO: 串联 parse_decision 与 apply_decision
    raise NotImplementedError


def main() -> None:
    """演示工具调用和结束决策的状态变化。"""
    # TODO: 打印两次 process_model_output 的结果
    raise NotImplementedError


if __name__ == "__main__":
    main()
