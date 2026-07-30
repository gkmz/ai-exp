"""游戏控制台布局测试。"""

from game_messages import GameConsole, MessageType


def test_banner_and_section_add_visual_boundaries(capsys) -> None:
    """横幅和阶段必须通过边框及空行与普通消息区分。"""
    GameConsole.banner("三国狼人杀 · 游戏开始")
    GameConsole.section("第 1 夜", "夜间行动")

    output = capsys.readouterr().out

    assert "════════" in output
    assert "三国狼人杀 · 游戏开始" in output
    assert "第 1 夜 · 夜间行动" in output
    assert "┌" in output and "└" in output
    assert "\n\n" in output


def test_role_table_hides_roles_outside_spectator_mode(capsys) -> None:
    """非观战模式的开局角色表不得泄露真实身份。"""
    GameConsole.role_table(
        ["刘备", "曹操"],
        {"刘备": "村民", "曹操": "狼人"},
        reveal_roles=False,
    )

    output = capsys.readouterr().out

    assert "01. 刘备" in output
    assert "02. 曹操" in output
    assert output.count("未公开") == 2
    assert "狼人" not in output


def test_role_table_reveals_roles_for_spectators(capsys) -> None:
    """观战模式必须展示完整身份。"""
    GameConsole.role_table(
        ["刘备", "曹操"],
        {"刘备": "村民", "曹操": "狼人"},
        reveal_roles=True,
    )

    output = capsys.readouterr().out

    assert "刘备" in output and "村民" in output
    assert "曹操" in output and "狼人" in output


def test_visible_content_redacts_private_information() -> None:
    """关闭观战模式时私密内容统一脱敏。"""
    assert GameConsole.visible_content("毒杀刘备", reveal_private=False) == "内容已隐藏"
    assert GameConsole.visible_content("毒杀刘备", reveal_private=True) == "毒杀刘备"


def test_round_summary_handles_no_deaths(capsys) -> None:
    """无人死亡时结算仍必须明确可读。"""
    GameConsole.round_summary("第 1 夜结算", [], ["刘备", "曹操"])

    output = capsys.readouterr().out

    assert "第 1 夜结算" in output
    assert "死亡玩家：无人死亡" in output
    assert "存活玩家：刘备、曹操" in output
    assert "当前人数：2" in output


def test_player_messages_are_separated_by_blank_lines(capsys) -> None:
    """连续玩家发言之间必须保留一个完整空行。"""
    GameConsole.player("刘备", MessageType.PUBLIC_SPEECH, "先听诸位分析。")
    GameConsole.player("司马懿", MessageType.PUBLIC_SPEECH, "此事仍有疑点。")

    output = capsys.readouterr().out

    assert (
        "[玩家][公开发言][刘备] 先听诸位分析。\n\n"
        "[玩家][公开发言][司马懿] 此事仍有疑点。\n\n"
    ) == output
