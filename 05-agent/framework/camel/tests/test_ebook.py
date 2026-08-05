import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ebook import (
    EbookExportError,
    IncompleteEbookError,
    build_pdf,
    extract_chapter,
    validate_chapters,
)


def _load_demo_module():
    """加载带连字符文件名的 demo 模块，且不执行 main。"""
    script_path = Path(__file__).parents[1] / "digital-book-writing.py"
    spec = importlib.util.spec_from_file_location(
        "digital_book_writing_demo", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 demo：{script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChapterExtractionTests(unittest.TestCase):
    def test_extracts_one_markdown_chapter_heading(self):
        result = extract_chapter("**第一章：拖延的大脑**\n\n正文内容")
        self.assertEqual(result, (1, "## 第一章：拖延的大脑\n\n正文内容"))

    def test_ignores_outline_with_multiple_chapters(self):
        result = extract_chapter("**第一章：A**\n**第二章：B**\n大纲")
        self.assertIsNone(result)

    def test_ignores_chapter_heading_without_body(self):
        result = extract_chapter("# 第一章：只有标题\n\nNext request.")
        self.assertIsNone(result)

    def test_drops_model_wrapper_and_normalizes_single_newline(self):
        result = extract_chapter(
            "Solution:\n\n# 第三章：启动\n正文内容\n\nNext request."
        )
        self.assertEqual(result, (3, "## 第三章：启动\n\n正文内容"))

    def test_validate_reports_missing_chapters(self):
        with self.assertRaisesRegex(IncompleteEbookError, "缺少章节：2、4"):
            validate_chapters({1: "一", 3: "三", 5: "五"})

    def test_validate_rejects_chapter_heading_without_body(self):
        chapters = {index: f"## 第{index}章：测试\n\n正文" for index in range(1, 6)}
        chapters[3] = "## 第三章：只有标题"
        with self.assertRaisesRegex(IncompleteEbookError, "缺少章节：3"):
            validate_chapters(chapters)


class PdfGenerationTests(unittest.TestCase):
    def test_build_pdf_writes_a_pdf_for_five_chapters(self):
        chapters = {
            index: f"## 第{index}章：测试\n\n中文正文。" for index in range(1, 6)
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output = build_pdf(chapters, Path(temp_dir) / "book.pdf")
            self.assertEqual(output.read_bytes()[:5], b"%PDF-")
            self.assertGreater(output.stat().st_size, 1000)

    def test_build_pdf_keeps_the_configured_unicode_filename(self):
        chapters = {
            index: f"## 第{index}章：测试\n\n中文正文。" for index in range(1, 6)
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            expected = Path(temp_dir) / "output" / "pdf" / "拖延心理学.pdf"
            output = build_pdf(chapters, expected)
            self.assertEqual(output, expected)
            self.assertTrue(expected.is_file())

    def test_missing_configured_font_does_not_create_pdf(self):
        chapters = {
            index: f"## 第{index}章：测试\n\n中文正文。" for index in range(1, 6)
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "book.pdf"
            missing_font = Path(temp_dir) / "missing.ttf"
            with (
                patch.dict(os.environ, {"EBOOK_FONT_PATH": str(missing_font)}),
                self.assertRaisesRegex(RuntimeError, "字体不存在"),
            ):
                build_pdf(chapters, output)
            self.assertFalse(output.exists())

    def test_invalid_output_parent_is_wrapped_as_export_error(self):
        chapters = {
            index: f"## 第{index}章：测试\n\n中文正文。" for index in range(1, 6)
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir) / "output"
            parent.write_text("这是一个文件", encoding="utf-8")
            with self.assertRaisesRegex(EbookExportError, "PDF 导出失败"):
                build_pdf(chapters, parent / "book.pdf")

    def test_render_failure_preserves_existing_pdf_and_removes_temporary_file(self):
        chapters = {
            index: f"## 第{index}章：测试\n\n中文正文。" for index in range(1, 6)
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "book.pdf"
            output.write_bytes(b"existing-pdf")
            with (
                patch(
                    "ebook._EbookDocTemplate.multiBuild",
                    side_effect=RuntimeError("boom"),
                ),
                self.assertRaisesRegex(EbookExportError, "PDF 导出失败"),
            ):
                build_pdf(chapters, output)
            self.assertEqual(output.read_bytes(), b"existing-pdf")
            self.assertEqual(list(Path(temp_dir).glob(".ebook-*.pdf")), [])


class CollaborationTests(unittest.TestCase):
    def test_task_prompt_requires_the_five_chapter_export_contract(self):
        demo = _load_demo_module()
        self.assertIn("必须恰好分为五章", demo.TASK_PROMPT)
        self.assertIn("## 第一章：", demo.TASK_PROMPT)
        self.assertIn("不要创建独立的引言或结语章节", demo.TASK_PROMPT)

    def test_session_does_not_rewrite_the_export_contract(self):
        demo = _load_demo_module()
        with (
            patch.object(demo.ModelFactory, "create", return_value=object()),
            patch.object(demo, "RolePlaying", return_value=object()) as role_playing,
        ):
            demo._create_session()

        self.assertFalse(role_playing.call_args.kwargs["with_task_specify"])

    def test_collects_last_chapter_on_the_turn_before_done_marker(self):
        demo = _load_demo_module()
        responses = iter(
            [
                (
                    SimpleNamespace(
                        msg=SimpleNamespace(content="# 第五章：完成\n正文"),
                        terminated=False,
                    ),
                    SimpleNamespace(
                        msg=SimpleNamespace(content="请撰写第五章"), terminated=False
                    ),
                ),
                (
                    SimpleNamespace(msg=None, terminated=False),
                    SimpleNamespace(
                        msg=SimpleNamespace(content="CAMEL_TASK_DONE"), terminated=False
                    ),
                ),
            ]
        )
        session = SimpleNamespace(
            init_chat=lambda: SimpleNamespace(),
            step=lambda _: next(responses),
        )

        with patch("builtins.print"):
            chapters, turn_count = demo._collect_chapters(session)

        self.assertEqual(turn_count, 2)
        self.assertEqual(chapters[5], "## 第五章：完成\n\n正文")

    def test_reports_agent_termination_without_accessing_empty_message(self):
        demo = _load_demo_module()
        session = SimpleNamespace(
            init_chat=lambda: SimpleNamespace(),
            step=lambda _: (
                SimpleNamespace(msg=None, terminated=True),
                SimpleNamespace(
                    msg=SimpleNamespace(content="继续写作"), terminated=False
                ),
            ),
        )

        with self.assertRaisesRegex(EbookExportError, "心理学家未返回有效内容"):
            demo._collect_chapters(session)


if __name__ == "__main__":
    unittest.main()
