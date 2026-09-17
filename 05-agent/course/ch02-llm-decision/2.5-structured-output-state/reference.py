"""2.5 结构化输出与状态更新参考实现。"""

import json
from dataclasses import dataclass, replace
from json import JSONDecodeError
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class Decision(BaseModel):
    """描述经过严格校验的模型决策。"""

    model_config = ConfigDict(extra="forbid")
    action: Literal["tool_call", "finish"]
    reason: str = Field(min_length=1)
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> "Decision":
        """校验动作与专属字段之间的关系。"""
        if self.action == "tool_call" and not self.tool_name:
            raise ValueError("tool_call 必须提供 tool_name")
        if self.action == "tool_call" and self.answer is not None:
            raise ValueError("tool_call 不能提供 answer")
        if self.action == "finish" and not self.answer:
            raise ValueError("finish 必须提供 answer")
        if self.action == "finish" and (self.tool_name is not None or self.arguments):
            raise ValueError("finish 不能提供工具字段")
        return self


@dataclass(frozen=True)
class AgentState:
    """保存由运行时维护的 Agent 进度。"""

    step: int = 0
    status: str = "running"
    pending_tool: str | None = None
    final_answer: str | None = None


def parse_decision(raw: str) -> Decision:
    """解析 JSON 并将 Pydantic 错误统一转换为 ValueError。"""
    try:
        payload = json.loads(raw)
        return Decision.model_validate(payload)
    except (JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError("模型输出不是合法决策") from exc


def apply_decision(state: AgentState, decision: Decision) -> AgentState:
    """根据可信决策返回新状态。"""
    if decision.action == "tool_call":
        return replace(
            state,
            step=state.step + 1,
            status="waiting_tool",
            pending_tool=decision.tool_name,
            final_answer=None,
        )
    return replace(
        state,
        step=state.step + 1,
        status="completed",
        pending_tool=None,
        final_answer=decision.answer,
    )


def process_model_output(state: AgentState, raw: str) -> AgentState:
    """完成模型输出解析和状态更新。"""
    return apply_decision(state, parse_decision(raw))


def main() -> None:
    """演示两轮决策如何推进状态。"""
    state = AgentState()
    state = process_model_output(
        state,
        '{"action":"tool_call","tool_name":"get_weather","arguments":{"city":"上海"},"reason":"需要查询天气"}',
    )
    print(state)
    state = process_model_output(
        state,
        '{"action":"finish","answer":"今天适合出门。","reason":"已获得天气结果"}',
    )
    print(state)


if __name__ == "__main__":
    main()
