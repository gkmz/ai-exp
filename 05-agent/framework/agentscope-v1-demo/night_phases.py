"""狼人杀夜间角色阶段。"""

import random
from typing import TYPE_CHECKING

from agentscope.pipeline import MsgHub

from game_messages import GameConsole, MessageType, MessageVisibility
from output import (
    DiscussionModel,
    get_guardian_model,
    get_seer_model,
    get_werewolf_kill_model,
    get_witch_action_model,
)
import util

if TYPE_CHECKING:
    from game import ThreeKingdomsWerewolfGame


class NightPhaseManager:
    """负责狼人、守护者、预言家和女巫的夜间行动。"""

    def __init__(self, game: "ThreeKingdomsWerewolfGame") -> None:
        """绑定当前游戏实例。"""
        self.game = game

    @staticmethod
    def resolve_guarded_kill(
        killed_player: str | None,
        guarded_player: str | None,
    ) -> str | None:
        """守护目标命中狼刀时取消该次狼人击杀。"""
        if killed_player is not None and killed_player == guarded_player:
            return None
        return killed_player

    async def werewolf_phase(self, round_num: int) -> str | None:
        """执行狼人讨论和击杀投票。"""
        if not self.game.werewolves:
            return None

        await self.game.notify_private_group(
            self.game.werewolves,
            f"第{round_num}夜狼人请睁眼并讨论击杀目标。"
            f"存活玩家：{util.format_player_list(self.game.alive_players)}",
            "狼人阵营",
        )

        async with MsgHub(self.game.werewolves, enable_auto_broadcast=True) as hub:
            for _ in range(self.game.config.discussion_rounds):
                for wolf in self.game.werewolves:
                    discussion_msg = await self.game.call_agent(
                        wolf,
                        structured_model=DiscussionModel,
                    )
                    self.game.display_agent_reply(
                        wolf,
                        discussion_msg,
                        MessageType.PRIVATE_SPEECH,
                        "狼人阵营",
                    )

            hub.set_auto_broadcast(False)
            kill_request = await self.game.moderator.announce(
                "请选择今晚的击杀目标",
                message_type=MessageType.PRIVATE_NOTICE,
                visibility=MessageVisibility.PRIVATE,
                recipient="狼人阵营",
            )
            werewolf_names = {wolf.name for wolf in self.game.werewolves}
            kill_model = get_werewolf_kill_model(
                self.game.alive_players,
                werewolf_names,
            )
            votes: dict[str, str | None] = {}
            for wolf in self.game.werewolves:
                vote_msg = await self.game.call_agent(
                    wolf,
                    msg=kill_request,
                    structured_model=kill_model,
                )
                metadata = self.game.message_metadata(vote_msg)
                target = metadata.get("target")
                if not isinstance(target, str):
                    GameConsole.system(
                        MessageType.WARNING,
                        f"{wolf.name}的击杀投票无效",
                    )
                    votes[wolf.name] = None
                    continue

                votes[wolf.name] = target
                GameConsole.player(
                    wolf.name,
                    MessageType.PRIVATE_ACTION,
                    f"击杀投票：{target}",
                    "系统",
                )

        killed_player, _ = util.majority_vote_cn(votes)
        if killed_player is not None:
            return killed_player

        valid_targets = [
            player.name
            for player in self.game.alive_players
            if player.name not in werewolf_names
        ]
        if not valid_targets:
            return None

        fallback_target = random.choice(valid_targets)
        GameConsole.system(
            MessageType.WARNING,
            f"狼人投票平票或无有效票，随机选择{fallback_target}作为狼刀目标",
        )
        return fallback_target

    async def guardian_phase(self) -> str | None:
        """执行守护者行动并记录连续守护状态。"""
        if not self.game.guardian:
            return None

        guardian_agent = self.game.guardian[0]
        await self.game.notify_private(
            guardian_agent,
            "守护者请睁眼，选择今晚要守护的玩家",
        )
        action_msg = await self.game.call_agent(
            guardian_agent,
            structured_model=get_guardian_model(
                self.game.alive_players,
                guardian_agent.name,
                self.game.last_guarded_player,
            ),
        )
        metadata = self.game.message_metadata(action_msg)
        target = metadata.get("target")
        valid_targets = {player.name for player in self.game.alive_players} - (
            {self.game.last_guarded_player} if self.game.last_guarded_player else set()
        )
        if not isinstance(target, str) or target not in valid_targets:
            self.game.last_guarded_player = None
            GameConsole.system(
                MessageType.WARNING,
                "守护者行动无效，本夜无人被守护",
            )
            return None

        self.game.last_guarded_player = target
        GameConsole.player(
            guardian_agent.name,
            MessageType.PRIVATE_ACTION,
            f"守护目标：{target}；理由：{metadata.get('guard_reason', '未说明')}",
            "系统",
        )
        await self.game.notify_private(
            guardian_agent,
            f"本夜守护目标已确定为{target}",
        )
        return target

    async def seer_phase(self) -> None:
        """执行预言家查验。"""
        if not self.game.seer:
            return

        seer_agent = self.game.seer[0]
        await self.game.notify_private(
            seer_agent,
            "预言家请睁眼，选择要查验的玩家",
        )
        check_msg = await self.game.call_agent(
            seer_agent,
            structured_model=get_seer_model(
                self.game.alive_players,
                seer_agent.name,
            ),
        )
        metadata = self.game.message_metadata(check_msg)
        target_name = metadata.get("target")
        if not isinstance(target_name, str):
            GameConsole.system(MessageType.WARNING, "预言家查验失败，跳过此阶段")
            return

        target_role = self.game.roles.get(target_name)
        if target_role is None:
            GameConsole.system(
                MessageType.ERROR,
                f"找不到玩家{target_name}的角色信息",
            )
            return

        GameConsole.player(
            seer_agent.name,
            MessageType.PRIVATE_ACTION,
            f"查验目标：{target_name}；理由：{metadata.get('check_reason', '未说明')}",
            "系统",
        )
        await self.game.notify_private(
            seer_agent,
            f"查验结果：{target_name}是{'狼人' if target_role == '狼人' else '好人'}",
        )

    async def witch_phase(
        self,
        killed_player: str | None,
    ) -> tuple[str | None, str | None]:
        """执行女巫用药并返回狼刀与毒杀的最终结果。"""
        if not self.game.witch:
            return killed_player, None

        witch_agent = self.game.witch[0]
        await self.game.notify_private(witch_agent, "女巫请睁眼")
        death_info = (
            f"今晚{killed_player}被狼人击杀" if killed_player else "今晚平安无事"
        )
        await self.game.notify_private(witch_agent, death_info)

        action_msg = await self.game.call_agent(
            witch_agent,
            structured_model=get_witch_action_model(
                self.game.alive_players,
                witch_agent.name,
                can_use_antidote=self.game.witch_has_antidote
                and killed_player is not None,
                can_use_poison=self.game.witch_has_poison,
            ),
        )
        metadata = self.game.message_metadata(action_msg)
        use_antidote = metadata.get("use_antidote") is True
        use_poison = metadata.get("use_poison") is True
        action_reason = metadata.get("action_reason") or "未说明"
        saved_player = None
        poisoned_player = None

        if use_antidote and use_poison:
            GameConsole.system(
                MessageType.WARNING,
                "女巫一晚只能使用一瓶药，本次行动无效",
            )
        elif use_antidote:
            if not self.game.witch_has_antidote or killed_player is None:
                GameConsole.system(MessageType.WARNING, "当前无法使用解药")
            else:
                saved_player = killed_player
                self.game.witch_has_antidote = False
                GameConsole.player(
                    witch_agent.name,
                    MessageType.PRIVATE_ACTION,
                    f"使用解药救助{killed_player}；理由：{action_reason}",
                    "系统",
                )
        elif use_poison:
            poison_target = metadata.get("poison_target")
            valid_targets = {
                player.name
                for player in self.game.alive_players
                if player.name != witch_agent.name
            }
            if (
                not self.game.witch_has_poison
                or not isinstance(poison_target, str)
                or poison_target not in valid_targets
            ):
                GameConsole.system(MessageType.WARNING, "女巫毒药行动无效")
            else:
                poisoned_player = poison_target
                self.game.witch_has_poison = False
                GameConsole.player(
                    witch_agent.name,
                    MessageType.PRIVATE_ACTION,
                    f"使用毒药毒杀{poison_target}；理由：{action_reason}",
                    "系统",
                )
        else:
            GameConsole.player(
                witch_agent.name,
                MessageType.PRIVATE_ACTION,
                f"本夜不使用药品；理由：{action_reason}",
                "系统",
            )

        final_killed = killed_player if saved_player is None else None
        return final_killed, poisoned_player
