"""2.4 上下文窗口示例参考实现（用字符数近似 Token）。"""

from dataclasses import dataclass


@dataclass
class Context:
    """保存组装上下文所需的信息。"""

    system: str
    goal: str
    summary: str
    history: list[dict[str, str]]


def count_tokens(text: str) -> int:
    """近似计算文本 Token 数。"""
    return len(text)


def assemble(context: Context, budget: int) -> tuple[list[dict[str, str]], int]:
    """优先保留规则、目标和摘要，再加入最新历史。"""
    messages = [
        {"role": "system", "content": context.system},
        {"role": "user", "content": f"目标：{context.goal}\n状态摘要：{context.summary}"},
    ]
    used = sum(count_tokens(item["content"]) for item in messages)
    kept: list[dict[str, str]] = []
    for item in reversed(context.history):
        size = count_tokens(item["content"])
        if used + size > budget:
            break
        kept.append(item)
        used += size
    messages.extend(reversed(kept))
    return messages, len(context.history) - len(kept)


if __name__ == "__main__":
    sample = Context(
        "你是助手。", "查询订单状态", "订单 A1001 未完成", [{"role": "user", "content": "上一问"}]
    )
    print(assemble(sample, 100))
