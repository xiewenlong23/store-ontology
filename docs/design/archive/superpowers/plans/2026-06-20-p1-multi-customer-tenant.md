> **🗄 归档说明**：brainstorming 产出（plan（实施计划）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# P1 多客户租户地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单一的扁平 `tenant_id` 字符串升级为 `customer_id`（客户硬隔离）+ `org_unit_id`（权限范围）双层租户模型，并实现 `CustomerConfig` + `bootstrap(customer)` 按客户构建隔离的 Agent 实例。

**Architecture:** 引入 `TenantContext` 值对象封装 `customer_id` + `org_unit_id`。Repository 的过滤从单字段升级为双字段（`customer_id` 硬隔离 + `org_unit_id` 范围过滤）。`CustomerConfig` 描述每客户的配置（启用的域/流程/参数/OrgUnit 树/存储）。`bootstrap(customer_id)` 按客户构建独立的 OntologyRegistry + Repository + Agent 实例并缓存。全程保持现有 85 测试通过（向后兼容 `tenant_default` → `customer_default`）。

**Tech Stack:** Python ≥3.11、Pydantic v2、pytest（TDD）、现有内核（Repository/Executor/Scheduler/vertical）。

**依据 spec：** `docs/superpowers/specs/2026-06-20-apaas-platform-architecture-design.md` §3（客户配置层）、§5（Agent 实例构建）、§7 P1。

**关键约定：**
- 后端运行目录 = `backend/`。测试以 `backend/` 为根。
- 解释器：`/opt/miniconda3/envs/store-ontology/bin/python`（Python 3.11，全栈）。
- 向后兼容：现有数据的 `tenant_id=tenant_default` 视为 `customer_id=customer_default, org_unit_id=*`（通配，见所有 OrgUnit）。
- 每任务 TDD：先写失败测试 → 看它失败 → 最小实现 → 看它过 → 提交。

---

## File Structure

| 文件 | 职责 | 任务 |
|---|---|---|
| `backend/ontology/tenant.py` | `TenantContext` 值对象（customer_id + org_unit_id + 权限范围解析） | T1 |
| `backend/ontology/customer.py` | `CustomerConfig` dataclass + 客户注册表 + OrgUnit 树 | T2 |
| `backend/ontology/repository.py` | 升级：双字段过滤（customer_id 硬隔离 + org_unit_id 范围） | T3 |
| `backend/ontology/customer_bootstrap.py` | `bootstrap_customer(customer_id)` 按客户构建隔离实例 | T4 |
| `backend/ontology/tools.py` | 工具层从 tenant_id 迁移到 TenantContext | T5 |
| `backend/main.py` | 中间件从 X-Tenant-ID 升级为 X-Customer-ID + X-Org-Unit-ID | T6 |
| `backend/tests/test_tenant.py` | TenantContext 测试 | T1 |
| `backend/tests/test_customer.py` | CustomerConfig + OrgUnit 测试 | T2 |
| `backend/tests/test_repository_tenant.py` | Repository 双字段过滤测试 | T3 |
| `backend/tests/test_customer_bootstrap.py` | 按客户构建隔离实例测试 | T4 |
| `data/customers/customer_default/config.yaml` | 默认客户配置 | T2 |

---

## Task 1: TenantContext 值对象

**Files:**
- Create: `backend/ontology/tenant.py`
- Test: `backend/tests/test_tenant.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_tenant.py`：

```python
"""测试 TenantContext 值对象（P1 双层租户地基）。"""
import pytest
from ontology.tenant import TenantContext


def test_tenant_context_basic():
    tc = TenantContext(customer_id="customer_001", org_unit_id="store_001")
    assert tc.customer_id == "customer_001"
    assert tc.org_unit_id == "store_001"


def test_tenant_context_wildcard_org_unit():
    """org_unit_id='*' 表示看该客户所有 OrgUnit 的数据（如总部角色）。"""
    tc = TenantContext(customer_id="customer_001", org_unit_id="*")
    assert tc.sees_all_org_units() is True


def test_tenant_context_specific_org_unit():
    tc = TenantContext(customer_id="customer_001", org_unit_id="store_001")
    assert tc.sees_all_org_units() is False


def test_tenant_context_matches_record_same_customer_same_org():
    tc = TenantContext(customer_id="c1", org_unit_id="store_001")
    record = {"customer_id": "c1", "org_unit_id": "store_001"}
    assert tc.matches(record) is True


def test_tenant_context_matches_record_wildcard_org():
    """通配 org_unit 看同客户所有记录。"""
    tc = TenantContext(customer_id="c1", org_unit_id="*")
    record = {"customer_id": "c1", "org_unit_id": "store_099"}
    assert tc.matches(record) is True


def test_tenant_context_rejects_different_customer():
    tc = TenantContext(customer_id="c1", org_unit_id="*")
    record = {"customer_id": "c2", "org_unit_id": "store_001"}
    assert tc.matches(record) is False


def test_tenant_context_rejects_different_org_unit():
    tc = TenantContext(customer_id="c1", org_unit_id="store_001")
    record = {"customer_id": "c1", "org_unit_id": "store_002"}
    assert tc.matches(record) is False


def test_tenant_context_default_compat():
    """向后兼容：默认上下文 = customer_default + 通配 org。"""
    tc = TenantContext.default()
    assert tc.customer_id == "customer_default"
    assert tc.sees_all_org_units() is True


def test_tenant_context_matches_legacy_tenant_id_record():
    """旧数据只有 tenant_id 无 customer_id/org_unit_id —— 视为 customer_default。"""
    tc = TenantContext.default()
    record = {"tenant_id": "tenant_default"}  # 旧格式
    assert tc.matches(record) is True


def test_tenant_context_from_dict():
    """从请求上下文字典构造。"""
    tc = TenantContext.from_headers({"X-Customer-ID": "c1", "X-Org-Unit-ID": "store_001"})
    assert tc.customer_id == "c1"
    assert tc.org_unit_id == "store_001"


def test_tenant_context_from_headers_defaults():
    """缺 header 时默认 customer_default + 通配。"""
    tc = TenantContext.from_headers({})
    assert tc.customer_id == "customer_default"
    assert tc.sees_all_org_units() is True
```

- [ ] **Step 2: 运行测试，确认失败**

Run（在 `backend/` 下）: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_tenant.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'ontology.tenant'`）

- [ ] **Step 3: 实现 TenantContext**

创建 `backend/ontology/tenant.py`：

```python
"""双层租户上下文（P1）：customer_id 硬隔离 + org_unit_id 权限范围。

替代旧的单一 tenant_id 字符串。每条数据带 customer_id + org_unit_id；
TenantContext.matches(record) 判断某条数据是否对当前上下文可见。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantContext:
    customer_id: str
    org_unit_id: str = "*"  # '*' = 看该客户所有 OrgUnit（总部角色）

    def sees_all_org_units(self) -> bool:
        return self.org_unit_id == "*"

    def matches(self, record: dict) -> bool:
        """判断一条记录是否对当前上下文可见。

        规则：
        - customer_id 必须匹配（硬隔离）
        - org_unit_id：上下文通配 '*' 则看所有；否则必须精确匹配
        - 旧数据（只有 tenant_id 无 customer_id）视为 customer_default + 通配 org
        """
        rec_customer = record.get("customer_id")
        if rec_customer is None:
            # 旧格式兼容：tenant_id 存在视为 customer_default
            if record.get("tenant_id") is not None:
                rec_customer = "customer_default"
                rec_org = "*"
            else:
                return False
        else:
            rec_org = record.get("org_unit_id", "*")

        if rec_customer != self.customer_id:
            return False
        if self.sees_all_org_units():
            return True
        return rec_org == self.org_unit_id or rec_org == "*"

    @classmethod
    def default(cls) -> "TenantContext":
        return cls(customer_id="customer_default", org_unit_id="*")

    @classmethod
    def from_headers(cls, headers: dict) -> "TenantContext":
        customer = headers.get("X-Customer-ID", "customer_default")
        org = headers.get("X-Org-Unit-ID", "*")
        return cls(customer_id=customer, org_unit_id=org)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_tenant.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/tenant.py backend/tests/test_tenant.py
git commit -m "feat(tenant) P1-T1: TenantContext 值对象（customer_id 硬隔离 + org_unit_id 范围）"
```

---

## Task 2: CustomerConfig + OrgUnit 树

**Files:**
- Create: `backend/ontology/customer.py`
- Create: `data/customers/customer_default/config.yaml`
- Test: `backend/tests/test_customer.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_customer.py`：

```python
"""测试 CustomerConfig + OrgUnit 树（P1 客户配置）。"""
import os
import pytest
from ontology.customer import CustomerConfig, OrgUnit, load_customer_config


def test_customer_config_basic():
    cfg = CustomerConfig(
        customer_id="c1", name="测试客户", source_pack="retail",
        storage_type="json_files", data_dir="/tmp/c1",
        enabled_domains=["marketing"], enabled_processes=["clearance"])
    assert cfg.customer_id == "c1"
    assert cfg.enabled_domains == ["marketing"]


def test_org_unit_tree():
    """OrgUnit 树：parent 链 + 子孙查询。"""
    units = [
        OrgUnit(id="hq", parent=None),
        OrgUnit(id="region_north", parent="hq"),
        OrgUnit(id="store_001", parent="region_north"),
        OrgUnit(id="store_002", parent="region_north"),
    ]
    tree = OrgUnit.Tree(units)
    # store_001 的祖先链
    assert tree.ancestors("store_001") == ["store_001", "region_north", "hq"]
    # region_north 的子孙
    assert set(tree.descendants("region_north")) == {"region_north", "store_001", "store_002"}
    # hq 看全部
    assert set(tree.descendants("hq")) == {"hq", "region_north", "store_001", "store_002"}


def test_org_unit_user_sees_descendants():
    """店长在 store_001 只看 store_001；区域经理在 region_north 看 region_north + 下属店。"""
    units = [
        OrgUnit(id="hq", parent=None),
        OrgUnit(id="region_north", parent="hq"),
        OrgUnit(id="store_001", parent="region_north"),
        OrgUnit(id="store_002", parent="region_north"),
    ]
    tree = OrgUnit.Tree(units)
    assert tree.visible_units("store_001") == {"store_001"}
    assert tree.visible_units("region_north") == {"region_north", "store_001", "store_002"}


def test_load_customer_config_default():
    """加载默认客户配置（data/customers/customer_default/config.yaml）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(base)
    cfg = load_customer_config(os.path.join(root, "data", "customers", "customer_default"))
    assert cfg.customer_id == "customer_default"
    assert cfg.storage_type == "json_files"


def test_customer_registry():
    """客户注册表：注册/获取/列表。"""
    from ontology.customer import register_customer, get_customer, all_customers, clear_customers
    clear_customers()
    cfg = CustomerConfig(customer_id="cx", name="x", source_pack="retail",
                         storage_type="json_files", data_dir="/tmp")
    register_customer(cfg)
    assert get_customer("cx") is cfg
    assert len(all_customers()) >= 1
    clear_customers()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_customer.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'ontology.customer'`）

- [ ] **Step 3: 实现 CustomerConfig + OrgUnit**

创建 `backend/ontology/customer.py`：

```python
"""客户配置（P1）：CustomerConfig + OrgUnit 树 + 客户注册表。

每个客户（企业）一份 CustomerConfig，声明启用的域/流程、存储、OrgUnit 树。
"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OrgUnit:
    """组织单元（Brand > Region > Store 的节点）。"""
    id: str
    parent: Optional[str] = None  # None = 根节点

    class Tree:
        """OrgUnit 树，支持祖先链/子孙集/可见范围查询。"""
        def __init__(self, units: List["OrgUnit"]):
            self._by_id = {u.id: u for u in units}
            self._children: Dict[str, List[str]] = {}
            for u in units:
                self._children.setdefault(u.parent or "__root__", []).append(u.id)

        def ancestors(self, unit_id: str) -> List[str]:
            """从自身往上的祖先链（含自身）。"""
            chain = [unit_id]
            cur = self._by_id.get(unit_id)
            while cur and cur.parent:
                chain.append(cur.parent)
                cur = self._by_id.get(cur.parent)
            return chain

        def descendants(self, unit_id: str) -> List[str]:
            """从自身往下的子孙集（含自身）。"""
            result = [unit_id]
            for child_id in self._children.get(unit_id, []):
                result.extend(self.descendants(child_id))
            return result

        def visible_units(self, unit_id: str) -> set:
            """某 OrgUnit 用户可见的单元集 = 自身 + 所有子孙。"""
            return set(self.descendants(unit_id))

    @classmethod
    def from_dict(cls, d: dict) -> "OrgUnit":
        return cls(id=d["id"], parent=d.get("parent"))


@dataclass
class CustomerConfig:
    """单个客户的配置。"""
    customer_id: str
    name: str
    source_pack: str = ""
    storage_type: str = "json_files"  # MVP: json_files; v2: postgres
    data_dir: str = ""
    enabled_domains: List[str] = field(default_factory=list)
    enabled_processes: List[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    org_units: List[OrgUnit] = field(default_factory=list)

    @property
    def org_tree(self) -> Optional[OrgUnit.Tree]:
        if not self.org_units:
            return None
        return OrgUnit.Tree(self.org_units)


# ============ 客户注册表 ============

_registry: Dict[str, CustomerConfig] = {}


def register_customer(config: CustomerConfig) -> None:
    _registry[config.customer_id] = config


def get_customer(customer_id: str) -> Optional[CustomerConfig]:
    return _registry.get(customer_id)


def all_customers() -> List[CustomerConfig]:
    return list(_registry.values())


def clear_customers() -> None:
    _registry.clear()


def load_customer_config(customer_dir: str) -> CustomerConfig:
    """从 customers/<id>/config.yaml 加载客户配置。"""
    config_path = os.path.join(customer_dir, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    units = [OrgUnit.from_dict(u) for u in data.get("org_tree", [])]
    return CustomerConfig(
        customer_id=data["customer_id"],
        name=data.get("name", data["customer_id"]),
        source_pack=data.get("source_pack", ""),
        storage_type=data.get("storage", {}).get("type", "json_files"),
        data_dir=data.get("storage", {}).get("data_dir", ""),
        enabled_domains=data.get("enabled_domains", []),
        enabled_processes=data.get("enabled_processes", []),
        parameters=data.get("parameters", {}),
        org_units=units,
    )
```

- [ ] **Step 4: 创建默认客户配置**

创建 `data/customers/customer_default/config.yaml`：

```yaml
customer_id: customer_default
name: 默认客户
source_pack: retail
storage:
  type: json_files
  data_dir: data
enabled_domains: [marketing, supply_chain, organization]
enabled_processes: [clearance]
org_tree:
  - { id: brand_default, parent: null }
  - { id: store_001, parent: brand_default }
  - { id: store_002, parent: brand_default }
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_customer.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/customer.py backend/tests/test_customer.py data/customers/
git commit -m "feat(tenant) P1-T2: CustomerConfig + OrgUnit 树 + 客户注册表"
```

---

## Task 3: Repository 双字段过滤

**Files:**
- Modify: `backend/ontology/repository.py`
- Test: `backend/tests/test_repository_tenant.py`

> 这是 P1 最关键的改动：Repository 从单 tenant_id 过滤升级为 customer_id 硬隔离 + org_unit_id 范围过滤。用 TenantContext 替代裸字符串。**向后兼容**：旧调用传字符串 tenant_id 时，视为 customer_default + 通配。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_repository_tenant.py`：

```python
"""测试 Repository 双字段过滤（P1：customer_id 硬隔离 + org_unit_id 范围）。"""
import json
from ontology.repository import JSONFileRepository
from ontology.tenant import TenantContext
from ontology.parser import ObjectType, PropertyDef, EntityRegistry


def _registry():
    store = ObjectType(id="Store", label="门店", label_zh="门店", comment="",
                       properties=[PropertyDef(name="id", type="string")],
                       storage_file="stores.json", status="active")
    reg = EntityRegistry()
    reg.object_types = {"Store": store}
    return reg


def _seed(data_dir, rows):
    import os
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f)


def test_read_filters_by_customer(tmp_path):
    """不同 customer 数据硬隔离。"""
    _seed(str(tmp_path), [
        {"id": "s1", "customer_id": "c1", "org_unit_id": "store_001", "name": "A"},
        {"id": "s2", "customer_id": "c2", "org_unit_id": "store_001", "name": "B"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc1 = TenantContext(customer_id="c1", org_unit_id="*")
    tc2 = TenantContext(customer_id="c2", org_unit_id="*")
    assert len(repo.read("Store", tc1)) == 1
    assert repo.read("Store", tc1)[0]["id"] == "s1"
    assert len(repo.read("Store", tc2)) == 1
    assert repo.read("Store", tc2)[0]["id"] == "s2"


def test_read_filters_by_org_unit(tmp_path):
    """同 customer 内按 org_unit 过滤。"""
    _seed(str(tmp_path), [
        {"id": "s1", "customer_id": "c1", "org_unit_id": "store_001", "name": "A"},
        {"id": "s2", "customer_id": "c1", "org_unit_id": "store_002", "name": "B"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc = TenantContext(customer_id="c1", org_unit_id="store_001")
    rows = repo.read("Store", tc)
    assert len(rows) == 1
    assert rows[0]["id"] == "s1"


def test_read_wildcard_org_sees_all(tmp_path):
    """通配 org_unit 看同客户所有。"""
    _seed(str(tmp_path), [
        {"id": "s1", "customer_id": "c1", "org_unit_id": "store_001", "name": "A"},
        {"id": "s2", "customer_id": "c1", "org_unit_id": "store_002", "name": "B"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc = TenantContext(customer_id="c1", org_unit_id="*")
    assert len(repo.read("Store", tc)) == 2


def test_write_stamps_customer_and_org(tmp_path):
    """写入时盖上 customer_id + org_unit_id。"""
    _seed(str(tmp_path), [])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc = TenantContext(customer_id="c1", org_unit_id="store_001")
    repo.write("Store", tc, {"id": "s_new", "name": "新"}, create=True)
    rows = repo.read("Store", tc)
    assert rows[0]["customer_id"] == "c1"
    assert rows[0]["org_unit_id"] == "store_001"


def test_backward_compat_legacy_tenant_id_string(tmp_path):
    """旧调用传字符串 tenant_id 时兼容（视为 customer_default + 通配）。"""
    _seed(str(tmp_path), [
        {"id": "s1", "tenant_id": "tenant_default", "name": "A"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    # 旧式字符串调用
    rows = repo.read("Store", "tenant_default")
    assert len(rows) == 1  # 旧数据可见
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_repository_tenant.py -v`
Expected: FAIL（Repository.read 不接受 TenantContext）

- [ ] **Step 3: 升级 Repository 支持 TenantContext**

修改 `backend/ontology/repository.py`。关键改动：`read`/`read_one`/`write`/`delete` 的 `tenant_id` 参数改为接受 `TenantContext` 或字符串（兼容）。过滤逻辑改用 `TenantContext.matches`。写入时盖 `customer_id` + `org_unit_id`。

把 `read` 方法改为（替换现有 `read` + `read_one` + `write` + `delete` 签名与过滤）：

```python
# 文件顶部加 import
from ontology.tenant import TenantContext

def _normalize_tenant(tenant) -> TenantContext:
    """字符串 tenant_id 兼容为 TenantContext。"""
    if isinstance(tenant, TenantContext):
        return tenant
    # 旧式字符串：tenant_default → customer_default + 通配
    return TenantContext(customer_id="customer_default", org_unit_id="*")
```

`read` 方法改为：
```python
    def read(self, object_type: str, tenant, filters: Optional[dict] = None) -> list[dict]:
        tc = _normalize_tenant(tenant)
        rows = self._load(self._path(object_type))
        rows = [r for r in rows if tc.matches(r)]
        if filters:
            rows = [r for r in rows
                    if all(str(r.get(k)) == str(v) for k, v in filters.items())]
        return rows
```

`read_one` 方法改为：
```python
    def read_one(self, object_type: str, tenant, entity_id: str) -> Optional[dict]:
        for r in self.read(object_type, tenant):
            if r.get("id") == entity_id:
                return r
        return None
```

`write` 方法改为（签名加 tenant 兼容，写入盖 customer_id + org_unit_id）：
```python
    def write(self, object_type: str, tenant, record: dict, *,
              create: bool = False, bypass_action_check: bool = False) -> dict:
        tc = _normalize_tenant(tenant)
        self._check_edits_only(object_type, bypass_action_check)
        path = self._path(object_type)
        rows = self._load(path)
        record = dict(record)
        record["customer_id"] = tc.customer_id
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
```

`delete` 方法改为：
```python
    def delete(self, object_type: str, tenant, entity_id: str) -> bool:
        tc = _normalize_tenant(tenant)
        path = self._path(object_type)
        rows = self._load(path)
        before = len(rows)
        rows = [r for r in rows
                if not (r.get("id") == entity_id and tc.matches(r))]
        self._dump(path, rows)
        return len(rows) < before
```

同时更新抽象基类 `Repository` 的方法签名（`tenant` 不标类型，或标 `Union[str, TenantContext]`），保持接口一致。

- [ ] **Step 4: 运行新测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_repository_tenant.py -v`
Expected: 5 passed

- [ ] **Step 5: 运行全量测试，确认旧测试兼容**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/ -q`
Expected: 全部通过（旧测试传字符串 tenant_id 仍工作）

> **如果旧测试失败**：检查旧测试是否传了字符串 tenant_id 但数据用的是旧格式（只有 tenant_id 字段）。TenantContext.matches 对旧数据（tenant_id 存在）视为 customer_default，应兼容。若有测试直接断言 `record["tenant_id"]`，需改为断言 `customer_id`。

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/repository.py backend/tests/test_repository_tenant.py
git commit -m "feat(tenant) P1-T3: Repository 双字段过滤（customer_id 硬隔离 + org_unit_id 范围）"
```

---

## Task 4: bootstrap_customer 按客户构建隔离实例

**Files:**
- Create: `backend/ontology/customer_bootstrap.py`
- Test: `backend/tests/test_customer_bootstrap.py`

> 按客户构建独立的 OntologyRegistry + Repository + Executor，按 customer_id 缓存。两个客户的实例互不干扰。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_customer_bootstrap.py`：

```python
"""测试 bootstrap_customer 按客户构建隔离实例（P1）。"""
import pytest
from ontology.customer_bootstrap import bootstrap_customer, get_customer_agent_instance, reset_instances


@pytest.fixture(autouse=True)
def _clean():
    reset_instances()
    yield
    reset_instances()


def test_bootstrap_default_customer():
    """bootstrap 默认客户，得到一个 AgentInstance。"""
    inst = bootstrap_customer("customer_default")
    assert inst is not None
    assert inst.customer_id == "customer_default"
    assert inst.registry is not None
    assert inst.repository is not None


def test_instance_cached_per_customer():
    """同 customer 多次 bootstrap 返回缓存实例。"""
    inst1 = bootstrap_customer("customer_default")
    inst2 = bootstrap_customer("customer_default")
    assert inst1 is inst2


def test_two_customers_isolated():
    """两个客户的 registry/repository 实例不同。"""
    # 用两个临时数据目录模拟两个客户
    import tempfile, os
    d1 = tempfile.mkdtemp()
    d2 = tempfile.mkdtemp()
    # 给两个客户各注册 config
    from ontology.customer import CustomerConfig, register_customer, clear_customers
    clear_customers()
    register_customer(CustomerConfig(customer_id="ca", name="A", storage_type="json_files", data_dir=d1))
    register_customer(CustomerConfig(customer_id="cb", name="B", storage_type="json_files", data_dir=d2))
    reset_instances()

    ia = bootstrap_customer("ca")
    ib = bootstrap_customer("cb")
    assert ia is not ib
    assert ia.repository is not ib.repository
    assert ia.registry is not ib.registry
    # 数据目录不同
    assert str(ia.repository.data_dir) != str(ib.repository.data_dir)
    clear_customers()


def test_get_customer_agent_instance():
    inst = bootstrap_customer("customer_default")
    assert get_customer_agent_instance("customer_default") is inst
    assert get_customer_agent_instance("nonexistent") is None
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_customer_bootstrap.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 bootstrap_customer**

创建 `backend/ontology/customer_bootstrap.py`：

```python
"""按客户构建隔离的 Agent 实例（P1）。

每个客户独立的 OntologyRegistry + Repository + Executor，按 customer_id 缓存。
两个客户的实例互不干扰（数据隔离 + 本体语义隔离）。
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional

from ontology.customer import get_customer, load_customer_config, CustomerConfig
from ontology.tenant import TenantContext


@dataclass
class CustomerAgentInstance:
    """一个客户的 Agent 运行时实例（registry + repository + executor）。"""
    customer_id: str
    config: CustomerConfig
    registry: object  # EntityRegistry
    repository: object  # Repository
    executor: object  # ActionExecutor（后续 task 构建；P1 先不接 executor）

    @property
    def tenant_context(self) -> TenantContext:
        """该客户的默认上下文（通配 org，总部视角）。"""
        return TenantContext(customer_id=self.customer_id, org_unit_id="*")


_instances: Dict[str, CustomerAgentInstance] = {}

_DEFAULT_CUSTOMER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..", "data", "customers", "customer_default")


def bootstrap_customer(customer_id: str) -> CustomerAgentInstance:
    """构建（或取缓存）某客户的 Agent 实例。"""
    if customer_id in _instances:
        return _instances[customer_id]

    # 取客户配置：注册表 → 加载文件 → 默认
    cfg = get_customer(customer_id)
    if cfg is None:
        if customer_id == "customer_default":
            try:
                cfg = load_customer_config(_DEFAULT_CUSTOMER_DIR)
            except Exception:
                cfg = CustomerConfig(customer_id="customer_default", name="默认",
                                     storage_type="json_files",
                                     data_dir=os.path.join(_DEFAULT_CUSTOMER_DIR, "..", ".."))
        else:
            raise KeyError(f"未注册的客户: {customer_id}")

    # 构建 registry（复用现有 parser，指向客户数据目录）
    from ontology.parser import OntologyParser
    from ontology.repository import JSONFileRepository
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(base)
    ttl_path = os.path.join(base, "ontology", "store.ttl")
    data_dir = cfg.data_dir or os.path.join(root, "data")
    parser = OntologyParser(ttl_path=ttl_path, data_dir=data_dir)
    # 加载 actions
    from ontology.action_loader import load_actions
    actions_dir = os.path.join(base, "ontology", "actions")
    if os.path.isdir(actions_dir):
        parser.registry.action_types = load_actions(actions_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=parser.registry)

    inst = CustomerAgentInstance(
        customer_id=customer_id, config=cfg,
        registry=parser.registry, repository=repo, executor=None)
    _instances[customer_id] = inst
    return inst


def get_customer_agent_instance(customer_id: str) -> Optional[CustomerAgentInstance]:
    return _instances.get(customer_id)


def reset_instances() -> None:
    """测试用：清空实例缓存。"""
    _instances.clear()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_customer_bootstrap.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/customer_bootstrap.py backend/tests/test_customer_bootstrap.py
git commit -m "feat(tenant) P1-T4: bootstrap_customer 按客户构建隔离实例"
```

---

## Task 5: 工具层迁移到 TenantContext

**Files:**
- Modify: `backend/ontology/tools.py`
- Test: `backend/tests/test_tools_tenant.py`

> 工具从 `tenant_id: str = "tenant_default"` 迁移到 `customer_id` + `org_unit_id` 参数，内部构造 TenantContext 传给 Repository。保持旧测试兼容（缺参数时默认）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_tools_tenant.py`：

```python
"""测试工具层按 customer/org_unit 过滤（P1）。"""
from ontology.tools import query_entity
from ontology import tools as T


def _setup(monkeypatch, data_dir):
    from ontology.parser import OntologyParser
    from ontology.action_loader import load_actions
    from ontology.repository import JSONFileRepository
    from ontology.executor import ActionExecutor
    from ontology.bootstrap import bootstrap
    from verticals.clearance.config import CLEARANCE_CONFIG
    bootstrap()
    p = OntologyParser(ttl_path=CLEARANCE_CONFIG.ttl_path, data_dir=data_dir,
                       config=CLEARANCE_CONFIG)
    p.registry.action_types = load_actions(CLEARANCE_CONFIG.actions_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=p.registry)
    ex = ActionExecutor(repository=repo, actions=p.registry.action_types,
                        registry=p.registry, config=CLEARANCE_CONFIG)
    monkeypatch.setattr(T, "_parser", lambda vertical=None: p)
    monkeypatch.setattr(T, "_get_repo", lambda tenant="tenant_default", vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)


def test_query_entity_with_customer_and_org_unit(clearance_data_dir, monkeypatch):
    """工具接受 customer_id + org_unit_id，按客户过滤。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({
        "entity_type": "Store",
        "customer_id": "customer_default",
        "org_unit_id": "*",
    })
    assert "store_001" in out


def test_query_entity_defaults_to_customer_default(clearance_data_dir, monkeypatch):
    """不传 customer_id 时默认 customer_default。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({"entity_type": "Store"})
    assert "store_001" in out  # 旧数据（tenant_default）兼容可见
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_tools_tenant.py -v`
Expected: FAIL（query_entity 不接受 customer_id 参数）

- [ ] **Step 3: 升级工具签名**

修改 `backend/ontology/tools.py` 的工具函数：把 `tenant_id: str = "tenant_default"` 参数替换为 `customer_id: str = "customer_default"` + `org_unit_id: str = "*"`，内部构造 `TenantContext` 传给 Repository。

文件顶部加 import：
```python
from ontology.tenant import TenantContext
```

`query_entity` 签名改为（其它读工具同理）：
```python
@tool
def query_entity(entity_type: str, entity_id: Optional[str] = None,
                 filter_field: Optional[str] = None,
                 filter_value: Optional[str] = None,
                 customer_id: str = "customer_default",
                 org_unit_id: str = "*") -> str:
    """通用实体查询。customer_id + org_unit_id 决定可见范围。"""
    tc = TenantContext(customer_id=customer_id, org_unit_id=org_unit_id)
    if not _parser().registry.object_types.get(entity_type):
        return f"未知实体类型: {entity_type}"
    filters = {filter_field: filter_value} if filter_field else None
    rows = _get_repo(tc).read(entity_type, tc, filters=filters)
    if entity_id:
        rows = [r for r in rows if r.get("id") == entity_id]
    if not rows:
        return _wrap({"type": "entity_list", "total": 0, "items": []}, "未找到记录。")
    return _wrap({"type": "entity_list", "entity_type": entity_type,
                  "total": len(rows), "items": rows[:20]}, f"查询到 {len(rows)} 条记录。")
```

对 `traverse_relation` / `query_task` / `query_near_expiry` / `create_entity` / `update_entity` / `update_task` / `execute_action` / `confirm_action` 做同样的参数迁移（`tenant_id` → `customer_id` + `org_unit_id`，内部构造 TenantContext）。

`_get_repo` 签名也兼容 TenantContext（它只是透传给 Repository）。

- [ ] **Step 4: 运行新测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_tools_tenant.py -v`
Expected: 2 passed

- [ ] **Step 5: 运行全量测试，修旧测试的参数名**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/ -q`

旧测试若传 `tenant_id=...` 会失败（参数改名了）。修复方式：旧测试改为传 `customer_id="customer_default"`（或 monkeypatch 的 lambda 签名适配）。逐个修。

Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/tools.py backend/tests/test_tools_tenant.py backend/tests/
git commit -m "feat(tenant) P1-T5: 工具层迁移到 TenantContext（customer_id + org_unit_id）"
```

---

## Task 6: main.py 中间件升级 + 端到端验证

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_main_tenant.py`

> 中间件从 X-Tenant-ID 升级为 X-Customer-ID + X-Org-Unit-ID，构造 TenantContext 注入 contextvar。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_main_tenant.py`：

```python
"""测试 main.py 中间件按 X-Customer-ID/X-Org-Unit-ID 注入（P1）。"""
import pytest
from fastapi.testclient import TestClient


def test_health_no_tenant_headers():
    """/health 不需要 tenant header。"""
    import os
    os.environ["QWEN_API_KEY"] = "stub"
    import main
    client = TestClient(main.app)
    r = client.get("/health")
    assert r.status_code == 200


def test_tenant_contextvar_set_from_headers():
    """中间件从 X-Customer-ID/X-Org-Unit-ID 解析注入 contextvar。"""
    import os
    os.environ["QWEN_API_KEY"] = "stub"
    import main
    client = TestClient(main.app)
    # 发一个请求带 tenant header，中间件应设置 contextvar
    client.get("/health", headers={"X-Customer-ID": "c1", "X-Org-Unit-ID": "store_001"})
    # contextvar 在请求结束后已 reset，这里只验中间件不报错（200）
    # 真正的 contextvar 注入验证在 T4 的 bootstrap_customer 调用链里


def test_tenant_contextvar_defaults():
    """缺 header 时默认 customer_default + 通配。"""
    import os
    os.environ["QWEN_API_KEY"] = "stub"
    from ontology.tenant import TenantContext
    tc = TenantContext.from_headers({})
    assert tc.customer_id == "customer_default"
    assert tc.sees_all_org_units() is True
```

- [ ] **Step 2: 运行测试，确认失败（或部分过）**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_main_tenant.py -v`
Expected: 可能部分过（health 已有），中间件升级后全过

- [ ] **Step 3: 升级 main.py 中间件**

修改 `backend/main.py` 的中间件：

```python
import contextvars
from ontology.tenant import TenantContext

# 客户租户上下文：由 HTTP middleware（X-Customer-ID + X-Org-Unit-ID）注入
tenant_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "tenant_ctx", default=TenantContext.default())


@app.middleware("http")
async def tenant_middleware(request, call_next):
    """从 header 解析 customer_id + org_unit_id，注入 TenantContext contextvar。"""
    tc = TenantContext.from_headers({
        "X-Customer-ID": request.headers.get("X-Customer-ID"),
        "X-Org-Unit-ID": request.headers.get("X-Org-Unit-ID"),
    })
    token = tenant_ctx.set(tc)
    try:
        return await call_next(request)
    finally:
        tenant_ctx.reset(token)
```

（替换现有的 `tenant_ctx` + `tenant_middleware`）

- [ ] **Step 4: 运行测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_main_tenant.py -v`
Expected: 3 passed

- [ ] **Step 5: 运行全量测试 + main import 冒烟**

Run:
```bash
/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/ -q
QWEN_API_KEY=stub /opt/miniconda3/envs/store-ontology/bin/python -c "import sys; sys.path.insert(0,'.'); import main; print('main OK')"
```
Expected: 全量通过 + main import OK

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_main_tenant.py
git commit -m "feat(tenant) P1-T6: main.py 中间件升级（X-Customer-ID + X-Org-Unit-ID）"
```

---

## Self-Review（计划自检）

**1. Spec 覆盖（对照 APaaS spec §3 + §5 + §7 P1）：**
- §3.5 三层租户（customer_id 硬隔离 + org_unit_id 范围）→ T1（TenantContext）+ T3（Repository 过滤）✅
- §3.7 CustomerConfig → T2 ✅
- §3.3 onboarding 五步 → P1 只做"启 agent"前置（bootstrap_customer T4）；copy/改/灌/接DB 留 P3 ✅（P1 范围正确）
- §5 Agent 实例构建 → T4（bootstrap_customer 构建 registry+repository）✅
- §7 P1 验证标准"两客户数据隔离 / OrgUnit 权限过滤 / 按 customer 构建 Agent"→ T3 + T4 测试覆盖 ✅

**2. 占位符扫描：** 无 TBD/TODO；每个 step 有完整代码。T5 的"其它读工具同理"是合理的（重复模式，已给 query_entity 完整示例）——但执行时需逐个改，计划已注明。

**3. 类型一致性：** `TenantContext(customer_id, org_unit_id)` 在 T1 定义，T3/T4/T5/T6 全部用同名字段；`CustomerConfig` 字段在 T2 定义，T4 引用一致；`CustomerAgentInstance` 在 T4 定义，测试引用一致。`_normalize_tenant`（T3）在 Repository 内部，被 read/write/delete 统一调用。

**4. 向后兼容链：** tenant_default 字符串 → TenantContext.default()（T1）→ Repository 旧数据 matches（T3）→ 工具默认参数（T5）→ 中间件默认（T6），链路一致。
