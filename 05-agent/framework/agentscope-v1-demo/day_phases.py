"""狼人杀白天、投票和猎人阶段。"""

from typing import TYPE_CHECKING

from agentscope.pipeline import MsgHub

from game_messages import GameConsole, MessageType, MessageVisibility
from output import get_hunter_model_cn, get_vote_model_cn
import util

if TYPE_CHECKING:
    from game import ThreeKingdomsWerewolfGame


class DayPhaseManager:
    """负责白天发言、放逐投票和猎人技能。"""

    def __init__(self, game: "ThreeKingdomsWerewolfGame") -> None:
        """绑定当前游戏实例。"""
        self.game = game

    async def day_phase(self, round_num: int) -> str | None:
        """执行白天公开讨论和放逐投票。"""
        await self.game.broadcast_message(
            await self.game.moderator.day_announcement(round_num)
        )
        GameConsole.section("公开讨论")
        await self.game.announce_public(
            f"现在开始自由讨论。存活玩家：{util.format_player_list(self.game.alive_players)}"
        )

        current_players = list(self.game.alive_players)
        async with MsgHub(current_players, enable_auto_broadcast=True) as hub:
            for player in current_players:
                speech_msg = await self.game.call_agent(player)
                self.game.display_agent_reply(
                    player,
                    speech_msg,
                    MessageType.PUBLIC_SPEECH,
                )

            hub.set_auto_broadcast(False)
            GameConsole.section("放逐投票")
            vote_request = await self.game.moderator.announce(
                "请投票选择要淘汰的玩家",
                message_type=MessageType.PUBLIC_ANNOUNCEMENT,
                visibility=MessageVisibility.PUBLIC,
            )
            votes: dict[str, str | None] = {}
            for player in current_players:
                vote_msg = await self.game.call_agent(
                    player,
                    msg=vote_request,
                    structured_model=get_vote_model_cn(
                        current_players,
                        player.name,
                    ),
                )
                metadata = self.game.message_metadata(vote_msg)
                vote_target = metadata.get("vote")
                if not isinstance(vote_target, str):
                    votes[player.name] = None
                    GameConsole.system(
                        MessageType.WARNING,
                        f"{player.name}的投票无效，视为弃票",
                    )
                    continue

                votes[player.name] = vote_target
                self.game.display_player_message(
                    player,
                    MessageType.PRIVATE_ACTION,
                    f"放逐投票：{vote_target}；理由：{metadata.get('reason', '未说明')}",
                    "系统",
                )

        voted_out, vote_count = util.majority_vote_cn(votes)
        await self.game.broadcast_message(
            await self.game.moderator.vote_result_announcement(
                voted_out,
                vote_count,
            )
        )
        return voted_out

    async def hunter_phase(
        self,
        dead_player: str | None,
        death_cause: str,
        unavailable_targets: set[str] | None = None,
    ) -> str | None:
        """处理猎人身份公开、最后遗言和开枪结算。"""
        if not self.game.hunter or dead_player is None:
            return None

        hunter_agent = self.game.hunter[0]
        if hunter_agent.name != dead_player:
            return None
        if death_cause == "毒杀":
            GameConsole.system(
                MessageType.STATE,
                f"{hunter_agent.name}因毒杀出局，不能发动猎人技能",
            )
            return None

        GameConsole.section("猎人技能", "身份公开、遗言与开枪")
        await self.game.announce_public(
            f"{hunter_agent.name}身份公开：猎人，死亡原因：{death_cause}",
            MessageType.SKILL,
        )
        unavailable_names = set(unavailable_targets or set())
        eligible_players = [
            player
            for player in self.game.alive_players
            if player.name not in unavailable_names
        ]
        action_msg = await self.game.call_agent(
            hunter_agent,
            structured_model=get_hunter_model_cn(
                eligible_players,
                hunter_agent.name,
            ),
        )
        metadata = self.game.message_metadata(action_msg)
        if not metadata:
            await self.game.announce_public(
                f"猎人{hunter_agent.name}技能输出无效，视为放弃开枪",
                MessageType.SKILL,
            )
            return None

        last_words = metadata.get("last_words")
        if not isinstance(last_words, str) or not last_words.strip():
            last_words = "我没有更多遗言。"
        await self.game.publish_player_speech(
            hunter_agent,
            last_words,
            MessageType.LAST_WORDS,
        )

        if metadata.get("shoot") is not True:
            await self.game.announce_public(
                f"猎人{hunter_agent.name}发表遗言后放弃开枪",
                MessageType.SKILL,
            )
            return None

        target = metadata.get("target")
        shoot_reason = metadata.get("shoot_reason")
        valid_targets = {player.name for player in eligible_players}
        if (
            not isinstance(target, str)
            or target not in valid_targets
            or not isinstance(shoot_reason, str)
            or not shoot_reason.strip()
        ):
            await self.game.announce_public(
                f"猎人{hunter_agent.name}开枪目标或理由无效，视为放弃",
                MessageType.SKILL,
            )
            return None

        await self.game.announce_public(
            f"猎人{hunter_agent.name}开枪带走了{target}；理由：{shoot_reason}",
            MessageType.SKILL,
        )
        return target
