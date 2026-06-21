"""ActionExecutor —— 声明式契约的瘦路由器（架构 spec §1.2 第6点）。
读 YAML 契约 → 校验 → 原子执行副作用。纯 Python，可单测。"""
import re
import uuid
from typing import Dict

from engine.errors import ValidationError, EntityNotFoundError
from engine.state_machine import is_valid_transition


def _resolve(value, params):
    """字段值解析：'$name' 取 params[name]，其余字面量。"""
    if isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        if key not in params:
            raise ValidationError(f"副作用引用了未提供的参数: {key}")
        return params[key]
    return value


def _match_constraint(value, constraint: str) -> bool:
    c = constraint.strip()
    if ".." in c:  # 形如 "0..100"
        lo, hi = c.split("..")
        return (lo == "" or value >= float(lo)) and (hi == "" or value <= float(hi))
    m = re.match(r"^(>=|<=|>|<)\s*(\d+(?:\.\d+)?)$", c)
    if m:
        op, num = m.group(1), float(m.group(2))
        return {">": value > num, ">=": value >= num,
                "<": value < num, "<=": value <= num}[op]
    return True  # 无可识别约束则放行


class ActionExecutor:
    def __init__(self, repository, actions: Dict[str, object], registry, config=None):
        self.repo = repository
        self.actions = actions
        self.registry = registry
        self.config = config  # 价值链流程上下文（提供状态机表与工作流对象类型）

    # ---------- 公共入口 ----------
    def validate(self, action_type: str, params: dict) -> dict:
        """只校验参数（不执行副作用）。供 execute_action 预览阶段调用，
        让错误参数名在预览时就报错，不进缓存、不等到 confirm 才失败。"""
        action = self.actions.get(action_type)
        if not action:
            raise ValidationError(f"未知 Action Type: {action_type}")
        return self._validate_params(action, params)

    def execute(self, action_type: str, params: dict, *, actor: dict, tenant_id: str) -> dict:
        action = self.actions.get(action_type)
        if not action:
            raise ValidationError(f"未知 Action Type: {action_type}")
        params = self._validate_params(action, params)
        target = self._load_target(action, params, tenant_id)
        self._check_submission(action, actor, target, params, tenant_id)
        changes = self._run_side_effects(action, params, tenant_id)
        return {"ok": True, "action": action_type, "created": changes["created"],
                "updated": changes["updated"]}

    # ---------- 校验 ----------
    def _validate_params(self, action, params):
        out = {}
        for p in action.parameters:
            name = p["name"]
            if name not in params or params[name] is None:
                if p.get("required") and "default" not in p:
                    raise ValidationError(f"缺少必填参数: {name}")
                out[name] = p.get("default")
                continue
            val = params[name]
            if "constraint" in p and p["constraint"]:
                if not _match_constraint(val, p["constraint"]):
                    raise ValidationError(
                        f"参数 {name} 不满足约束 {p['constraint']}（当前 {val}）")
            out[name] = val
        return out

    def _load_target(self, action, params, tenant_id):
        target_type = action.target_object_type
        if target_type not in self.registry.object_types:
            return None
        # 定位键优先级：Action 声明的 locator_field > workflow 对象用 task_id 类约定 > target_id。
        # locator_field 是数据驱动的（在 Action YAML 里声明，如 task_id / ticket_id），
        # 取代旧的 target_type == "Task" 硬编码（见 docs/manual/01）。
        locator = getattr(action, "locator_field", None)
        if locator and locator in params:
            ident = params[locator]
        elif self.config and self.config.workflow_object_type == target_type \
                and "task_id" in params:
            # 向后兼容：未声明 locator_field 时，workflow 对象按 task_id 定位
            ident = params["task_id"]
        else:
            ident = params.get("target_id")
        if not ident:
            return None
        return self.repo.read_one(target_type, tenant_id, ident)

    def _check_submission(self, action, actor, target, params, tenant_id):
        sc = action.submission_criteria or {}
        roles = sc.get("roles", [])
        if roles and actor.get("role") not in roles:
            raise ValidationError(
                f"角色 {actor.get('role')} 无权提交 {action.api_name}（需 {roles}）")
        for cond in sc.get("conditions", []):
            # field 形如 "target.status" 或 "<workflow_object>.status"
            field_path = cond["field"]
            obj = self._resolve_condition_obj(field_path, target, params, tenant_id, action)
            if obj is None:
                raise ValidationError(f"submission 条件无法解析对象: {field_path}")
            key = field_path.split(".")[-1]
            actual = obj.get(key)
            op, want = cond["operator"], cond.get("value")
            ok = (op == "is" and actual == want) or \
                 (op == "is_not" and actual != want)
            if not ok:
                raise ValidationError(cond.get("fail_msg", "submission 条件不满足"))

    def _resolve_condition_obj(self, field_path, target, params, tenant_id, action):
        root = field_path.split(".")[0]
        if root == "target":
            return target
        # 工作流对象别名：旧 YAML 用 "task.xxx"，现按 config.workflow_object_type 通用化。
        # 如价值链流程的工作流对象是 RepairTicket，条件写 "repair_ticket.status" 即可。
        # 注意：工作流对象的定位键是 config.workflow_object_id_field（如 task_id/ticket_id），
        # 与 action.locator_field（定位 target 用的）是两个不同的概念。
        wf_type = (self.config.workflow_object_type if self.config else "Task") or "Task"
        wf_id_field = (self.config.workflow_object_id_field if self.config else "task_id")
        if root == wf_type.lower():
            tid = params.get(wf_id_field)
            return self.repo.read_one(wf_type, tenant_id, tid) if tid else None
        return target

    # ---------- 副作用执行 ----------
    def _run_side_effects(self, action, params, tenant_id):
        created = {}
        updated = {}
        for eff in action.side_effects:
            t = eff["type"]
            if t == "create_object":
                obj_type = eff["object_type"]
                fields = {k: _resolve(v, params) for k, v in eff.get("fields", {}).items()}
                fields.setdefault("id", f"{obj_type.lower()}_{uuid.uuid4().hex[:8]}")
                rec = self.repo.write(obj_type, tenant_id, fields,
                                      create=True, bypass_action_check=True)
                created.setdefault(obj_type, []).append(rec)
            elif t == "update_object":
                obj_type = eff["object_type"]
                match = {k: _resolve(v, params) for k, v in eff.get("match", {}).items()}
                rec = self.repo.read_one(obj_type, tenant_id, match.get("id"))
                if not rec:
                    raise EntityNotFoundError(f"未找到 {obj_type}: {match}")
                new_rec = dict(rec)
                for k, v in eff.get("fields", {}).items():
                    new_rec[k] = _resolve(v, params)
                for tr in eff.get("transforms", []):
                    f, by = tr["field"], _resolve(tr.get("by"), params)
                    cur = new_rec.get(f, 0)
                    if tr["op"] == "increment":
                        new_rec[f] = cur + by
                    elif tr["op"] == "decrement":
                        new_rec[f] = cur - by
                    elif tr["op"] == "set":
                        new_rec[f] = by
                self.repo.write(obj_type, tenant_id, new_rec,
                                bypass_action_check=True)
                updated.setdefault(obj_type, []).append(new_rec)
            elif t == "state_transition":
                obj_type = eff["object_type"]
                match = {k: _resolve(v, params) for k, v in eff.get("match", {}).items()}
                rec = self.repo.read_one(obj_type, tenant_id, match.get("id"))
                if not rec:
                    raise EntityNotFoundError(f"未找到 {obj_type}: {match}")
                # 状态迁移表从 config 取（per-process 价值链流程）；未配 config 则用 clearance 默认
                trans = (self.config.state_transitions if self.config
                         and self.config.state_transitions else None)
                terms = (self.config.terminal_states if self.config
                         and self.config.terminal_states else None)
                if not is_valid_transition(rec.get("status"), eff["to"], trans, terms):
                    raise ValidationError(
                        f"非法状态迁移: {rec.get('status')} -> {eff['to']}")
                rec["status"] = eff["to"]
                self.repo.write(obj_type, tenant_id, rec, bypass_action_check=True)
                updated.setdefault(obj_type, []).append(rec)
            elif t in ("notification", "external_call"):
                pass  # MVP 仅声明，不实际触发（v2 接对接层）
        return {"created": created, "updated": updated}
