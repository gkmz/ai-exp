"""三国狼人杀游戏状态和主循环。"""

import asyncio
import random
from typing import Any

from agentscope.agent import AgentBase, ReActAgent
from agentscope.message import Msg
from pydantic import BaseModel

import util
from config import GameConfig
from day_phases import DayPhaseManager
from game_messages import GameConsole, MessageType, MessageVisibility
from model_factory import create_model_components
from night_phases import NightPhaseManager
from prompt import ChinesePrompts
from roles import GameModerator, GameRoles


class ThreeKingdomsWerewolfGame:
    """管理玩家状态、消息投递和整局游戏结算。"""

    def __init__(
        self,
        config: GameConfig,
        moderator: GameModerator | None = None,
    ) -> None:
        """使用完整配置初始化游戏状态。"""
        self.config = config
        self.players: dict[str, ReActAgent] = {}
        self.roles: dict[str, str] = {}
        self.moderator = moderator or GameModerator()
        self.moderator.set_private_content_visible(config.spectator_mode)
        self.alive_players: list[ReActAgent] = []
        self.werewolves: list[ReActAgent] = []
        self.villagers: list[ReActAgent] = []
        self.seer: list[ReActAgent] = []
        self.witch: list[ReActAgent] = []
        self.hunter: list[ReActAgent] = []
        self.guardian: list[ReActAgent] = []
        self.witch_has_antidote = True
        self.witch_has_poison = True
        self.last_guarded_player: str | None = None
        self.night = NightPhaseManager(self)
        self.day = DayPhaseManager(self)

    @staticmethod
    def message_metadata(msg: Msg | Any | None) -> dict[str, Any]:
        """安全读取 Agent 消息中的结构化 metadata。"""
        metadata = getattr(msg, "metadata", None)
        return metadata if isinstance(metadata, dict) else {}

    @staticmethod
    def message_text(msg: Msg | Any | None) -> str:
        """提取 Agent 消息中的可读文本。"""
        if msg is None:
            return "无有效回复"
        get_text_content = getattr(msg, "get_text_content", None)
        if callable(get_text_content):
            text_content = get_text_content()
            if isinstance(text_content, str) and text_content:
                # 部分兼容接口偶尔把内部 DSML 工具协议放进普通文本块。
                if "<｜｜DSML｜｜" in text_content:
                    return "无有效回复"
                return text_content
        return "无文本回复"

    async def broadcast_message(
        self,
        msg: Msg,
        recipients: list[ReActAgent] | None = None,
    ) -> None:
        """将消息写入指定玩家或所有存活玩家的记忆。"""
        target_agents = list(self.alive_players if recipients is None else recipients)
        await asyncio.gather(*(agent.observe(msg) for agent in target_agents))

    async def announce_public(
        self,
        content: str,
        message_type: MessageType = MessageType.PUBLIC_ANNOUNCEMENT,
    ) -> Msg:
        """创建公开公告并广播给所有存活玩家。"""
        msg = await self.moderator.announce(
            content,
            message_type=message_type,
            visibility=MessageVisibility.PUBLIC,
        )
        await self.broadcast_message(msg)
        return msg

    async def notify_private(
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

    async def notify_private_group(
        self,
        agents: list[ReActAgent],
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
        await self.broadcast_message(msg, agents)
        return msg

    def display_agent_reply(
        self,
        agent: ReActAgent,
        msg: Msg | None,
        message_type: MessageType,
        recipient: str | None = None,
    ) -> None:
        """按照游戏消息类型展示 Agent 的最终回复。"""
        self.display_player_message(
            agent,
            message_type,
            self.message_text(msg),
            recipient,
        )

    def display_player_message(
        self,
        agent: ReActAgent,
        message_type: MessageType,
        content: str,
        recipient: str | None = None,
    ) -> None:
        """按照消息可见范围打印玩家发言或行动。"""
        private_types = {
            MessageType.PRIVATE_SPEECH,
            MessageType.PRIVATE_ACTION,
        }
        display_content = (
            GameConsole.visible_content(content, self.config.spectator_mode)
            if message_type in private_types
            else content
        )
        GameConsole.player(
            agent.name,
            message_type,
            display_content,
            recipient,
        )

    async def publish_player_speech(
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
        await self.broadcast_message(msg)
        return msg

    async def call_agent(
        self,
        agent: AgentBase,
        msg: Msg | list[Msg] | None = None,
        structured_model: type[BaseModel] | None = None,
    ) -> Msg | None:
        """调用 Agent；暂时性异常按配置重试，耗尽后返回空结果。"""
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        for attempt in range(1, self.config.agent_attempts + 1):
            try:
                return await agent(msg=msg, structured_model=structured_model)
            except Exception as error:
                GameConsole.system(
                    MessageType.WARNING,
                    f"调用{agent_name}失败（{attempt}/{self.config.agent_attempts}）：{error}",
                )
                if attempt < self.config.agent_attempts:
                    await asyncio.sleep(0)
        return None

    async def create_player(self, role: str, character: str) -> ReActAgent:
        """创建并初始化具有三国背景的玩家 Agent。"""
        name = util.get_chinese_name(character)
        self.roles[name] = role
        model_components = create_model_components(self.config)
        agent = ReActAgent(
            name=name,
            sys_prompt=ChinesePrompts.get_role_prompt(role, character),
            model=model_components.model,
            formatter=model_components.formatter,
        )
        agent.set_console_output_enabled(False)
        await self.notify_private(
            agent,
            f"你在这场三国狼人杀中扮演{GameRoles.get_role_desc(role)}，"
            f"你的角色是{character}。{GameRoles.get_role_ability(role)}",
        )
        self.players[name] = agent
        return agent

    async def setup_game(self) -> None:
        """根据配置创建玩家并分配角色。"""
        GameConsole.banner("三国狼人杀 · 游戏开始")
        GameConsole.system(MessageType.STATE, "开始设置三国狼人杀游戏")
        GameConsole.system(
            MessageType.STATE,
            f"模型接口协议：{self.config.provider}",
        )
        GameConsole.system(
            MessageType.STATE,
            f"观战模式：{'开启' if self.config.spectator_mode else '关闭'}",
        )
        roles = GameRoles.get_standard_setup(self.config.player_count)
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
            self.config.player_count,
        )

        for role, character in zip(roles, characters, strict=True):
            agent = await self.create_player(role, character)
            self.alive_players.append(agent)
            if role == "狼人":
                self.werewolves.append(agent)
            elif role == "预言家":
                self.seer.append(agent)
            elif role == "女巫":
                self.witch.append(agent)
            elif role == "猎人":
                self.hunter.append(agent)
            elif role == "守护者":
                self.guardian.append(agent)
            else:
                self.villagers.append(agent)

        GameConsole.role_table(
            [player.name for player in self.alive_players],
            self.roles,
            reveal_roles=self.config.spectator_mode,
        )
        await self.announce_public(
            f"三国狼人杀游戏开始！参与者：{util.format_player_list(self.alive_players)}"
        )
        GameConsole.system(
            MessageType.STATE,
            f"游戏设置完成，共{len(self.alive_players)}名玩家",
        )

    def update_alive_players(self, dead_players: list[str]) -> None:
        """从所有存活角色集合中移除死亡玩家。"""
        dead_names = set(dead_players)
        if not dead_names:
            return
        self.alive_players = [
            player for player in self.alive_players if player.name not in dead_names
        ]
        self.werewolves = [
            player for player in self.werewolves if player.name not in dead_names
        ]
        self.villagers = [
            player for player in self.villagers if player.name not in dead_names
        ]
        self.seer = [player for player in self.seer if player.name not in dead_names]
        self.witch = [player for player in self.witch if player.name not in dead_names]
        self.hunter = [
            player for player in self.hunter if player.name not in dead_names
        ]
        self.guardian = [
            player for player in self.guardian if player.name not in dead_names
        ]

    async def _announce_winner_if_any(self) -> str | None:
        """检查胜负并在出现胜者时发布结束公告。"""
        winner = util.check_winning_cn(self.alive_players, self.roles)
        if winner:
            await self.broadcast_message(
                await self.moderator.game_over_announcement(winner)
            )
            self.display_game_over(winner)
        return winner

    def display_game_over(self, winner: str) -> None:
        """打印游戏结果和所有玩家的最终身份。"""
        GameConsole.banner("三国狼人杀 · 游戏结束")
        GameConsole.system(MessageType.RESULT, f"胜负结果：{winner}")
        GameConsole.role_table(
            list(self.roles),
            self.roles,
            reveal_roles=True,
            title="最终身份",
        )

    async def run_game(self) -> str:
        """运行完整游戏并返回胜方或平局。"""
        await self.setup_game()
        for round_num in range(1, self.config.max_rounds + 1):
            GameConsole.section(f"第 {round_num} 夜", "夜间行动")
            await self.broadcast_message(
                await self.moderator.night_announcement(round_num)
            )

            guarded_player = await self.night.guardian_phase()
            wolf_target = await self.night.werewolf_phase(round_num)
            killed_player = self.night.resolve_guarded_kill(
                wolf_target,
                guarded_player,
            )
            await self.night.seer_phase()
            final_killed, poisoned_player = await self.night.witch_phase(killed_player)
            night_deaths = list(
                dict.fromkeys(
                    player for player in [final_killed, poisoned_player] if player
                )
            )
            await self.broadcast_message(
                await self.moderator.death_announcement(night_deaths)
            )

            hunter_shot = None
            if self.hunter and self.hunter[0].name in night_deaths:
                hunter_name = self.hunter[0].name
                death_cause = "毒杀" if hunter_name == poisoned_player else "狼人击杀"
                hunter_shot = await self.day.hunter_phase(
                    hunter_name,
                    death_cause,
                    unavailable_targets=set(night_deaths),
                )
            if hunter_shot and hunter_shot not in night_deaths:
                night_deaths.append(hunter_shot)
            self.update_alive_players(night_deaths)
            GameConsole.round_summary(
                f"第 {round_num} 夜结算",
                night_deaths,
                [player.name for player in self.alive_players],
            )

            winner = await self._announce_winner_if_any()
            if winner:
                return winner

            GameConsole.section(f"第 {round_num} 天", "白天行动")
            voted_out = await self.day.day_phase(round_num)
            hunter_shot = await self.day.hunter_phase(
                voted_out,
                "放逐",
                unavailable_targets={voted_out} if voted_out else set(),
            )
            day_deaths = list(
                dict.fromkeys(player for player in [voted_out, hunter_shot] if player)
            )
            self.update_alive_players(day_deaths)
            GameConsole.round_summary(
                f"第 {round_num} 天结算",
                day_deaths,
                [player.name for player in self.alive_players],
            )

            winner = await self._announce_winner_if_any()
            if winner:
                return winner

        draw_result = "平局：达到最大轮数仍未分出胜负"
        await self.broadcast_message(
            await self.moderator.game_over_announcement(draw_result)
        )
        self.display_game_over(draw_result)
        return "平局"
