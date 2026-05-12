# ============================================================
# HITL 飞书通知器 — Phase 4.3
# 功能：构建审批卡片、发送飞书通知、处理回调
# 来源：app/integrations/feishu_notifier.py（Phase 1.5已有，飞书推送基础设施）
# ============================================================
from enum import Enum
from typing import Literal, TypedDict
from datetime import datetime

# 通知类型
NotificationType = Literal["discount_approval", "task_approval"]


class HITLDecision(TypedDict):
    """HITL 审批决策"""
    decision: Literal["approve", "edit", "reject"]
    approver_id: str
    edited_rate: float = None
    rejection_reason: str = None


# ============================================================
# 卡片元素构建
# ============================================================

def _fmt_currency(amount: float) -> str:
    return f"¥{amount:.2f}"


def _fmt_rate(rate: float) -> str:
    return f"{rate * 100:.0f}%"


def build_discount_card_elements(pending_item: dict) -> list[dict]:
    """构建折扣审批卡片元素"""
    product_name = pending_item.get("product_name", "未知商品")
    original_price = pending_item.get("original_price", 0)
    discount_rate = pending_item.get("discount_rate", 0)
    final_price = original_price * (1 - discount_rate)
    category = pending_item.get("category", "未知")
    remaining_days = pending_item.get("remaining_days", "N/A")

    return [
        {"tag": "markdown", "content": f"**🛒 商品**\n{product_name}"},
        {"tag": "markdown", "content": f"**📂 品类**\n{category}"},
        {"tag": "markdown", "content": f"**⏰ 剩余保质期**\n{remaining_days} 天"},
        {"tag": "hr"},
        {
            "tag": "column_set",
            "flex_mode": "border",
            "fields": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "fields": [
                        {"tag": "markdown", "content": "**原价**"},
                        {"tag": "markdown", "content": _fmt_currency(original_price)},
                    ],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "fields": [
                        {"tag": "markdown", "content": "**折扣率**"},
                        {"tag": "markdown", "content": f"⬇️ {_fmt_rate(discount_rate)}"},
                    ],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "fields": [
                        {"tag": "markdown", "content": "**折后价**"},
                        {"tag": "markdown", "content": f"💰 {_fmt_currency(final_price)}"},
                    ],
                },
            ],
        },
    ]


def build_task_card_elements(pending_item: dict) -> list[dict]:
    """构建任务审批卡片元素"""
    task_title = pending_item.get("task_title", "未知任务")
    task_type = pending_item.get("task_type", "未知")
    assignee = pending_item.get("assignee_name", "待分配")
    due_date = pending_item.get("due_date", "未设截止日期")
    priority = pending_item.get("priority", "medium")

    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")

    return [
        {"tag": "markdown", "content": f"**📋 任务**\n{task_title}"},
        {"tag": "markdown", "content": f"**🏷️ 类型**\n{task_type}"},
        {"tag": "markdown", "content": f"**👤 指派给**\n{assignee}"},
        {"tag": "markdown", "content": f"**📅 截止日期**\n{due_date}"},
        {"tag": "markdown", "content": f"**⚡ 优先级**\n{priority_emoji} {priority.upper()}"},
    ]


def build_approval_card(
    notification_type: NotificationType,
    pending_item: dict,
    requester_id: str,
    requester_role: str,
) -> dict:
    """
    构建飞书审批交互卡片（Interactive Card）
    包含「批准」「修改折扣率」「拒绝」三个按钮
    """
    if notification_type == "discount_approval":
        elements = build_discount_card_elements(pending_item)
        header_title = "🧾 临期折扣审批请求"
    else:
        elements = build_task_card_elements(pending_item)
        header_title = "📋 任务创建审批请求"

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "subtitle": {
                    "tag": "plain_text",
                    "content": f"申请人: {requester_id}（{requester_role}）| 时间: {datetime.now().strftime('%m-%d %H:%M')}"
                },
                "template": "warning",
            },
            "elements": elements
            + [
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 批准"},
                            "type": "primary",
                            "action_id": "approve",
                            "value": {
                                "task_id": pending_item.get("task_id", ""),
                                "action": "approve"
                            },
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✏️ 修改折扣率"},
                            "type": "default",
                            "action_id": "edit",
                            "value": {
                                "task_id": pending_item.get("task_id", ""),
                                "action": "edit"
                            },
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                            "type": "danger",
                            "action_id": "reject",
                            "value": {
                                "task_id": pending_item.get("task_id", ""),
                                "action": "reject"
                            },
                        },
                    ],
                }
            ],
        },
    }


# ============================================================
# 发送通知
# ============================================================
async def send_approval_notification(
    notification_type: NotificationType,
    pending_item: dict,
    requester_id: str,
    requester_role: str,
    approver_id: str,
) -> bool:
    """
    发送飞书审批卡片通知
    复用 Phase 1.5 的 FeishuNotifier 基础设施
    """
    from app.integrations.feishu_notifier import FeishuNotifier
    from app.config import settings

    notifier = FeishuNotifier(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
    )

    card = build_approval_card(notification_type, pending_item, requester_id, requester_role)

    success = await notifier.send_message(
        receive_id=approver_id,
        msg_type="interactive",
        content=card,
    )

    return success
