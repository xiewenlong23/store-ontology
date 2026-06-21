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
    """字符串 tenant_id 兼容为 TenantContext。"""
    if isinstance(tenant, TenantContext):
        return tenant
    # 旧式字符串：视为 jjy + 通配 org
    return TenantContext(workspace_name="jjy", org_unit_id="*")


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
      过滤用 TenantContext.matches(record)；写入盖 workspace_name + org_unit_id。
      向后兼容旧 tenant_id 字符串/旧数据（customer_id 字段）。
    - 文件锁：fcntl.flock（仅 Unix）。
    - 原子写：临时文件 + os.replace。
    - edits-only-via-actions：object_type 在 registry 中标记时，非 bypass 写直接拒绝。
    """

    def __init__(self, data_dir: str, registry):
        self.data_dir = data_dir
        self.registry = registry

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
        rows = self._load(self._path(object_type))
        rows = [r for r in rows if tc.matches(r)]
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
                if r.get("id") == record.get("id") and tc.matches(r):
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
        path = self._path(object_type)
        rows = self._load(path)
        before = len(rows)
        rows = [r for r in rows
                if not (r.get("id") == entity_id and tc.matches(r))]
        self._dump(path, rows)
        return len(rows) < before
