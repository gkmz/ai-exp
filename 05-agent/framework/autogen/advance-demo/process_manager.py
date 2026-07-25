"""管理生成应用的 Streamlit 子进程。"""

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def find_available_port() -> int:
    """由操作系统分配一个当前可绑定的本地端口。"""
    # 端口 0 表示让操作系统选择空闲端口，避免固定 8501 与已有服务冲突。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def local_url(port: int) -> str:
    """生成仅供本机访问的 HTTP 地址。"""
    return f"http://127.0.0.1:{port}"


class StreamlitProcess:
    """启动、检查并关闭 Streamlit 开发服务。"""

    def __init__(self, workspace: Path, entrypoint: str = "app.py") -> None:
        """绑定生成应用的目录和入口文件。"""
        self.workspace = workspace.resolve()
        self.entrypoint = entrypoint
        self.process: subprocess.Popen[str] | None = None
        self.port: int | None = None
        self.log_file = None

    def start(self, timeout: float = 20.0) -> str:
        """启动服务并在健康检查成功后返回访问地址。"""
        entrypoint = self.workspace / self.entrypoint
        if not entrypoint.is_file():
            raise FileNotFoundError(f"应用入口不存在：{entrypoint}")

        # 每次启动重新选端口，并把子进程输出写入工作区日志，方便失败时排查。
        self.port = find_available_port()
        log_path = self.workspace / ".streamlit.log"
        self.log_file = log_path.open("w", encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            self.entrypoint,
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(self.port),
            "--server.headless",
            "true",
        ]
        # cwd 指向生成代码的工作区，因此 Streamlit 能按项目内相对路径加载文件。
        self.process = subprocess.Popen(
            command,
            cwd=self.workspace,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

        url = local_url(self.port)
        deadline = time.monotonic() + timeout
        # 子进程创建成功不代表应用已经可访问，需要轮询 Streamlit 健康检查接口。
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Streamlit 启动失败，请查看日志：{log_path}")
            try:
                with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1) as response:
                    if response.status == 200:
                        return url
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.2)

        self.stop()
        raise TimeoutError(f"Streamlit 未在 {timeout:.0f} 秒内就绪，请查看日志：{log_path}")

    def stop(self) -> None:
        """终止服务并释放日志文件。"""
        if self.process and self.process.poll() is None:
            # 先发送温和的 terminate；5 秒内未退出再 kill，避免遗留后台进程。
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log_file and not self.log_file.closed:
            self.log_file.close()
