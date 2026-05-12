# ============================================================
# 飞书推送通知集成（Feishu Notification Integration）
# Phase 1.5
# 功能：折扣审批通知、任务分配通知、库存预警通知
# ============================================================
import os
import httpx
from typing import Optional
from app.config import settings


class FeishuNotifier:
    """飞书通知服务"""

    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.base_url = "https://open.feishu.cn/open-apis"

    async def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token"""
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["tenant_access_token"]

    async def send_message(
        self,
        receive_id: str,
        receive_id_type: str,
        msg_type: str,
        content: dict,
    ) -> dict:
        """
        发送消息到用户或群

        Args:
            receive_id: 接收者 ID（open_id / union_id / user_id / email / chat_id）
            receive_id_type: 接收者类型（open_id / union_id / user_id / email / chat_id）
            msg_type: 消息类型（text / interactive / image / file / audio / media）
            content: 消息内容 dict
        """
        token = await self._get_tenant_access_token()
        url = f"{self.base_url}/im/v1/messages"

        params = {"receive_id_type": receive_id_type}
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def send_text(self, receive_id: str, text: str) -> dict:
        """发送文本消息"""
        return await self.send_message(
            receive_id=receive_id,
            receive_id_type="open_id",
            msg_type="text",
            content={"text": text},
        )

    async def send_discount_approval(
        self,
        feishu_user_id: str,
        task_id: str,
        product_name: str,
        suggested_rate: float,
        remaining_days: int,
    ) -> dict:
        """
        发送折扣审批通知卡片（卡片消息）

        店长收到通知后，点击「批准」或「拒绝」按钮，
        回调到 FastAPI /api/approve 端点。
        """
        # 折扣率显示转换：0.20 → "8折"
        discount_display = f"{int(suggested_rate * 10)}折"

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "⏰ 折扣审批提醒"},
                    "template": "orange",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**商品**：{product_name}\n"
                                f"**折扣**：{discount_display}\n"
                                f"**剩余保质期**：{remaining_days}天"
                            ),
                        },
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "✅ 批准"},
                                "type": "primary",
                                "action_id": "approve_discount",
                                "value": {"task_id": task_id, "action": "approve"},
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                                "type": "danger",
                                "action_id": "reject_discount",
                                "value": {"task_id": task_id, "action": "reject"},
                            },
                        ],
                    },
                ],
            },
        }
        return await self.send_message(
            receive_id=feishu_user_id,
            receive_id_type="open_id",
            msg_type="interactive",
            content=card,
        )

    async def send_task_assignment(
        self,
        feishu_user_id: str,
        task_id: str,
        task_title: str,
        description: str,
    ) -> dict:
        """发送任务分配通知卡片"""
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "📋 新任务分配"},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{task_title}**\n{description}",
                        },
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "查看详情"},
                                "type": "primary",
                                "action_id": "view_task",
                                "value": {"task_id": task_id},
                            },
                        ],
                    },
                ],
            },
        }
        return await self.send_message(
            receive_id=feishu_user_id,
            receive_id_type="open_id",
            msg_type="interactive",
            content=card,
        )


# FastAPI 回调端点（用于飞书卡片按钮点击回调）
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/feishu", tags=["飞书"])


@router.post("/callback")
async def feishu_callback(payload: dict):
    """
    飞书卡片按钮点击回调
    action_id: approve / edit / reject
    value: { task_id, action, edited_rate?, rejection_reason? }
    """
    action_id = payload.get("action_id", "")
    value = payload.get("value", {})
    task_id = value.get("task_id", "")

    # 从 payload 提取审批人信息（飞书事件回调带 user_id）
    approver_id = payload.get("operator_id", payload.get("user_id", "unknown"))

    # 构造 HITLDecision
    decision: HITLDecision = {
        "decision": action_id,  # approve | edit | reject
        "approver_id": approver_id,
    }
    if action_id == "edit":
        decision["edited_rate"] = value.get("edited_rate", 0.0)
    elif action_id == "reject":
        decision["rejection_reason"] = value.get("rejection_reason", "")

    # 更新 ABOX 任务状态（SPARQL UPDATE）
    from app.agent.tools.sparql_tools import update_discount_task_status
    status_map = {
        "approve": "approved",
        "edit": "approved",
        "reject": "rejected",
    }
    new_status = status_map.get(action_id, "pending")
    try:
        await update_discount_task_status(task_id, new_status, approver_id, decision.get("rejection_reason"))
    except Exception as e:
        # 写库失败不影响回调响应
        import structlog
        log = structlog.get_logger()
        log.error("HITL 回调更新任务状态失败", task_id=task_id, error=str(e))

    return {"code": 0, "message": f"已{'批准' if action_id in ('approve','edit') else '拒绝'}"}


from typing import TypedDict


class HITLDecision(TypedDict):
    """HITL 审批决策"""
    decision: str
    approver_id: str
    edited_rate: float = None
    rejection_reason: str = None
