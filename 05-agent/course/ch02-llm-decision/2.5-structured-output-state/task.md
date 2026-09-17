# 2.5 结构化输出与状态更新

## 任务目标

实现一个不调用真实 LLM 的运行时适配层：把模型返回的 JSON 解析为可信决策，再根据决策生成新的不可变 `AgentState`。

## 你需要完成的函数

1. `parse_decision(raw)`：使用 Pydantic 校验 JSON 结构，拒绝未知字段、未知动作和动作专属字段错误。
2. `apply_decision(state, decision)`：用 `dataclasses.replace` 返回新状态，不修改旧状态。
3. `process_model_output(state, raw)`：串联解析和状态更新。
4. `main()`：打印一次工具调用和一次结束决策的状态变化。

## 编码引导

1. 先阅读 `Decision` 和 `AgentState` 类型，区分模型字段与运行时字段。
2. 让 `Decision` 只允许 `tool_call`、`finish` 两种动作，并设置额外字段禁止策略。
3. 在模型校验后补充动作专属约束：工具调用需要 `tool_name`，结束需要 `answer`。
4. 用 `json.loads` 将字符串转换为对象，再交给 Pydantic 校验器。
5. 状态更新只根据已校验的动作设置 `status`、`pending_tool` 和 `final_answer`。
6. 运行测试，确认旧状态在每次更新后仍保持原值。

## 验收标准

- `python -m unittest -v test_reference.py` 中参考实现测试全部通过。
- 你完成 `mine.py` 后，学习者测试全部通过。
- 非法 JSON、缺失字段、未知动作、额外字段和专属参数错误都会抛出 `ValueError`。
- `tool_call` 产生 `waiting_tool` 状态；`finish` 产生 `completed` 状态。

## 运行

```bash
cd ai-exp/05-agent/course/ch02-llm-decision/2.5-structured-output-state
python -m unittest -v test_mine.py
python mine.py
```

完成 `mine.py` 后，再打开 `reference.py` 对比实现差异，并把你的思路和收获补充回笔记。
