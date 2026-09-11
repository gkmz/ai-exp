"""
1.4 环境、状态、观察与行动 — 参考实现

与 mine.py 的主要设计差异：
1. check_stock 用 .get() 防御不存在的商品（不会 KeyError）
2. observe 同样用 .get() 防御，返回 stock=0 而不是崩溃
3. decide 的分支和状态转移完全对称
4. act 中每个 action 都有清晰的状态转移注释
"""

from dataclasses import dataclass, field


@dataclass
class Order:
    order_id: str
    product: str
    quantity: int
    status: str = "pending"


@dataclass
class Environment:
    order: Order
    stock: dict[str, int] = field(default_factory=dict)

    def check_stock(self, product: str) -> int:
        return self.stock.get(product, 0)

    def deduct_stock(self, product: str, quantity: int) -> bool:
        current = self.stock.get(product, 0)
        if current >= quantity:
            self.stock[product] = current - quantity
            return True
        return False

    def update_order_status(self, status: str) -> None:
        self.order.status = status


def observe(env: Environment) -> dict:
    return {
        "order_id": env.order.order_id,
        "order_status": env.order.status,
        "product": env.order.product,
        "quantity": env.order.quantity,
        "stock": env.stock.get(env.order.product, 0),
    }


def decide(observation: dict) -> dict | None:
    status = observation["order_status"]

    if status == "pending":
        if observation["stock"] >= observation["quantity"]:
            return {
                "action": "deduct_stock",
                "product": observation["product"],
                "quantity": observation["quantity"],
            }
        return {"action": "mark_out_of_stock", "order_id": observation["order_id"]}

    if status == "confirmed":
        return {"action": "notify_confirmed", "order_id": observation["order_id"]}

    if status == "out_of_stock":
        return {"action": "notify_out_of_stock", "order_id": observation["order_id"]}

    # notified 或其他未知状态 → 任务结束
    return None


def act(env: Environment, action: dict) -> dict:
    name = action["action"]

    if name == "deduct_stock":
        # pending → confirmed
        ok = env.deduct_stock(action["product"], action["quantity"])
        if ok:
            env.update_order_status("confirmed")
            remaining = env.check_stock(action["product"])
            return {
                "success": True,
                "message": f"扣减库存: {action['product']} -{action['quantity']} → 成功, 剩余 {remaining}",
            }
        return {"success": False, "message": "扣减库存失败: 库存不足"}

    if name == "mark_out_of_stock":
        # pending → out_of_stock
        env.update_order_status("out_of_stock")
        return {"success": True, "message": f"订单 {action['order_id']} 标记为缺货"}

    if name == "notify_confirmed":
        # confirmed → notified
        env.update_order_status("notified")
        return {"success": True, "message": f"发送通知: 订单 {action['order_id']} 已确认"}

    if name == "notify_out_of_stock":
        # out_of_stock → notified
        env.update_order_status("notified")
        return {"success": True, "message": f"发送通知: 订单 {action['order_id']} 缺货"}

    return {"success": False, "message": f"未知行动: {name}"}


def run_agent(env: Environment, max_steps: int = 10) -> None:
    print(
        f"[环境] 订单: {env.order.order_id}, "
        f"商品: {env.order.product}, "
        f"需求: {env.order.quantity}, "
        f"库存: {env.check_stock(env.order.product)}"
    )

    for step in range(1, max_steps + 1):
        obs = observe(env)
        print(
            f"[观察] 订单 {obs['order_id']} {obs['order_status']}, "
            f"需要 {obs['product']} x{obs['quantity']}, "
            f"库存 {obs['stock']}"
        )

        action = decide(obs)
        if action is None:
            print(f"[结束] 任务完成, 共执行 {step} 轮")
            return

        print(f"[决策] {action['action']}")

        result = act(env, action)
        print(f"[行动] {result['message']}")

    print(f"[警告] 达到最大步数 {max_steps}，任务未完成")


if __name__ == "__main__":
    print("=" * 60)
    print("场景 1：库存充足")
    print("=" * 60)
    run_agent(
        Environment(
            order=Order(order_id="A1001", product="Widget", quantity=5),
            stock={"Widget": 100},
        )
    )

    print()

    print("=" * 60)
    print("场景 2：库存不足")
    print("=" * 60)
    run_agent(
        Environment(
            order=Order(order_id="A1002", product="Gadget", quantity=50),
            stock={"Gadget": 10},
        )
    )

    print()

    print("=" * 60)
    print("场景 3：商品不存在")
    print("=" * 60)
    run_agent(
        Environment(
            order=Order(order_id="A1003", product="Unknown", quantity=1),
            stock={},
        )
    )
