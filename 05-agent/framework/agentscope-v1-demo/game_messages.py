"""游戏消息分类和控制台展示工具。"""

from enum import StrEnum


class MessageType(StrEnum):
    """游戏消息类型。"""

    PHASE = "阶段"
    PUBLIC_ANNOUNCEMENT = "公开公告"
    PRIVATE_NOTICE = "私密通知"
    PUBLIC_SPEECH = "公开发言"
    PRIVATE_SPEECH = "私密发言"
    PRIVATE_ACTION = "私密行动"
    LAST_WORDS = "猎人遗言"
    SKILL = "技能公告"
    RESULT = "结算"
    STATE = "状态"
    WARNING = "警告"
    ERROR = "错误"


class MessageVisibility(StrEnum):
    """消息可见范围。"""

    PUBLIC = "public"
    PRIVATE = "private"
    SYSTEM = "system"


class GameConsole:
    """按照发送方和消息类型统一展示控制台信息。"""

    @staticmethod
    def _format(
        sender_type: str,
        message_type: MessageType,
        content: str,
        sender_name: str | None = None,
        recipient: str | None = None,
    ) -> str:
        """生成统一的控制台消息文本。"""
        labels = [sender_type, message_type.value]
        if sender_name:
            labels.append(sender_name)
        if recipient:
            labels.append(f"→{recipient}")
        return "".join(f"[{label}]" for label in labels) + f" {content}"

    @classmethod
    def format_system(cls, message_type: MessageType, content: str) -> str:
        """生成系统消息文本。"""
        return cls._format("系统", message_type, content)

    @classmethod
    def format_moderator(
        cls,
        message_type: MessageType,
        content: str,
        recipient: str | None = None,
    ) -> str:
        """生成主持人消息文本。"""
        return cls._format("主持人", message_type, content, recipient=recipient)

    @classmethod
    def format_player(
        cls,
        player_name: str,
        message_type: MessageType,
        content: str,
        recipient: str | None = None,
    ) -> str:
        """生成玩家消息文本。"""
        return cls._format(
            "玩家",
            message_type,
            content,
            sender_name=player_name,
            recipient=recipient,
        )

    @classmethod
    def system(cls, message_type: MessageType, content: str) -> None:
        """打印系统消息。"""
        print(cls.format_system(message_type, content))

    @classmethod
    def moderator(
        cls,
        message_type: MessageType,
        content: str,
        recipient: str | None = None,
    ) -> None:
        """打印主持人消息。"""
        print(cls.format_moderator(message_type, content, recipient))

    @classmethod
    def player(
        cls,
        player_name: str,
        message_type: MessageType,
        content: str,
        recipient: str | None = None,
    ) -> None:
        """打印玩家消息。"""
        print(cls.format_player(player_name, message_type, content, recipient))
