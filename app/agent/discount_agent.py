# ============================================================
# Deep Agents 运行时 — Phase 2.3
# discount-skill 的 Agent 核心
# 基于 LangChain Deep Agents + interrupt_on 实现 HITL 审批流
# ============================================================
from typing import Literal
from app.agent.state import AgentState, DiscountTask
from app.agent.tools.discount_tools import (
    calculate_discount_tier,
    create_discount_task,
    approve_discount,
    reject_discount,
)
from app.agent.tools.sparql_tools import query_expiring_products, query_product_info
from app.integrations.feishu_notifier import FeishuNotifier
from langchain_core.messages import HumanMessage, AIMessage
import structlog

logger = structlog.get_logger()


class DiscountAgent:
    """
    临期折扣 Agent（Deep Agents 运行时）

    流程：
    1. 接收用户折扣请求
    2. 查临期商品（SPARQL）
    3. 计算折扣层级
    4. 创建 discount_task，写入 state
    5. HITL 中断 → 等待店长审批（飞书卡片）
    6. 审批回调后恢复执行
    7. 执行折扣 → 记录审计日志
    """

    def __init__(self):
        self.notifier = FeishuNotifier()

    async def run(self, state: AgentState) -> AgentState:
        """
        主运行函数

        每次工具执行后返回新状态，Deep Agents 框架自动处理中断和恢复。
        """
        user_message = state["messages"][-1].content.lower()
        store_id = state["store_id"]
        user_id = state["user_id"]

        # ======================================================
        # 场景 1：用户询问临期商品
        # ======================================================
        if any(kw in user_message for kw in ["临期", "快过期", "哪些要打折"]):
            logger.info("discount_agent_expiring_products", store_id=store_id)

            # 查询临期商品
            products = await query_expiring_products(store_id=store_id, days=7)
            state["expiring_products_cache"] = products

            if not products:
                state["recent_results"] = ["目前没有需要处理的临期商品。"]
                return state

            # 构建回复
            lines = ["以下是需要关注处理的临期商品："]
            for p in products[:5]:
                lines.append(
                    f"• {p['product_name']}（剩余 {p['remaining_days']} 天）"
                )
            state["recent_results"] = ["\n".join(lines)]
            return state

        # ======================================================
        # 场景 2：用户申请折扣
        # ======================================================
        if any(kw in user_message for kw in ["打折", "折扣", "申请折扣"]):
            logger.info("discount_agent_create_task", store_id=store_id)

            # 取缓存中的临期商品或重新查询
            products = state.get("expiring_products_cache") or []
            if not products:
                products = await query_expiring_products(store_id=store_id, days=7)
                state["expiring_products_cache"] = products

            if not products:
                state["recent_results"] = ["没有可申请折扣的临期商品。"]
                return state

            # 取第一个商品生成折扣任务（实际生产中应让用户选择）
            top_product = products[0]
            tier = await calculate_discount_tier(
                product_id=top_product["product_id"],
                remaining_days=top_product["remaining_days"],
                store_id=store_id,
            )

            if tier["tier"] == "EXEMPT":
                state["recent_results"] = [
                    f"{top_product['product_name']} 是豁免商品，不参与折扣。"
                ]
                return state

            task = await create_discount_task(
                product_id=top_product["product_id"],
                discount_tier=tier["tier"],
                suggested_rate=tier["rate"],
                store_id=store_id,
                created_by=state["employee_id"],
                product_name=top_product["product_name"],
            )

            state["current_task"] = task
            state["pending_approvals"].append(task)

            # ==============================================
            # HITL 中断：发送飞书卡片给店长
            # ==============================================
            state["interrupt"] = True
            state["interrupt_reason"] = "pending_approval"
            state["interrupt_data"] = {
                "task_id": task["task_id"],
                "product_name": top_product["product_name"],
            }

            await self.notifier.send_discount_approval(
                feishu_user_id=user_id,
                task_id=task["task_id"],
                product_name=top_product["product_name"],
                suggested_rate=tier["rate"],
                remaining_days=top_product["remaining_days"],
            )

            logger.info(
                "discount_agent_waiting_approval",
                task_id=task["task_id"],
                store_id=store_id,
            )
            return state

        # ======================================================
        # 场景 3：审批回调（通过飞书卡片触发）
        # ======================================================
        # 实际由 /api/feishu/callback 端点处理，更新 state 后恢复 Agent
        return state

    # ============================================================
    # 审批回调处理（供外部调用）
    # ============================================================
    async def handle_approval(
        self,
        task_id: str,
        action: Literal["approve", "reject"],
        approved_rate: float = None,
        reason: str = None,
        approver_id: str = None,
    ) -> AgentState:
        """
        飞书卡片回调触发此方法，恢复 Agent 执行。

        Args:
            task_id: 折扣任务 ID
            action: approve / reject
            approved_rate: 店长修改后的折扣率（approve 时）
            reason: 拒绝原因（reject 时）
            approver_id: 审批人 ID
        """
        # 查找对应任务（从全局状态中，此处简化处理）
        # 实际应从 ABOX 数据库中恢复任务状态
        task = None  # 实际从 state["pending_approvals"] 中查找

        if action == "approve":
            task = await approve_discount(task, approved_rate, approver_id)
            logger.info("discount_approved", task_id=task_id, rate=approved_rate)
            return {
                "recent_results": [
                    f"折扣已批准：{task['product_name']} {task['discount_tier']['rate_display']}"
                ],
                "interrupt": False,
            }
        else:
            task = await reject_discount(task, reason, approver_id)
            logger.info("discount_rejected", task_id=task_id, reason=reason)
            return {
                "recent_results": [
                    f"折扣已拒绝：{task['product_name']}，原因：{reason}"
                ],
                "interrupt": False,
            }
