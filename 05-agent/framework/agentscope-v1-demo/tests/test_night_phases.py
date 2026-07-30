"""夜间阶段测试。"""

import contextlib
import io

import pytest

from config import GameConfig
from game import ThreeKingdomsWerewolfGame
from night_phases import NightPhaseManager
from tests.helpers import FakeAgent


def make_config() -> GameConfig:
    """创建无需真实网络调用的测试配置。"""
    return GameConfig("key", "model", "https://example.com", agent_attempts=2)


def test_guarded_wolf_target_survives() -> None:
    """守护目标与狼刀目标相同时应抵挡狼刀。"""
    assert NightPhaseManager.resolve_guarded_kill("刘备", "刘备") is None
    assert NightPhaseManager.resolve_guarded_kill("刘备", "曹操") == "刘备"


@pytest.mark.asyncio
async def test_guardian_phase_records_target_and_allows_self_guard() -> None:
    """合法守护行动会记录本夜目标和连续守护状态。"""
    game = ThreeKingdomsWerewolfGame(make_config())
    guardian = FakeAgent(
        "赵云",
        {"target": "赵云", "guard_reason": "首夜优先自守"},
    )
    game.guardian = [guardian]
    game.alive_players = [guardian, FakeAgent("刘备")]

    with contextlib.redirect_stdout(io.StringIO()):
        target = await game.night.guardian_phase()

    assert target == "赵云"
    assert game.last_guarded_player == "赵云"
