"""2.3 Agent 指令示例框架：请补全 TODO 后运行。"""

import json
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
    messages = []
    # TODO: 编写稳定的 System 指令
    messages.append(
        {
            "role": "system",
            "content": "你是订单查询助手，只根据已验证事实做决定。返回 JSON：action、arguments、reason。如果你得到了最终答案，那么 action 应该是 final_answer",
        }
    )
    # TODO: 将 goal、state 和 tools 序列化到 User 消息
    payload = {"goal": context.goal, "state": context.state, "tools": context.tools}
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    return messages


def validate_action(action: dict[str, Any], tools: list[dict[str, Any]]) -> None:
    """校验模型候选行动是否存在且参数完整。"""
    # TODO: 检查 action、arguments、reason 字段及工具 Schema
    allowed = {tool["name"] for tool in tools}
    required = {"action", "arguments", "reason"}
    missing = required - action.keys()
    if missing:
        raise ValueError(f"缺少字段: {', '.join(sorted(missing))}")

    if action["action"] not in allowed | {"final_answer"}:
        raise ValueError(f"未知工具: {action['action']}")

    arguments = action.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("arguments 必须为对象")
    if not isinstance(action.get("reason"), str):
        raise ValueError("reason 必须为字符串")


if __name__ == "__main__":
    context = AgentContext(
        "检查订单 A1001 的库存", {"status": "pending"}, [{"name": "check_stock"}]
    )
    print(build_messages(context))
