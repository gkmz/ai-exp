"""完整终端记录图片渲染测试。"""

import re
from pathlib import Path

from PIL import Image

from share_cards.renderer import prepare_terminal_layout, render_terminal_transcript


def _long_terminal_output() -> str:
    """构造接近真实对局长度的完整终端输出。"""
    messages = []
    # 短段落数量模拟真实日志中大量独立发言和空行造成的分页开销。
    for index in range(246):
        player = f"玩家{index % 8 + 1}"
        messages.append(
            f"[玩家][公开发言][{player}] "
            "曹操的发言存在矛盾，需要结合昨夜行动、身份信息和投票结果继续分析。"
            "若预言家的查验可信，今日应优先放逐最可疑的目标。"
        )
    return "\n\n".join(messages)


def test_prepare_terminal_layout_preserves_all_non_whitespace_content() -> None:
    """自动换行和空行压缩不得删除任何非空白内容。"""
    text = "[系统][状态] 游戏开始\n\n\n[玩家][公开发言][刘备] 第一行\n第二行"

    layout = prepare_terminal_layout(text, max_pages=15)
    rendered_text = "".join(line.text for line in layout.lines)

    assert re.sub(r"\s+", "", rendered_text) == re.sub(r"\s+", "", text)
    assert layout.page_count == 1


def test_prepare_terminal_layout_fits_dense_output_within_fifteen_pages() -> None:
    """短段落密集的完整对局应自动压缩到十五页以内。"""
    layout = prepare_terminal_layout(_long_terminal_output(), max_pages=15)

    assert 24 <= layout.font_size <= 28
    assert layout.page_count <= 15


def test_render_terminal_transcript_creates_9_by_16_pngs(tmp_path: Path) -> None:
    """终端记录应生成连续编号的 1080×1920 图片。"""
    paths = render_terminal_transcript(
        "[系统][状态] 游戏开始\n[主持人][结算] 狼人阵营胜利",
        tmp_path,
    )

    assert [path.name for path in paths] == ["01-terminal.png"]
    with Image.open(paths[0]) as image:
        assert image.size == (1080, 1920)
        colors = image.convert("RGB").getcolors(maxcolors=1_000_000)
        assert colors is not None and len(colors) > 3


def test_render_terminal_transcript_refuses_nonempty_directory(
    tmp_path: Path,
) -> None:
    """输出目录已有内容时应避免静默覆盖。"""
    (tmp_path / "existing.txt").write_text("keep", encoding="utf-8")

    try:
        render_terminal_transcript("[系统][状态] 游戏开始", tmp_path)
    except ValueError as error:
        assert "输出目录不是空目录" in str(error)
    else:
        raise AssertionError("应拒绝覆盖非空目录")
