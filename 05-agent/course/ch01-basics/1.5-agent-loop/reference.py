"""
1.5 Agent Loop — 参考实现

与 mine.py 的主要差异：
1. 代码注释更详细，每个分支都有解释
2. decide 中提取了天气判断逻辑到独立函数 make_suggestion
3. update_state 中用 dataclass.replace() 替代 with_updates
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AgentState:
    goal: str
    step: int = 0
    tool_results: tuple = ()
    retry_count: int = 0
    max_retries: int = 2
    final_answer: str | None = None
    gave_up: bool = False


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

_weather_fail_count = 0


def reset_weather_tool(fail_times: int = 0) -> None:
    global _weather_fail_count
    _weather_fail_count = fail_times


def tool_weather(date: str) -> dict:
    """模拟天气查询。前 N 次失败，之后返回正常数据。"""
    global _weather_fail_count
    if _weather_fail_count > 0:
        _weather_fail_count -= 1
        return {"success": False, "error": "服务超时"}
    return {"success": True, "data": f"晴天, 25°C ({date})"}


TOOLS = {"weather": tool_weather}


def execute_tool(tool_name: str, args: dict) -> dict:
    if tool_name not in TOOLS:
        return {"success": False, "error": f"未知工具: {tool_name}"}
    try:
        return TOOLS[tool_name](**args)
    except Exception as e:
        return {"success": False, "error": f"工具执行异常: {e}"}


# ---------------------------------------------------------------------------
# 决策
# ---------------------------------------------------------------------------


def make_suggestion(weather_data: str) -> str:
    """根据天气数据生成出行建议"""
    if "雨" in weather_data or "雪" in weather_data:
        return f"明天{weather_data}，建议改天再去公园"
    if "晴" in weather_data:
        return f"明天{weather_data}，非常适合去公园！"
    return f"明天{weather_data}，可以考虑去公园"


def decide(state: AgentState) -> dict:
    last_result = state.tool_results[-1] if state.tool_results else None

    # 没有工具结果 → 首次调用天气工具
    if last_result is None:
        return {"type": "tool_call", "tool": "weather", "args": {"date": "tomorrow"}}

    # 有结果且成功 → 生成最终答案
    if last_result.get("success"):
        weather = last_result.get("data", "")
        answer = make_suggestion(weather)
        return {"type": "final_answer", "answer": answer}

    # 有结果但失败 → 判断是否重试
    if state.retry_count < state.max_retries:
        return {"type": "tool_call", "tool": "weather", "args": {"date": "tomorrow"}}

    # 重试耗尽 → 放弃
    return {"type": "give_up", "reason": "无法获取天气信息，请稍后再试"}


# ---------------------------------------------------------------------------
# 状态更新
# ---------------------------------------------------------------------------


def update_state(state: AgentState, decision: dict, tool_result: dict | None) -> AgentState:
    updates = {"step": state.step + 1}

    # 追加工具结果
    if tool_result:
        updates["tool_results"] = state.tool_results + (tool_result,)

    # 更新重试计数
    if tool_result and not tool_result.get("success"):
        updates["retry_count"] = state.retry_count + 1
    elif tool_result and tool_result.get("success"):
        updates["retry_count"] = 0

    # 设置最终答案或放弃标记
    if decision["type"] == "final_answer":
        updates["final_answer"] = decision["answer"]
    elif decision["type"] == "give_up":
        updates["gave_up"] = True

    return replace(state, **updates)


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------


def agent_loop(goal: str, max_steps: int = 10) -> str:
    state = AgentState(goal=goal)
    print(f"[开始] 目标: {goal}")

    for step in range(1, max_steps + 1):
        # 1. 观察
        last_result = state.tool_results[-1] if state.tool_results else None
        if last_result and last_result.get("success"):
            print(f"[循环 {step}] 观察: 已有工具结果: {last_result.get('data')}")
        elif last_result:
            print(
                f"[循环 {step}] 观察: 上次工具失败({last_result.get('error')}), "
                f"重试 {state.retry_count}/{state.max_retries}"
            )
        else:
            print(f"[循环 {step}] 观察: 无工具结果")

        # 2. 决策
        decision = decide(state)
        print(f"[循环 {step}] 决策: {decision['type']}", end="")
        if decision["type"] == "tool_call":
            print(f" → {decision['tool']}({decision['args']})")
        elif decision["type"] == "final_answer":
            print(f" → {decision['answer']}")
        else:
            print(f" → {decision['reason']}")

        # 3. 行动
        tool_result = None
        if decision["type"] == "tool_call":
            tool_result = execute_tool(decision["tool"], decision["args"])
            status = "成功" if tool_result.get("success") else "失败"
            detail = tool_result.get("data") or tool_result.get("error")
            print(f"[循环 {step}] 行动: {decision['tool']} → {status}: {detail}")

        # 4. 更新状态
        state = update_state(state, decision, tool_result)

        # 5. 终止判断
        if state.final_answer is not None:
            print(f"[结束] 答案: {state.final_answer}  共执行 {step} 轮")
            return state.final_answer

        if state.gave_up:
            reason = decision.get("reason", "未知原因")
            print(f"[结束] 放弃: {reason}  共执行 {step} 轮")
            return f"放弃: {reason}"

    print(f"[警告] 达到最大步数 {max_steps}")
    return "超出最大执行步数"


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("场景 1：正常流程")
    print("=" * 60)
    reset_weather_tool(fail_times=0)
    agent_loop("明天适合去公园吗？")

    print()

    print("=" * 60)
    print("场景 2：工具失败后重试成功")
    print("=" * 60)
    reset_weather_tool(fail_times=1)
    agent_loop("明天适合去公园吗？")

    print()

    print("=" * 60)
    print("场景 3：重试耗尽后放弃")
    print("=" * 60)
    reset_weather_tool(fail_times=10)
    agent_loop("明天适合去公园吗？")
