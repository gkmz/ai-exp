"""游戏消息分类和控制台展示工具。"""

from collections.abc import Mapping, Sequence
from enum import StrEnum

WIDE_DIVIDER = "═" * 40
THIN_DIVIDER = "─" * 40


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

    @classmethod
    def banner(cls, title: str) -> None:
        """打印游戏开始或结束横幅。"""
        print(f"\n{WIDE_DIVIDER}\n{title.center(32)}\n{WIDE_DIVIDER}\n")

    @classmethod
    def section(cls, title: str, subtitle: str | None = None) -> None:
        """打印具有明确边界的游戏阶段标题。"""
        label = f"{title} · {subtitle}" if subtitle else title
        print(f"\n┌{THIN_DIVIDER}┐\n│ {label}\n└{THIN_DIVIDER}┘\n")

    @classmethod
    def role_table(
        cls,
        player_names: Sequence[str],
        roles: Mapping[str, str],
        reveal_roles: bool,
        title: str = "角色总览",
    ) -> None:
        """打印玩家名单，并按配置决定是否展示真实身份。"""
        print(f"\n{THIN_DIVIDER}\n{title}\n{THIN_DIVIDER}")
        if not player_names:
            print("暂无玩家")
        for index, player_name in enumerate(player_names, start=1):
            role = roles.get(player_name, "未知") if reveal_roles else "未公开"
            print(f"  {index:02d}. {player_name:<8} {role}")
        print(f"{THIN_DIVIDER}\n")

    @classmethod
    def round_summary(
        cls,
        title: str,
        dead_players: Sequence[str],
        alive_players: Sequence[str],
    ) -> None:
        """打印昼夜结算后的死亡与存活玩家摘要。"""
        dead_text = "、".join(dead_players) if dead_players else "无人死亡"
        alive_text = "、".join(alive_players) if alive_players else "无人存活"
        print(
            f"\n{THIN_DIVIDER}\n"
            f"{title}\n"
            f"死亡玩家：{dead_text}\n"
            f"存活玩家：{alive_text}\n"
            f"当前人数：{len(alive_players)}\n"
            f"{THIN_DIVIDER}\n"
        )

    @staticmethod
    def visible_content(content: str, reveal_private: bool) -> str:
        """根据观战模式返回原始私密内容或统一脱敏文案。"""
        return content if reveal_private else "内容已隐藏"

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
        # 玩家消息使用独立段落，避免连续发言在控制台中挤成一块。
        print(
            cls.format_player(player_name, message_type, content, recipient),
            end="\n\n",
        )
