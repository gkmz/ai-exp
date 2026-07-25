"""为智能体提供受任务目录约束的文件操作。"""

from pathlib import Path


class TaskWorkspace:
    """封装任务工作区，阻止智能体读写目录外的文件。"""

    def __init__(self, root: Path) -> None:
        """创建工作区并确保根目录存在。"""
        # resolve() 将根目录规范化为绝对路径，后续才能可靠判断目标是否越界。
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        """解析并校验工作区内的相对路径。"""
        # 禁止绝对路径，确保 Agent 的工具参数只能描述工作区内部位置。
        if not relative_path or Path(relative_path).is_absolute():
            raise ValueError("必须提供工作区内的相对路径")

        # 必须在 resolve() 之后判断 is_relative_to()，这样 ../ 和符号链接造成的
        # 路径穿越也会被还原成真实绝对路径后拦截。
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"禁止访问工作区之外的路径：{relative_path}")
        return target

    def write_text(self, relative_path: str, content: str) -> str:
        """将 UTF-8 文本写入工作区并返回相对路径。"""
        target = self._resolve(relative_path)
        # 工程师可以直接写 src/app.py 等多级路径，无需先单独创建目录。
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target.relative_to(self.root).as_posix()

    def read_text(self, relative_path: str) -> str:
        """读取工作区内的 UTF-8 文本文件。"""
        target = self._resolve(relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"文件不存在：{relative_path}")
        return target.read_text(encoding="utf-8")

    def list_files(self) -> list[str]:
        """按名称排序返回工作区中的全部文件。"""
        # 隐藏 .streamlit.log 等运行时文件，避免 Agent 把日志误当成项目源码处理。
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
            and not any(
                part.startswith(".")
                for part in path.relative_to(self.root).parts
            )
        )
