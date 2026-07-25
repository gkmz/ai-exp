import asyncio
import tempfile
import unittest
from pathlib import Path

from verifier import WorkspaceVerifier
from workspace import TaskWorkspace


class WorkspaceVerifierTest(unittest.TestCase):
    """验证自动检查能够阻止语法错误进入用户验收。"""

    def test_passes_valid_python_application(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = TaskWorkspace(Path(temp_dir))
            workspace.write_text("app.py", "value = 1\n")

            result = asyncio.run(WorkspaceVerifier(workspace).verify())

            self.assertTrue(result.passed)
            self.assertIn("Python 语法检查通过", result.details)

    def test_fails_invalid_python_application(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = TaskWorkspace(Path(temp_dir))
            workspace.write_text("app.py", "if True print('broken')\n")

            result = asyncio.run(WorkspaceVerifier(workspace).verify())

            self.assertFalse(result.passed)
            self.assertIn("语法检查失败", result.summary)

    def test_fails_when_entrypoint_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = TaskWorkspace(Path(temp_dir))

            result = asyncio.run(WorkspaceVerifier(workspace).verify())

            self.assertFalse(result.passed)
            self.assertIn("app.py", result.summary)


if __name__ == "__main__":
    unittest.main()
