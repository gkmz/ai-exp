"""纯游戏规则测试。"""

from types import SimpleNamespace

import pytest

import util
from roles import GameRoles


def make_game_state(
    *role_pairs: tuple[str, str],
) -> tuple[list[SimpleNamespace], dict[str, str]]:
    """根据姓名和角色创建胜负规则测试状态。"""
    alive_players = [SimpleNamespace(name=name) for name, _ in role_pairs]
    roles = dict(role_pairs)
    return alive_players, roles


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


def test_equal_werewolf_and_good_counts_do_not_end_slaughter_side_game() -> None:
    """狼人和好人人数持平但村民、神职都尚存时应继续游戏。"""
    alive_players, roles = make_game_state(
        ("曹操", "狼人"),
        ("司马懿", "狼人"),
        ("周瑜", "狼人"),
        ("刘备", "村民"),
        ("诸葛亮", "预言家"),
        ("华佗", "女巫"),
    )

    assert util.check_winning_cn(alive_players, roles) is None


def test_werewolves_win_after_all_villagers_are_eliminated() -> None:
    """仍有神职存活但村民全部出局时狼人屠民获胜。"""
    alive_players, roles = make_game_state(
        ("曹操", "狼人"),
        ("司马懿", "狼人"),
        ("诸葛亮", "预言家"),
        ("华佗", "女巫"),
    )

    assert util.check_winning_cn(alive_players, roles) == (
        "狼人阵营胜利！所有村民已被淘汰！"
    )


def test_werewolves_win_after_all_gods_are_eliminated() -> None:
    """仍有村民存活但神职全部出局时狼人屠神获胜。"""
    alive_players, roles = make_game_state(
        ("曹操", "狼人"),
        ("司马懿", "狼人"),
        ("刘备", "村民"),
        ("关羽", "村民"),
    )

    assert util.check_winning_cn(alive_players, roles) == (
        "狼人阵营胜利！所有神职已被淘汰！"
    )


def test_good_team_wins_after_all_werewolves_are_eliminated() -> None:
    """所有狼人出局后好人阵营获胜。"""
    alive_players, roles = make_game_state(
        ("刘备", "村民"),
        ("诸葛亮", "预言家"),
    )

    assert util.check_winning_cn(alive_players, roles) == (
        "好人阵营胜利！所有狼人已被淘汰！"
    )


def test_werewolf_role_describes_slaughter_side_win_condition() -> None:
    """狼人角色说明必须与实际屠边胜负规则一致。"""
    assert GameRoles.ROLES["狼人"]["win_condition"] == ("淘汰所有村民或所有神职")
