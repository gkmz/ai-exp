"""2.2 消息角色示例参考实现（不调用真实模型 API）。"""
from typing import Any

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def build_messages() -> list[dict[str, Any]]:
    """构造一次天气查询的四条消息。"""
    return [
        {"role": "system", "content": "你是严谨的天气助手，只使用工具返回的事实。"},
        {"role": "user", "content": "明天北京会下雨吗？"},
        {"role": "assistant", "tool_calls": [{"id": "call_1", "name": "get_weather", "arguments": {"city": "北京"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "降雨概率 80%"},
    ]


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """校验角色、内容和工具调用关联关系。"""
    for message in messages:
        role = message.get("role")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"未知消息角色: {role}")
        if role == "tool":
            if not message.get("tool_call_id") or "content" not in message:
                raise ValueError("tool 消息必须包含 tool_call_id 和 content")
        elif role == "assistant":
            if "content" not in message and "tool_calls" not in message:
                raise ValueError("assistant 消息必须包含 content 或 tool_calls")
        elif "content" not in message:
            raise ValueError(f"{role} 消息缺少 content")


def main() -> None:
    """构造、校验并打印消息。"""
    messages = build_messages()
    validate_messages(messages)
    for index, message in enumerate(messages, start=1):
        print(f"{index}. {message['role']}: {message}")


if __name__ == "__main__":
    main()
