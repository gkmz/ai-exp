"""在用户验收前执行确定性的工作区检查。"""

import asyncio
import sys

from schemas import VerificationResult
from workspace import TaskWorkspace


class WorkspaceVerifier:
    """检查入口文件、Python 语法和项目自带单元测试。"""

    def __init__(self, workspace: TaskWorkspace) -> None:
        """绑定待检查的任务工作区。"""
        self.workspace = workspace

    async def _run(self, *arguments: str) -> tuple[int, str]:
        """异步执行固定命令并收集输出。"""
        # 使用 create_subprocess_exec 而不是 shell=True，参数不会再经过 shell 解析，
        # 可以避免工作区文件名被解释成额外命令。
        process = await asyncio.create_subprocess_exec(
            *arguments,
            cwd=self.workspace.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        return process.returncode or 0, output.decode("utf-8", errors="replace")

    async def verify(self) -> VerificationResult:
        """执行所有允许的检查并汇总失败原因。"""
        details: list[str] = []

        # StreamlitProcess 固定从 app.py 启动，因此入口不存在时无需继续执行后续检查。
        if not (self.workspace.root / "app.py").is_file():
            return VerificationResult(
                passed=False,
                summary="缺少应用入口 app.py",
                details=[],
            )

        # 收集所有 Python 文件并交给当前解释器的 py_compile 做确定性语法检查。
        # 过滤隐藏目录，避免把工具缓存目录中的文件纳入生成项目验证。
        python_files = [
            path
            for path in self.workspace.root.rglob("*.py")
            if not any(part.startswith(".") for part in path.relative_to(self.workspace.root).parts)
        ]
        compile_code, compile_output = await self._run(
            sys.executable,
            "-m",
            "py_compile",
            *(str(path.relative_to(self.workspace.root)) for path in python_files),
        )
        if compile_code:
            return VerificationResult(
                passed=False,
                summary="Python 语法检查失败",
                details=[compile_output.strip()],
            )
        details.append("Python 语法检查通过")

        # tests/ 是可选的；如果工程师生成了测试，就必须全部通过才能进入用户验收。
        if (self.workspace.root / "tests").is_dir():
            test_code, test_output = await self._run(
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
            )
            if test_code:
                return VerificationResult(
                    passed=False,
                    summary="项目单元测试失败",
                    details=[test_output.strip()],
                )
            details.append("项目单元测试通过")

        return VerificationResult(passed=True, summary="自动检查通过", details=details)
