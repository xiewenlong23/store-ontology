"""存储抽象层 —— 所有数据读写经此，承载多租户隔离、文件锁、原子写、edits-only 治理。"""
import json
import os
import fcntl
import tempfile
from typing import Optional

from ontology.errors import ActionRequiredError


class Repository:
    """Repository 接口（实现见 JSONFileRepository）。"""

    def read(self, object_type: str, tenant_id: str, filters: Optional[dict] = None) -> list[dict]:
        raise NotImplementedError

    def read_one(self, object_type: str, tenant_id: str, entity_id: str) -> Optional[dict]:
        raise NotImplementedError

    def write(self, object_type: str, tenant_id: str, record: dict, *,
              create: bool = False, bypass_action_check: bool = False) -> dict:
        raise NotImplementedError

    def delete(self, object_type: str, tenant_id: str, entity_id: str) -> bool:
        raise NotImplementedError


class JSONFileRepository(Repository):
    """JSON 文件实现。

    - 多租户：record 的 tenant_id 字段为准，缺失视为 tenant_default；
      读取按 tenant_id 过滤，写入时盖上 tenant_id。
    - 文件锁：fcntl.flock（仅 Unix）。
    - 原子写：临时文件 + os.rename。
    - edits-only-via-actions：object_type 在 registry 中标记时，非 bypass 写直接拒绝。
    """

    DEFAULT_TENANT = "tenant_default"

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

    def read(self, object_type: str, tenant_id: str, filters: Optional[dict] = None) -> list[dict]:
        rows = self._load(self._path(object_type))
        rows = [r for r in rows if r.get("tenant_id", self.DEFAULT_TENANT) == tenant_id]
        if filters:
            rows = [r for r in rows
                    if all(str(r.get(k)) == str(v) for k, v in filters.items())]
        return rows

    def read_one(self, object_type: str, tenant_id: str, entity_id: str) -> Optional[dict]:
        for r in self.read(object_type, tenant_id):
            if r.get("id") == entity_id:
                return r
        return None

    def _check_edits_only(self, object_type: str, bypass: bool) -> None:
        obj = self.registry.object_types.get(object_type)
        if obj and getattr(obj, "edits_only_via_actions", False) and not bypass:
            raise ActionRequiredError(
                f"{object_type} 已锁定为 edits-only-via-actions，必须经 Action 修改")

    def write(self, object_type: str, tenant_id: str, record: dict, *,
              create: bool = False, bypass_action_check: bool = False) -> dict:
        self._check_edits_only(object_type, bypass_action_check)
        path = self._path(object_type)
        rows = self._load(path)
        record = dict(record)
        record["tenant_id"] = tenant_id
        if create:
            rows.append(record)
        else:
            replaced = False
            for i, r in enumerate(rows):
                if r.get("id") == record.get("id") and \
                   r.get("tenant_id", self.DEFAULT_TENANT) == tenant_id:
                    merged = {**r, **record}
                    rows[i] = merged
                    replaced = True
                    break
            if not replaced:
                rows.append(record)
        self._dump(path, rows)
        return record

    def delete(self, object_type: str, tenant_id: str, entity_id: str) -> bool:
        path = self._path(object_type)
        rows = self._load(path)
        before = len(rows)
        rows = [r for r in rows
                if not (r.get("id") == entity_id
                        and r.get("tenant_id", self.DEFAULT_TENANT) == tenant_id)]
        self._dump(path, rows)
        return len(rows) < before
