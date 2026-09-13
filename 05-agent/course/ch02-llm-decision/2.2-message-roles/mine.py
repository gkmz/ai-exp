"""2.2 消息角色示例框架：请补全 TODO 后运行。"""

from typing import Any

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def build_messages() -> list[dict[str, Any]]:
    """组装一轮 System → User → Assistant → Tool 消息。"""
    messages: list[dict[str, Any]] = []
    # 添加 system 消息，说明助手规则
    messages.append({"role": "system", "content": "你是一个天气助手"})
    # TODO: 添加 user 消息，表达用户目标
    messages.append({"role": "user", "content": "成都明天天气怎么样？"})
    #  添加 assistant 消息，记录工具调用及 tool_call_id
    messages.append(
        {
            "role": "assistant",
            "tool_calls": [{"id": "abc", "name": "get_weather", "arguments": {"city": "成都"}}],
        }
    )
    # TODO: 添加 tool 消息，写入工具返回结果
    messages.append({"role": "tool", "content": "成都明天多云，24°C", "tool_call_id": "abc"})
    return messages


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """校验角色名称和消息必需字段。"""
    for msg in messages:
        role = msg.get("role")
        # TODO: 检查 role 是否属于 ALLOWED_ROLES
        if role not in ALLOWED_ROLES:
            raise ValueError(f"invalid role {role}")
        # TODO: 检查非 tool 消息是否包含 content 或 tool_calls
        if role == "assistant":
            if "content" not in msg and not msg.get("tool_calls"):
                raise ValueError("assistant消息必须包含content 或 tool_calls")
        # TODO: 检查 tool 消息是否包含 tool_call_id
        elif role == "tool":
            if not msg.get("tool_calls") or "content" not in msg:
                raise ValueError("tool 消息必须包含 tool_call_id 或 content")
        elif "content" not in msg:
            raise ValueError("非tool调用和assistant的消息必须包含content")


def main() -> None:
    """打印并校验消息列表。"""
    messages = build_messages()
    validate_messages(messages)
    for message in messages:
        print(message["role"], message)


if __name__ == "__main__":
    main()
