"""PermissionEvaluator 通用权限求值引擎（v2 WP5，设计文档 §4）。

求值顺序（设计文档 §2.5）：
  1. system_admin 短路（全 allow）
  2. PermissionGrant runtime override（deny 优先）
  3. TTL 元数据（read_roles/read_except 正反向）
  4. allow-by-default（无声明 → allow）

支持 5 类资源：tool / object_type / property / action / link（设计文档 §3.1）。
正反向语法：``roles`` 正向白名单 + ``except`` 反向除外；同时声明则 ``roles - except``。
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from engine.errors import PermissionDenied


# ============ 求值结果 ============

@dataclass(frozen=True)
class PermissionResult:
    """权限求值结果。"""
    granted: bool
    reason: str = ""
    denied_at: str = ""        # 哪一层拒绝（system_admin / grant / ttl / default）
    masked_fields: Tuple[str, ...] = ()   # 属性级求值时被 mask 的字段名

    @classmethod
    def allow(cls, reason: str = "") -> "PermissionResult":
        return cls(granted=True, reason=reason)

    @classmethod
    def deny(cls, reason: str, denied_at: str) -> "PermissionResult":
        return cls(granted=False, reason=reason, denied_at=denied_at)


# ============ 角色解析 helper ============

def _split_roles(roles_str: str) -> Set[str]:
    """逗号分隔的角色字符串 → 集合（去空白，忽略空）。"""
    if not roles_str:
        return set()
    return {r.strip() for r in roles_str.split(",") if r.strip()}


def eval_role_rule(actor_role: str, roles_str: str, except_str: str) -> Optional[bool]:
    """评估一条角色规则（正反向 + allow-by-default）。

    返回三态：
    - True：规则允许（actor_role 在 roles 内，且不在 except 内）
    - False：规则拒绝（roles 非空且 actor_role 不在；或 actor_role 在 except 内）
    - None：规则未声明（roles 与 except 都为空），交给下层（allow-by-default）

    特殊：
    - roles == "*" 表示所有角色允许（except 仍可除外）
    - except == "*" 表示全员除外（即无人允许）；用于表达"任何角色都不可读"
      （如 password_hash：read_except="*" 表示所有人被除外）
    """
    roles = _split_roles(roles_str)
    excepts = _split_roles(except_str)

    # 反向除外：actor 命中 except → 拒绝（优先级最高）
    # 特殊：except 含 "*" 表示全员除外
    if actor_role in excepts or "*" in excepts:
        return False

    # 正向白名单
    if roles:
        if "*" in roles:
            return True
        return actor_role in roles

    # roles 为空但 except 非空 → 除 except 外都允许
    if excepts:
        return True

    # 都未声明 → None（未裁决，交给下层）
    return None


# ============ PermissionGrant 数据访问 ============

@dataclass
class GrantRow:
    """PermissionGrant 的精简内存表示（从 workspace 的 permission_grants.json 加载）。"""
    role_id: str          # 对应 actor.role（不是 role 表的 id）
    resource_type: str    # object_type / property / action / link / tool
    resource_id: str      # 具体资源名
    action: str           # read / write / execute / traverse / use
    effect: str           # allow / deny


def _load_grants(data_dir: str) -> List[GrantRow]:
    """从 workspace/data/permission_grants.json 加载 GrantRow 列表。

    文件不存在/为空返回空列表。设计文档 §2.5：Grant 是 runtime override，优先级 > TTL。
    """
    import json
    import os
    path = os.path.join(data_dir, "permission_grants.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    rows = []
    for row in data or []:
        if not isinstance(row, dict):
            continue
        rows.append(GrantRow(
            role_id=str(row.get("role_id", "")),
            resource_type=str(row.get("resource_type", "")),
            resource_id=str(row.get("resource_id", "")),
            action=str(row.get("action", "")),
            effect=str(row.get("effect", "allow")),
        ))
    return rows


def _find_grant(grants: List[GrantRow], role: str, resource_type: str,
                resource_id: str, action: str) -> Optional[bool]:
    """在 grants 里找匹配的 effect。deny 优先于 allow。

    匹配条件：role_id 匹配（或 "*"）+ resource_type/resource_id/action 匹配。
    无匹配返回 None（未裁决）。
    """
    allow_matched = False
    for g in grants:
        if g.role_id not in (role, "*"):
            continue
        if g.resource_type != resource_type:
            continue
        if g.resource_id != resource_id and g.resource_id != "*":
            continue
        if g.action not in (action, "*"):
            continue
        if g.effect == "deny":
            return False   # deny 立即返回
        if g.effect == "allow":
            allow_matched = True
    return True if allow_matched else None


# ============ PermissionEvaluator ============

class PermissionEvaluator:
    """通用权限求值引擎。

    依赖：
    - registry：EntityRegistry（含 ObjectType/LinkType/ActionType 的 TTL 元数据）
    - grants：PermissionGrant 列表（runtime override）
    - tool_manifest：Dict[tool_name, ToolPerm]（来自 tool_manifest.py）

    所有方法返回 PermissionResult（不抛异常）；调用方决定失败时抛 PermissionDenied。
    """

    def __init__(self, registry, grants: List[GrantRow], tool_manifest: Dict):
        self.registry = registry
        self.grants = grants or []
        self.tool_manifest = tool_manifest or {}

    # ---------- 内部：通用求值骨架 ----------

    def _eval(self, actor_role: str, resource_type: str, resource_id: str,
              action: str, ttl_roles: str, ttl_except: str) -> PermissionResult:
        """统一求值骨架（设计文档 §2.5 顺序）。

        1. system_admin 短路
        2. Grant runtime override（deny 优先）
        3. TTL 正反向
        4. allow-by-default
        """
        # 1. system_admin 短路
        if actor_role == "system_admin":
            return PermissionResult.allow(reason="system_admin 短路")

        # 2. Grant runtime override
        grant_effect = _find_grant(self.grants, actor_role,
                                   resource_type, resource_id, action)
        if grant_effect is False:
            return PermissionResult.deny(
                reason=f"PermissionGrant 拒绝 {resource_type}/{resource_id}/{action}",
                denied_at="grant")
        if grant_effect is True:
            return PermissionResult.allow(reason="PermissionGrant 允许")

        # 3. TTL 元数据（正反向）
        ttl_decision = eval_role_rule(actor_role, ttl_roles, ttl_except)
        if ttl_decision is False:
            return PermissionResult.deny(
                reason=f"TTL 元数据拒绝（role={actor_role} 不在允许集 / 在除外集）",
                denied_at="ttl")
        if ttl_decision is True:
            return PermissionResult.allow(reason="TTL 元数据允许")

        # 4. allow-by-default
        return PermissionResult.allow(reason="allow-by-default")

    # ---------- 公开 API（5 类资源） ----------

    def can_use_tool(self, actor_role: str, tool_name: str) -> PermissionResult:
        """Tool 级权限（use）。tool_manifest 是数据源（设计文档 §2.8）。"""
        perm = self.tool_manifest.get(tool_name)
        if perm is None:
            # 未在 manifest 声明的 tool → allow-by-default
            return self._eval(actor_role, "tool", tool_name, "use", "", "")
        return self._eval(actor_role, "tool", tool_name, "use",
                          perm.use_roles, perm.use_except)

    def can_read_object(self, actor_role: str, obj_type: str) -> PermissionResult:
        """Object Type 级读权限。"""
        ot = self.registry.object_types.get(obj_type)
        roles = ot.read_roles if ot else ""
        excepts = ot.read_except if ot else ""
        return self._eval(actor_role, "object_type", obj_type, "read", roles, excepts)

    def can_write_object(self, actor_role: str, obj_type: str) -> PermissionResult:
        """Object Type 级写权限。"""
        ot = self.registry.object_types.get(obj_type)
        roles = ot.write_roles if ot else ""
        excepts = ot.write_except if ot else ""
        return self._eval(actor_role, "object_type", obj_type, "write", roles, excepts)

    def can_execute_action(self, actor_role: str, action_type: str) -> PermissionResult:
        """Action 级执行权限。

        注：ActionType 当前 dataclass 无 use_roles/use_except 字段（WP3 未扩到 action）。
        现有 submission_criteria.roles 仍是 action 的角色门控（由 executor 校验）；
        本方法只覆盖 PermissionGrant override（如有）。无 Grant → allow-by-default。
        """
        return self._eval(actor_role, "action", action_type, "execute", "", "")

    def can_traverse_link(self, actor_role: str, link_type: str) -> PermissionResult:
        """Link Type 级遍历权限。"""
        lt = self.registry.link_types.get(link_type)
        roles = lt.use_roles if lt else ""
        excepts = lt.use_except if lt else ""
        return self._eval(actor_role, "link", link_type, "traverse", roles, excepts)

    # ---------- 属性级 ----------

    def readable_properties(self, actor_role: str, obj_type: str) -> Set[str]:
        """返回该 actor 对 obj_type 的可读属性名集合。

        Object 级 read 被拒 → 空集合（完全不可读）。
        Object 级允许 → 逐属性求值，被拒的属性从全集中减去，返回剩余 + masked。
        """
        obj_result = self.can_read_object(actor_role, obj_type)
        if not obj_result.granted:
            return set()
        ot = self.registry.object_types.get(obj_type)
        if not ot:
            return set()
        all_props = {p.name for p in ot.properties}
        denied = set()
        for p in ot.properties:
            r = self._eval(actor_role, "property",
                           f"{obj_type}.{p.name}", "read",
                           p.read_roles, p.read_except)
            if not r.granted:
                denied.add(p.name)
        return all_props - denied

    def denied_properties(self, actor_role: str, obj_type: str) -> Set[str]:
        """返回该 actor 对 obj_type 的不可读属性名集合（用于响应文本提示）。"""
        ot = self.registry.object_types.get(obj_type)
        if not ot:
            return set()
        denied = set()
        for p in ot.properties:
            r = self._eval(actor_role, "property",
                           f"{obj_type}.{p.name}", "read",
                           p.read_roles, p.read_except)
            if not r.granted:
                denied.add(p.name)
        return denied

    def can_write_property(self, actor_role: str, obj_type: str, prop_name: str) -> PermissionResult:
        """属性级写权限（execute_action 参数校验用）。"""
        ot = self.registry.object_types.get(obj_type)
        if not ot:
            return PermissionResult.allow(reason="未知 Object Type，allow-by-default")
        for p in ot.properties:
            if p.name == prop_name:
                return self._eval(actor_role, "property",
                                  f"{obj_type}.{prop_name}", "write",
                                  p.write_roles, p.write_except)
        # 属性不存在 → allow-by-default（参数校验别处会拦）
        return PermissionResult.allow(reason="未知属性，allow-by-default")


# ============ 工厂：从 workspace 装配 ============

def build_evaluator_from_workspace(ws_name: str) -> PermissionEvaluator:
    """从 workspace 名装配 PermissionEvaluator（合并 registry + grants + tool_manifest）。

    依赖 bootstrap 已注册该 workspace。失败返回空 evaluator（全 allow）。
    """
    from engine.pack import get_workspace_dir, domains_to_registry
    from engine.tool_manifest import (
        load_kernel_tool_manifest, load_workspace_tool_manifest, merge_manifests,
    )

    ws = get_workspace_dir(ws_name)
    if ws is None:
        return PermissionEvaluator(registry=_EmptyRegistry(), grants=[], tool_manifest={})

    registry = domains_to_registry(ws, data_dir=ws.data_dir or ".")
    grants = _load_grants(ws.data_dir or ".")
    kernel = load_kernel_tool_manifest()
    ws_manifest = load_workspace_tool_manifest(ws.data_dir or ".")
    manifest = merge_manifests(kernel, ws_manifest)
    return PermissionEvaluator(registry=registry, grants=grants, tool_manifest=manifest)


@dataclass
class _EmptyRegistry:
    """空 registry 占位（workspace 未注册时用，让求值全 allow-by-default）。"""
    object_types: dict = None
    link_types: dict = None
    action_types: dict = None

    def __post_init__(self):
        if self.object_types is None:
            self.object_types = {}
        if self.link_types is None:
            self.link_types = {}
        if self.action_types is None:
            self.action_types = {}


# ============ raise 辅助 ============

def require(result: PermissionResult, action_desc: str) -> None:
    """求值结果为 deny → 抛 PermissionDenied；否则 no-op。

    给 Tool 拦截层用：``require(evaluator.can_use_tool(role, name), f"使用 {name}")``
    """
    if not result.granted:
        raise PermissionDenied(
            f"无权{action_desc}：{result.reason}（拒绝层：{result.denied_at}）")
