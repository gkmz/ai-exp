"""2.3 Agent 指令示例参考实现（不调用真实模型 API）。"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentContext:
    """保存任务目标、状态和工具描述。"""

    goal: str
    state: dict[str, Any]
    tools: list[dict[str, Any]]


SYSTEM_INSTRUCTION = "你是订单助手。只根据已验证事实做决定。返回 JSON：action、arguments、reason。"


def build_messages(context: AgentContext) -> list[dict[str, Any]]:
    """组装稳定规则和动态上下文。"""
    payload = {"goal": context.goal, "state": context.state, "tools": context.tools}
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def validate_action(action: dict[str, Any], tools: list[dict[str, Any]]) -> None:
    """验证候选行动的字段和工具名称。"""
    if set(action) != {"action", "arguments", "reason"}:
        raise ValueError("行动字段必须为 action、arguments、reason")
    if action["action"] not in {tool["name"] for tool in tools} | {"final_answer"}:
        raise ValueError(f"未知行动: {action['action']}")
    if not isinstance(action["arguments"], dict) or not isinstance(action["reason"], str):
        raise ValueError("arguments 必须是对象，reason 必须是字符串")


if __name__ == "__main__":
    context = AgentContext(
        "检查订单 A1001 的库存", {"status": "pending"}, [{"name": "check_stock"}]
    )
    print(*build_messages(context), sep="\n")
