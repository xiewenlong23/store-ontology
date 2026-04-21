#!/usr/bin/env python3
"""
飞书卡片通知服务

使用飞书开放API发送卡片通知，支持任务创建/完成/到期提醒。
"""

import os
import json
import logging
from typing import Optional, Any
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
FEISHU_BOT_TOKEN = os.getenv("FEISHU_BOT_TOKEN", "")
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")


class FeishuNotificationService:
    """
    飞书卡片通知服务

    支持两种模式：
    1. Webhook 模式（简单，无需 token）- 使用传入的 Webhook URL
    2. Bot Token 模式（支持更多操作）- 使用 FEISHU_BOT_TOKEN
    """

    def __init__(self, webhook_url: Optional[str] = None, bot_token: Optional[str] = None):
        self.webhook_url = webhook_url or FEISHU_WEBHOOK_URL
        self.bot_token = bot_token or FEISHU_BOT_TOKEN

    def _send_webhook(self, payload: dict) -> bool:
        """通过 Webhook 发送消息（简单模式）"""
        if not self.webhook_url:
            logger.warning("[Feishu] Webhook URL not configured, skipping notification")
            return False

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    logger.info("[Feishu] Webhook notification sent successfully")
                    return True
                else:
                    logger.error(f"[Feishu] Webhook failed: {response.status_code} {response.text}")
                    return False
        except Exception as e:
            logger.error(f"[Feishu] Webhook error: {e}")
            return False

    def _send_card(self, card_payload: dict) -> bool:
        """发送富文本卡片消息"""
        payload = {
            "msg_type": "interactive",
            "card": card_payload,
        }
        return self._send_webhook(payload)

    def send_task_created_card(
        self,
        task_id: str,
        product_name: str,
        category: str,
        discount_rate: float,
        days_left: int,
        assignee: str = "店长",
    ) -> bool:
        """发送任务创建卡片"""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🆕 出清任务已创建"},
                "template": "orange" if days_left <= 1 else "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**任务编号**\n{task_id}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**负责人**\n{assignee}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**商品**\n{product_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**品类**\n{category}"}},
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**推荐折扣**\n{discount_rate*100:.0f}%"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**剩余天数**\n{days_left} 天"}},
                    ],
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}],
                },
            ],
        }
        return self._send_card(card)

    def send_task_completed_card(
        self,
        task_id: str,
        product_name: str,
        sell_through_rate: float,
        completed_by: str = "店长",
    ) -> bool:
        """发送任务完成卡片"""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "✅ 出清任务已完成"},
                "template": "green",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**任务编号**\n{task_id}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**完成人**\n{completed_by}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**商品**\n{product_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**售罄率**\n{sell_through_rate*100:.0f}%"}},
                    ],
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}],
                },
            ],
        }
        return self._send_card(card)

    def send_expiry_reminder_card(
        self,
        product_name: str,
        days_left: int,
        urgent: bool = False,
    ) -> bool:
        """发送临期提醒卡片"""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 商品临期提醒"},
                "template": "red" if urgent else "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{product_name}** 剩余保质期 **{days_left} 天**，请及时处理！",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看详情"},
                            "type": "primary",
                        },
                    ],
                },
            ],
        }
        return self._send_card(card)

    def send_daily_scan_report(
        self,
        total_skus: int,
        tasks_created: int,
        high_urgency_count: int,
    ) -> bool:
        """发送每日库存扫描报告卡片"""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📊 每日库存扫描报告"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**扫描 SKU**\n{total_skus}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**新建任务**\n{tasks_created}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**高紧急**\n{high_urgency_count}"}},
                    ],
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}],
                },
            ],
        }
        return self._send_card(card)


# 全局单例
_feishu_instance: Optional[FeishuNotificationService] = None


def get_feishu_service() -> FeishuNotificationService:
    global _feishu_instance
    if _feishu_instance is None:
        _feishu_instance = FeishuNotificationService()
    return _feishu_instance