"""角色配置测试。"""

from roles import GameRoles


def test_eight_player_setup_contains_hunter() -> None:
    """默认八人局必须包含猎人。"""
    roles = GameRoles.get_standard_setup(8)

    assert len(roles) == 8
    assert "猎人" in roles


def test_nine_player_setup_contains_guardian() -> None:
    """九人局必须包含已经实现的守护者。"""
    roles = GameRoles.get_standard_setup(9)

    assert len(roles) == 9
    assert "守护者" in roles
