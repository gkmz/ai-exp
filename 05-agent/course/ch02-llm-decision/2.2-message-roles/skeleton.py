"""2.2 消息角色示例框架：请补全 TODO 后运行。"""

from typing import Any

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def build_messages() -> list[dict[str, Any]]:
    """组装一轮 System → User → Assistant → Tool 消息。"""
    messages: list[dict[str, Any]] = []
    # TODO: 添加 system 消息，说明助手规则
    # TODO: 添加 user 消息，表达用户目标
    # TODO: 添加 assistant 消息，记录工具调用及 tool_call_id
    # TODO: 添加 tool 消息，写入工具返回结果
    return messages


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """校验角色名称和消息必需字段。"""
    # TODO: 检查 role 是否属于 ALLOWED_ROLES
    # TODO: 检查非 tool 消息是否包含 content 或 tool_calls
    # TODO: 检查 tool 消息是否包含 tool_call_id


def main() -> None:
    """打印并校验消息列表。"""
    messages = build_messages()
    validate_messages(messages)
    for message in messages:
        print(message["role"], message)


if __name__ == "__main__":
    main()
