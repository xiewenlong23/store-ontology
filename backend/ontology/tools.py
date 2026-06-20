"""本体驱动工具 —— 薄封装层。
读工具走 Repository；execute_action(preview)/confirm_action 走 ActionExecutor + PreviewCache。
所有 @tool 仅做参数编排与结果包装，业务逻辑在 Executor/Repository（见架构 spec §1.2 第6点）。"""

import json
import uuid
from typing import Optional, Any

from langchain_core.tools import tool

from ontology.parser import get_ontology_parser
from ontology.repository import JSONFileRepository
from ontology.executor import ActionExecutor
from ontology.preview_cache import PreviewCache
from ontology.errors import OntologyError


# ============ 依赖装配（按 vertical+tenant 构造；测试用 monkeypatch 替换）============

_preview_cache = PreviewCache(ttl_seconds=300)


def _parser(vertical: str = None):
    """获取某 vertical 的 parser。不传则取默认 vertical。"""
    return get_ontology_parser(vertical)


def _get_repo(tenant: str = "tenant_default", vertical: str = None) -> JSONFileRepository:
    p = _parser(vertical)
    return JSONFileRepository(data_dir=str(p.data_dir), registry=p.registry)


def _get_executor(vertical: str = None) -> ActionExecutor:
    p = _parser(vertical)
    repo = _get_repo(vertical=vertical)
    return ActionExecutor(repository=repo, actions=p.registry.action_types,
                          registry=p.registry, config=p.config)


def build_ontology_prompt(vertical: str = None) -> str:
    p = _parser(vertical)
    intro = p.config.system_prompt_intro if p.config else ""
    return p.build_system_prompt(intro)


def _wrap(data: dict, summary: str) -> str:
    return f"{summary}\n<!--COPILOTKIT_DATA-->\n{json.dumps(data, ensure_ascii=False)}\n<!--/COPILOTKIT_DATA-->"


# ============ 读工具 ============

@tool
def query_entity(entity_type: str, entity_id: Optional[str] = None,
                 filter_field: Optional[str] = None,
                 filter_value: Optional[str] = None,
                 tenant_id: str = "tenant_default") -> str:
    """通用实体查询。entity_type: Store/Employee/Product/NearExpiryProduct/Task/LossReport。"""
    if not _parser().registry.object_types.get(entity_type):
        return f"未知实体类型: {entity_type}"
    filters = {filter_field: filter_value} if filter_field else None
    rows = _get_repo(tenant_id).read(entity_type, tenant_id, filters=filters)
    if entity_id:
        rows = [r for r in rows if r.get("id") == entity_id]
    if not rows:
        return _wrap({"type": "entity_list", "total": 0, "items": []}, "未找到记录。")
    return _wrap({"type": "entity_list", "entity_type": entity_type,
                  "total": len(rows), "items": rows[:20]}, f"查询到 {len(rows)} 条记录。")


@tool
def traverse_relation(source_type: str, source_id: str, relation: str,
                      tenant_id: str = "tenant_default") -> str:
    """遍历实体关系。"""
    link = _parser().registry.link_types.get(relation)
    if not link:
        return f"未知关系: {relation}"
    repo = _get_repo(tenant_id)
    src = repo.read_one(source_type, tenant_id, source_id)
    if not src:
        return f"未找到 {source_type}: {source_id}"
    via_val = src.get(link.via, "")
    targets = [r for r in repo.read(link.range, tenant_id) if r.get(link.via) == via_val]
    return _wrap({"type": "relation_result", "relation": relation,
                  "total": len(targets), "targets": targets[:20]},
                 f"找到 {len(targets)} 条 {link.label_zh} 关系。")


@tool
def query_task(status: Optional[str] = None, store_id: Optional[str] = None,
               tenant_id: str = "tenant_default") -> str:
    """查询任务记录。"""
    rows = _get_repo(tenant_id).read("Task", tenant_id)
    if status:
        rows = [t for t in rows if t.get("status") == status]
    if store_id:
        rows = [t for t in rows if t.get("store_id") == store_id]
    return _wrap({"type": "task_list", "total": len(rows), "items": rows[:20]},
                 f"查询到 {len(rows)} 条任务。")


# clearance 专属工具已下沉到 verticals/clearance/tools.py。
# 此处保留 re-export 仅作向后兼容（main.py / 旧测试过渡期）；Batch 3 后 main.py 改为注册表聚合。
try:
    from verticals.clearance.tools import query_near_expiry  # noqa: F401
except ImportError:
    query_near_expiry = None  # clearance vertical 未安装时优雅降级


# ============ 写工具（降级 CRUD）============

@tool
def create_entity(entity_type: str, tenant_id: str = "tenant_default", **kwargs: Any) -> str:
    """通用创建（仅限非业务数据；受治理实体会被 Repository 拒绝）。"""
    kwargs.setdefault("id", f"{entity_type.lower()}_{uuid.uuid4().hex[:8]}")
    try:
        rec = _get_repo(tenant_id).write(entity_type, tenant_id, kwargs, create=True)
        return _wrap({"type": "create_result", "success": True, "data": rec},
                     f"已创建 {entity_type}: {kwargs['id']}")
    except OntologyError as e:
        return _wrap({"type": "create_result", "success": False, "error": str(e)},
                     f"创建失败: {e}")


@tool
def update_entity(entity_type: str, entity_id: str,
                  tenant_id: str = "tenant_default", **kwargs) -> str:
    """通用更新（仅限非业务数据；受治理实体会被 Repository 拒绝）。"""
    repo = _get_repo(tenant_id)
    rec = repo.read_one(entity_type, tenant_id, entity_id)
    if not rec:
        return _wrap({"type": "update_result", "success": False, "error": "未找到"},
                     f"未找到 {entity_type}: {entity_id}")
    rec.update(kwargs)
    try:
        repo.write(entity_type, tenant_id, rec)
        return _wrap({"type": "update_result", "success": True}, "已更新。")
    except OntologyError as e:
        return _wrap({"type": "update_result", "success": False, "error": str(e)},
                     f"更新失败: {e}")


@tool
def update_task(task_id: str, tenant_id: str = "tenant_default", **kwargs) -> str:
    """任务更新（受治理实体，仅允许改 notes 等非业务字段；status 走 Action）。

    Task 标记为 edits-only-via-actions。本工具仅放行白名单字段（notes/priority），
    其它业务字段（discount_percent/planned_quantity/sold_quantity/assignee_id 等）
    必须经对应 Action 修改，避免绕过治理。
    """
    ALLOWED = {"notes", "priority"}
    forbidden = set(kwargs) - ALLOWED
    if "status" in kwargs or forbidden:
        return _wrap({"type": "update_task_result", "success": False,
                      "error": f"受治理字段只能经 Action 修改，本工具仅允许: {sorted(ALLOWED)}"},
                     "受治理字段请走对应 Action。")
    repo = _get_repo(tenant_id)
    rec = repo.read_one("Task", tenant_id, task_id)
    if not rec:
        return _wrap({"type": "update_task_result", "success": False}, "未找到任务。")
    rec.update(kwargs)
    try:
        repo.write("Task", tenant_id, rec, bypass_action_check=True)
        return _wrap({"type": "update_task_result", "success": True}, "已更新任务。")
    except OntologyError as e:
        return _wrap({"type": "update_task_result", "success": False, "error": str(e)},
                     f"更新失败: {e}")


# ============ Action 工具（Preview -> Confirm）============

@tool
def execute_action(action_type: str, params: dict,
                   actor_role: str = "store_manager",
                   tenant_id: str = "tenant_default") -> str:
    """执行 Action 预览。返回 preview_id，用户确认后用 confirm_action(preview_id) 提交。

    params 是该 Action 的参数字典，具体参数名见系统提示中的 Action 清单。
    例如 create_clearance_task 的 params: {"target_id":"...", "store_id":"...",
    "assignee_id":"...", "discount_percent":30, "planned_quantity":50}
    """
    ex = _get_executor()
    actions = ex.actions
    if action_type not in actions:
        return _wrap({"type": "action_preview", "valid": False,
                      "error": f"未知 Action: {action_type}，可用: {list(actions.keys())}"},
                     f"未知操作: {action_type}")
    if not isinstance(params, dict):
        params = params or {}
    # 预览阶段就校验参数：错误参数名/缺必填/约束不满足立即报错，
    # 不进缓存、不等到 confirm 才失败（避免 LLM 重试死循环）。
    try:
        validated = ex.validate(action_type, params)
    except OntologyError as e:
        action = actions[action_type]
        required = [p["name"] for p in action.parameters if p.get("required")]
        return _wrap({"type": "action_preview", "valid": False,
                      "error": str(e),
                      "required_params": required},
                     f"预览失败: {e}。该 Action 必填参数: {required}")
    preview = {"action_type": action_type, "params": validated,
               "actor_role": actor_role, "tenant_id": tenant_id}
    preview_id = _preview_cache.put(preview)
    return _wrap({"type": "action_preview", "valid": True, "preview_id": preview_id,
                  "action_type": action_type, "params": validated},
                 f"预览已生成，preview_id={preview_id}，确认请调 confirm_action。")


@tool
def confirm_action(preview_id: str) -> str:
    """凭 preview_id 执行已预览的 Action（架构 spec §1.6 治理闭环）。"""
    preview = _preview_cache.get(preview_id)
    if not preview:
        return _wrap({"type": "action_result", "success": False,
                      "error": "preview 无效或已过期，请先 execute_action"},
                     "preview 无效或已过期，请重新预览。")
    try:
        result = _get_executor().execute(
            preview["action_type"], preview["params"],
            actor={"role": preview["actor_role"]},
            tenant_id=preview["tenant_id"])
        return _wrap({"type": "action_result", "success": True, **result},
                     f"操作完成: {preview['action_type']}")
    except OntologyError as e:
        return _wrap({"type": "action_result", "success": False, "error": str(e)},
                     f"操作失败: {e}")
