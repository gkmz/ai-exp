"""白天和猎人阶段测试。"""

import contextlib
import io

import pytest

from config import GameConfig
from game import ThreeKingdomsWerewolfGame
from tests.helpers import FakeAgent


@pytest.mark.asyncio
async def test_hunter_can_shoot_after_exile() -> None:
    """猎人被放逐后先发表遗言再开枪。"""
    config = GameConfig("key", "model", "https://example.com")
    game = ThreeKingdomsWerewolfGame(config)
    hunter = FakeAgent(
        "赵云",
        {
            "last_words": "曹操的发言有矛盾",
            "shoot": True,
            "target": "曹操",
            "shoot_reason": "前后逻辑不一致",
        },
    )
    target = FakeAgent("曹操")
    game.hunter = [hunter]
    game.alive_players = [hunter, target]

    with contextlib.redirect_stdout(io.StringIO()):
        shot_target = await game.day.hunter_phase(
            "赵云",
            "放逐",
            unavailable_targets={"赵云"},
        )

    assert shot_target == "曹操"
    assert any(
        msg.metadata.get("message_type") == "猎人遗言" for msg in target.observed
    )


@pytest.mark.asyncio
async def test_poisoned_hunter_cannot_activate_skill() -> None:
    """猎人被女巫毒杀时不能调用模型或开枪。"""
    config = GameConfig("key", "model", "https://example.com")
    game = ThreeKingdomsWerewolfGame(config)
    hunter = FakeAgent("赵云")
    game.hunter = [hunter]
    game.alive_players = [hunter, FakeAgent("曹操")]

    with contextlib.redirect_stdout(io.StringIO()):
        shot_target = await game.day.hunter_phase("赵云", "毒杀")

    assert shot_target is None
    assert hunter.call_count == 0
