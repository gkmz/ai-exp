"""游戏配置测试。"""

import pytest

from config import ConfigError, build_argument_parser, load_config


def test_cli_defaults_to_eight_players() -> None:
    """默认启动八人局以覆盖猎人角色。"""
    args = build_argument_parser().parse_args([])

    assert args.players == 8


def test_cli_rejects_unsupported_player_count() -> None:
    """CLI 只允许项目已经实现的玩家人数。"""
    parser = build_argument_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--players", "10"])


def test_load_config_reports_all_missing_environment_variables() -> None:
    """缺少模型配置时一次性报告全部变量。"""
    args = build_argument_parser().parse_args([])

    with pytest.raises(ConfigError) as error_info:
        load_config(args, environ={})

    error_message = str(error_info.value)
    assert "LLM_API_KEY" in error_message
    assert "LLM_MODEL_ID" in error_message
    assert "LLM_BASE_URL" in error_message


def test_load_config_builds_valid_configuration() -> None:
    """完整环境变量能够生成游戏配置。"""
    args = build_argument_parser().parse_args(["--players", "9", "--max-rounds", "12"])

    config = load_config(
        args,
        environ={
            "LLM_API_KEY": "test-key",
            "LLM_MODEL_ID": "test-model",
            "LLM_BASE_URL": "https://example.com/api",
        },
    )

    assert config.player_count == 9
    assert config.max_rounds == 12
    assert config.model_id == "test-model"
