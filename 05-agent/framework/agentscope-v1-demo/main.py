import asyncio
import os
import random
from typing import Dict, List

from agentscope.agent import AgentBase, ReActAgent
from agentscope.formatter import DashScopeMultiAgentFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import MsgHub, fanout_pipeline

from game_messages import GameConsole, MessageType, MessageVisibility
import util
from output import (
    DiscussionModel,
    WerewolfKillModel,
    get_hunter_model_cn,
    get_seer_model,
    get_vote_model_cn,
    get_witch_action_model,
)
from prompt import ChinesePrompts
from roles import GameModerator, GameRoles

LLM_API_KEY = "LLM_API_KEY"
LLM_MODEL_ID_KEY = "LLM_MODEL_ID"
LLM_BASE_URL_KEY = "LLM_BASE_URL"


class ThreeKingdomsWerewolfGame:
    """三国狼人杀游戏主类"""

    def __init__(self):
        self.players: Dict[str, ReActAgent] = {}
        self.roles: dict[str, str] = {}
        self.moderator = GameModerator()
        self.alive_players: List[ReActAgent] = []
        self.werewolves: List[ReActAgent] = []
        self.villagers: List[ReActAgent] = []
        self.seer: List[ReActAgent] = []
        self.witch: List[ReActAgent] = []
        self.hunter: List[ReActAgent] = []

        # 女巫道具状态
        self.witch_has_antidote = True
        self.witch_has_poison = True

    @staticmethod
    def _message_text(msg: Msg | None) -> str:
        """提取 Agent 消息中的可读文本。"""
        if msg is None:
            return "无有效回复"
        return msg.get_text_content() or "无文本回复"

    async def _broadcast_message(
        self,
        msg: Msg,
        recipients: List[ReActAgent] | None = None,
    ) -> None:
        """将公开消息写入指定玩家的记忆。"""
        target_agents = list(
            self.alive_players if recipients is None else recipients
        )
        await asyncio.gather(*(agent.observe(msg) for agent in target_agents))

    async def _announce_public(
        self,
        content: str,
        message_type: MessageType = MessageType.PUBLIC_ANNOUNCEMENT,
    ) -> Msg:
        """创建公开公告并广播给所有当前存活玩家。"""
        msg = await self.moderator.announce(
            content,
            message_type=message_type,
            visibility=MessageVisibility.PUBLIC,
        )
        await self._broadcast_message(msg)
        return msg

    async def _notify_private(
        self,
        agent: ReActAgent,
        content: str,
        message_type: MessageType = MessageType.PRIVATE_NOTICE,
    ) -> Msg:
        """创建只对指定玩家可见的私密通知。"""
        msg = await self.moderator.announce(
            content,
            message_type=message_type,
            visibility=MessageVisibility.PRIVATE,
            recipient=agent.name,
        )
        await agent.observe(msg)
        return msg

    async def _notify_private_group(
        self,
        agents: List[ReActAgent],
        content: str,
        recipient: str,
    ) -> Msg:
        """创建只对指定阵营可见的私密通知。"""
        msg = await self.moderator.announce(
            content,
            message_type=MessageType.PRIVATE_NOTICE,
            visibility=MessageVisibility.PRIVATE,
            recipient=recipient,
        )
        await self._broadcast_message(msg, agents)
        return msg

    def _display_agent_reply(
        self,
        agent: ReActAgent,
        msg: Msg | None,
        message_type: MessageType,
        recipient: str | None = None,
    ) -> None:
        """按照游戏消息类型展示 Agent 的最终回复。"""
        GameConsole.player(
            agent.name,
            message_type,
            self._message_text(msg),
            recipient,
        )

    async def _publish_player_speech(
        self,
        agent: ReActAgent,
        content: str,
        message_type: MessageType,
    ) -> Msg:
        """打印玩家公开发言并写入所有存活玩家的记忆。"""
        msg = Msg(
            name=agent.name,
            content=content,
            role="assistant",
            metadata={
                "message_type": message_type.value,
                "visibility": MessageVisibility.PUBLIC.value,
            },
        )
        GameConsole.player(agent.name, message_type, content)
        await self._broadcast_message(msg)
        return msg

    async def create_player(self, role: str, character: str) -> ReActAgent:
        """创建具有三国背景的玩家"""
        name = util.get_chinese_name(character)
        self.roles[name] = role

        agent = ReActAgent(
            name=name,
            sys_prompt=ChinesePrompts.get_role_prompt(role, character),
            model=DashScopeChatModel(
                model_name=os.environ[LLM_MODEL_ID_KEY],  # 调用的大模型
                api_key=os.environ[LLM_API_KEY],
                base_http_api_url=os.environ[LLM_BASE_URL_KEY],
                enable_thinking=True,
            ),
            formatter=DashScopeMultiAgentFormatter(),
        )
        # 关闭框架默认输出，统一由游戏层按照消息类型打印。
        agent.set_console_output_enabled(False)

        # 角色身份确认
        await self._notify_private(
            agent,
            f"你在这场三国狼人杀中扮演{GameRoles.get_role_desc(role)}，"
            f"你的角色是{character}。{GameRoles.get_role_ability(role)}",
        )

        self.players[name] = agent
        return agent

    async def setup_game(self, player_count: int = 6):
        """设置游戏"""
        GameConsole.system(MessageType.STATE, "开始设置三国狼人杀游戏")

        # 获取角色配置
        roles = GameRoles.get_standard_setup(player_count)
        characters = random.sample(
            [
                "刘备",
                "关羽",
                "张飞",
                "诸葛亮",
                "赵云",
                "曹操",
                "司马懿",
                "周瑜",
                "孙权",
            ],
            player_count,
        )

        # 创建玩家
        for role, character in zip(roles, characters):
            agent = await self.create_player(role, character)
            self.alive_players.append(agent)

            # 分配到对应阵营
            if role == "狼人":
                self.werewolves.append(agent)
            elif role == "预言家":
                self.seer.append(agent)
            elif role == "女巫":
                self.witch.append(agent)
            elif role == "猎人":
                self.hunter.append(agent)
            else:
                self.villagers.append(agent)

        # 游戏开始公告
        await self._announce_public(
            f"三国狼人杀游戏开始！参与者：{util.format_player_list(self.alive_players)}"
        )

        GameConsole.system(
            MessageType.STATE,
            f"游戏设置完成，共{len(self.alive_players)}名玩家",
        )

    async def werewolf_phase(self, round_num: int) -> str | None:
        """狼人阶段"""
        if not self.werewolves:
            return None

        await self._notify_private_group(
            self.werewolves,
            "狼人请睁眼，选择今晚要击杀的目标",
            "狼人阵营",
        )

        await self._notify_private_group(
            self.werewolves,
            f"请讨论今晚的击杀目标。存活玩家：{util.format_player_list(self.alive_players)}",
            "狼人阵营",
        )

        # 狼人讨论
        async with MsgHub(
            self.werewolves,
            enable_auto_broadcast=True,
        ) as werewolves_hub:
            # 讨论阶段
            for _ in range(util.MAX_DISCUSSION_ROUND):
                for wolf in self.werewolves:
                    # 调用ReActAgent对象，它实现了__call__方法，可以像方法一样调用
                    # 依次让每个狼人智能体使用 `DiscussionModel` 进行一次讨论，并等待它完成。
                    discussion_msg = await wolf(structured_model=DiscussionModel)
                    self._display_agent_reply(
                        wolf,
                        discussion_msg,
                        MessageType.PRIVATE_SPEECH,
                        "狼人阵营",
                    )

            # 投票击杀
            werewolves_hub.set_auto_broadcast(False)
            # 让所有狼人依次对“请选择击杀目标”进行投票，并把投票结果保存到 `kill_votes` 列表中。
            # fanout_pipeline 是AgentScope的扇出管道，把同一条消息发送给多个Agent, 这里就是 self.werewolves
            #
            # 整体流程：
            # 主持人发布“请选择击杀目标”
            #              ↓
            # 把消息依次发送给所有狼人
            #              ↓
            # 每个狼人按照 WerewolfKillModel 投票
            #              ↓
            # 把所有投票结果放入 kill_votes
            fanout_agents: list[AgentBase] = list(
                self.werewolves
            )  # list不支持协变，导致pyright错误，这里创建一个新的list[AgentBase]
            kill_request = await self.moderator.announce(
                "请选择今晚的击杀目标",
                message_type=MessageType.PRIVATE_NOTICE,
                visibility=MessageVisibility.PRIVATE,
                recipient="狼人阵营",
            )
            kill_votes = await fanout_pipeline(
                fanout_agents,
                msg=kill_request,
                structured_model=WerewolfKillModel,  # 狼人Agent按照 WerewolfKillModel 定义的结构返回结果，而不是输出普通文本
                enable_gather=False,  # 狼人们依次执行，而不是同时
            )

            # 统计投票
            votes = {}
            for vote_index, vote_msg in enumerate(kill_votes):
                # 检查vote_msg是否为None或metadata是否存在
                if (
                    vote_msg is not None
                    and hasattr(vote_msg, "metadata")
                    and isinstance(vote_msg.metadata, dict)
                ):
                    target = vote_msg.metadata.get("target")
                    votes[self.werewolves[vote_index].name] = target
                    GameConsole.player(
                        self.werewolves[vote_index].name,
                        MessageType.PRIVATE_ACTION,
                        f"击杀投票：{target}",
                        "系统",
                    )
                else:
                    # 如果返回无效,随机选择一个目标
                    GameConsole.system(
                        MessageType.WARNING,
                        f"{self.werewolves[vote_index].name}的击杀投票无效，随机选择目标",
                    )
                    import random

                    valid_targets = [
                        p.name
                        for p in self.alive_players
                        if p.name not in [w.name for w in self.werewolves]
                    ]
                    votes[self.werewolves[vote_index].name] = (
                        random.choice(valid_targets) if valid_targets else None
                    )

            killed_player, _ = util.majority_vote_cn(votes)
            return killed_player

    async def seer_phase(self):
        """预言家阶段"""
        if not self.seer:
            return

        seer_agent = self.seer[0]
        await self._notify_private(
            seer_agent,
            "预言家请睁眼，选择要查验的玩家",
        )

        # 底层相当于调用 seer_agent.reply方法，返回的是一个 Msg 对象
        check_result = await seer_agent(
            structured_model=get_seer_model(self.alive_players)
        )

        # 检查返回结果是否有效
        if (
            check_result is None
            or not hasattr(check_result, "metadata")
            or check_result.metadata is None
        ):
            GameConsole.system(MessageType.WARNING, "预言家查验失败，跳过此阶段")
            return

        target_name = check_result.metadata.get("target")
        if not isinstance(target_name, str) or not target_name.strip():
            GameConsole.system(
                MessageType.WARNING,
                "预言家未选择查验目标，跳过此阶段",
            )
            return

        target_role = self.roles.get(target_name)
        if target_role is None:
            GameConsole.system(
                MessageType.WARNING,
                f"找不到玩家{target_name}的角色信息，查验失败",
            )
            return

        GameConsole.player(
            seer_agent.name,
            MessageType.PRIVATE_ACTION,
            f"查验目标：{target_name}；理由：{check_result.metadata.get('check_reason', '未说明')}",
            "系统",
        )

        # 告知预言家结果
        result_msg = (
            f"查验结果：{target_name}是{'狼人' if target_role == '狼人' else '好人'}"
        )
        await self._notify_private(seer_agent, result_msg)

    async def witch_phase(self, killed_player: str | None):
        """女巫阶段"""
        if not self.witch:
            return killed_player, None

        witch_agent = self.witch[0]
        await self._notify_private(witch_agent, "女巫请睁眼")

        # 告知女巫死亡信息
        death_info = (
            f"今晚{killed_player}被狼人击杀" if killed_player else "今晚平安无事"
        )
        await self._notify_private(witch_agent, death_info)

        # 女巫行动
        witch_action = await witch_agent(
            structured_model=get_witch_action_model(
                self.alive_players,
                witch_agent.name,
                can_use_antidote=self.witch_has_antidote and killed_player is not None,
                can_use_poison=self.witch_has_poison,
            )
        )

        saved_player = None
        poisoned_player = None

        # 检查返回结果是否有效
        if (
            witch_action is None
            or not hasattr(witch_action, "metadata")
            or not isinstance(witch_action.metadata, dict)
        ):
            GameConsole.system(
                MessageType.WARNING,
                "女巫行动失败，视为不使用技能",
            )
        else:
            use_antidote = witch_action.metadata.get("use_antidote") is True
            use_poison = witch_action.metadata.get("use_poison") is True
            action_reason = witch_action.metadata.get("action_reason") or "未说明"

            # 结构化模型已经校验互斥关系，此处再次防御异常 metadata。
            if use_antidote and use_poison:
                GameConsole.system(
                    MessageType.WARNING,
                    "女巫一晚只能使用一瓶药，本次行动无效",
                )
            elif use_antidote:
                if not self.witch_has_antidote or killed_player is None:
                    GameConsole.system(
                        MessageType.WARNING,
                        "当前无法使用解药，本次行动无效",
                    )
                else:
                    GameConsole.player(
                        witch_agent.name,
                        MessageType.PRIVATE_ACTION,
                        f"使用解药救助{killed_player}；理由：{action_reason}",
                        "系统",
                    )
                    saved_player = killed_player
                    self.witch_has_antidote = False
                    await self._notify_private(
                        witch_agent,
                        f"你使用解药救了{killed_player}",
                    )
            elif use_poison:
                poison_target = witch_action.metadata.get("poison_target")
                valid_poison_targets = {
                    player.name
                    for player in self.alive_players
                    if player.name != witch_agent.name
                }

                # 只有合法的非自身存活目标才会消耗毒药。
                if not self.witch_has_poison:
                    GameConsole.system(
                        MessageType.WARNING,
                        "毒药已经使用，本次行动无效",
                    )
                elif (
                    not isinstance(poison_target, str)
                    or poison_target not in valid_poison_targets
                ):
                    GameConsole.system(
                        MessageType.WARNING,
                        "毒药目标无效或为女巫自己，本次行动无效",
                    )
                else:
                    GameConsole.player(
                        witch_agent.name,
                        MessageType.PRIVATE_ACTION,
                        f"使用毒药毒杀{poison_target}；理由：{action_reason}",
                        "系统",
                    )
                    poisoned_player = poison_target
                    self.witch_has_poison = False
                    await self._notify_private(
                        witch_agent,
                        f"你使用毒药毒杀了{poisoned_player}",
                    )
            else:
                GameConsole.player(
                    witch_agent.name,
                    MessageType.PRIVATE_ACTION,
                    f"本夜不使用药品；理由：{action_reason}",
                    "系统",
                )

        # 确定最终死亡玩家
        final_killed = killed_player if not saved_player else None

        return final_killed, poisoned_player

    async def hunter_phase(
        self,
        dead_player: str | None,
        death_cause: str,
        unavailable_targets: set[str] | None = None,
    ) -> str | None:
        """处理猎人身份公开、最后遗言和开枪结算。"""
        if not self.hunter or dead_player is None:
            return None

        hunter_agent = self.hunter[0]
        if hunter_agent.name != dead_player:
            return None

        # 被毒杀时不能发动猎人技能，也不会因技能公开身份。
        if death_cause == "毒杀":
            GameConsole.system(
                MessageType.STATE,
                f"{hunter_agent.name}因毒杀出局，不能发动猎人技能",
            )
            return None

        await self._announce_public(
            f"{hunter_agent.name}身份公开：猎人，死亡原因：{death_cause}",
            MessageType.SKILL,
        )

        unavailable_names = set(unavailable_targets or set())
        eligible_players = [
            player
            for player in self.alive_players
            if player.name not in unavailable_names
        ]
        hunter_action = await hunter_agent(
            structured_model=get_hunter_model_cn(
                eligible_players,
                hunter_agent.name,
            )
        )

        # 异常结构化输出视为放弃开枪，避免阻塞整局游戏。
        if (
            hunter_action is None
            or not hasattr(hunter_action, "metadata")
            or not isinstance(hunter_action.metadata, dict)
        ):
            GameConsole.system(
                MessageType.WARNING,
                "猎人技能输出无效，视为放弃开枪",
            )
            await self._announce_public(
                f"猎人{hunter_agent.name}放弃开枪",
                MessageType.SKILL,
            )
            return None

        last_words = hunter_action.metadata.get("last_words")
        if not isinstance(last_words, str) or not last_words.strip():
            last_words = "我没有更多遗言。"

        # 猎人遗言属于公开发言，所有当前存活玩家都需要记住。
        await self._publish_player_speech(
            hunter_agent,
            last_words,
            MessageType.LAST_WORDS,
        )

        if hunter_action.metadata.get("shoot") is not True:
            await self._announce_public(
                f"猎人{hunter_agent.name}发表遗言后放弃开枪",
                MessageType.SKILL,
            )
            return None

        target = hunter_action.metadata.get("target")
        shoot_reason = hunter_action.metadata.get("shoot_reason")
        valid_targets = {
            player.name
            for player in eligible_players
            if player.name != hunter_agent.name
        }
        if (
            not isinstance(target, str)
            or target not in valid_targets
            or not isinstance(shoot_reason, str)
            or not shoot_reason.strip()
        ):
            GameConsole.system(
                MessageType.WARNING,
                "猎人开枪目标或理由无效，视为放弃开枪",
            )
            await self._announce_public(
                f"猎人{hunter_agent.name}放弃开枪",
                MessageType.SKILL,
            )
            return None

        await self._announce_public(
            f"猎人{hunter_agent.name}开枪带走了{target}；理由：{shoot_reason}",
            MessageType.SKILL,
        )
        return target

    def update_alive_players(self, dead_players: List[str]):
        """更新存活玩家列表"""
        for dead_name in dead_players:
            if dead_name:
                # 从存活列表移除
                self.alive_players = [
                    p for p in self.alive_players if p.name != dead_name
                ]
                # 从各阵营移除
                self.werewolves = [p for p in self.werewolves if p.name != dead_name]
                self.villagers = [p for p in self.villagers if p.name != dead_name]
                self.seer = [p for p in self.seer if p.name != dead_name]
                self.witch = [p for p in self.witch if p.name != dead_name]
                self.hunter = [p for p in self.hunter if p.name != dead_name]

    async def day_phase(self, round_num: int):
        """白天阶段"""
        await self._broadcast_message(
            await self.moderator.day_announcement(round_num)
        )
        await self._announce_public(
            f"现在开始自由讨论。存活玩家：{util.format_player_list(self.alive_players)}"
        )

        # 讨论阶段
        async with MsgHub(
            self.alive_players,
            enable_auto_broadcast=True,
        ) as all_hub:
            # 每名玩家依次公开发言，MsgHub负责把发言写入其他玩家记忆。
            current_alive_players = list(self.alive_players)
            for player in current_alive_players:
                speech_msg = await player()
                self._display_agent_reply(
                    player,
                    speech_msg,
                    MessageType.PUBLIC_SPEECH,
                )

            # 投票阶段
            all_hub.set_auto_broadcast(False)
            vote_request = await self.moderator.announce(
                "请投票选择要淘汰的玩家",
                message_type=MessageType.PUBLIC_ANNOUNCEMENT,
                visibility=MessageVisibility.PUBLIC,
            )
            fanout_agents: list[AgentBase] = list(current_alive_players)
            vote_msgs = await fanout_pipeline(
                fanout_agents,
                vote_request,
                structured_model=get_vote_model_cn(self.alive_players),
                enable_gather=False,
            )

            # 统计投票
            votes = {}
            for vote_index, vote_msg in enumerate(vote_msgs):
                # 检查vote_msg是否为None或metadata是否存在
                if (
                    vote_msg is not None
                    and hasattr(vote_msg, "metadata")
                    and isinstance(vote_msg.metadata, dict)
                ):
                    vote_target = vote_msg.metadata.get("vote")
                    votes[current_alive_players[vote_index].name] = vote_target
                    GameConsole.player(
                        current_alive_players[vote_index].name,
                        MessageType.PRIVATE_ACTION,
                        f"放逐投票：{vote_target}",
                        "系统",
                    )
                else:
                    # 如果返回无效,默认弃票
                    GameConsole.system(
                        MessageType.WARNING,
                        f"{current_alive_players[vote_index].name}的投票无效，视为弃票",
                    )
                    votes[current_alive_players[vote_index].name] = None

            voted_out, vote_count = util.majority_vote_cn(votes)
            await self._broadcast_message(
                await self.moderator.vote_result_announcement(
                    voted_out,
                    vote_count,
                )
            )

            return voted_out

    async def run_game(self):
        """运行游戏主循环"""
        try:
            await self.setup_game()

            for round_num in range(1, util.MAX_GAME_ROUND + 1):
                GameConsole.system(
                    MessageType.PHASE,
                    f"第{round_num}轮游戏开始",
                )

                # 夜晚阶段
                await self._broadcast_message(
                    await self.moderator.night_announcement(round_num)
                )

                # 狼人击杀
                killed_player = await self.werewolf_phase(round_num)

                # 预言家查验
                await self.seer_phase()

                # 女巫行动
                final_killed, poisoned_player = await self.witch_phase(killed_player)

                # 先公开夜间死亡，再根据猎人的具体死亡原因决定是否发动技能。
                night_deaths = list(
                    dict.fromkeys(
                        player
                        for player in [final_killed, poisoned_player]
                        if player
                    )
                )
                await self._broadcast_message(
                    await self.moderator.death_announcement(night_deaths)
                )

                hunter_shot = None
                if self.hunter and self.hunter[0].name in night_deaths:
                    hunter_name = self.hunter[0].name
                    death_cause = (
                        "毒杀" if hunter_name == poisoned_player else "狼人击杀"
                    )
                    hunter_shot = await self.hunter_phase(
                        hunter_name,
                        death_cause,
                        unavailable_targets=set(night_deaths),
                    )
                if hunter_shot and hunter_shot not in night_deaths:
                    night_deaths.append(hunter_shot)

                self.update_alive_players(night_deaths)

                # 检查胜利条件
                winner = util.check_winning_cn(self.alive_players, self.roles)
                if winner:
                    await self._broadcast_message(
                        await self.moderator.game_over_announcement(winner)
                    )
                    return

                # 白天阶段
                voted_out = await self.day_phase(round_num)

                # 猎人技能
                hunter_shot = await self.hunter_phase(
                    voted_out,
                    "放逐",
                    unavailable_targets={voted_out} if voted_out else set(),
                )

                # 更新死亡玩家
                day_deaths = list(
                    dict.fromkeys(
                        player for player in [voted_out, hunter_shot] if player
                    )
                )
                self.update_alive_players(day_deaths)

                # 检查胜利条件
                winner = util.check_winning_cn(self.alive_players, self.roles)
                if winner:
                    await self._broadcast_message(
                        await self.moderator.game_over_announcement(winner)
                    )
                    return

                GameConsole.system(
                    MessageType.STATE,
                    f"第{round_num}轮结束，存活玩家：{util.format_player_list(self.alive_players)}",
                )

        except Exception as error:
            GameConsole.system(MessageType.ERROR, f"游戏运行出错：{error}")
            import traceback

            traceback.print_exc()


async def main():
    """主函数"""
    # 检查环境变量
    if LLM_API_KEY not in os.environ:
        GameConsole.system(MessageType.ERROR, "请设置环境变量 LLM_API_KEY")
        return

    GameConsole.system(MessageType.STATE, "欢迎来到三国狼人杀")

    # 创建并运行游戏
    game = ThreeKingdomsWerewolfGame()
    await game.run_game()


if __name__ == "__main__":
    asyncio.run(main())
