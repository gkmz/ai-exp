"""2.5 结构化输出与状态更新：学习者实现文件。"""
import json
from json import JSONDecodeError
from dataclasses import dataclass, replace
from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationError
from typing import Any, Literal


class Decision(BaseModel):
    """描述模型提出的下一步决策。"""

    # 不允许扩展额外属性
    model_config = ConfigDict(extra="forbid")

    # 只能是这两个值
    action: Literal["tool_call", "finish"]
    reason: str = Field(min_length=1)
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> "Decision":
        """检查不同动作所需的专属字段。"""
        # 校验必填字段，并拒绝另一个动作的专属字段
        # 工具调用必须有工具名称
        if self.action == "tool_call" and not self.tool_name:
            raise ValueError("tool_call 必须提供 tool_name")
        # 工具调用不能有最终答案
        if self.action == "tool_call" and self.answer is not None:
            raise ValueError("tool_call 不能提供 answer")
        # 最终回答阶段必须有answer
        if self.action == "finish" and not self.answer:
            raise ValueError("finish 必须提供 answer")
        # 最终回答阶段必须不能存在工具调用
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
    """解析 JSON 并返回经过业务校验的决策。"""
    # 捕获 JSONDecodeError，并将 JSON 对象交给 Decision.model_validate
    try:
        data = json.loads(raw)
        return Decision.model_validate(data)
    except (JSONDecodeError, ValidationError, TypeError) as e:
        raise ValueError("模型输出不是合法决策") from e


def apply_decision(state: AgentState, decision: Decision) -> AgentState:
    """根据决策返回新状态，不修改传入的旧状态。"""
    # 分别处理 tool_call 和 finish，并将 step 加一
    if decision.action == "tool_call":
        # replace方法适合将frozen的dataclass的属性进行替换
        # 只能传入 dataclass 中存在且参与初始化的字段，否则会报错。
        # replace() 是浅复制；如果字段中包含 list、dict 等可变对象，新旧对象可能仍共享这些内部对象。
        return replace(state,
                       step=state.step + 1,
                       status="waiting_tool",
                       pending_tool=decision.tool_name,
                       final_answer=None)
    elif decision.action == "finish":
        return replace(state,
                       step=state.step + 1,
                       status="completed",
                       pending_tool=None,
                       final_answer=decision.answer
                       )
    else:
        raise ValueError(f"未知的 action: {decision.action}")


def process_model_output(state: AgentState, raw: str) -> AgentState:
    """完成模型输出解析和状态更新。"""
    # 串联 parse_decision 与 apply_decision
    decision = parse_decision(raw)
    return apply_decision(state, decision)


def main() -> None:
    """演示工具调用和结束决策的状态变化。"""
    # 打印两次 process_model_output 的结果
    # 创建状态
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
