"""存储抽象层 —— 所有数据读写经此，承载多租户隔离、文件锁、原子写、edits-only 治理。

架构 spec §3.3/§5.5：workspace_name（硬隔离）+ org_unit_id（权限范围）双层。
向后兼容：字符串 tenant_id 自动转为 TenantContext（customer_default + 通配 org）。
"""
import json
import os
import fcntl
import tempfile
from typing import Optional, Union

from engine.errors import ActionRequiredError
from engine.tenant import TenantContext


def _normalize_tenant(tenant) -> TenantContext:
    """字符串 tenant_id 兼容为 TenantContext。

    v2（WP4 修复）：
    - TenantContext 原样返回
    - 已知 workspace 名（在 pack 注册表里）→ 用其作 workspace_name
    - 未知字符串（含历史值 ``tenant_default``/``customer_default``）→ 回落 jjy（向后兼容）
    """
    if isinstance(tenant, TenantContext):
        return tenant
    if isinstance(tenant, str) and tenant:
        # 已知 workspace 名直接用
        from engine.pack import get_workspace_dir
        if get_workspace_dir(tenant) is not None:
            return TenantContext(workspace_name=tenant, org_unit_id="*")
        # 历史/未知字符串值：保持旧行为（视为 jjy 默认 workspace）
        return TenantContext(workspace_name="jjy", org_unit_id="*")
    return TenantContext(workspace_name="jjy", org_unit_id="*")


def _matches_with_tree(record: dict, tc: TenantContext,
                       org_tree=None, visible_units=None) -> bool:
    """v2（WP5 接入）：用 OrgTree.visible_units 判断记录可见性。

    - workspace_name 必须精确匹配（硬隔离）
    - org_unit_id：
      - tc.org_unit_id == "*" → 看全部（总部视角）
      - 有 org_tree 或预算的 visible_units → record.org_unit_id 必须在 visible_units 内
        （自身 + 所有子孙，如 region_cat_mgr 看 region 时能见子树所有门店）
      - 都无 → 回落精确匹配（向后兼容）
    - 旧数据（无 workspace_name）视为 jjy + 通配 org

    visible_units 参数：调用方预算的集合（性能优化，避免每条 record 重算）。
    传 None 时按需用 org_tree 计算（每次都全树遍历）。
    """
    # workspace_name 硬隔离
    rec_workspace = record.get("workspace_name")
    if rec_workspace is None:
        rec_workspace = record.get("customer_id", "jjy")
    if rec_workspace != tc.workspace_name:
        return False

    # 总部视角
    if tc.sees_all_org_units():
        return True

    rec_org = record.get("org_unit_id", "*")
    # record 自身标记为通配（共享数据，如品类）→ 可见
    if rec_org == "*":
        return True

    # 优先用预算的 visible_units（性能优化）
    if visible_units is not None:
        return rec_org in visible_units
    # 无预算 → 用 org_tree 计算（慢路径）
    if org_tree is not None:
        return rec_org in org_tree.visible_units(tc.org_unit_id)
    # 无 org_tree → 回落精确匹配（向后兼容）
    return rec_org == tc.org_unit_id


def _compute_visible_units(tc: TenantContext, org_tree) -> set:
    """对当前 tc 求一次 visible_units（None 表示"全部可见"——总部视角）。

    性能：让 Repository.read 调用方求一次，传给 _matches_with_tree 复用，
    避免每条 record 都全树遍历。
    """
    if tc.sees_all_org_units():
        return None   # None 表示"全部可见"（_matches_with_tree 内已短路）
    if org_tree is None:
        return None   # 无 tree → _matches_with_tree 回落精确匹配
    return org_tree.visible_units(tc.org_unit_id)


class Repository:
    """Repository 接口（实现见 JSONFileRepository）。

    tenant 参数接受 TenantContext 或字符串（向后兼容）。
    """

    def read(self, object_type: str, tenant, filters: Optional[dict] = None) -> list[dict]:
        raise NotImplementedError

    def read_one(self, object_type: str, tenant, entity_id: str) -> Optional[dict]:
        raise NotImplementedError

    def write(self, object_type: str, tenant, record: dict, *,
              create: bool = False, bypass_action_check: bool = False) -> dict:
        raise NotImplementedError

    def delete(self, object_type: str, tenant, entity_id: str) -> bool:
        raise NotImplementedError


class JSONFileRepository(Repository):
    """JSON 文件实现。

    - 多租户（架构 spec §3.3 双层）：workspace_name 硬隔离 + org_unit_id 权限范围。
      v2（WP5 接入）：过滤用 OrgTree.visible_units（取代精确字符串匹配）——
      region_cat_mgr 登录后能看到本 region 子树的所有门店数据。
      无 OrgTree（缺 org_units.json）回落精确匹配。
      写入盖 workspace_name + org_unit_id。
      向后兼容旧 tenant_id 字符串/旧数据（customer_id 字段）。
    - 文件锁：fcntl.flock（仅 Unix）。
    - 原子写：临时文件 + os.replace。
    - edits-only-via-actions：object_type 在 registry 中标记时，非 bypass 写直接拒绝。
    """

    def __init__(self, data_dir: str, registry):
        self.data_dir = data_dir
        self.registry = registry
        # v2（WP5 接入）：加载 OrgTree（可选，None 时回落精确匹配）
        from engine.org_tree import load_org_tree_from_data_dir
        self._org_tree = load_org_tree_from_data_dir(data_dir)

    def _path(self, object_type: str) -> str:
        obj = self.registry.object_types.get(object_type)
        if not obj:
            raise KeyError(f"未知 Object Type: {object_type}")
        return os.path.join(self.data_dir, obj.storage_file)

    def _load(self, path: str) -> list[dict]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _dump(self, path: str, data: list[dict]) -> None:
        # 整文件级排他锁 + 原子替换
        lock_path = path + ".lock"
        with open(lock_path, "w") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)

    def read(self, object_type: str, tenant, filters: Optional[dict] = None) -> list[dict]:
        tc = _normalize_tenant(tenant)
        # v2 性能：对当前 tc 求一次 visible_units，复用给所有 record
        visible = _compute_visible_units(tc, self._org_tree)
        rows = self._load(self._path(object_type))
        rows = [r for r in rows if _matches_with_tree(r, tc, self._org_tree, visible)]
        if filters:
            rows = [r for r in rows
                    if all(str(r.get(k)) == str(v) for k, v in filters.items())]
        return rows

    def read_one(self, object_type: str, tenant, entity_id: str) -> Optional[dict]:
        for r in self.read(object_type, tenant):
            if r.get("id") == entity_id:
                return r
        return None

    def _check_edits_only(self, object_type: str, bypass: bool) -> None:
        obj = self.registry.object_types.get(object_type)
        if obj and getattr(obj, "edits_only_via_actions", False) and not bypass:
            raise ActionRequiredError(
                f"{object_type} 已锁定为 edits-only-via-actions，必须经 Action 修改")

    def write(self, object_type: str, tenant, record: dict, *,
              create: bool = False, bypass_action_check: bool = False) -> dict:
        tc = _normalize_tenant(tenant)
        visible = _compute_visible_units(tc, self._org_tree)
        self._check_edits_only(object_type, bypass_action_check)
        path = self._path(object_type)
        rows = self._load(path)
        record = dict(record)
        record["workspace_name"] = tc.workspace_name
        record["org_unit_id"] = tc.org_unit_id
        if create:
            rows.append(record)
        else:
            replaced = False
            for i, r in enumerate(rows):
                if r.get("id") == record.get("id") and _matches_with_tree(r, tc, self._org_tree, visible):
                    merged = {**r, **record}
                    rows[i] = merged
                    replaced = True
                    break
            if not replaced:
                rows.append(record)
        self._dump(path, rows)
        return record

    def delete(self, object_type: str, tenant, entity_id: str) -> bool:
        tc = _normalize_tenant(tenant)
        visible = _compute_visible_units(tc, self._org_tree)
        path = self._path(object_type)
        rows = self._load(path)
        before = len(rows)
        rows = [r for r in rows
                if not (r.get("id") == entity_id and _matches_with_tree(r, tc, self._org_tree, visible))]
        self._dump(path, rows)
        return len(rows) < before
