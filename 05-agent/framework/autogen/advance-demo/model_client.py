"""高级版演示使用的模型客户端配置。"""

import os

from autogen_ext.models.openai import OpenAIChatCompletionClient


def create_model_client() -> OpenAIChatCompletionClient:
    """根据环境变量创建 OpenAI 兼容模型客户端。"""
    # API Key 是唯一不能安全提供默认值的配置，因此缺失时立即终止。
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise ValueError("缺少 LLM_API_KEY，请先配置 advance-demo/.env")

    # OpenAIChatCompletionClient 不只支持 OpenAI 官方接口，也支持实现了
    # OpenAI Chat Completions 协议的兼容服务，因此 base_url 可以由环境变量覆盖。
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "gpt-4o"),
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        # AutoGen 通过 model_info 判断当前模型支持哪些能力。
        # 本 Demo 的产品规格和审查结论依赖 structured_output/json_output。
        model_info={
            "vision": True,
            "function_calling": True,
            "json_output": True,
            "structured_output": True,
            "family": "gpt-5",
        },
    )
