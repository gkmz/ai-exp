"""2.5 参考实现验收测试。"""

import unittest

import reference


class DecisionTests(unittest.TestCase):
    """验证决策解析的成功与拒绝路径。"""

    def test_parses_tool_call_and_finish(self) -> None:
        tool = reference.parse_decision(
            '{"action":"tool_call","tool_name":"search","arguments":{"q":"agent"},"reason":"查询"}'
        )
        self.assertEqual(tool.action, "tool_call")
        finish = reference.parse_decision(
            '{"action":"finish","answer":"完成","reason":"已足够"}'
        )
        self.assertEqual(finish.answer, "完成")

    def test_rejects_invalid_payloads(self) -> None:
        invalid = [
            "不是 JSON",
            '{"action":"unknown","reason":"x"}',
            '{"action":"tool_call","reason":"x"}',
            '{"action":"finish","reason":"x"}',
            '{"action":"tool_call","tool_name":"search","answer":"越界","reason":"x"}',
            '{"action":"finish","answer":"完成","tool_name":"search","reason":"x"}',
            '{"action":"finish","answer":"完成","reason":"x","extra":1}',
        ]
        for raw in invalid:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    reference.parse_decision(raw)


class StateTests(unittest.TestCase):
    """验证不可变状态更新。"""

    def test_updates_tool_call_without_mutating_old_state(self) -> None:
        old = reference.AgentState()
        new = reference.process_model_output(
            old,
            '{"action":"tool_call","tool_name":"search","reason":"查询"}',
        )
        self.assertEqual(old, reference.AgentState())
        self.assertEqual(new.status, "waiting_tool")
        self.assertEqual(new.pending_tool, "search")
        self.assertEqual(new.step, 1)

    def test_updates_finish(self) -> None:
        state = reference.AgentState(step=1, status="waiting_tool", pending_tool="search")
        new = reference.process_model_output(
            state,
            '{"action":"finish","answer":"完成","reason":"结束"}',
        )
        self.assertEqual(new.status, "completed")
        self.assertEqual(new.final_answer, "完成")
        self.assertIsNone(new.pending_tool)
        self.assertEqual(new.step, 2)


if __name__ == "__main__":
    unittest.main()
