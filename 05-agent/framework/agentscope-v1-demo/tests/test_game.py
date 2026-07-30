"""游戏引擎测试。"""

import contextlib
import io

import pytest
from agentscope.message import Msg

from config import GameConfig
from game import ThreeKingdomsWerewolfGame
from tests.helpers import FakeAgent


def test_message_text_rejects_dsml_tool_protocol() -> None:
    """模型误放进文本块的 DSML 工具协议不得作为玩家发言展示。"""
    game = ThreeKingdomsWerewolfGame(
        GameConfig("key", "model", "https://example.com")
    )
    message = Msg(
        "刘备",
        """<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="generate_response">
<｜｜DSML｜｜parameter name="vote" string="true">赵云</｜｜DSML｜｜parameter>
<｜｜DSML｜｜parameter name="reason" string="true">投票理由</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>""",
        "assistant",
    )

    assert game.message_text(message) == "无有效回复"


@pytest.mark.asyncio
async def test_private_notice_is_redacted_only_on_console() -> None:
    """关闭观战模式时控制台隐藏私密内容，但接收 Agent 获得原文。"""
    game = ThreeKingdomsWerewolfGame(
        GameConfig(
            "key",
            "model",
            "https://example.com",
            spectator_mode=False,
        )
    )
    witch = FakeAgent("貂蝉")
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        await game.notify_private(witch, "今晚刘备被狼人击杀")

    assert "内容已隐藏" in output.getvalue()
    assert "刘备" not in output.getvalue()
    assert witch.observed[0].get_text_content() == "今晚刘备被狼人击杀"


@pytest.mark.asyncio
async def test_spectator_mode_prints_private_notice() -> None:
    """开启观战模式时控制台展示私密行动原文。"""
    game = ThreeKingdomsWerewolfGame(
        GameConfig(
            "key",
            "model",
            "https://example.com",
            spectator_mode=True,
        )
    )
    witch = FakeAgent("貂蝉")
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        await game.notify_private(witch, "今晚刘备被狼人击杀")

    assert "今晚刘备被狼人击杀" in output.getvalue()


@pytest.mark.asyncio
async def test_agent_call_retries_temporary_failure() -> None:
    """单次暂时性异常不会直接终止整局游戏。"""
    config = GameConfig(
        "key",
        "model",
        "https://example.com",
        agent_attempts=2,
    )
    game = ThreeKingdomsWerewolfGame(config)
    agent = FakeAgent("刘备", failures_before_success=1)

    with contextlib.redirect_stdout(io.StringIO()):
        result = await game.call_agent(agent)

    assert result is not None
    assert agent.call_count == 2


@pytest.mark.parametrize(
    ("spectator_mode", "expected_role", "hidden_role"),
    [(False, "未公开", "狼人"), (True, "狼人", None)],
)
@pytest.mark.asyncio
async def test_setup_game_displays_role_overview(
    monkeypatch,
    spectator_mode: bool,
    expected_role: str,
    hidden_role: str | None,
) -> None:
    """开局总览根据观战模式展示或隐藏真实身份。"""
    game = ThreeKingdomsWerewolfGame(
        GameConfig(
            "key",
            "model",
            "https://example.com",
            player_count=6,
            spectator_mode=spectator_mode,
        )
    )
    characters = ["刘备", "关羽", "张飞", "诸葛亮", "赵云", "曹操"]

    async def create_fake_player(role: str, character: str) -> FakeAgent:
        game.roles[character] = role
        player = FakeAgent(character)
        game.players[character] = player
        return player

    monkeypatch.setattr("game.random.sample", lambda population, count: characters)
    monkeypatch.setattr(game, "create_player", create_fake_player)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        await game.setup_game()

    console_output = output.getvalue()
    first_role_line = next(
        line for line in console_output.splitlines() if line.strip().startswith("01.")
    )
    assert "三国狼人杀 · 游戏开始" in console_output
    assert "角色总览" in console_output
    assert expected_role in first_role_line
    if hidden_role is not None:
        assert hidden_role not in first_role_line


@pytest.mark.asyncio
async def test_game_announces_draw_after_max_rounds() -> None:
    """达到最大轮数且无人获胜时必须公开宣布平局。"""
    config = GameConfig(
        "key",
        "model",
        "https://example.com",
        max_rounds=1,
    )
    game = ThreeKingdomsWerewolfGame(config)
    wolf = FakeAgent("曹操")
    villager = FakeAgent("刘备")
    second_villager = FakeAgent("关羽")
    seer = FakeAgent("诸葛亮")
    game.alive_players = [wolf, villager, second_villager, seer]
    game.werewolves = [wolf]
    game.villagers = [villager, second_villager]
    game.seer = [seer]
    game.roles = {
        "曹操": "狼人",
        "刘备": "村民",
        "关羽": "村民",
        "诸葛亮": "预言家",
    }

    async def no_setup() -> None:
        return None

    async def no_kill(round_num: int) -> None:
        return None

    async def no_action() -> None:
        return None

    async def no_witch(killed_player):
        return killed_player, None

    async def no_vote(round_num: int) -> None:
        return None

    game.setup_game = no_setup
    game.night.werewolf_phase = no_kill
    game.night.guardian_phase = no_action
    game.night.seer_phase = no_action
    game.night.witch_phase = no_witch
    game.day.day_phase = no_vote

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = await game.run_game()

    console_output = output.getvalue()
    assert result == "平局"
    assert any("平局" in line for line in game.moderator.game_log)
    assert "第 1 夜 · 夜间行动" in console_output
    assert "第 1 夜结算" in console_output
    assert "第 1 天 · 白天行动" in console_output
    assert "第 1 天结算" in console_output
    assert "三国狼人杀 · 游戏结束" in console_output
    assert "最终身份" in console_output
