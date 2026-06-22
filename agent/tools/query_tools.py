"""系统原子 Tool —— 通用查询（读工具）。

走 Repository 读，不做写操作。与业务无关，对所有 workspace 通用。
helper 通过 shared 模块引用（非直接 import），便于测试 monkeypatch。

v2（WP5 接入收尾）：query_entity / traverse_relation 调 PermissionEvaluator
做 Object 级读校验 + 属性级 mask + 不可读字段文本提示（不静默裁剪）。
"""
from typing import Optional

from langchain_core.tools import tool

from agent.tools import shared


@tool
def query_entity(entity_type: str, entity_id: Optional[str] = None,
                 filter_field: Optional[str] = None,
                 filter_value: Optional[str] = None,
                 workspace_name: str = None,
                 org_unit_id: str = None) -> str:
    """通用实体查询。entity_type: Store/Employee/Product/NearExpiryProduct/Task/LossReport。
    workspace_name + org_unit_id 决定可见范围。
    """
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    if not shared._parser().registry.object_types.get(entity_type):
        return f"未知实体类型: {entity_type}"

    # v2 权限：Object 级读校验（actor 从 auth_ctx 派生）
    actor = shared._get_actor(tc)
    evaluator = shared._get_evaluator()
    obj_result = evaluator.can_read_object(actor.get("role", ""), entity_type)
    if not obj_result.granted:
        return shared._wrap(
            {"type": "entity_list", "total": 0, "items": [],
             "permission_denied": True, "reason": obj_result.reason},
            f"无权访问 {entity_type}：{obj_result.reason}")

    # 属性级 mask：从返回中隐去不可读字段，文本提示哪些字段被 mask
    denied_props = evaluator.denied_properties(actor.get("role", ""), entity_type)

    filters = {filter_field: filter_value} if filter_field else None
    rows = shared._get_repo(tc).read(entity_type, tc, filters=filters)
    if entity_id:
        rows = [r for r in rows if r.get("id") == entity_id]
    if not rows:
        return shared._wrap({"type": "entity_list", "total": 0, "items": []}, "未找到记录。")

    # mask 不可读属性
    masked_rows = []
    for r in rows[:20]:
        if denied_props:
            masked = {k: v for k, v in r.items() if k not in denied_props}
            masked_rows.append(masked)
        else:
            masked_rows.append(r)

    summary = f"查询到 {len(rows)} 条记录。"
    if denied_props:
        summary += f" 以下字段无权访问已隐去：{', '.join(sorted(denied_props))}"

    return shared._wrap({"type": "entity_list", "entity_type": entity_type,
                         "total": len(rows), "items": masked_rows,
                         "masked_fields": sorted(denied_props) if denied_props else []},
                        summary)


@tool
def traverse_relation(source_type: str, source_id: str, relation: str,
                      workspace_name: str = None,
                      org_unit_id: str = None) -> str:
    """遍历实体关系。"""
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    link = shared._parser().registry.link_types.get(relation)
    if not link:
        return f"未知关系: {relation}"

    # v2 权限：Link 级遍历校验
    actor = shared._get_actor(tc)
    evaluator = shared._get_evaluator()
    link_result = evaluator.can_traverse_link(actor.get("role", ""), relation)
    if not link_result.granted:
        return shared._wrap(
            {"type": "relation_result", "total": 0, "targets": [],
             "permission_denied": True, "reason": link_result.reason},
            f"无权遍历 {relation}：{link_result.reason}")

    repo = shared._get_repo(tc)
    src = repo.read_one(source_type, tc, source_id)
    if not src:
        return f"未找到 {source_type}: {source_id}"
    via_val = src.get(link.via, "")
    targets = [r for r in repo.read(link.range, tc) if r.get(link.via) == via_val]
    return shared._wrap({"type": "relation_result", "relation": relation,
                         "total": len(targets), "targets": targets[:20]},
                        f"找到 {len(targets)} 条 {link.label_zh} 关系。")


@tool
def query_task(status: Optional[str] = None, store_id: Optional[str] = None,
               workspace_name: str = None,
               org_unit_id: str = None) -> str:
    """查询任务记录。"""
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    # v2 权限：Task 级读校验
    actor = shared._get_actor(tc)
    evaluator = shared._get_evaluator()
    obj_result = evaluator.can_read_object(actor.get("role", ""), "Task")
    if not obj_result.granted:
        return shared._wrap(
            {"type": "task_list", "total": 0, "items": [],
             "permission_denied": True, "reason": obj_result.reason},
            f"无权访问 Task：{obj_result.reason}")
    rows = shared._get_repo(tc).read("Task", tc)
    if status:
        rows = [t for t in rows if t.get("status") == status]
    if store_id:
        rows = [t for t in rows if t.get("store_id") == store_id]
    return shared._wrap({"type": "task_list", "total": len(rows), "items": rows[:20]},
                        f"查询到 {len(rows)} 条任务。")


TOOLS = [query_entity, traverse_relation, query_task]
