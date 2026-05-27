"""本体驱动通用工具 — Object/Link/Action Types 的统一操作接口"""

import json
import uuid
from datetime import datetime, date
from typing import Any, Optional

from langchain_core.tools import tool

from models.schemas import ActionType, TaskStatus


# ============ 本体 Registry（延迟导入避免循环）============

def _get_registry():
    from ontology.parser import get_ontology_parser
    return get_ontology_parser().registry


def _parser():
    from ontology.parser import get_ontology_parser
    return get_ontology_parser()


def build_ontology_prompt() -> str:
    """生成基于本体定义的系统提示，供 main.py 使用"""
    return _parser().build_system_prompt()


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _wrap(data: dict, summary: str) -> str:
    """将结构化数据用特殊标记包裹，供前端提取渲染 UI"""
    return f"{summary}\n<!--COPILOTKIT_DATA-->\n{json.dumps(data, ensure_ascii=False)}\n<!--/COPILOTKIT_DATA-->"


# ============ 通用 Object Tools ============

@tool
def query_entity(entity_type: str, entity_id: Optional[str] = None, store_id: Optional[str] = None,
                 filter_field: Optional[str] = None, filter_value: Optional[str] = None) -> str:
    """通用实体查询 — 根据本体定义查询任意实体类型。

    Args:
        entity_type: 实体类型名，如 Store,Employee,Product,NearExpiryProduct,Task
        entity_id: 实体ID（可选）
        store_id: 门店ID过滤（可选）
        filter_field: 自定义过滤字段（可选）
        filter_value: 自定义过滤值（可选）
    """
    registry = _get_registry()
    obj_type = registry.object_types.get(entity_type)
    if not obj_type:
        return f"未知实体类型: {entity_type}。可选: {', '.join(registry.object_types.keys())}"

    data = _load_json(f"{_parser().data_dir}/{obj_type.storage_file}")

    if entity_id:
        match = next((d for d in data if d.get('id') == entity_id), None)
        if not match:
            return f"未找到 {entity_type}: {entity_id}"
        return _wrap({
            "type": "entity_detail",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "data": match,
        }, f"查询到 {entity_type} 详情，详见右侧卡片。")

    if store_id:
        data = [d for d in data if d.get('store_id') == store_id]
    elif filter_field and filter_value is not None:
        data = [d for d in data if str(d.get(filter_field, '')) == str(filter_value)]

    if not data:
        return _wrap({
            "type": "entity_list",
            "entity_type": entity_type,
            "total": 0,
            "items": [],
        }, f"未找到 {entity_type} 记录。")

    items = []
    for item in data[:20]:
        key_vals = {p.name: item.get(p.name, '') for p in obj_type.properties[:6] if item.get(p.name)}
        items.append({"id": item.get('id', ''), "fields": key_vals})

    return _wrap({
        "type": "entity_list",
        "entity_type": entity_type,
        "label_zh": obj_type.label_zh,
        "total": len(data),
        "items": items,
        "has_more": len(data) > 20,
    }, f"查询到 {len(items)} 条 {obj_type.label_zh} 记录，详见右侧卡片。")


@tool
def create_entity(entity_type: str, name: str = "", **kwargs: Any) -> str:
    """通用实体创建。"""
    registry = _get_registry()
    obj_type = registry.object_types.get(entity_type)
    if not obj_type:
        return f"未知实体类型: {entity_type}"

    kwargs.setdefault("id", f"{entity_type.lower()}_{uuid.uuid4().hex[:8]}")
    if name:
        kwargs["name"] = name

    file_path = f"{_parser().data_dir}/{obj_type.storage_file}"
    data = _load_json(file_path)
    data.append(kwargs)
    _save_json(file_path, data)

    return _wrap({
        "type": "create_result",
        "entity_type": entity_type,
        "entity_id": kwargs['id'],
        "success": True,
        "data": kwargs,
    }, f"已创建 {obj_type.label_zh}: {kwargs['id']}")


@tool
def update_entity(entity_type: str, entity_id: str, **kwargs) -> str:
    """更新任意实体。"""
    registry = _get_registry()
    obj_type = registry.object_types.get(entity_type)
    if not obj_type:
        return f"未知实体类型: {entity_type}"

    file_path = f"{_parser().data_dir}/{obj_type.storage_file}"
    data = _load_json(file_path)

    for i, item in enumerate(data):
        if item.get('id') == entity_id:
            data[i] = {**item, **kwargs}
            _save_json(file_path, data)
            return _wrap({
                "type": "update_result",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "success": True,
                "updated_fields": kwargs,
            }, f"已更新 {obj_type.label_zh} {entity_id}")

    return _wrap({
        "type": "update_result",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "success": False,
        "error": f"未找到 {entity_type}: {entity_id}",
    }, f"未找到 {entity_type}: {entity_id}")


@tool
def traverse_relation(source_type: str, source_id: str, relation: str) -> str:
    """遍历实体关系。"""
    registry = _get_registry()
    link = registry.link_types.get(relation)
    if not link:
        return f"未知关系: {relation}。可选: {', '.join(registry.link_types.keys())}"
    if link.domain != source_type:
        return f"关系 {relation} 的起点是 {link.domain}，不是 {source_type}"

    src_type = registry.object_types.get(source_type)
    if not src_type:
        return f"未知实体类型: {source_type}"

    src_data = _load_json(f"{_parser().data_dir}/{src_type.storage_file}")
    source = next((d for d in src_data if d.get('id') == source_id), None)
    if not source:
        return f"未找到 {source_type}: {source_id}"

    via_value = source.get(link.via, '')
    target_type = registry.object_types.get(link.range)
    if not target_type:
        return f"未知目标实体类型: {link.range}"

    target_data = _load_json(f"{_parser().data_dir}/{target_type.storage_file}")
    targets = [d for d in target_data if d.get(link.via) == via_value] if via_value else []

    if not targets:
        return _wrap({
            "type": "relation_result",
            "source_type": source_type,
            "source_id": source_id,
            "relation": relation,
            "relation_label": link.label_zh,
            "total": 0,
            "targets": [],
        }, f"未找到 {link.label_zh} 关系")

    return _wrap({
        "type": "relation_result",
        "source_type": source_type,
        "source_id": source_id,
        "source_name": source.get('name', source_id),
        "relation": relation,
        "relation_label": link.label_zh,
        "target_type": link.range,
        "total": len(targets),
        "targets": [{"id": t.get('id', ''), "name": t.get('name', t.get('id', ''))} for t in targets],
    }, f"找到 {link.label_zh} 关系，共 {len(targets)} 条，详见右侧卡片。")


# ============ 通用 Action Tools ============

@tool
def execute_action(action_type: str, target_id: str, store_id: str,
                   discount: Optional[int] = None, quantity: Optional[int] = None,
                   from_store: Optional[str] = None, to_store: Optional[str] = None,
                   supplier_id: Optional[str] = None, notes: Optional[str] = None) -> str:
    """执行操作（预览模式）。调用后返回预览，用户确认后调用 confirm_action。"""
    try:
        at = ActionType(action_type)
    except ValueError:
        return f"未知操作类型: {action_type}。可选: {[a.value for a in ActionType]}"

    registry = _get_registry()
    action_def = registry.action_types.get(action_type)
    if not action_def:
        return f"操作类型 {action_type} 未在本体中定义"

    target_obj = registry.object_types.get(action_def.output_type)
    target_data = _load_json(f"{_parser().data_dir}/{target_obj.storage_file}")
    target = next((d for d in target_data if d.get('id') == target_id), None)
    if not target:
        return _wrap({
            "type": "action_preview",
            "action_type": action_type,
            "target_id": target_id,
            "store_id": store_id,
            "valid": False,
            "error": f"操作目标不存在: {target_id}",
        }, f"操作目标不存在: {target_id}")

    if at == ActionType.CLEARANCE:
        if target.get('status') == 'expired':
            return _wrap({
                "type": "action_preview",
                "action_type": action_type,
                "target_id": target_id,
                "store_id": store_id,
                "valid": False,
                "error": "商品已过期，无法创建出清任务",
            }, "错误：商品已过期，无法创建出清任务")
        if discount is None:
            return _wrap({
                "type": "action_preview",
                "action_type": action_type,
                "target_id": target_id,
                "store_id": store_id,
                "valid": False,
                "error": "请提供 discount 参数（折扣百分比 0-100）",
            }, "请提供 discount 参数（折扣百分比 0-100）")
        if discount < 0 or discount > 100:
            return _wrap({
                "type": "action_preview",
                "action_type": action_type,
                "store_id": store_id,
                "valid": False,
                "error": f"折扣必须在 0-100 之间",
            }, f"折扣必须在 0-100 之间，当前: {discount}")

    params = {}
    if discount is not None:
        params["discount"] = discount
    if quantity is not None:
        params["quantity"] = quantity
    if from_store is not None:
        params["from_store"] = from_store
    if to_store is not None:
        params["to_store"] = to_store
    if supplier_id is not None:
        params["supplier_id"] = supplier_id
    if notes:
        params["notes"] = notes

    store_data = _load_json(f"{_parser().data_dir}/stores.json")
    store = next((s for s in store_data if s.get('id') == store_id), None)
    assignee_id = store.get('manager_id', '') if store else ''
    store_name = store.get('name', store_id) if store else store_id

    target_name = target.get('name', target_id)

    return _wrap({
        "type": "action_preview",
        "action_type": action_type,
        "action_label": action_def.label_zh,
        "target_id": target_id,
        "target_name": target_name,
        "store_id": store_id,
        "store_name": store_name,
        "assignee_id": assignee_id,
        "params": params,
        "valid": True,
    }, f"操作预览已生成，请确认是否执行 {action_def.label_zh}（{target_name}），详见右侧卡片。")


@tool
def confirm_action(action_type: str, target_id: str, store_id: str,
                   discount: Optional[int] = None, quantity: Optional[int] = None,
                   from_store: Optional[str] = None, to_store: Optional[str] = None,
                   supplier_id: Optional[str] = None, notes: Optional[str] = None) -> str:
    """用户确认后，实际执行操作并创建任务记录。"""
    try:
        at = ActionType(action_type)
    except ValueError:
        return f"未知操作类型: {action_type}"

    registry = _get_registry()
    action_def = registry.action_types.get(action_type)
    if not action_def:
        return f"操作类型 {action_type} 未在本体中定义"

    target_obj = registry.object_types.get(action_def.output_type)
    target_data = _load_json(f"{_parser().data_dir}/{target_obj.storage_file}")
    target = next((d for d in target_data if d.get('id') == target_id), None)
    if not target:
        return _wrap({
            "type": "action_result",
            "action_type": action_type,
            "target_id": target_id,
            "store_id": store_id,
            "success": False,
            "error": f"操作目标不存在: {target_id}",
        }, f"操作目标不存在: {target_id}")

    if at == ActionType.CLEARANCE and target.get('status') == 'expired':
        return _wrap({
            "type": "action_result",
            "action_type": action_type,
            "target_id": target_id,
            "store_id": store_id,
            "success": False,
            "error": "商品已过期，无法执行",
        }, "错误：商品已过期，无法执行")

    params = {}
    if discount is not None:
        params["discount"] = discount
    if quantity is not None:
        params["quantity"] = quantity
    if from_store is not None:
        params["from_store"] = from_store
    if to_store is not None:
        params["to_store"] = to_store
    if supplier_id is not None:
        params["supplier_id"] = supplier_id
    if notes:
        params["notes"] = notes

    store_data = _load_json(f"{_parser().data_dir}/stores.json")
    store = next((s for s in store_data if s.get('id') == store_id), None)
    assignee_id = store.get('manager_id', '') if store else ''

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "type": action_type,
        "target_id": target_id,
        "store_id": store_id,
        "assignee_id": assignee_id,
        "status": "pending",
        "params_json": params,
        "result_json": {},
        "priority": "medium",
        "notes": notes or "",
        "created_at": datetime.now().isoformat(),
    }

    tasks_path = f"{_parser().data_dir}/tasks.json"
    tasks = _load_json(tasks_path)
    tasks.append(task)
    _save_json(tasks_path, tasks)

    return _wrap({
        "type": "action_result",
        "action_type": action_type,
        "action_label": action_def.label_zh,
        "target_id": target_id,
        "target_name": target.get('name', target_id),
        "store_id": store_id,
        "params": params,
        "success": True,
        "task_id": task_id,
        "task": task,
    }, f"✅ 操作已创建！任务ID: {task_id}，详见右侧卡片。")


@tool
def query_task(action_type: Optional[str] = None, store_id: Optional[str] = None,
               status: Optional[str] = None) -> str:
    """查询任务记录。"""
    tasks_path = f"{_parser().data_dir}/tasks.json"
    tasks = _load_json(tasks_path)

    for t in tasks:
        t.setdefault('type', t.pop('action_type', None))
        t.setdefault('target_id', t.pop('near_expiry_product_id', None))
        t.setdefault('params_json', t.pop('input_params', {}))

    if action_type:
        tasks = [t for t in tasks if t.get('type') == action_type]
    if store_id:
        tasks = [t for t in tasks if t.get('store_id') == store_id]
    if status:
        tasks = [t for t in tasks if t.get('status') == status]

    if not tasks:
        return _wrap({
            "type": "task_list",
            "total": 0,
            "items": [],
        }, "未找到任务记录。")

    status_colors = {"pending": "#f59e0b", "completed": "#22c55e", "failed": "#ef4444"}
    status_labels = {"pending": "待处理", "completed": "已完成", "failed": "已失败"}

    items = []
    for t in tasks[:20]:
        params = t.get('params_json', {})
        discount = params.get('discount')
        if discount and isinstance(discount, float):
            discount = int(discount * 100)
        items.append({
            "id": t.get('id', ''),
            "type": t.get('type', 'unknown'),
            "target_id": t.get('target_id', ''),
            "store_id": t.get('store_id', ''),
            "status": t.get('status', '-'),
            "status_label": status_labels.get(t.get('status', ''), t.get('status', '-')),
            "status_color": status_colors.get(t.get('status', ''), '#94a3b8'),
            "priority": t.get('priority', 'medium'),
            "discount": discount,
            "params": params,
            "created_at": t.get('created_at', ''),
        })

    return _wrap({
        "type": "task_list",
        "total": len(tasks),
        "has_more": len(tasks) > 20,
        "items": items,
    }, f"查询到 {len(items)} 条任务记录，详见右侧卡片。")


@tool
def update_task(task_id: str, **kwargs) -> str:
    """修改任务记录。"""
    tasks_path = f"{_parser().data_dir}/tasks.json"
    tasks = _load_json(tasks_path)

    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = {**t, **kwargs}
            _save_json(tasks_path, tasks)
            return _wrap({
                "type": "update_task_result",
                "task_id": task_id,
                "success": True,
                "updated_fields": kwargs,
            }, f"已更新任务 {task_id}")

    return _wrap({
        "type": "update_task_result",
        "task_id": task_id,
        "success": False,
        "error": f"未找到任务: {task_id}",
    }, f"未找到任务: {task_id}")


# ============ 业务专用查询（不涉及 Action）============

@tool
def query_near_expiry(store_id: Optional[str] = None) -> str:
    """查询临期商品列表。"""
    nep_data = _load_json(f"{_parser().data_dir}/near_expiry_products.json")

    if store_id:
        nep_data = [n for n in nep_data if n.get('store_id') == store_id]

    if not nep_data:
        return _wrap({
            "type": "near_expiry_list",
            "store_id": store_id or "all",
            "total": 0,
            "items": [],
        }, f"门店 {store_id or '全部'} 暂无临期商品。")

    prod_data = _load_json(f"{_parser().data_dir}/products.json")
    prod_map = {p['id']: p for p in prod_data}

    tier_discount = {"T1": 60, "T2": 40, "T3": 20}
    tier_colors = {"T1": "#ef4444", "T2": "#f59e0b", "T3": "#3b82f6"}
    tier_labels = {"T1": "紧急处理", "T2": "尽快出清", "T3": "关注中"}

    items = []
    for nep in nep_data[:20]:
        pid = nep.get('product_id', '')
        prod = prod_map.get(pid, {})
        tier = nep.get('discount_tier', 'T3')
        discount = tier_discount.get(tier, 20)
        original_price = prod.get('retail_price', 0)
        discounted_price = round(original_price * (100 - discount) / 100, 2)
        days = nep.get('days_left', 0)

        if days <= 3:
            urgency_color = "#ef4444"
        elif days <= 7:
            urgency_color = "#f59e0b"
        else:
            urgency_color = "#22c55e"

        items.append({
            "id": nep.get('id', ''),
            "product_id": pid,
            "product_name": prod.get('name', pid),
            "category": prod.get('category', ''),
            "brand": prod.get('brand', ''),
            "unit": prod.get('unit', ''),
            "store_id": nep.get('store_id', ''),
            "batch_no": nep.get('batch_no', ''),
            "production_date": nep.get('production_date', ''),
            "expiry_date": nep.get('expiry_date', ''),
            "stock_quantity": nep.get('stock_quantity', 0),
            "days_left": days,
            "discount_tier": tier,
            "discount_percent": discount,
            "tier_label": tier_labels.get(tier, tier),
            "tier_color": tier_colors.get(tier, "#94a3b8"),
            "urgency_color": urgency_color,
            "original_price": original_price,
            "discounted_price": discounted_price,
            "status": nep.get('status', ''),
        })

    return _wrap({
        "type": "near_expiry_list",
        "store_id": store_id or "all",
        "total": len(items),
        "items": items,
    }, f"已查询到 {len(items)} 条临期商品，详见右侧卡片。")


def get_registry():
    return _get_registry()
