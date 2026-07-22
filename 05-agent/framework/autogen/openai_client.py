import os

from autogen_ext.models.openai import OpenAIChatCompletionClient


def create_openai_model_client():
    """创建并配置 OpenAI 模型客户端"""
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "gpt-4o"),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        # autogen无法识别gpt-5.6模型，这里需要显示告诉它model_info，让它可以直接使用
        model_info={
            "vision": True,
            # "max_tokens": 4096,
            # "content_length": 32768,
            "function_calling": True,
            "json_output": True,
            "structured_output": True,
            "family": "gpt-5",
        },
    )
