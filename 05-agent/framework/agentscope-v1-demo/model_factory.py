"""根据接口协议创建匹配的 AgentScope 模型和 formatter。"""

from dataclasses import dataclass

from agentscope.formatter import (
    DashScopeMultiAgentFormatter,
    OpenAIMultiAgentFormatter,
)
from agentscope.model import DashScopeChatModel, OpenAIChatModel
from agentscope.types import JSONSerializableObject

from config import GameConfig


@dataclass(frozen=True)
class ModelComponents:
    """一组协议匹配的模型与多 Agent formatter。"""

    model: OpenAIChatModel | DashScopeChatModel
    formatter: OpenAIMultiAgentFormatter | DashScopeMultiAgentFormatter


def create_model_components(config: GameConfig) -> ModelComponents:
    """按照 provider 创建协议兼容的模型和 formatter。"""
    if config.provider == "dashscope":
        return ModelComponents(
            model=DashScopeChatModel(
                model_name=config.model_id,
                api_key=config.api_key,
                base_http_api_url=config.base_url,
                enable_thinking=True,
            ),
            formatter=DashScopeMultiAgentFormatter(),
        )

    generate_kwargs: dict[str, JSONSerializableObject] = {}
    if config.provider == "deepseek":
        # DeepSeek 思考模式不支持 ReActAgent 结构化输出使用的强制工具调用。
        generate_kwargs = {
            "extra_body": {"thinking": {"type": "disabled"}},
        }

    return ModelComponents(
        model=OpenAIChatModel(
            model_name=config.model_id,
            api_key=config.api_key,
            client_kwargs={"base_url": config.base_url},
            generate_kwargs=generate_kwargs,
        ),
        formatter=OpenAIMultiAgentFormatter(),
    )
