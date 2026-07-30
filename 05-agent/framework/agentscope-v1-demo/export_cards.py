"""将三国狼人杀控制台文本导出为小红书分享图片。"""

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from share_cards.renderer import render_terminal_transcript


def build_argument_parser() -> argparse.ArgumentParser:
    """构建分享图片导出命令行参数。"""
    parser = argparse.ArgumentParser(description="生成三国狼人杀完整终端记录图片")
    parser.add_argument("input", type=Path, help="游戏控制台输出文本")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="图片输出目录；默认写入 exports 下的时间戳目录",
    )
    return parser


def _default_output_dir(input_path: Path) -> Path:
    """根据输入文件名和当前时间生成不覆盖旧结果的目录。"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("exports") / f"{input_path.stem}-{timestamp}"


def main(argv: Sequence[str] | None = None) -> int:
    """运行图片导出流程并返回进程状态码。"""
    args = build_argument_parser().parse_args(argv)
    output_dir = args.output_dir or _default_output_dir(args.input)
    try:
        text = args.input.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("输入文件为空")
        paths = render_terminal_transcript(
            text,
            output_dir,
            source_name=args.input.name,
        )
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"导出失败：{error}", file=sys.stderr)
        return 1

    print(f"生成完成：{len(paths)} 张完整记录图片")
    print(f"输出目录：{output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
