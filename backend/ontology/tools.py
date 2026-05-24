"""
通用 CRUD 工具 — 基于本体语义定义，动态支持所有实体类型的增删改查。
"""
import json
from typing import Optional, Any
from langchain_core.tools import tool
from ontology.parser import OntologyParser


_parser = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
_registry = _parser.registry


def _load_json(file_path: str) -> list:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_json(file_path: str, data: list):
    import os
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


@tool
def query_entity(entity_type: str, entity_id: str = None, store_id: str = None,
                 filter_field: str = None, filter_value: str = None) -> str:
    """通用实体查询 — 根据本体定义查询任意实体类型。
    Args:
        entity_type: 实体类型名，如 Store,Employee,Product,NearExpiryProduct,DiscountRule,ClearanceTask
        entity_id: 实体ID（可选）
        store_id: 门店ID过滤（可选）
        filter_field: 自定义过滤字段（可选）
        filter_value: 自定义过滤值（可选）
    """
    obj_type = _registry.object_types.get(entity_type)
    if not obj_type:
        return f"未知实体类型: {entity_type}。可选: {', '.join(_registry.object_types.keys())}"

    data = _load_json(f"{_parser.data_dir}/{obj_type.storage_file}")

    if entity_id:
        match = next((d for d in data if d.get('id') == entity_id), None)
        return f"未找到 {entity_type}: {entity_id}" if not match else \
               json.dumps(match, ensure_ascii=False, default=str, indent=2)

    if store_id:
        data = [d for d in data if d.get('store_id') == store_id]
    elif filter_field and filter_value is not None:
        data = [d for d in data if str(d.get(filter_field, '')) == str(filter_value)]

    if not data:
        return f"未找到 {entity_type} 记录"

    lines = [f"📊 {obj_type.label} ({entity_type}) — {len(data)} 条记录"]
    for item in data:
        key_vals = [f"{p.name}={item.get(p.name, '')}" for p in obj_type.properties[:4] if item.get(p.name)]
        lines.append("  • " + " | ".join(key_vals))
    return "\n".join(lines)


@tool
def create_entity(entity_type: str, name: str = "", **kwargs: Any) -> str:
    """通用实体创建。
    Args:
        entity_type: 实体类型名
        name: 实体名称
    """
    obj_type = _registry.object_types.get(entity_type)
    if not obj_type:
        return f"未知实体类型: {entity_type}"

    import uuid
    kwargs.setdefault("id", f"{entity_type.lower()}_{uuid.uuid4().hex[:8]}")
    if name:
        kwargs["name"] = name

    file_path = f"{_parser.data_dir}/{obj_type.storage_file}"
    data = _load_json(file_path)
    data.append(kwargs)
    _save_json(file_path, data)
    return f"✅ 已创建 {obj_type.label_zh}: {kwargs['id']}"


@tool
def traverse_relation(source_type: str, source_id: str, relation: str) -> str:
    """遍历实体关系。
    Args:
        source_type: 源实体类型
        source_id: 源实体ID
        relation: 关系名（has_employee, has_near_expiry, located_in, is_instance_of, manages, has_task）
    """
    link = _registry.link_types.get(relation)
    if not link:
        return f"未知关系: {relation}。可选: {', '.join(_registry.link_types.keys())}"
    if link.domain != source_type:
        return f"关系 {relation} 的起点是 {link.domain}，不是 {source_type}"

    src_type = _registry.object_types.get(source_type)
    if not src_type:
        return f"未知实体类型: {source_type}"

    src_data = _load_json(f"{_parser.data_dir}/{src_type.storage_file}")
    source = next((d for d in src_data if d.get('id') == source_id), None)
    if not source:
        return f"未找到 {source_type}: {source_id}"

    via_value = source.get(link.via, '')
    target_type = _registry.object_types.get(link.range)
    if not target_type:
        return f"未知目标实体类型: {link.range}"

    target_data = _load_json(f"{_parser.data_dir}/{target_type.storage_file}")
    targets = [d for d in target_data if d.get(link.via) == via_value] if via_value else []

    if not targets:
        return f"未找到 {link.label_zh}: {source_type}.{source_id} → {link.range}"

    lines = [f"🔗 {link.label_zh}: {source_type}({source_id}) → {link.range} ({len(targets)} 条)"]
    for t in targets:
        lines.append(f"  • {t.get('id', '')}: {t.get('name', str(t))}")
    return "\n".join(lines)


def get_registry():
    return _registry


def build_ontology_prompt() -> str:
    return _parser.build_system_prompt()


@tool
def update_entity(entity_type: str, entity_id: str, **kwargs) -> str:
    """更新任意实体（通用修改工具）。
    根据实体ID更新指定字段。只传入需要修改的字段。
    Args:
        entity_type: 实体类型名
        entity_id: 实体ID
        **kwargs: 要更新的字段名和值（如 discount=20, quantity=50）
    """
    obj_type = _registry.object_types.get(entity_type)
    if not obj_type:
        return f"未知实体类型: {entity_type}"

    file_path = f"{_parser.data_dir}/{obj_type.storage_file}"
    data = _load_json(file_path)

    for i, item in enumerate(data):
        if item.get('id') == entity_id:
            data[i] = {**item, **kwargs}
            _save_json(file_path, data)
            updated = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"✅ 已更新 {obj_type.label_zh} {entity_id}: {updated}"
    
    return f"未找到 {entity_type}: {entity_id}"
