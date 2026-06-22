"""系统原子 Tool —— 通用 CRUD（写工具，降级直写）。

仅限非业务数据；受治理实体（edits_only_via_actions）会被 Repository 拒绝。
update_task 是例外：仅放行白名单字段（notes/priority），经 update_task_notes Action 执行。
helper 通过 shared 模块引用（非直接 import），便于测试 monkeypatch。

v2（WP5 接入收尾）：create/update_entity 调 PermissionEvaluator 做 tool 级 +
Object 写权限校验（manifest 默认锁 system_admin）。
"""
import uuid
from typing import Any

from langchain_core.tools import tool

from agent.tools import shared
from engine.errors import OntologyError


@tool
def create_entity(entity_type: str,
                  workspace_name: str = None,
                  org_unit_id: str = None, **kwargs: Any) -> str:
    """通用创建（仅限非业务数据；受治理实体会被 Repository 拒绝）。"""
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    # v2 权限：tool 级 + Object 写校验
    actor = shared._get_actor(tc)
    evaluator = shared._get_evaluator()
    role = actor.get("role", "")
    tool_r = evaluator.can_use_tool(role, "create_entity")
    if not tool_r.granted:
        return shared._wrap({"type": "create_result", "success": False,
                             "permission_denied": True, "reason": tool_r.reason},
                            f"无权使用 create_entity：{tool_r.reason}")
    obj_r = evaluator.can_write_object(role, entity_type)
    if not obj_r.granted:
        return shared._wrap({"type": "create_result", "success": False,
                             "permission_denied": True, "reason": obj_r.reason},
                            f"无权创建 {entity_type}：{obj_r.reason}")
    kwargs.setdefault("id", f"{entity_type.lower()}_{uuid.uuid4().hex[:8]}")
    try:
        rec = shared._get_repo(tc).write(entity_type, tc, kwargs, create=True)
        return shared._wrap({"type": "create_result", "success": True, "data": rec},
                            f"已创建 {entity_type}: {kwargs['id']}")
    except OntologyError as e:
        return shared._wrap({"type": "create_result", "success": False, "error": str(e)},
                            f"创建失败: {e}")


@tool
def update_entity(entity_type: str, entity_id: str,
                  workspace_name: str = None,
                  org_unit_id: str = None, **kwargs) -> str:
    """通用更新（仅限非业务数据；受治理实体会被 Repository 拒绝）。"""
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    # v2 权限：tool 级 + Object 写校验
    actor = shared._get_actor(tc)
    evaluator = shared._get_evaluator()
    role = actor.get("role", "")
    tool_r = evaluator.can_use_tool(role, "update_entity")
    if not tool_r.granted:
        return shared._wrap({"type": "update_result", "success": False,
                             "permission_denied": True, "reason": tool_r.reason},
                            f"无权使用 update_entity：{tool_r.reason}")
    obj_r = evaluator.can_write_object(role, entity_type)
    if not obj_r.granted:
        return shared._wrap({"type": "update_result", "success": False,
                             "permission_denied": True, "reason": obj_r.reason},
                            f"无权更新 {entity_type}：{obj_r.reason}")
    # v2 权限：属性级写校验（kwargs 里的字段逐个 check）
    for field_name in kwargs:
        prop_r = evaluator.can_write_property(role, entity_type, field_name)
        if not prop_r.granted:
            return shared._wrap({"type": "update_result", "success": False,
                                 "permission_denied": True,
                                 "reason": prop_r.reason,
                                 "denied_field": field_name},
                                f"无权更新字段 {entity_type}.{field_name}：{prop_r.reason}")
    repo = shared._get_repo(tc)
    rec = repo.read_one(entity_type, tc, entity_id)
    if not rec:
        return shared._wrap({"type": "update_result", "success": False, "error": "未找到"},
                            f"未找到 {entity_type}: {entity_id}")
    rec.update(kwargs)
    try:
        repo.write(entity_type, tc, rec)
        return shared._wrap({"type": "update_result", "success": True}, "已更新。")
    except OntologyError as e:
        return shared._wrap({"type": "update_result", "success": False, "error": str(e)},
                            f"更新失败: {e}")


@tool
def update_task(task_id: str, notes: str = None, priority: str = None,
                workspace_name: str = None,
                org_unit_id: str = None) -> str:
    """任务更新（受治理实体，仅允许改 notes/priority，走受治理的 update_task_notes Action）。

    Task 标记为 edits-only-via-actions。本工具仅放行白名单字段（notes/priority），
    经 update_task_notes Action 执行；其它业务字段
    （discount_percent/planned_quantity/sold_quantity/assignee_id/status 等）
    必须经各自对应的 Action 修改。
    """
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    actor = shared._get_actor(tc)
    # v2 权限：tool 级校验（manifest 默认锁 system_admin；可由 workspace 覆盖）
    evaluator = shared._get_evaluator()
    role = actor.get("role", "")
    tool_r = evaluator.can_use_tool(role, "update_task")
    if not tool_r.granted:
        return shared._wrap({"type": "update_task_result", "success": False,
                             "permission_denied": True, "reason": tool_r.reason},
                            f"无权使用 update_task：{tool_r.reason}")
    params = {"task_id": task_id}
    if notes is not None:
        params["notes"] = notes
    if priority is not None:
        params["priority"] = priority
    try:
        result = shared._get_executor().execute(
            "update_task_notes", params,
            actor=actor,
            tenant_id=tc)
        return shared._wrap({"type": "update_task_result", "success": True, **result},
                            "已更新任务。")
    except OntologyError as e:
        return shared._wrap({"type": "update_task_result", "success": False, "error": str(e)},
                            f"更新失败: {e}")


TOOLS = [create_entity, update_entity, update_task]
