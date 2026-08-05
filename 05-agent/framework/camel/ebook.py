"""电子书章节收集、校验与 PDF 导出。"""

from __future__ import annotations

import html
import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

CHAPTER_NAMES = ("一", "二", "三", "四", "五")
_CHAPTER_HEADING = re.compile(
    r"(?m)^(?:\*\*|#{1,6}\s+)第([一二三四五])章[：:](.+?)(?:\*\*)?[ \t]*$"
)
_NORMALIZED_CHAPTER_HEADING = re.compile(r"^## 第[一二三四五1-5]章[：:].+$")
_BOLD_TEXT = re.compile(r"\*\*(.+?)\*\*")


class IncompleteEbookError(ValueError):
    """电子书章节不完整时抛出的异常。"""


class EbookExportError(RuntimeError):
    """电子书 PDF 导出失败时抛出的异常。"""


def extract_chapter(content: str) -> tuple[int, str] | None:
    """从单轮模型响应中提取一个正式章节，忽略大纲和非章节消息。"""
    headings = list(_CHAPTER_HEADING.finditer(content))
    if len(headings) != 1:
        return None

    heading = headings[0]
    chapter_number = CHAPTER_NAMES.index(heading.group(1)) + 1
    title = f"第{heading.group(1)}章：{heading.group(2).strip()}"
    # 丢弃模型的 Solution 前缀和 CAMEL 协议控制语，只保留出版正文。
    body = content[heading.end() :].strip()
    body = re.sub(r"(?i)\n*Next request\.\s*$", "", body).strip()
    if not body:
        return None
    normalized = f"## {title}"
    normalized += f"\n\n{body}"
    return chapter_number, normalized.strip()


def _has_chapter_body(content: str) -> bool:
    """判断章节内容是否在标题之外包含正文。"""
    lines = content.strip().splitlines()
    if not lines:
        return False
    if _NORMALIZED_CHAPTER_HEADING.fullmatch(lines[0].strip()):
        return bool("\n".join(lines[1:]).strip())
    return True


def validate_chapters(chapters: dict[int, str]) -> None:
    """校验五章是否齐全；缺失时抛出包含缺失编号的异常。"""
    missing = [
        str(index)
        for index in range(1, len(CHAPTER_NAMES) + 1)
        if index not in chapters or not _has_chapter_body(chapters[index])
    ]
    if missing:
        raise IncompleteEbookError(f"电子书章节不完整，缺少章节：{'、'.join(missing)}")


def _font_candidates() -> Iterable[Path]:
    """返回当前平台常见的中文字体路径。"""
    return (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttf"),
    )


def _resolve_font() -> Path:
    """解析环境变量或系统默认的中文字体。"""
    configured = os.getenv("EBOOK_FONT_PATH")
    if configured:
        font_path = Path(configured).expanduser()
        if font_path.is_file():
            return font_path
        raise EbookExportError(f"EBOOK_FONT_PATH 指向的字体不存在：{font_path}")

    for candidate in _font_candidates():
        if candidate.is_file():
            return candidate
    raise EbookExportError(
        "未找到中文字体，请设置 EBOOK_FONT_PATH，例如："
        "EBOOK_FONT_PATH=/path/to/chinese-font.ttf"
    )


def _register_font(font_path: Path) -> str:
    """注册中文字体并返回 ReportLab 样式中使用的字体名。"""
    font_name = "EbookChinese"
    try:
        if font_path.suffix.lower() == ".ttc":
            pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=0))
        else:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    except Exception as exc:  # ReportLab 对不同字体容器的错误类型不统一。
        raise EbookExportError(f"无法注册中文字体：{font_path}") from exc
    return font_name


class _EbookDocTemplate(BaseDocTemplate):
    """带目录事件和页脚页码的 ReportLab 文档模板。"""

    def __init__(self, filename: str, *, font_name: str, **kwargs):
        super().__init__(filename, **kwargs)
        self.font_name = font_name
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
        )
        self.addPageTemplates(
            [PageTemplate(id="ebook", frames=[frame], onPage=self._draw_footer)]
        )

    def afterFlowable(self, flowable):
        """收集章节标题，让 TableOfContents 在多遍构建时填充页码。"""
        if isinstance(flowable, Paragraph) and flowable.style.name == "ChapterTitle":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))

    def _draw_footer(self, canvas, document):
        """绘制简洁的页码页脚。"""
        canvas.saveState()
        canvas.setFont(self.font_name, 8)
        canvas.drawCentredString(A5[0] / 2, 10 * mm, str(document.page))
        canvas.restoreState()


def _paragraphs(content: str, styles: StyleSheet1):
    """将有限 Markdown 正文转换为 ReportLab 段落流。"""
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        text = block.strip()
        if not text or text in {"---", "```", "```markdown"}:
            continue
        if text.startswith("## "):
            lines = text.splitlines()
            yield Paragraph(html.escape(lines[0][3:]), styles["ChapterTitle"])
            if len(lines) > 1:
                yield from _paragraphs("\n".join(lines[1:]), styles)
            continue
        if text.startswith("### "):
            lines = text.splitlines()
            yield Paragraph(html.escape(lines[0][4:]), styles["SectionTitle"])
            if len(lines) > 1:
                yield from _paragraphs("\n".join(lines[1:]), styles)
            continue
        if text.startswith("- "):
            items = [
                f"&#8226; {html.escape(line[2:].strip())}"
                for line in text.splitlines()
                if line.strip().startswith("- ")
            ]
            yield Paragraph("<br/>".join(items), styles["Body"])
            continue

        escaped = html.escape(" ".join(line.strip() for line in text.splitlines()))
        escaped = _BOLD_TEXT.sub(r"<b>\1</b>", escaped)
        yield Paragraph(escaped, styles["Body"])


def _create_styles(font_name: str) -> StyleSheet1:
    """创建电子书封面、目录、章节和正文样式。"""
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=25,
            leading=34,
            alignment=TA_CENTER,
            spaceAfter=18 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=12,
            leading=20,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ChapterTitle",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=17,
            leading=24,
            spaceBefore=4 * mm,
            spaceAfter=8 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=19,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=18,
            alignment=TA_JUSTIFY,
            firstLineIndent=2 * 10.5,
            spaceAfter=4 * mm,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="TOCTitle",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=18,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        )
    )
    return styles


def _create_story(
    chapters: dict[int, str], styles: StyleSheet1, font_name: str
) -> list:
    """按封面、目录和章节顺序创建 ReportLab 内容流。"""
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCEntry",
            fontName=font_name,
            fontSize=11,
            leading=20,
            leftIndent=12,
            firstLineIndent=-12,
        )
    ]
    story = [
        Spacer(1, 35 * mm),
        Paragraph("拖延心理学", styles["CoverTitle"]),
        Paragraph("拖延不是懒，而是情绪调节问题", styles["CoverSubtitle"]),
        PageBreak(),
        Paragraph("目录", styles["TOCTitle"]),
        toc,
        PageBreak(),
    ]
    for index in range(1, len(CHAPTER_NAMES) + 1):
        story.extend(_paragraphs(chapters[index], styles))
        if index != len(CHAPTER_NAMES):
            story.append(PageBreak())
    return story


def build_pdf(chapters: dict[int, str], output_path: Path) -> Path:
    """校验章节并生成中文 PDF，成功后返回最终文件路径。"""
    validate_chapters(chapters)
    output_path = Path(output_path)
    temporary_path: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font_name = _register_font(_resolve_font())
        styles = _create_styles(font_name)
        story = _create_story(chapters, styles, font_name)
        with tempfile.NamedTemporaryFile(
            prefix=".ebook-", suffix=".pdf", dir=output_path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        document = _EbookDocTemplate(
            str(temporary_path),
            font_name=font_name,
            pagesize=A5,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title="拖延心理学",
            author="CAMEL",
        )
        document.multiBuild(story)
        temporary_path.replace(output_path)
    except EbookExportError:
        raise
    except Exception as exc:
        raise EbookExportError(f"PDF 导出失败：{exc}") from exc
    finally:
        if temporary_path and temporary_path.exists():
            # 清理失败不能覆盖真正的导出异常；遗留文件仍使用隐藏临时前缀。
            try:
                temporary_path.unlink()
            except OSError:
                pass
    return output_path
