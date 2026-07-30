"""将完整终端输出渲染为 9:16 小说式长图。"""

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

IMAGE_WIDTH: Final = 1080
IMAGE_HEIGHT: Final = 1920
PAGE_MARGIN: Final = 52
CONTENT_TOP: Final = 142
CONTENT_BOTTOM: Final = 1828
CONTENT_WIDTH: Final = IMAGE_WIDTH - PAGE_MARGIN * 2
MAX_FONT_SIZE: Final = 28
MIN_FONT_SIZE: Final = 24

BACKGROUND: Final = "#101312"
HEADER_BACKGROUND: Final = "#171B19"
PRIMARY_TEXT: Final = "#E8EAE7"
SECONDARY_TEXT: Final = "#8F9691"
DIVIDER: Final = "#343A36"
GOLD: Final = "#E0B64C"
GREEN: Final = "#72A98A"
BLUE: Final = "#6E9FC5"
RED: Final = "#D9655B"

_TAG_RE = re.compile(r"\[([^\]]+)\]")
_DIVIDER_CHARS = frozenset("═─┌┐└┘│")
_NO_LINE_START = frozenset("，。！？；：、）》】」’”")
_FONT_CANDIDATES = (
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


class TerminalLineStyle(StrEnum):
    """终端行的语义样式。"""

    SYSTEM = "system"
    MODERATOR = "moderator"
    PLAYER = "player"
    PRIVATE = "private"
    RESULT = "result"
    SECTION = "section"
    PLAIN = "plain"
    BLANK = "blank"


@dataclass(frozen=True, slots=True)
class TerminalLine:
    """完成换行后的单行终端文字。"""

    text: str
    style: TerminalLineStyle
    continuation: bool = False


@dataclass(frozen=True, slots=True)
class TerminalLayout:
    """字体和分页均已确定的完整终端布局。"""

    lines: tuple[TerminalLine, ...]
    font_size: int
    line_height: int
    lines_per_page: int
    page_count: int


def _find_font_path() -> Path:
    """查找能够离线渲染中文的系统字体。"""
    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    raise RuntimeError("找不到可用的中文字体，请安装苹方、黑体或 Noto Sans CJK")


def _line_style(text: str) -> TerminalLineStyle:
    """根据终端标签和分隔符判断整行样式。"""
    stripped = text.strip()
    if not stripped:
        return TerminalLineStyle.BLANK
    if set(stripped) <= _DIVIDER_CHARS or stripped.startswith(("┌", "│", "└")):
        return TerminalLineStyle.SECTION
    if "[结算]" in text or "[技能公告]" in text or "[猎人遗言]" in text:
        return TerminalLineStyle.RESULT
    if "[私密" in text or "[→" in text:
        return TerminalLineStyle.PRIVATE
    if text.startswith("[系统]"):
        return TerminalLineStyle.SYSTEM
    if text.startswith("[主持人]"):
        return TerminalLineStyle.MODERATOR
    if text.startswith("[玩家]"):
        return TerminalLineStyle.PLAYER
    return TerminalLineStyle.PLAIN


def _normalize_source_lines(text: str) -> list[str]:
    """压缩连续空行，同时保留全部非空白字符和原始顺序。"""
    normalized: list[str] = []
    previous_blank = True
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        normalized.append("" if is_blank else line)
        previous_blank = is_blank
    while normalized and not normalized[-1]:
        normalized.pop()
    return normalized


def _wrap_source_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> list[str]:
    """按字体真实宽度拆分一行，并避免中文句末标点孤行。"""
    if not text:
        return [""]
    wrapped: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and draw.textlength(candidate, font=font) > CONTENT_WIDTH:
            if character in _NO_LINE_START and len(current) > 1:
                wrapped.append(current[:-1])
                current = current[-1] + character
                continue
            wrapped.append(current)
            current = character
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped


def _wrap_terminal_text(
    text: str,
    font: ImageFont.FreeTypeFont,
) -> list[TerminalLine]:
    """将完整文本转换为带样式和续行标记的视觉行。"""
    measurement_image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(measurement_image)
    wrapped_lines: list[TerminalLine] = []
    for source_line in _normalize_source_lines(text):
        style = _line_style(source_line)
        chunks = _wrap_source_line(draw, source_line, font)
        wrapped_lines.extend(
            TerminalLine(chunk, style, continuation=index > 0)
            for index, chunk in enumerate(chunks)
        )
    return wrapped_lines


def _remove_boundary_blanks(
    lines: list[TerminalLine],
    lines_per_page: int,
) -> list[TerminalLine]:
    """移除页首和页尾空行，避免新页面出现无意义留白。"""
    compact: list[TerminalLine] = []
    for line in lines:
        if line.style is TerminalLineStyle.BLANK:
            if not compact or len(compact) % lines_per_page in {0, lines_per_page - 1}:
                continue
        compact.append(line)
    while compact and compact[-1].style is TerminalLineStyle.BLANK:
        compact.pop()
    return compact


def prepare_terminal_layout(text: str, max_pages: int = 15) -> TerminalLayout:
    """为完整终端文本选择满足页数限制的最大可读字号。"""
    if not text.strip():
        raise ValueError("输入文件为空")
    if max_pages < 1:
        raise ValueError("最大页数必须大于 0")
    font_path = _find_font_path()
    smallest_layout: TerminalLayout | None = None
    for font_size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -1):
        font = ImageFont.truetype(str(font_path), font_size)
        # 小字号使用紧凑但不重叠的行高，给短段落密集日志留出足够容量。
        line_height = max(font_size + 8, round(font_size * 1.36))
        lines_per_page = (CONTENT_BOTTOM - CONTENT_TOP) // line_height
        lines = _remove_boundary_blanks(
            _wrap_terminal_text(text, font),
            lines_per_page,
        )
        page_count = max(1, math.ceil(len(lines) / lines_per_page))
        layout = TerminalLayout(
            lines=tuple(lines),
            font_size=font_size,
            line_height=line_height,
            lines_per_page=lines_per_page,
            page_count=page_count,
        )
        smallest_layout = layout
        if page_count <= max_pages:
            return layout
    required_pages = smallest_layout.page_count if smallest_layout else 1
    raise ValueError(
        f"完整内容在最小字号 {MIN_FONT_SIZE}px 下仍需 {required_pages} 张图片，"
        f"超过上限 {max_pages}"
    )


def _style_color(style: TerminalLineStyle) -> str:
    """返回终端行正文的默认颜色。"""
    if style is TerminalLineStyle.SYSTEM:
        return SECONDARY_TEXT
    if style is TerminalLineStyle.RESULT:
        return RED
    if style is TerminalLineStyle.SECTION:
        return GOLD
    return PRIMARY_TEXT


def _tag_color(tag: str) -> str:
    """根据标签含义返回对应强调色。"""
    if tag in {"系统", "状态", "警告", "错误"}:
        return SECONDARY_TEXT
    if tag == "主持人" or tag in {"阶段", "公开公告"}:
        return GOLD
    if tag == "玩家" or tag == "公开发言":
        return GREEN
    if tag.startswith("→") or tag.startswith("私密"):
        return BLUE
    if tag in {"结算", "技能公告", "猎人遗言"}:
        return RED
    return PRIMARY_TEXT


def _draw_tagged_line(
    draw: ImageDraw.ImageDraw,
    line: TerminalLine,
    font: ImageFont.FreeTypeFont,
    y: int,
) -> None:
    """分别绘制终端标签和正文，使消息类型易于快速扫描。"""
    x: float = float(PAGE_MARGIN + (22 if line.continuation else 0))
    if line.continuation:
        draw.text((x, y), line.text, font=font, fill=_style_color(line.style))
        return
    cursor = 0
    matches = list(_TAG_RE.finditer(line.text))
    for match in matches:
        if match.start() > cursor:
            segment = line.text[cursor : match.start()]
            draw.text((x, y), segment, font=font, fill=_style_color(line.style))
            x += draw.textlength(segment, font=font)
        tag_text = match.group(0)
        draw.text((x, y), tag_text, font=font, fill=_tag_color(match.group(1)))
        x += draw.textlength(tag_text, font=font)
        cursor = match.end()
    remainder = line.text[cursor:]
    draw.text((x, y), remainder, font=font, fill=_style_color(line.style))


def _draw_page(
    page_lines: tuple[TerminalLine, ...],
    layout: TerminalLayout,
    font_path: Path,
    page_number: int,
    source_name: str,
) -> Image.Image:
    """绘制一页终端小说图片。"""
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    body_font = ImageFont.truetype(str(font_path), layout.font_size)
    header_font = ImageFont.truetype(str(font_path), 23)
    footer_font = ImageFont.truetype(str(font_path), 21)

    draw.rectangle((0, 0, IMAGE_WIDTH, 106), fill=HEADER_BACKGROUND)
    draw.text(
        (PAGE_MARGIN, 39),
        f"TERMINAL LOG  ·  {source_name}",
        font=header_font,
        fill=PRIMARY_TEXT,
    )
    page_label = f"PAGE {page_number:02d} / {layout.page_count:02d}"
    page_label_width = draw.textlength(page_label, font=header_font)
    draw.text(
        (IMAGE_WIDTH - PAGE_MARGIN - page_label_width, 39),
        page_label,
        font=header_font,
        fill=GOLD,
    )
    draw.line((0, 105, IMAGE_WIDTH, 105), fill=DIVIDER, width=2)

    for index, line in enumerate(page_lines):
        y = CONTENT_TOP + index * layout.line_height
        _draw_tagged_line(draw, line, body_font, y)

    draw.line(
        (PAGE_MARGIN, 1860, IMAGE_WIDTH - PAGE_MARGIN, 1860),
        fill=DIVIDER,
        width=2,
    )
    draw.text(
        (PAGE_MARGIN, 1875),
        "三国狼人杀 · 完整对局记录",
        font=footer_font,
        fill=SECONDARY_TEXT,
    )
    return image


def render_terminal_transcript(
    text: str,
    output_dir: Path,
    *,
    source_name: str = "output.txt",
    max_pages: int = 15,
) -> list[Path]:
    """将完整终端输出渲染为不超过指定页数的 9:16 PNG 图片。"""
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"输出目录不是空目录，拒绝覆盖：{output_dir}")
    layout = prepare_terminal_layout(text, max_pages=max_pages)
    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = _find_font_path()
    paths: list[Path] = []
    for page_number in range(1, layout.page_count + 1):
        start = (page_number - 1) * layout.lines_per_page
        end = start + layout.lines_per_page
        page_lines = layout.lines[start:end]
        image = _draw_page(page_lines, layout, font_path, page_number, source_name)
        path = output_dir / f"{page_number:02d}-terminal.png"
        image.save(path, format="PNG", optimize=True)
        paths.append(path)
    return paths
