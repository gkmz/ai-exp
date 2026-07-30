"""纯游戏规则测试。"""

from types import SimpleNamespace

import pytest

import util


def test_majority_vote_ignores_abstentions() -> None:
    """弃票不应该成为可以胜出的候选项。"""
    assert util.majority_vote_cn({"刘备": None, "关羽": "曹操", "张飞": "曹操"}) == (
        "曹操",
        2,
    )


def test_all_abstain_means_no_player_is_eliminated() -> None:
    """全员弃票时本轮无人出局。"""
    assert util.majority_vote_cn({"刘备": None, "关羽": None}) == (None, 0)


def test_tied_vote_means_no_player_is_eliminated() -> None:
    """最高票平票时本轮无人出局。"""
    assert util.majority_vote_cn({"刘备": "曹操", "关羽": "张飞"}) == (None, 1)


def test_winning_check_rejects_missing_role_mapping() -> None:
    """角色状态缺失时不能静默按村民处理。"""
    alive_players = [SimpleNamespace(name="刘备")]

    with pytest.raises(ValueError, match="刘备"):
        util.check_winning_cn(alive_players, roles={})
