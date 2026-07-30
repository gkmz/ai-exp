"""模型适配器工厂测试。"""

from agentscope.formatter import (
    DashScopeMultiAgentFormatter,
    OpenAIMultiAgentFormatter,
)
from agentscope.model import DashScopeChatModel, OpenAIChatModel

from config import GameConfig
from model_factory import create_model_components


def test_openai_provider_uses_openai_compatible_adapter() -> None:
    """OpenAI 兼容地址不能错误地交给 DashScope 原生 SDK。"""
    config = GameConfig(
        "key",
        "model",
        "https://example.com/v1",
        provider="openai",
    )

    components = create_model_components(config)

    assert isinstance(components.model, OpenAIChatModel)
    assert isinstance(components.formatter, OpenAIMultiAgentFormatter)


def test_deepseek_provider_disables_thinking_for_structured_output() -> None:
    """DeepSeek 必须关闭思考模式以允许 ReActAgent 强制调用结构化工具。"""
    config = GameConfig(
        "key",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
        provider="deepseek",
    )

    components = create_model_components(config)

    assert isinstance(components.model, OpenAIChatModel)
    assert components.model.generate_kwargs == {
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    assert isinstance(components.formatter, OpenAIMultiAgentFormatter)


def test_dashscope_provider_keeps_native_adapter() -> None:
    """显式选择 DashScope 时保留原生模型和 formatter。"""
    config = GameConfig(
        "key",
        "qwen-plus",
        "https://dashscope.aliyuncs.com",
        provider="dashscope",
    )

    components = create_model_components(config)

    assert isinstance(components.model, DashScopeChatModel)
    assert isinstance(components.formatter, DashScopeMultiAgentFormatter)
