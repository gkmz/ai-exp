"""2.5 学习者实现验收测试。完成 mine.py 后运行。"""

import unittest

import mine


class MineTests(unittest.TestCase):
    """验证学习者实现必须满足的行为契约。"""

    def test_parses_valid_decisions(self) -> None:
        tool = mine.parse_decision(
            '{"action":"tool_call","tool_name":"search","arguments":{"q":"agent"},"reason":"查询"}'
        )
        self.assertEqual(tool.action, "tool_call")
        finish = mine.parse_decision(
            '{"action":"finish","answer":"完成","reason":"已足够"}'
        )
        self.assertEqual(finish.answer, "完成")

    def test_rejects_invalid_decisions(self) -> None:
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
                    mine.parse_decision(raw)

    def test_preserves_old_state_when_updating_tool(self) -> None:
        old = mine.AgentState()
        new = mine.process_model_output(
            old,
            '{"action":"tool_call","tool_name":"search","reason":"查询"}',
        )
        self.assertEqual(old, mine.AgentState())
        self.assertEqual(new.status, "waiting_tool")
        self.assertEqual(new.pending_tool, "search")
        self.assertEqual(new.step, 1)

    def test_updates_finish_state(self) -> None:
        state = mine.AgentState(step=1, status="waiting_tool", pending_tool="search")
        new = mine.process_model_output(
            state,
            '{"action":"finish","answer":"完成","reason":"结束"}',
        )
        self.assertEqual(new.status, "completed")
        self.assertEqual(new.final_answer, "完成")
        self.assertIsNone(new.pending_tool)
        self.assertEqual(new.step, 2)


if __name__ == "__main__":
    unittest.main()
