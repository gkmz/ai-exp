from collections.abc import Sequence

from agentscope.agent import AgentBase
from agentscope.message import Msg

from game_messages import GameConsole, MessageType, MessageVisibility
import util


class GameRoles:
    """游戏角色管理类"""

    ROLES = {
        "狼人": {
            "description": "狼人",
            "ability": "夜晚可以击杀一名玩家",
            "win_condition": "淘汰所有村民或所有神职",
            "team": "狼人阵营",
        },
        "预言家": {
            "description": "预言家",
            "ability": "每晚可以查验一名玩家的身份",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营",
        },
        "女巫": {
            "description": "女巫",
            "ability": "拥有解药和毒药各一瓶，每晚最多使用一瓶药且不能毒自己",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营",
        },
        "猎人": {
            "description": "猎人",
            "ability": "被狼人击杀或被放逐时可以发表遗言并开枪带走一名玩家",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营",
        },
        "村民": {
            "description": "村民",
            "ability": "无特殊技能，依靠推理和投票",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营",
        },
        "守护者": {
            "description": "守护者",
            "ability": "每晚可以守护一名玩家免受狼人攻击",
            "win_condition": "消灭所有狼人",
            "team": "好人阵营",
        },
    }

    CHARACTER_TRAITS = {
        "刘备": "仁德宽厚，善于团结众人，说话温和有礼",
        "关羽": "忠义刚烈，言辞直接，重情重义",
        "张飞": "性格豪爽，说话大声直接，容易冲动",
        "诸葛亮": "智慧超群，分析透彻，言辞谨慎",
        "赵云": "忠勇双全，话语简洁有力",
        "曹操": "雄才大略，善于权谋，话语犀利",
        "司马懿": "深谋远虑，城府极深，言辞含蓄",
        "周瑜": "才华横溢，略显傲气，分析精准",
        "孙权": "年轻有为，善于决断，话语果决",
    }

    @classmethod
    def get_role_desc(cls, role: str) -> str:
        """获取角色描述"""
        return cls.ROLES.get(role, {}).get("description", "未知角色")

    @classmethod
    def get_role_ability(cls, role: str) -> str:
        """获取角色技能"""
        return cls.ROLES.get(role, {}).get("ability", "无特殊技能")

    @classmethod
    def get_character_trait(cls, character: str) -> str:
        """获取角色性格特点"""
        return cls.CHARACTER_TRAITS.get(character, "性格温和，说话得体")

    @classmethod
    def is_werewolf(cls, role: str) -> bool:
        """判断是否为狼人"""
        return role == "狼人"

    @classmethod
    def is_villager_team(cls, role: str) -> bool:
        """判断是否为好人阵营"""
        return cls.ROLES.get(role, {}).get("team") == "好人阵营"

    @classmethod
    def get_standard_setup(cls, player_count: int) -> list[str]:
        """获取标准角色配置"""
        if player_count == 6:
            return ["狼人", "狼人", "预言家", "女巫", "村民", "村民"]
        elif player_count == 8:
            return ["狼人", "狼人", "狼人", "预言家", "女巫", "猎人", "村民", "村民"]
        elif player_count == 9:
            return [
                "狼人",
                "狼人",
                "狼人",
                "预言家",
                "女巫",
                "猎人",
                "守护者",
                "村民",
                "村民",
            ]
        else:
            # 默认配置：约1/3狼人
            werewolf_count = max(1, player_count // 3)
            roles = ["狼人"] * werewolf_count

            # 添加神职
            remaining = player_count - werewolf_count
            if remaining >= 1:
                roles.append("预言家")
                remaining -= 1
            if remaining >= 1:
                roles.append("女巫")
                remaining -= 1
            if remaining >= 1:
                roles.append("猎人")
                remaining -= 1

            # 剩余为村民
            roles.extend(["村民"] * remaining)

            return roles


class GameModerator(AgentBase):
    """游戏主持人。"""

    def __init__(self) -> None:
        super().__init__()
        self.name = "游戏主持人"
        self.game_log: list[str] = []
        self._private_content_visible = False

    def set_private_content_visible(self, visible: bool) -> None:
        """设置主持人私密消息是否在控制台显示原文。"""
        self._private_content_visible = visible

    async def announce(
        self,
        content: str,
        message_type: MessageType = MessageType.PUBLIC_ANNOUNCEMENT,
        visibility: MessageVisibility = MessageVisibility.PUBLIC,
        recipient: str | None = None,
    ) -> Msg:
        """创建并打印带有类型和可见范围的主持人消息。"""
        msg = Msg(
            name=self.name,
            content=content,
            role="system",
            metadata={
                "message_type": message_type.value,
                "visibility": visibility.value,
                "recipient": recipient,
            },
        )
        # 私密消息只隐藏控制台副本，投递给 Agent 的 Msg 始终保留原文。
        display_content = (
            GameConsole.visible_content(content, self._private_content_visible)
            if visibility is MessageVisibility.PRIVATE
            else content
        )
        self.game_log.append(
            GameConsole.format_moderator(message_type, display_content, recipient)
        )
        GameConsole.moderator(message_type, display_content, recipient)
        return msg

    async def night_announcement(self, round_num: int) -> Msg:
        """夜晚阶段公告"""
        content = f"第{round_num}夜降临，天黑请闭眼"
        return await self.announce(content, MessageType.PHASE)

    async def day_announcement(self, round_num: int) -> Msg:
        """白天阶段公告"""
        content = f"第{round_num}天天亮了，请大家睁眼"
        return await self.announce(content, MessageType.PHASE)

    async def death_announcement(self, dead_players: Sequence[str]) -> Msg:
        """死亡公告"""
        if not dead_players:
            content = "昨夜平安无事，无人死亡。"
        else:
            content = f"昨夜，{util.format_player_list_str(dead_players)}不幸遇害。"
        return await self.announce(content, MessageType.RESULT)

    async def vote_result_announcement(
        self,
        voted_out: str | None,
        vote_count: int,
    ) -> Msg:
        """投票结果公告"""
        if voted_out is None:
            content = f"投票平票或无有效票，本轮无人出局。最高票数：{vote_count}。"
        else:
            content = f"投票结果：{voted_out}以{vote_count}票被淘汰出局。"
        return await self.announce(content, MessageType.RESULT)

    async def game_over_announcement(self, winner: str) -> Msg:
        """游戏结束公告"""
        content = f"游戏结束：{winner}"
        return await self.announce(content, MessageType.RESULT)
