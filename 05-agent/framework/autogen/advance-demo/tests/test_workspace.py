import tempfile
import unittest
from pathlib import Path

from workspace import TaskWorkspace


class TaskWorkspaceTest(unittest.TestCase):
    """验证任务工作区只能访问自己的目录。"""

    def test_write_and_read_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = TaskWorkspace(Path(temp_dir))

            workspace.write_text("src/app.py", "print('ok')\n")

            self.assertEqual(workspace.read_text("src/app.py"), "print('ok')\n")

    def test_rejects_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = TaskWorkspace(Path(temp_dir) / "task")

            with self.assertRaises(ValueError):
                workspace.write_text("../outside.py", "unsafe")

    def test_lists_files_without_internal_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = TaskWorkspace(Path(temp_dir))
            workspace.write_text("app.py", "")
            workspace.write_text("tests/test_app.py", "")

            self.assertEqual(workspace.list_files(), ["app.py", "tests/test_app.py"])


if __name__ == "__main__":
    unittest.main()
