import tempfile
import unittest
from pathlib import Path

from autogen_ext.models.openai import OpenAIChatCompletionClient

from agents import create_code_reviewer, create_engineer
from workspace import TaskWorkspace


class AgentToolSchemaTest(unittest.TestCase):
    """验证与结构化输出共同使用的工具满足 OpenAI 严格模式。"""

    def setUp(self) -> None:
        """创建无需真实网络请求的模型客户端和临时工作区。"""
        self.model_client = OpenAIChatCompletionClient(
            model="gpt-4o",
            api_key="test-key",
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = TaskWorkspace(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        """释放临时工作区。"""
        self.temp_dir.cleanup()

    def test_engineer_tools_use_strict_schemas(self) -> None:
        """工程师的全部文件工具都应允许 OpenAI 自动解析。"""
        agent = create_engineer(self.model_client, self.workspace)

        self.assertTrue(agent._tools)
        self.assertTrue(all(tool.schema["strict"] for tool in agent._tools))

    def test_reviewer_tools_use_strict_schemas(self) -> None:
        """审查员的全部只读工具都应允许 OpenAI 自动解析。"""
        agent = create_code_reviewer(self.model_client, self.workspace)

        self.assertTrue(agent._tools)
        self.assertTrue(all(tool.schema["strict"] for tool in agent._tools))


if __name__ == "__main__":
    unittest.main()
