# ============================================================
# HITL 审批节点 — Phase 4.1
# 功能：折扣审批 / 任务创建审批的中断等待节点
# Deep Agents interrupt_on 触发后，发送飞书通知并等待审批
# ============================================================
import structlog
from typing import Literal
from app.agent.state import AgentState, DiscountTask, HITLDecision
from app.integrations.hitl_notifier import (
    NotificationType,
    build_approval_card,
    send_approval_notification,
)
from app.auth.roles import resolve_user_role

logger = structlog.get_logger(__name__)


async def hitl_approval_node(
    state: AgentState,
    action_type: Literal["discount", "task"],
    pending_item: DiscountTask,
) -> AgentState:
    """
    HITL 审批节点：触发审批流程，等待店长/总部审批决策。

    流程：
    1. 解析当前用户角色
    2. 判断是否需要 HITL（角色 + 权限矩阵）
    3. 推送飞书审批卡片
    4. 设置中断标志，等待外部回调
    """
    user_id = state.get("user_id", "unknown")
    role = await resolve_user_role(user_id, state.get("store_id"))

    # ===== 权限检查 =====
    if action_type == "discount":
        if role == "clerk":
            # 店员发起的折扣 → 需要店长审批
            state["hitl_required"] = True
            state["hitl_approver"] = state.get("store_manager_id")
            pending_item["status"] = "pending_approval"
            state["pending_discount_task"] = pending_item
            notif_type = NotificationType.DISCOUNT_APPROVAL

        elif role == "store_manager":
            # 店长发起 → 检查折扣率是否在权限内
            discount_rate = pending_item.get("discount_rate", 0)
            if discount_rate > 0.70:
                # 超出店长权限 → 需要总部审批
                state["hitl_required"] = True
                state["hitl_approver"] = state.get("headquarters_id")
                pending_item["status"] = "pending_headquarters_approval"
                state["pending_discount_task"] = pending_item
                notif_type = NotificationType.DISCOUNT_APPROVAL
            else:
                # 店长权限内 → 自动通过
                state["hitl_required"] = False
                pending_item["status"] = "approved"
                logger.info("折扣店长权限内自动通过",
                           discount_rate=discount_rate, user_id=user_id)

        elif role == "headquarters":
            # 总部发起 → 无需审批
            state["hitl_required"] = False
            pending_item["status"] = "approved"

    elif action_type == "task":
        if role == "clerk":
            # 店员创建任务 → 需要店长审批
            state["hitl_required"] = True
            state["hitl_approver"] = state.get("store_manager_id")
            pending_item["status"] = "pending_approval"
            state["pending_discount_task"] = pending_item
            notif_type = NotificationType.TASK_APPROVAL
        else:
            # 店长/总部 → 直接通过
            state["hitl_required"] = False
            pending_item["status"] = "approved"

    # ===== 推送飞书通知 =====
    if state["hitl_required"]:
        try:
            await send_approval_notification(
                notification_type=notif_type,
                pending_item=pending_item,
                requester_id=user_id,
                requester_role=role,
                approver_id=state["hitl_approver"],
            )
            logger.info("HITL 审批通知已发送",
                       action_type=action_type,
                       approver=state["hitl_approver"])
        except Exception as e:
            logger.error("飞书审批通知发送失败", error=str(e))
            # 不阻塞流程，飞书失败不影响审批流程本身

    return state


async def handle_approval_callback(
    state: AgentState,
    decision: HITLDecision,
    approver_id: str,
    edited_rate: float = None,
    rejection_reason: str = None,
) -> AgentState:
    """
    处理审批回调（由飞书回调路由调用）
    在 Agent 被 interrupt 后，恢复执行时调用此函数
    """
    pending_item = state.get("pending_discount_task")

    if decision == "approve":
        pending_item["status"] = "approved"
        pending_item["approved_by"] = approver_id
        logger.info("审批通过", approver_id=approver_id,
                   discount_rate=pending_item.get("discount_rate"))
        state["last_approval_result"] = "approved"

    elif decision == "edit" and edited_rate is not None:
        # 店长修改折扣率后通过
        pending_item["status"] = "approved"
        pending_item["approved_rate"] = edited_rate
        pending_item["approved_by"] = approver_id
        pending_item["edit_note"] = f"店长修改折扣率: {pending_item.get('discount_rate')} → {edited_rate}"
        logger.info("审批通过（修改折扣率）", approver_id=approver_id,
                   original_rate=pending_item.get("discount_rate"),
                   new_rate=edited_rate)
        state["last_approval_result"] = "approved"

    elif decision == "reject":
        pending_item["status"] = "rejected"
        pending_item["rejected_by"] = approver_id
        pending_item["rejection_reason"] = rejection_reason
        logger.info("审批拒绝", approver_id=approver_id,
                   reason=rejection_reason)
        state["last_approval_result"] = "rejected"

    state["pending_discount_task"] = None
    state["hitl_required"] = False
    return state
