"""
1.4 环境、状态、观察与行动 — 代码框架

场景：订单处理 Agent
- 检查库存 → 库存充足则扣减并通知 → 库存不足则通知缺货

核心逻辑需要你填充，搜索 TODO 找到需要实现的部分。
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 环境（Environment）
# ---------------------------------------------------------------------------


@dataclass
class Order:
    """订单信息"""

    order_id: str
    product: str  # 商品
    quantity: int  # 下单的数量
    status: str = "pending"  # pending → confirmed / out_of_stock → notified


@dataclass
class Environment:
    """
    Agent 之外的世界：维护订单和库存。
    Agent 只能通过 Environment 提供的方法来查询和操作。
    """

    order: Order
    stock: dict[str, int] = field(default_factory=dict)  # 产品库存

    def check_stock(self, product: str) -> int:
        """查询某个商品的库存数量"""
        # 返回 product 的库存数量，不存在则返回 0
        if product == "":
            return 0
        return self.stock[product]

    def deduct_stock(self, product: str, quantity: int) -> bool:
        """
        扣减库存。
        成功返回 True，库存不足返回 False。
        """
        # 检查库存是否充足，充足则扣减并返回 True，否则返回 False
        if product == "":
            return False
        _stock = self.stock[product]
        if _stock >= quantity:
            self.stock[product] = _stock - quantity
            return True
        return False

    def update_order_status(self, status: str) -> None:
        """更新订单状态"""
        # 修改 self.order.status
        self.order.status = status


# ---------------------------------------------------------------------------
# 观察（Observation）— 只读，不改变环境
# ---------------------------------------------------------------------------


def observe(env: Environment) -> dict:
    """
    从环境中提取 Agent 决策所需的信息。

    返回格式：
    {
        "order_id": str,
        "order_status": str,
        "product": str,
        "quantity": int,
        "stock": int,
    }
    """
    # TODO: 从 env 中读取订单信息和库存信息，组装成字典返回
    return {
        "order_id": env.order.order_id,
        "order_status": env.order.status,
        "product": env.order.product,
        "quantity": env.order.quantity,
        "stock": env.stock[env.order.product],
    }


# ---------------------------------------------------------------------------
# 决策（Decision）
# ---------------------------------------------------------------------------


def decide(observation: dict) -> dict | None:
    """
    根据观察结果决定下一步行动。

    返回格式：
    {"action": "deduct_stock", "product": ..., "quantity": ...}
    {"action": "notify_confirmed", "order_id": ...}
    {"action": "notify_out_of_stock", "order_id": ...}
    None 表示任务已完成，无需继续

    决策逻辑：
    1. 如果订单状态是 pending：
       - 库存充足 → 返回 deduct_stock
       - 库存不足 → 返回 notify_out_of_stock
    2. 如果订单状态是 confirmed → 返回 notify_confirmed
    3. 如果订单状态是 notified → 返回 None（任务完成）
    """
    # 根据 observation 中的 order_status 和 stock 做决策
    order_status = observation["order_status"]
    if order_status == "pending":
        if observation["stock"] >= observation["quantity"]:
            return {
                "action": "deduct_stock",
                "product": observation["product"],
                "quantity": observation["quantity"],
            }
        else:
            return {"action": "mark_out_of_stock", "order_id": observation["order_id"]}
    elif order_status == "confirmed":
        return {"action": "notify_confirmed", "order_id": observation["order_id"]}
    elif order_status == "out_of_stock":
        return {"action": "notify_out_of_stock", "order_id": observation["order_id"]}
    elif order_status == "notified":
        return None
    return None


# ---------------------------------------------------------------------------
# 行动（Action）— 改变环境
# ---------------------------------------------------------------------------


def act(env: Environment, action: dict) -> dict:
    """
    执行行动，改变环境状态。

    返回格式：
    {"success": True/False, "message": str}
    """
    action_name = action["action"]

    if action_name == "deduct_stock":
        # 调用 env.deduct_stock，成功则更新订单状态为 confirmed
        success = env.deduct_stock(env.order.product, action["quantity"])
        if success:
            # 成功扣减库存
            env.update_order_status("confirmed")
            return {"success": True, "message": "success"}
        else:
            return {"success": False, "message": "failed"}
    elif action_name == "mark_out_of_stock":
        # 标记订单缺货
        env.update_order_status("out_of_stock")
        return {"success": True, "message": "marked out_of_stock"}
    elif action_name == "notify_confirmed":
        # 模拟发送确认通知，更新订单状态为 notified
        env.update_order_status("notified")
        return {"success": True, "message": "confirmed"}
    elif action_name == "notify_out_of_stock":
        # 模拟发送缺货通知，更新订单状态为 notified
        env.update_order_status("notified")
        return {"success": True, "message": "out_of_stock"}

    else:
        return {"success": False, "message": f"未知行动: {action_name}"}


# ---------------------------------------------------------------------------
# 主循环：观察 → 决策 → 行动
# ---------------------------------------------------------------------------


def run_agent(env: Environment, max_steps: int = 10) -> None:
    """
    Agent 主循环。
    每一轮：观察 → 决策 → 行动，直到任务完成或达到最大步数。
    """
    print(
        f"[环境] 订单: {env.order.order_id}, "
        f"商品: {env.order.product}, "
        f"需求: {env.order.quantity}, "
        f"库存: {env.check_stock(env.order.product)}"
    )

    for step in range(1, max_steps + 1):
        # 1. 观察
        obs = observe(env)
        print(
            f"[观察] 订单 {obs['order_id']} {obs['order_status']}, "
            f"需要 {obs['product']} x{obs['quantity']}, "
            f"库存 {obs['stock']}"
        )

        # 2. 决策
        action = decide(obs)
        if action is None:
            print(f"[结束] 任务完成, 共执行 {step} 轮")
            return

        print(f"[决策] {action}")

        # 3. 行动
        result = act(env, action)
        print(f"[行动] {result['message']}")

    print(f"[警告] 达到最大步数 {max_steps}，任务未完成")


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 场景 1：库存充足
    print("=" * 60)
    print("场景 1：库存充足")
    print("=" * 60)
    env1 = Environment(
        order=Order(order_id="A1001", product="Widget", quantity=5),
        stock={"Widget": 100},
    )
    run_agent(env1)

    print()

    # 场景 2：库存不足
    print("=" * 60)
    print("场景 2：库存不足")
    print("=" * 60)
    env2 = Environment(
        order=Order(order_id="A1002", product="Gadget", quantity=50),
        stock={"Gadget": 10},
    )
    run_agent(env2)
