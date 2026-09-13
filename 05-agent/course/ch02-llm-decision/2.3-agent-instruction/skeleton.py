"""2.3 Agent 指令示例框架：请补全 TODO 后运行。"""
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentContext:
    """构造指令所需的动态上下文。"""
    goal: str
    state: dict[str, Any]
    tools: list[dict[str, Any]]


def build_messages(context: AgentContext) -> list[dict[str, Any]]:
    """将稳定规则与动态上下文组装成消息列表。"""
    # TODO: 编写稳定的 System 指令
    # TODO: 将 goal、state 和 tools 序列化到 User 消息
    raise NotImplementedError


def validate_action(action: dict[str, Any], tools: list[dict[str, Any]]) -> None:
    """校验模型候选行动是否存在且参数完整。"""
    # TODO: 检查 action、arguments、reason 字段及工具 Schema
    raise NotImplementedError


if __name__ == "__main__":
    context = AgentContext("检查订单 A1001 的库存", {"status": "pending"}, [{"name": "check_stock"}])
    print(build_messages(context))
