#!/usr/bin/env python3
"""
门店业务工具集 — 注册到工具注册表

每个工具在模块顶层调用 registry.register() 注册自身。
导入此模块即触发注册。

工具分类：
    查询类：query_pending_products, query_tasks, query_discount_rules
    操作类：create_task, confirm_task, execute_task, review_task
    解释类：explain_discount

重要设计：
    - 工具函数通过 context.get() 获取当前门店上下文
    - store_id 参数保留用于覆盖（向下兼容），默认从 context 读取
"""

from app.tools.registry import registry
from app.models import ProductCategory, TaskStatus
from app.services.ttl_llm_reasoning import (
    ttl_query_clearance_rules,
    ttl_query_pending_skus,
    ttl_query_exemption_rules,
    reason_discount_llm,
    assess_risk_llm,
    explain_discount_reasoning,
)
from app.services.event_system import get_event_bus, EventType
from app.services.context import get_context, ToolContext
from app.services.data import get_data_service
from datetime import datetime, date
from pathlib import Path
import json
import uuid
import logging

logger = logging.getLogger(__name__)


def _get_store_id(store_id: str = None) -> str:
    """获取门店ID：优先使用参数覆盖，否则从上下文读取"""
    if store_id:
        return store_id
    ctx = get_context()
    return ctx.store_id


# ============================================================================
# 辅助函数（已迁移到 DataService）
# ============================================================================


def _get_task(tasks, task_id):
    for i, t in enumerate(tasks):
        if t["task_id"] == task_id:
            return i, t
    return None, None


def _load_products():
    """加载商品（按当前上下文 store_id 过滤）"""
    return get_data_service().load_products()


def _load_tasks():
    """加载任务（按当前上下文 store_id 过滤）"""
    return get_data_service().load_tasks()


def _load_all_tasks():
    """加载所有任务（不过滤 store_id），用于需要整体读写的场景"""
    return get_data_service().load_all_tasks()


def _save_tasks(tasks):
    """保存所有任务（不过滤 store_id），使用 DataService 失效缓存"""
    get_data_service().save_tasks(tasks)


# ============================================================================
# 查询类工具
# ============================================================================


def _query_pending_products_impl(
    category: str = None,
    days_threshold: int = 7,
    store_id: str = None,
) -> dict:
    """
    查询临期商品。

    Args:
        category: 品类筛选（如 daily_fresh），可选
        days_threshold: 多少天内到期的商品，默认7天
        store_id: 门店ID，可选（默认从 ToolContext 读取）

    Returns:
        临期商品列表
    """
    # 从上下文获取 store_id（支持参数覆盖）
    effective_store_id = _get_store_id(store_id)
    products = _load_products()
    today = date.today()
    result = []

    for p in products:
        try:
            exp = date.fromisoformat(p.get("expiry_date", ""))
            days_left = (exp - today).days
            if days_left < 0:
                continue
            if days_left >= days_threshold:
                continue
            if category and p.get("category") != category:
                continue
            # 权限过滤：只返回当前门店的商品
            if p.get("store_id") != effective_store_id:
                continue
            result.append({**p, "days_left": days_left})
        except (ValueError, TypeError):
            continue

    return {
        "success": True,
        "count": len(result),
        "products": result,
        "store_id": effective_store_id,  # 返回查询所用的门店ID
    }


def _query_tasks_impl(
    status: str = None,
    store_id: str = None,
) -> dict:
    """
    查询出清任务列表。

    Args:
        status: 状态筛选（pending/confirmed/executed/reviewed/completed），可选
        store_id: 门店ID，可选（默认从 ToolContext 读取）

    Returns:
        任务列表
    """
    effective_store_id = _get_store_id(store_id)
    tasks = _load_tasks()
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    # 权限过滤：只返回当前门店的任务
    tasks = [t for t in tasks if t.get("store_id") == effective_store_id]
    return {
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
        "store_id": effective_store_id,
    }


def _query_discount_rules_impl(
    category: str,
    days_left: int = None,
    stock: int = None,
) -> dict:
    """
    查询某品类的折扣规则。

    Args:
        category: 品类（如 daily_fresh）
        days_left: 剩余天数，可选
        stock: 库存量，可选

    Returns:
        折扣规则列表
    """
    result = ttl_query_clearance_rules(
        category=category,
    )
    return {
        "success": True,
        "rules": result,
    }


# ============================================================================
# 操作类工具
# ============================================================================


def _create_task_impl(
    product_id: str,
    product_name: str,
    category: str,
    discount_rate: float,
    original_stock: int,
    expiry_date: str,
    store_id: str = None,
    created_by: str = "店长",
    urgency: str = "medium",
) -> dict:
    """
    创建临期出清任务。

    Args:
        product_id: 商品ID
        product_name: 商品名称
        category: 品类
        discount_rate: 折扣率（0.0 - 1.0）
        original_stock: 原库存量
        expiry_date: 到期日期（YYYY-MM-DD）
        store_id: 门店ID（默认从 ToolContext 读取）
        created_by: 创建人
        urgency: 紧急程度（low/medium/high/critical）

    Returns:
        创建的任务信息
    """
    effective_store_id = _get_store_id(store_id)
    ctx = get_context()
    tasks = _load_tasks()
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    task = {
        "task_id": task_id,
        "store_id": effective_store_id,
        "product_id": product_id,
        "product_name": product_name,
        "category": category,
        "discount_rate": discount_rate,
        "original_stock": original_stock,
        "expiry_date": expiry_date,
        "status": TaskStatus.PENDING.value,
        "created_by": created_by or ctx.user_id or "店长",
        "created_at": now,
        "urgency": urgency,
    }

    tasks.append(task)
    _save_tasks(tasks)

    # 发送事件（最终一致性：核心操作已落盘，事件失败不影响业务结果）
    # 事件总线为 fire-and-forget 模式，用于异步通知观察者（如审计日志、外部系统同步）
    try:
        bus = get_event_bus()
        bus.emit_task_event(
            event_type=EventType.TASK_CREATED,
            task_id=task_id,
            product_id=product_id,
            from_status=None,
            to_status=TaskStatus.PENDING.value,
        )
    except Exception as e:
        logger.warning("Failed to emit task created event (eventual consistency): %s", e)

    return {
        "success": True,
        "task_id": task_id,
        "message": f"任务创建成功：{product_name}，折扣率 {discount_rate*100:.0f}%",
    }


def _confirm_task_impl(
    task_id: str,
    confirmed_discount_rate: float,
    confirmed_by: str = None,
    notes: str = None,
) -> dict:
    """
    确认出清任务。

    Args:
        task_id: 任务ID
        confirmed_discount_rate: 确认的折扣率
        confirmed_by: 确认人（默认从上下文读取）
        notes: 备注

    Returns:
        确认结果
    """
    ctx = get_context()
    if not ctx.has_permission("task:confirm"):
        return {"success": False, "error": "权限不足：确认任务需要 manager 或更高角色"}
    tasks = _load_all_tasks()
    idx, task = _get_task(tasks, task_id)
    if task is None:
        return {"success": False, "error": f"任务不存在: {task_id}"}

    # 权限检查：只能确认本门店的任务
    if task.get("store_id") != ctx.store_id:
        return {"success": False, "error": f"无权操作其他门店的任务"}

    if TaskStatus(task["status"]) != TaskStatus.PENDING:
        return {"success": False, "error": f"只有Pending状态的任务可以确认，当前状态: {task['status']}"}

    task["status"] = TaskStatus.CONFIRMED.value
    task["confirmed_discount_rate"] = confirmed_discount_rate
    task["confirmed_by"] = confirmed_by or ctx.user_id or "店长"
    task["confirmed_at"] = datetime.now().isoformat()
    if notes:
        task["confirmed_notes"] = notes

    _save_tasks(tasks)

    # 发送事件（最终一致性：核心操作已落盘，事件失败不影响业务结果）
    try:
        bus = get_event_bus()
        bus.emit_task_event(
            event_type=EventType.TASK_CONFIRMED,
            task_id=task_id,
            product_id=task["product_id"],
            from_status=TaskStatus.PENDING.value,
            to_status=TaskStatus.CONFIRMED.value,
        )
    except Exception as e:
        logger.warning("Failed to emit task confirmed event (eventual consistency): %s", e)

    return {
        "success": True,
        "message": f"任务已确认：{task['product_name']}，折扣率 {confirmed_discount_rate*100:.0f}%。请员工执行扫描和价签打印。",
        "task_id": task_id,
    }


def _execute_task_impl(
    task_id: str,
    executed_by: str = None,
    scan_barcode: str = None,
    price_label_printed: bool = True,
    executed_discount_rate: float = None,
) -> dict:
    """
    执行出清任务（扫描 + 打印价签）。

    Args:
        task_id: 任务ID
        executed_by: 执行人（默认从上下文读取）
        scan_barcode: 扫描的条码
        price_label_printed: 是否已打印价签
        executed_discount_rate: 实际执行的折扣率

    Returns:
        执行结果
    """
    ctx = get_context()
    if not ctx.has_permission("task:execute"):
        return {"success": False, "error": "权限不足：执行任务需要 clerk 或更高角色"}
    tasks = _load_all_tasks()
    idx, task = _get_task(tasks, task_id)
    if task is None:
        return {"success": False, "error": f"任务不存在: {task_id}"}

    # 权限检查：只能执行本门店的任务
    if task.get("store_id") != ctx.store_id:
        return {"success": False, "error": f"无权操作其他门店的任务"}

    if TaskStatus(task["status"]) != TaskStatus.CONFIRMED:
        return {"success": False, "error": f"只有Confirmed状态的任务可以执行，当前状态: {task['status']}"}

    task["status"] = TaskStatus.EXECUTED.value
    task["executed_by"] = executed_by or ctx.user_id or "员工"
    task["executed_at"] = datetime.now().isoformat()
    if scan_barcode:
        task["scan_barcode"] = scan_barcode
    task["price_label_printed"] = price_label_printed
    if executed_discount_rate is not None:
        task["executed_discount_rate"] = executed_discount_rate

    _save_tasks(tasks)

    # 发送事件（最终一致性：核心操作已落盘，事件失败不影响业务结果）
    try:
        bus = get_event_bus()
        bus.emit_task_event(
            event_type=EventType.TASK_EXECUTED,
            task_id=task_id,
            product_id=task["product_id"],
            from_status=TaskStatus.CONFIRMED.value,
            to_status=TaskStatus.EXECUTED.value,
        )
    except Exception as e:
        logger.warning("Failed to emit task executed event (eventual consistency): %s", e)

    return {
        "success": True,
        "message": f"任务已执行：{task['product_name']}。请店长复核售罄率。",
        "task_id": task_id,
    }


def _review_task_impl(
    task_id: str,
    reviewed_by: str = None,
    sell_through_rate: float = None,
    review_notes: str = None,
    requires_rectification: bool = False,
) -> dict:
    """
    复核出清任务，确认售罄率。

    Args:
        task_id: 任务ID
        reviewed_by: 复核人（默认从上下文读取）
        sell_through_rate: 售罄率（0.0 - 1.0）
        review_notes: 复核备注
        requires_rectification: 是否需要整改

    Returns:
        复核结果
    """
    ctx = get_context()
    if not ctx.has_permission("task:review"):
        return {"success": False, "error": "权限不足：复核任务需要 manager 或更高角色"}
    tasks = _load_all_tasks()
    idx, task = _get_task(tasks, task_id)
    if task is None:
        return {"success": False, "error": f"任务不存在: {task_id}"}

    # 权限检查：只能复核本门店的任务
    if task.get("store_id") != ctx.store_id:
        return {"success": False, "error": f"无权操作其他门店的任务"}

    if TaskStatus(task["status"]) != TaskStatus.EXECUTED:
        return {"success": False, "error": f"只有Executed状态的任务可以复核，当前状态: {task['status']}"}

    task["status"] = TaskStatus.REVIEWED.value if requires_rectification else TaskStatus.COMPLETED.value
    task["reviewed_by"] = reviewed_by or ctx.user_id or "店长"
    task["reviewed_at"] = datetime.now().isoformat()
    if sell_through_rate is not None:
        task["sell_through_rate"] = sell_through_rate
    if review_notes:
        task["review_notes"] = review_notes

    _save_tasks(tasks)

    # 发送事件（最终一致性：核心操作已落盘，事件失败不影响业务结果）
    try:
        bus = get_event_bus()
        bus.emit_task_event(
            event_type=EventType.TASK_REVIEWED,
            task_id=task_id,
            product_id=task["product_id"],
            from_status=TaskStatus.EXECUTED.value,
            to_status=TaskStatus.REVIEWED.value,
        )
    except Exception as e:
        logger.warning("Failed to emit task reviewed event (eventual consistency): %s", e)

    final_status = "需要整改" if requires_rectification else "已完成"
    return {
        "success": True,
        "message": f"任务已复核：{task['product_name']}，状态: {final_status}。任务闭环。",
        "task_id": task_id,
        "final_status": final_status,
    }


# ============================================================================
# 解释类工具
# ============================================================================


def _query_discount_impl(
    product_id: str = None,
    product_name: str = None,
    category: str = None,
    expiry_date: str = None,
    stock: int = None,
    discount_rate: float = None,
) -> dict:
    """
    查询折扣建议或解释为什么某商品是某个折扣。

    Args:
        product_id: 商品ID
        product_name: 商品名称
        category: 品类（如 daily_fresh）
        expiry_date: 到期日期（YYYY-MM-DD）
        stock: 库存量
        discount_rate: 当前折扣率（查询为什么是这个折扣时传入）

    Returns:
        折扣建议或解释
    """
    if discount_rate is not None and product_name:
        # 解释型查询：为什么这件商品打这个折扣
        exp_date = date.fromisoformat(expiry_date) if expiry_date else None
        result = explain_discount_reasoning(
            product_id=product_id or "UNKNOWN",
            product_name=product_name,
            category=category,
            expiry_date=exp_date,
            stock=stock,
            discount_rate=discount_rate,
        )
        return result
    else:
        # 建议型查询：这件商品应该打几折
        exp_date = date.fromisoformat(expiry_date) if expiry_date else None
        try:
            cat = ProductCategory(category) if category else ProductCategory.DAILY_FRESH
        except ValueError:
            cat = ProductCategory.DAILY_FRESH

        # 查 TTL 规则
        rules = ttl_query_clearance_rules(category=category or "daily_fresh")
        if not rules and exp_date:
            days_left = (exp_date - date.today()).days
            rules = ttl_query_clearance_rules(category=category or "daily_fresh")

        # 推理折扣
        discount_result = reason_discount_llm(
            product_id=product_id or "UNKNOWN",
            product_name=product_name or "商品",
            category=cat,
            expiry_date=exp_date or date.today(),
            stock=stock or 0,
            use_llm=False,
        )

        # 风险评估
        risk_result = assess_risk_llm(
            discount_rate=discount_result.get("recommended_discount") or 0.3,
            stock=stock or 0,
            days_left=discount_result.get("days_left", 0),
            category=cat,
            use_llm=False,
        )

        return {
            "success": True,
            "product_name": product_name,
            "category": category,
            "recommended_discount": discount_result.get("recommended_discount"),
            "discount_range": discount_result.get("discount_range"),
            "tier": discount_result.get("tier"),
            "tier_name": discount_result.get("tier_name"),
            "reasoning": discount_result.get("reasoning"),
            "risk_level": risk_result.get("risk_level"),
            "auto_confirm": risk_result.get("auto_confirm"),
        }


# ============================================================================
# 注册工具
# ============================================================================

# 查询类工具 schema
QUERY_PENDING_SCHEMA = {
    "name": "query_pending_products",
    "description": "查询当前门店的临期商品列表。可按品类和天数筛选。返回商品名称、品类、库存、到期日期、剩余天数。",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "商品品类，如 daily_fresh（日配）、bakery（烘焙）、frozen（冷冻）等",
            },
            "days_threshold": {
                "type": "integer",
                "description": "多少天内到期的商品算临期，默认7天",
                "default": 7,
            },
            "store_id": {
                "type": "string",
                "description": "门店ID，可选",
            },
        },
    },
}

QUERY_TASKS_SCHEMA = {
    "name": "query_tasks",
    "description": "查询出清任务列表。可按状态和门店筛选。返回任务ID、商品名称、折扣率、状态、创建时间等。",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["pending", "confirmed", "executed", "reviewed", "completed"],
                "description": "任务状态筛选",
            },
            "store_id": {
                "type": "string",
                "description": "门店ID，可选",
            },
        },
    },
}

QUERY_DISCOUNT_RULES_SCHEMA = {
    "name": "query_discount_rules",
    "description": "查询某品类的临期折扣规则，包括各tier的折扣率范围和建议折扣。用于了解某品类临期品的标准折扣政策。",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "品类（如 daily_fresh、bakery、frozen）",
            },
            "days_left": {
                "type": "integer",
                "description": "剩余天数，可选",
            },
            "stock": {
                "type": "integer",
                "description": "库存量，可选",
            },
        },
        "required": ["category"],
    },
}

# 操作类工具 schema
CREATE_TASK_SCHEMA = {
    "name": "create_task",
    "description": "创建一个临期商品出清任务。需要提供商品信息、折扣率、库存等。创建后任务状态为pending，需店长确认。",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "商品ID"},
            "product_name": {"type": "string", "description": "商品名称"},
            "category": {"type": "string", "description": "商品品类"},
            "discount_rate": {"type": "number", "description": "折扣率，如0.4表示4折"},
            "original_stock": {"type": "integer", "description": "原价库存量"},
            "expiry_date": {"type": "string", "description": "到期日期，格式YYYY-MM-DD"},
            "store_id": {"type": "string", "description": "门店ID"},
            "created_by": {"type": "string", "description": "创建人"},
            "urgency": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "紧急程度",
            },
        },
        "required": ["product_id", "product_name", "discount_rate", "original_stock", "expiry_date"],
    },
}

CONFIRM_TASK_SCHEMA = {
    "name": "confirm_task",
    "description": "确认一个待确认的出清任务。确认后任务状态从pending变为confirmed，员工可以执行扫描和打印价签。",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务ID"},
            "confirmed_discount_rate": {"type": "number", "description": "确认的折扣率"},
            "confirmed_by": {"type": "string", "description": "确认人"},
            "notes": {"type": "string", "description": "备注"},
        },
        "required": ["task_id", "confirmed_discount_rate"],
    },
}

EXECUTE_TASK_SCHEMA = {
    "name": "execute_task",
    "description": "执行一个已确认的出清任务。员工完成IF枪扫描和价签打印后调用此工具。",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务ID"},
            "executed_by": {"type": "string", "description": "执行人"},
            "scan_barcode": {"type": "string", "description": "扫描的条码"},
            "price_label_printed": {"type": "boolean", "description": "是否已打印价签"},
            "executed_discount_rate": {"type": "number", "description": "实际执行的折扣率"},
        },
        "required": ["task_id"],
    },
}

REVIEW_TASK_SCHEMA = {
    "name": "review_task",
    "description": "复核一个已执行的出清任务。店长确认售罄率后调用此工具，任务闭环。",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务ID"},
            "reviewed_by": {"type": "string", "description": "复核人"},
            "sell_through_rate": {"type": "number", "description": "售罄率（0.0-1.0）"},
            "review_notes": {"type": "string", "description": "复核备注"},
            "requires_rectification": {"type": "boolean", "description": "是否需要整改"},
        },
        "required": ["task_id"],
    },
}

# 解释类工具 schema
QUERY_DISCOUNT_SCHEMA = {
    "name": "query_discount",
    "description": "查询某商品的折扣建议，或解释为什么某商品当前是某个折扣。传入discount_rate时为解释型查询（为什么），不传时为建议型查询（应该打几折）。",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "商品ID"},
            "product_name": {"type": "string", "description": "商品名称"},
            "category": {"type": "string", "description": "品类"},
            "expiry_date": {"type": "string", "description": "到期日期 YYYY-MM-DD"},
            "stock": {"type": "integer", "description": "库存量"},
            "discount_rate": {"type": "number", "description": "当前折扣率（解释型查询时传入）"},
        },
    },
}


def _query_pending_with_discount_impl(
    category: str = None,
    days_threshold: int = 7,
    store_id: str = None,
) -> dict:
    """
    查询临期商品并返回每个商品的折扣建议。

    这是一个组合工具：先查临期商品列表，再对每个商品调用折扣推理引擎。

    Args:
        category: 品类筛选（如 daily_fresh），可选
        days_threshold: 多少天内到期的商品，默认7天
        store_id: 门店ID，可选（默认从 ToolContext 读取）

    Returns:
        临期商品列表，每个商品包含折扣建议
    """
    effective_store_id = _get_store_id(store_id)
    products = _load_products()
    today = date.today()
    result = []

    for p in products:
        try:
            exp = date.fromisoformat(p.get("expiry_date", ""))
            days_left = (exp - today).days
            if days_left < 0:
                continue
            if days_left >= days_threshold:
                continue
            if category and p.get("category") != category:
                continue
            # 权限过滤：只返回当前门店的商品
            if p.get("store_id") != effective_store_id:
                continue

            # 对每个商品进行折扣推理
            cat = ProductCategory(p.get("category", "daily_fresh"))
            discount_result = reason_discount_llm(
                product_id=p.get("product_id", "UNKNOWN"),
                product_name=p.get("name", "商品"),
                category=cat,
                expiry_date=exp,
                stock=p.get("stock", 0),
                use_llm=False,
            )
            risk_result = assess_risk_llm(
                discount_rate=discount_result.get("recommended_discount") or 0.3,
                stock=p.get("stock", 0),
                days_left=days_left,
                category=cat,
                use_llm=False,
            )

            item = {
                **p,
                "days_left": days_left,
                "recommended_discount": discount_result.get("recommended_discount"),
                "discount_range": discount_result.get("discount_range"),
                "tier": discount_result.get("tier"),
                "tier_name": discount_result.get("tier_name"),
                "risk_level": risk_result.get("risk_level"),
                "auto_confirm": risk_result.get("auto_confirm"),
            }
            result.append(item)
        except (ValueError, TypeError, KeyError):
            continue

    return {
        "success": True,
        "count": len(result),
        "products": result,
        "store_id": effective_store_id,
    }


# ============================================================================
# 组合工具 Schema
# ============================================================================

QUERY_PENDING_WITH_DISCOUNT_SCHEMA = {
    "name": "query_pending_with_discount",
    "description": "查询临期商品并同时返回每个商品的折扣建议。组合了 query_pending_products 和 query_discount 的能力，适合店长一站式了解「临期哪些商品 + 该打几折」。返回商品名称、品类、库存、到期天数、推荐折扣、风险等级。",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "商品品类，如 daily_fresh（日配）、bakery（烘焙）、frozen（冷冻）等",
            },
            "days_threshold": {
                "type": "integer",
                "description": "多少天内到期的商品算临期，默认7天",
                "default": 7,
            },
            "store_id": {
                "type": "string",
                "description": "门店ID，可选",
            },
        },
    },
}


# 模块导入时注册所有工具
registry.register(
    name="query_pending_with_discount",
    toolset="store",
    schema=QUERY_PENDING_WITH_DISCOUNT_SCHEMA,
    handler=_query_pending_with_discount_impl,
)
registry.register(
    name="query_pending_products",
    toolset="store",
    schema=QUERY_PENDING_SCHEMA,
    handler=_query_pending_products_impl,
)
registry.register(
    name="query_tasks",
    toolset="store",
    schema=QUERY_TASKS_SCHEMA,
    handler=_query_tasks_impl,
)
registry.register(
    name="query_discount_rules",
    toolset="store",
    schema=QUERY_DISCOUNT_RULES_SCHEMA,
    handler=_query_discount_rules_impl,
)
registry.register(
    name="create_task",
    toolset="store",
    schema=CREATE_TASK_SCHEMA,
    handler=_create_task_impl,
)
registry.register(
    name="confirm_task",
    toolset="store",
    schema=CONFIRM_TASK_SCHEMA,
    handler=_confirm_task_impl,
)
registry.register(
    name="execute_task",
    toolset="store",
    schema=EXECUTE_TASK_SCHEMA,
    handler=_execute_task_impl,
)
registry.register(
    name="review_task",
    toolset="store",
    schema=REVIEW_TASK_SCHEMA,
    handler=_review_task_impl,
)
registry.register(
    name="query_discount",
    toolset="store",
    schema=QUERY_DISCOUNT_SCHEMA,
    handler=_query_discount_impl,
)
