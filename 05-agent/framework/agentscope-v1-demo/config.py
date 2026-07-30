"""游戏命令行参数和模型环境配置。"""

import argparse
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

LLM_API_KEY = "LLM_API_KEY"
LLM_MODEL_ID_KEY = "LLM_MODEL_ID"
LLM_BASE_URL_KEY = "LLM_BASE_URL"
LLM_PROVIDER_KEY = "LLM_PROVIDER"
SPECTATOR_MODE_KEY = "SPECTATOR_MODE"
SUPPORTED_PLAYER_COUNTS = (6, 8, 9)
SUPPORTED_PROVIDERS = ("openai", "dashscope", "deepseek")
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class ConfigError(ValueError):
    """表示游戏启动配置不完整或不合法。"""


@dataclass(frozen=True)
class GameConfig:
    """运行一局游戏所需的完整配置。"""

    api_key: str = field(repr=False)
    model_id: str
    base_url: str
    provider: Literal["openai", "dashscope", "deepseek"] = "openai"
    player_count: int = 8
    max_rounds: int = 10
    discussion_rounds: int = 3
    agent_attempts: int = 2
    spectator_mode: bool = False


def _positive_int(value: str) -> int:
    """将命令行参数转换为正整数。"""
    parsed_value = int(value)
    if parsed_value < 1:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return parsed_value


def _parse_bool(value: str) -> bool:
    """解析环境变量布尔值，非法值直接阻止游戏启动。"""
    normalized_value = value.strip().lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False
    raise ConfigError(f"{SPECTATOR_MODE_KEY} 仅支持：true/false、1/0、yes/no、on/off")


def build_argument_parser() -> argparse.ArgumentParser:
    """创建狼人杀 Demo 的命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行三国主题多智能体狼人杀")
    parser.add_argument(
        "--players",
        type=int,
        choices=SUPPORTED_PLAYER_COUNTS,
        default=8,
        help="玩家人数，支持 6、8、9，默认 8",
    )
    parser.add_argument(
        "--max-rounds",
        type=_positive_int,
        default=10,
        help="最大游戏轮数，默认 10",
    )
    parser.add_argument(
        "--discussion-rounds",
        type=_positive_int,
        default=3,
        help="狼人每夜讨论轮数，默认 3",
    )
    parser.add_argument(
        "--agent-attempts",
        type=_positive_int,
        default=2,
        help="单次 Agent 调用最大尝试次数，默认 2",
    )
    return parser


def load_config(
    args: argparse.Namespace,
    environ: Mapping[str, str] | None = None,
) -> GameConfig:
    """从命令行参数和环境变量加载并校验游戏配置。"""
    environment = os.environ if environ is None else environ
    required_keys: Sequence[str] = (
        LLM_API_KEY,
        LLM_MODEL_ID_KEY,
        LLM_BASE_URL_KEY,
    )
    missing_keys = [
        key for key in required_keys if not environment.get(key, "").strip()
    ]
    if missing_keys:
        raise ConfigError(f"缺少必要环境变量：{', '.join(missing_keys)}")

    provider_value = environment.get(LLM_PROVIDER_KEY, "openai").strip().lower()
    if provider_value not in SUPPORTED_PROVIDERS:
        raise ConfigError(f"LLM_PROVIDER 仅支持：{', '.join(SUPPORTED_PROVIDERS)}")
    provider = cast(
        Literal["openai", "dashscope", "deepseek"],
        provider_value,
    )

    return GameConfig(
        api_key=environment[LLM_API_KEY],
        model_id=environment[LLM_MODEL_ID_KEY],
        base_url=environment[LLM_BASE_URL_KEY],
        provider=provider,
        player_count=args.players,
        max_rounds=args.max_rounds,
        discussion_rounds=args.discussion_rounds,
        agent_attempts=args.agent_attempts,
        spectator_mode=_parse_bool(
            environment.get(SPECTATOR_MODE_KEY, "false"),
        ),
    )
