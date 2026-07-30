"""游戏引擎测试。"""

import contextlib
import io

import pytest

from config import GameConfig
from game import ThreeKingdomsWerewolfGame
from tests.helpers import FakeAgent


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
    game.alive_players = [wolf, villager, second_villager]
    game.werewolves = [wolf]
    game.villagers = [villager, second_villager]
    game.roles = {"曹操": "狼人", "刘备": "村民", "关羽": "村民"}

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

    with contextlib.redirect_stdout(io.StringIO()):
        result = await game.run_game()

    assert result == "平局"
    assert any("平局" in line for line in game.moderator.game_log)
