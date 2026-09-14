"""2.4 上下文窗口示例框架：请补全 TODO 后运行。"""

from dataclasses import dataclass


@dataclass
class Context:
    """保存组装上下文所需的信息。"""

    system: str
    goal: str
    summary: str
    history: list[dict[str, str]]


def count_tokens(text: str) -> int:
    """用字符数近似 Token 数；生产环境应使用模型 tokenizer。"""
    return len(text)


def assemble(context: Context, budget: int) -> tuple[list[dict[str, str]], int]:
    """按预算组装消息，并返回被丢弃的历史数量。"""
    # 先加入 system、goal 和 summary
    messages = [
        {"role": "system", "content": context.system},
        {"role": "user", "content": f"目标：{context.goal}\n状态摘要：{context.summary}"},
    ]
    # 从最新历史向前加入，直到达到 budget
    used = sum(count_tokens(item["content"]) for item in messages)
    print(f"used: {used}")
    # 返回消息列表和丢弃数量
    kept: list[dict[str, str]] = []
    for item in reversed(context.history):
        size = count_tokens(item["content"])
        print(f"size: {size}")
        if used + size > budget:
            break
        kept.append(item)
        used += size
    messages.extend(reversed(kept))
    return messages, len(context.history) - len(kept)


if __name__ == "__main__":
    sample = Context(
        "你是助手。",
        "查询订单状态",
        "订单 A1001 未完成",
        [
            {"role": "user", "content": "第一轮问题"},
            {"role": "assistant", "content": "第一轮回答"},
            {"role": "user", "content": "第二轮问题"},
            {"role": "assistant", "content": "第二轮回答"},
        ],
    )
    print(assemble(sample, 40))
