"""
1.5 Agent Loop — 代码框架

场景：天气出行助手
- 用户问"明天适合去公园吗？"
- Agent 调用天气工具 → 根据结果给出建议
- 工具可能失败，需要重试

核心逻辑需要你填充，搜索 TODO 找到需要实现的部分。
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 状态（State）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentState:
    """
    Agent 在循环中需要记住的所有信息。
    frozen=True 表示不可变，每轮返回新的 state。
    """

    goal: str
    step: int = 0
    tool_results: tuple = ()  # 历史工具调用结果，用 tuple 保持不可变
    retry_count: int = 0
    max_retries: int = 2
    final_answer: str | None = None
    gave_up: bool = False

    def with_updates(self, **kwargs) -> "AgentState":
        """返回一个更新了指定字段的新 AgentState"""
        current = {
            "goal": self.goal,
            "step": self.step,
            "tool_results": self.tool_results,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "final_answer": self.final_answer,
            "gave_up": self.gave_up,
        }
        current.update(kwargs)
        return AgentState(**current)


# ---------------------------------------------------------------------------
# 工具（Tools）
# ---------------------------------------------------------------------------

# 控制工具是否模拟失败，用于测试不同场景
_weather_fail_count = 0


def reset_weather_tool(fail_times: int = 0) -> None:
    """重置天气工具的失败计数器。fail_times=0 表示不失败。"""
    global _weather_fail_count
    _weather_fail_count = fail_times


def tool_weather(date: str) -> dict:
    """
    天气查询工具（模拟）。
    前 N 次调用会失败（由 reset_weather_tool 控制），之后返回正常结果。

    _weather_fail_count 的含义：还要失败几次。
    > 0 时返回失败（每次 -1），减到 0 后恢复正常返回天气数据。
    """
    global _weather_fail_count
    if _weather_fail_count > 0:
        _weather_fail_count -= 1
        return {"success": False, "error": "服务超时"}
    return {"success": True, "data": f"晴天, 25°C ({date})"}


# ---------------------------------------------------------------------------
# 工具执行器（Tool Executor）
# ---------------------------------------------------------------------------

TOOLS = {
    "weather": tool_weather,
}


def execute_tool(tool_name: str, args: dict) -> dict:
    """
    根据工具名称分发执行。
    捕获异常，确保工具失败不会导致 Agent 崩溃。
    """
    # 从 TOOLS 中查找工具函数
    f = TOOLS[tool_name]
    # 调用工具函数，传入 args
    try:
        ret = f(**args)  # 解包参数
        # 捕获异常，返回统一格式
        return ret
    except Exception as e:
        print(f"except: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 决策（Decision）
# ---------------------------------------------------------------------------


def decide(state: AgentState) -> dict:
    """
    根据当前状态决定下一步行动。

    返回三种类型之一：
    {"type": "tool_call", "tool": "weather", "args": {"date": "tomorrow"}}
    {"type": "final_answer", "answer": "..."}
    {"type": "give_up", "reason": "..."}

    决策逻辑：
    1. 如果没有天气结果 → 调用天气工具
    2. 如果上次工具失败且未超过重试上限 → 重试
    3. 如果上次工具失败且重试耗尽 → 放弃
    4. 如果有天气结果 → 生成最终答案
    """
    # 获取最近一次工具结果（如果有的话）
    last_result = state.tool_results[-1] if state.tool_results else None
    # 根据上述逻辑返回决策
    if last_result:
        if last_result.get("success"):
            # 有天气数据，根据内容生成建议
            weather = last_result.get("data", "")
            if "雨" in weather:
                answer = f"明天{weather}，建议改天再去公园"
            else:
                answer = f"明天{weather}，非常适合去公园！"
            return {"type": "final_answer", "answer": answer}
        else:
            # 工具失败，判断是否还能重试
            if state.retry_count >= state.max_retries:
                return {"type": "give_up", "reason": "无法获取天气信息，请稍后再试"}
            return {"type": "tool_call", "tool": "weather", "args": {"date": "tomorrow"}}
    return {"type": "tool_call", "tool": "weather", "args": {"date": "tomorrow"}}


# ---------------------------------------------------------------------------
# 状态更新（State Update）
# ---------------------------------------------------------------------------


def update_state(state: AgentState, decision: dict, tool_result: dict | None) -> AgentState:
    """
    根据决策和工具结果，返回新的状态。
    """
    # step +1
    step = state.step + 1
    # 如果有 tool_result，追加到 tool_results
    tool_results = state.tool_results
    if tool_result:
        # tuple 拼接
        tool_results = state.tool_results + (tool_result,)
    # 如果工具失败，retry_count +1
    if tool_result and not tool_result.get("success"):
        retry_count = state.retry_count + 1
    # 如果工具成功，retry_count 归零
    elif tool_result and tool_result.get("success"):
        retry_count = 0
    else:
        # 没有工具调用（如 final_answer / give_up），保持不变
        retry_count = state.retry_count

    # 如果决策是 final_answer，设置 final_answer
    gave_up = False
    final_answer = None
    if decision["type"] == "final_answer":
        final_answer = decision["answer"]
    elif decision["type"] == "give_up":
        gave_up = True
    else:
        final_answer = state.final_answer
    return state.with_updates(
        step=step,
        tool_results=tool_results,
        retry_count=retry_count,
        gave_up=gave_up,
        final_answer=final_answer,
    )


# ---------------------------------------------------------------------------
# Agent Loop 主循环
# ---------------------------------------------------------------------------


def agent_loop(goal: str, max_steps: int = 10) -> str:
    """
    Agent 主循环。

    返回最终答案或放弃原因。
    """
    state = AgentState(goal=goal)
    print(f"[开始] 目标: {goal}")

    for step in range(1, max_steps + 1):
        # 1. 观察（打印当前状态）
        last_result = state.tool_results[-1] if state.tool_results else None
        if last_result and last_result.get("success"):
            print(f"[循环 {step}] 观察: 已有工具结果: {last_result.get('data')}")
        elif last_result and not last_result.get("success"):
            print(
                f"[循环 {step}] 观察: 上次工具失败({last_result.get('error')}), 重试 {state.retry_count}/{state.max_retries}"
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
        tool_results = None
        if decision["type"] == "tool_call":
            tool_results = execute_tool(decision["tool"], decision["args"])
            status = "成功" if tool_results.get("success") else "失败"
            detail = tool_results.get("data") or tool_results.get("error")
            print(f"[循环 {step}] 行动: {decision['tool']} → {status}: {detail}")

        # 4. 更新状态
        state = update_state(state, decision, tool_results)

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
    # 场景 1：正常流程
    print("=" * 60)
    print("场景 1：正常流程")
    print("=" * 60)
    reset_weather_tool(fail_times=0)
    agent_loop("明天适合去公园吗？")

    print()

    # 场景 2：第一次失败，重试成功
    print("=" * 60)
    print("场景 2：工具失败后重试成功")
    print("=" * 60)
    reset_weather_tool(fail_times=1)
    agent_loop("明天适合去公园吗？")

    print()

    # 场景 3：连续失败，重试耗尽
    print("=" * 60)
    print("场景 3：重试耗尽后放弃")
    print("=" * 60)
    reset_weather_tool(fail_times=10)
    agent_loop("明天适合去公园吗？")
