"""系统原子 Tool —— Action 治理管道（Preview -> Confirm）。

execute_action 生成预览（校验参数、返回 preview_id），confirm_action 凭 preview_id 执行。
这是受治理写操作的统一入口（架构 spec §1.6 治理闭环），与具体 Action 定义无关——
Action Type 由各 workspace 的 ontology 声明，本工具只负责调用管道。
helper 通过 shared 模块引用（非直接 import），便于测试 monkeypatch。

v2（WP6 信任修复）：actor 一律从 auth_ctx contextvar 派生（shared._get_actor），
LLM 不再能自报 actor_role。未登录用户的 actor.role="anonymous"，多数业务资源拒绝。
"""
from langchain_core.tools import tool

from agent.tools import shared
from engine.errors import OntologyError


@tool
def execute_action(action_type: str, params: dict,
                   workspace_name: str = None,
                   org_unit_id: str = None) -> str:
    """执行 Action 预览。返回 preview_id，用户确认后用 confirm_action(preview_id) 提交。

    params 是该 Action 的参数字典，具体参数名见系统提示中的 Action 清单。
    例如 create_clearance_task 的 params: {"target_id":"...", "store_id":"...",
    "assignee_id":"...", "discount_percent":30, "planned_quantity":50}

    注：actor 从当前登录用户派生（auth_ctx），不需要也不能由调用方指定。
    """
    tc = shared._tc_ctx(workspace_name, org_unit_id)
    actor = shared._get_actor(tc)
    ex = shared._get_executor()
    actions = ex.actions
    if action_type not in actions:
        return shared._wrap({"type": "action_preview", "valid": False,
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
        return shared._wrap({"type": "action_preview", "valid": False,
                             "error": str(e),
                             "required_params": required},
                            f"预览失败: {e}。该 Action 必填参数: {required}")
    preview = {"action_type": action_type, "params": validated,
               "actor": actor, "tenant_id": tc}
    preview_id = shared._preview_cache.put(preview)
    return shared._wrap({"type": "action_preview", "valid": True, "preview_id": preview_id,
                         "action_type": action_type, "params": validated},
                        f"预览已生成，preview_id={preview_id}，确认请调 confirm_action。")


@tool
def confirm_action(preview_id: str) -> str:
    """凭 preview_id 执行已预览的 Action（架构 spec §1.6 治理闭环）。"""
    preview = shared._preview_cache.get(preview_id)
    if not preview:
        return shared._wrap({"type": "action_result", "success": False,
                             "error": "preview 无效或已过期，请先 execute_action"},
                            "preview 无效或已过期，请重新预览。")
    try:
        result = shared._get_executor().execute(
            preview["action_type"], preview["params"],
            actor=preview["actor"],
            tenant_id=preview["tenant_id"])
        return shared._wrap({"type": "action_result", "success": True, **result},
                            f"操作完成: {preview['action_type']}")
    except OntologyError as e:
        return shared._wrap({"type": "action_result", "success": False, "error": str(e)},
                            f"操作失败: {e}")


TOOLS = [execute_action, confirm_action]
