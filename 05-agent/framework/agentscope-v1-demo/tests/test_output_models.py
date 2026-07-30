"""结构化输出模型测试。"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import output as output_module
from output import (
    get_guardian_model,
    get_seer_model,
    get_vote_model_cn,
    get_werewolf_kill_model,
)
from prompt import ChinesePrompts


def make_players(*names: str) -> list[SimpleNamespace]:
    """创建只包含姓名的测试玩家。"""
    return [SimpleNamespace(name=name) for name in names]


def test_vote_model_rejects_self_vote() -> None:
    """白天玩家不能投票给自己。"""
    model = get_vote_model_cn(make_players("刘备", "曹操"), "刘备")

    with pytest.raises(ValidationError):
        model(vote="刘备", reason="测试", suspicion_level=5)


def test_seer_model_rejects_self_check() -> None:
    """预言家不能查验自己的身份。"""
    model = get_seer_model(make_players("诸葛亮", "曹操"), "诸葛亮")

    with pytest.raises(ValidationError):
        model(target="诸葛亮", check_reason="测试", priority_level=5)


def test_werewolf_model_only_accepts_non_werewolf_alive_target() -> None:
    """狼人只能击杀当前存活的非狼人玩家。"""
    players = make_players("曹操", "司马懿", "刘备")
    model = get_werewolf_kill_model(players, {"曹操", "司马懿"})

    model(target="刘备", kill_strategy="测试")
    with pytest.raises(ValidationError):
        model(target="司马懿", kill_strategy="测试")
    with pytest.raises(ValidationError):
        model(target="不存在的玩家", kill_strategy="测试")


def test_werewolf_discussion_rejects_teammate_target() -> None:
    """狼人讨论不能提议击杀自己或其他狼人。"""
    factory = getattr(output_module, "get_werewolf_discussion_model", None)
    assert factory is not None
    players = make_players("赵云", "曹操", "刘备", "关羽")
    model = factory(players, {"赵云", "曹操"})

    model(
        proposed_target="刘备",
        reach_agreement=False,
        confidence_level=6,
        key_evidence="刘备的发言有矛盾",
    )
    with pytest.raises(ValidationError):
        model(
            proposed_target="赵云",
            reach_agreement=False,
            confidence_level=6,
            key_evidence="测试",
        )


def test_werewolf_prompt_forbids_targeting_teammates() -> None:
    """狼人角色提示必须说明目标规则并禁止击杀狼队友。"""
    prompt = ChinesePrompts.get_role_prompt("狼人", "赵云")

    assert "淘汰所有村民或所有神职" in prompt
    assert "禁止自刀或击杀狼人队友" in prompt


def test_guardian_can_guard_self_but_not_same_player_twice() -> None:
    """守护者可以自守，但不能连续两晚守同一名玩家。"""
    players = make_players("赵云", "刘备", "曹操")
    first_night_model = get_guardian_model(players, "赵云", None)
    first_night_model(target="赵云", guard_reason="保护自己")

    next_night_model = get_guardian_model(players, "赵云", "赵云")
    with pytest.raises(ValidationError):
        next_night_model(target="赵云", guard_reason="继续保护自己")
    next_night_model(target="刘备", guard_reason="改为保护刘备")


def test_role_prompt_does_not_force_discussion_json_for_every_action() -> None:
    """系统提示不能与投票、技能等动态结构化模型冲突。"""
    prompt = ChinesePrompts.get_role_prompt("猎人", "赵云")

    assert '"reach_agreement"' not in prompt
    assert "根据主持人的当前要求" in prompt
