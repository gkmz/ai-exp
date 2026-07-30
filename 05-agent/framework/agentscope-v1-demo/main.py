"""三国狼人杀命令行入口。"""

import asyncio
from collections.abc import Mapping, Sequence

from config import ConfigError, build_argument_parser, load_config
from game import ThreeKingdomsWerewolfGame
from game_messages import GameConsole, MessageType


async def run(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """解析配置并运行游戏，返回适合进程退出的状态码。"""
    args = build_argument_parser().parse_args(argv)
    try:
        config = load_config(args, environ)
    except ConfigError as error:
        GameConsole.system(MessageType.ERROR, str(error))
        return 2

    GameConsole.system(MessageType.STATE, "欢迎来到三国狼人杀")
    try:
        game = ThreeKingdomsWerewolfGame(config)
        await game.run_game()
    except Exception as error:
        GameConsole.system(MessageType.ERROR, f"游戏运行出错：{error}")
        return 1
    return 0


def main() -> None:
    """运行异步入口并将结果作为进程退出码。"""
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
