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


@pytest.mark.asyncio
async def test_werewolf_phase_announces_teammates_and_valid_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """狼人讨论前必须明确队友和仅包含好人的击杀候选。"""

    class DummyMsgHub:
        """绕过 AgentScope 广播机制的测试消息中心。"""

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def set_auto_broadcast(self, enabled: bool) -> None:
            pass

    game = ThreeKingdomsWerewolfGame(make_config())
    wolf_a = FakeAgent("赵云", {"proposed_target": "刘备", "target": "刘备"})
    wolf_b = FakeAgent("曹操", {"proposed_target": "刘备", "target": "刘备"})
    game.werewolves = [wolf_a, wolf_b]
    game.alive_players = [wolf_a, wolf_b, FakeAgent("刘备"), FakeAgent("关羽")]
    monkeypatch.setattr("night_phases.MsgHub", DummyMsgHub)

    with contextlib.redirect_stdout(io.StringIO()):
        await game.night.werewolf_phase(1)

    briefing = wolf_a.observed[0].get_text_content()
    assert "狼人队友：曹操、赵云" in briefing
    assert "可击杀目标：关羽、刘备" in briefing
    assert "禁止自刀或击杀狼人队友" in briefing
