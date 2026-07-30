"""测试使用的轻量 Agent 替身。"""

from types import SimpleNamespace

from agentscope.message import Msg


class FakeAgent:
    """记录调用和消息投递的可调用 Agent。"""

    def __init__(
        self,
        name: str,
        metadata: dict | None = None,
        failures_before_success: int = 0,
    ) -> None:
        self.name = name
        self.metadata = metadata
        self.failures_before_success = failures_before_success
        self.call_count = 0
        self.observed: list[Msg] = []

    async def __call__(self, **kwargs):
        """模拟 Agent 调用和暂时性失败。"""
        self.call_count += 1
        if self.call_count <= self.failures_before_success:
            raise RuntimeError("temporary failure")
        return SimpleNamespace(
            metadata=self.metadata,
            get_text_content=lambda: "测试回复",
        )

    async def observe(self, msg) -> None:
        """记录收到的消息。"""
        if isinstance(msg, list):
            self.observed.extend(msg)
        elif msg is not None:
            self.observed.append(msg)
