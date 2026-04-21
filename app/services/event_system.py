#!/usr/bin/env python3
"""
事件驱动架构 - 内存事件总线

支持事件发布/订阅模式，库存变化触发推理等场景。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型枚举"""
    INVENTORY_SHELF_LIFE_WARNING = "inventory_shelf_life_warning"  # 临期预警
    INVENTORY_SHELF_LIFE_CRITICAL = "inventory_shelf_life_critical"  # 临界过期
    INVENTORY_SHELF_LIFE_EXPIRED = "inventory_shelf_life_expired"  # 已过期
    CLEARANCE_START = "clearance_start"  # 开始出清
    CLEARANCE_COMPLETE = "clearance_complete"  # 出清完成
    TASK_CREATED = "task_created"  # 任务创建
    TASK_CONFIRMED = "task_confirmed"  # 任务确认
    TASK_EXECUTED = "task_executed"  # 任务执行
    TASK_REVIEWED = "task_reviewed"  # 任务复核
    POS_SALE_RECORDED = "pos_sale_recorded"  # POS销售记录


@dataclass
class InventoryEvent:
    """库存变化事件"""
    event_id: str
    event_type: EventType
    product_id: str
    product_name: str
    category: str
    stock: int
    expiry_date: str
    days_left: int
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


@dataclass
class TaskEvent:
    """任务状态变化事件"""
    event_id: str
    event_type: EventType
    task_id: str
    product_id: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


@dataclass
class POSSaleEvent:
    """POS销售记录事件"""
    event_id: str
    event_type: EventType
    task_id: str
    product_id: str
    sold_qty: int
    sell_through_rate: float
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


# 类型别名：事件处理器
EventHandler = Callable[[dict], None]


class EventBus:
    """
    内存事件总线

    支持：
    - 事件发布（emit）
    - 事件订阅（subscribe）
    - 事件历史查询
    """
    _instance: Optional["EventBus"] = None

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._event_history: list[dict] = []
        self._max_history: int = 1000
        logger.info("[EventBus] EventBus initialized")

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅指定类型的事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"[EventBus] Subscribed handler to {event_type.value}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"[EventBus] Unsubscribed handler from {event_type.value}")
            except ValueError:
                pass

    def emit(self, event: InventoryEvent | TaskEvent | POSSaleEvent) -> str:
        """
        发布事件，触发所有订阅的处理程序

        Returns:
            event_id: 事件的唯一标识符
        """
        # 保存到历史
        event_dict = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "triggered_at": event.triggered_at.isoformat(),
        }
        if isinstance(event, InventoryEvent):
            event_dict.update({
                "product_id": event.product_id,
                "product_name": event.product_name,
                "category": event.category,
                "stock": event.stock,
                "expiry_date": event.expiry_date,
                "days_left": event.days_left,
                "metadata": event.metadata,
            })
        elif isinstance(event, TaskEvent):
            event_dict.update({
                "task_id": event.task_id,
                "product_id": event.product_id,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "metadata": event.metadata,
            })
        elif isinstance(event, POSSaleEvent):
            event_dict.update({
                "task_id": event.task_id,
                "product_id": event.product_id,
                "sold_qty": event.sold_qty,
                "sell_through_rate": event.sell_through_rate,
                "metadata": event.metadata,
            })

        self._event_history.append(event_dict)
        # 限制历史大小
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # 调用订阅的处理程序
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    handler(event_dict)
                except Exception as e:
                    logger.error(f"[EventBus] Handler error for {event.event_type.value}: {e}")

        logger.info(f"[EventBus] Emitted {event.event_type.value} for {event.event_id}")
        return event.event_id

    def emit_inventory_event(
        self,
        event_type: EventType,
        product_id: str,
        product_name: str,
        category: str,
        stock: int,
        expiry_date: str,
        days_left: int,
        metadata: Optional[dict] = None,
    ) -> str:
        """发布库存事件的便捷方法"""
        event = InventoryEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            product_id=product_id,
            product_name=product_name,
            category=category,
            stock=stock,
            expiry_date=expiry_date,
            days_left=days_left,
            metadata=metadata or {},
        )
        return self.emit(event)

    def emit_task_event(
        self,
        event_type: EventType,
        task_id: str,
        product_id: str,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """发布任务状态变化事件的便捷方法"""
        event = TaskEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            task_id=task_id,
            product_id=product_id,
            from_status=from_status,
            to_status=to_status,
            metadata=metadata or {},
        )
        return self.emit(event)

    def emit_pos_sale_event(
        self,
        task_id: str,
        product_id: str,
        sold_qty: int,
        sell_through_rate: float,
        metadata: Optional[dict] = None,
    ) -> str:
        """发布POS销售记录事件的便捷方法"""
        event = POSSaleEvent(
            event_id=str(uuid4()),
            event_type=EventType.POS_SALE_RECORDED,
            task_id=task_id,
            product_id=product_id,
            sold_qty=sold_qty,
            sell_through_rate=sell_through_rate,
            metadata=metadata or {},
        )
        return self.emit(event)

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> list[dict]:
        """获取事件历史"""
        history = self._event_history
        if event_type:
            history = [e for e in history if e["event_type"] == event_type.value]
        return history[-limit:]


# 全局单例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取事件总线单例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# 默认导出
EventBusInstance = get_event_bus()
