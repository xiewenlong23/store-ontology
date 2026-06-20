# 临期出清 MVP 本体重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把临期出清场景从"单轮 demo 建模"重构为符合《业务本体建模规范》的可治理跨天流程：Repository 多租户抽象 + 元数据完整本体 + 8 个 YAML Action 契约 + 瘦路由器执行器 + Task 状态机 + 折扣单一事实源。

**Architecture:** 分四层依赖递进——(1) 存储与数据模型地基（Repository / schemas），(2) 本体定义与解析（TTL / parser / Action YAML loader），(3) 业务逻辑（discount 单一事实源 / 状态机 / preview cache / ActionExecutor），(4) Tool 薄封装与 Agent 接线。所有业务逻辑写成纯 Python（可单测），`@tool` 函数只做薄封装；不写任何依赖 LLM/外部 API 的单测。

**Tech Stack:** Python ≥3.11、FastAPI、Pydantic v2、langchain-core(@tool)、pytest（TDD）、fcntl 文件锁、YAML（PyYAML，已随 deepagents 间接安装，需在 deps 确认）。

**依据：**
- 设计：`docs/superpowers/specs/2026-06-20-clearance-ontology-remodel.md`（下称"建模文档"）
- 规范：`docs/业务本体建模规范.md`
- 架构：`docs/superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md`（下称"架构 spec"）

**重要约定（贯穿全计划）：**
- 后端运行目录 = `backend/`。`main.py` 已 `sys.path.insert(0, backend/)`，故 import 形如 `from ontology.xxx import`、`from models.schemas import`。测试同样以 `backend/` 为根。
- 数据目录 = 项目根 `data/`（即 `backend/../data`）。
- 折扣语义 = **减扣百分比 int（0-100）**，50 表示五折。
- 禁止 `eval`；所有副作用 transform 用结构化操作（见 Task 8）。

---

## File Structure

| 文件 | 职责 | 任务 |
|---|---|---|
| `backend/tests/conftest.py` | sys.path 注入 + 临时数据目录 fixture | T1 |
| `backend/ontology/repository.py` | `Repository` 抽象 + `JSONFileRepository`（多租户过滤/文件锁/原子写/edits-only 检查） | T2 |
| `backend/models/schemas.py` | 重写：新枚举、Task 字段重命名、删 LinkTypes、加 LossReport | T3 |
| `backend/ontology/store.ttl` | 重写：7 Object + 10 Link + 新元数据谓词 | T4 |
| `backend/ontology/parser.py` | 扩展：解析 `status`/`visibility`/`edits_only_via_actions` | T5 |
| `backend/ontology/actions/*.yaml` | 8 个 Action 契约 | T6 |
| `backend/ontology/action_loader.py` | 加载 YAML → `ActionDefinition` | T7 |
| `backend/business/discount.py` | `calculate_discount` 单一事实源 | T8 |
| `backend/data/discount_rules.json` | 迁移：乘数→减扣百分比（种子数据，复制到 `data/`） | T8 |
| `backend/ontology/state_machine.py` | `TASK_TRANSITIONS` + `is_valid_transition` | T9 |
| `backend/ontology/preview_cache.py` | preview 记录 + TTL | T10 |
| `backend/ontology/executor.py` | `ActionExecutor` 瘦路由器（核心） | T11 |
| `backend/ontology/tools.py` | 重写：薄封装走 Repository + Executor | T12 |
| `backend/ontology/errors.py` | 自定义异常 | T2 |
| `data/tasks.json`、`data/clearance_tasks.json`、`data/discount_rules.json` | 种子迁移 / 清理 | T13 |
| `backend/skills/...` | 重写 SKILL.md、修双层目录 | T14 |
| `backend/main.py` | tenant 上下文注入、prompt 组装 | T15 |
| `frontend/...` | tenant 选择器 + route.ts header（独立子系统） | T16 |

---

## Task 1: 测试脚手架

**Files:**
- Create: `backend/tests/__init__.py`（空）
- Create: `backend/tests/conftest.py`
- Modify: `backend/pyproject.toml`（加 pytest 配置 + PyYAML 依赖）

- [ ] **Step 1: 加 pytest 配置与 PyYAML 依赖**

修改 `backend/pyproject.toml`，在 `dependencies` 数组末尾加 `"pyyaml>=6.0"`，并在文件末尾追加：

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: 写 conftest**

创建 `backend/tests/conftest.py`：

```python
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

import pytest

# 以 backend/ 为 sys.path 根，使 from ontology... / from models... 可用
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def tmp_data_dir(tmp_path):
    """提供一个空数据目录 + 基础 stores.json，供 Repository 测试用。"""
    stores = [{
        "id": "store_001", "name": "测试门店", "region_id": "region_001",
        "address": "测试地址", "manager_id": "emp_001",
        "created_at": "2024-01-01T00:00:00",
    }]
    (tmp_path / "stores.json").write_text(json.dumps(stores, ensure_ascii=False), encoding="utf-8")
    return str(tmp_path)
```

- [ ] **Step 3: 验证 pytest 可运行**

Run（在 `backend/` 下）: `python -m pytest tests/ -v`
Expected: `no tests ran`（无报错，说明脚手架与 import 链路通）。

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/tests/
git commit -m "test: 初始化 pytest 脚手架与 conftest"
```

---

## Task 2: Repository 抽象 + JSONFileRepository

**Files:**
- Create: `backend/ontology/errors.py`
- Create: `backend/ontology/repository.py`
- Test: `backend/tests/test_repository.py`

- [ ] **Step 1: 写错误类型**

创建 `backend/ontology/errors.py`：

```python
class OntologyError(Exception):
    """本体相关错误基类。"""


class EntityNotFoundError(OntologyError):
    pass


class ActionRequiredError(OntologyError):
    """对 edits-only-via-actions 实体直接写时抛出。"""


class ValidationError(OntologyError):
    pass
```

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_repository.py`：

```python
import json
from ontology.repository import JSONFileRepository
from ontology.parser import ObjectType, PropertyDef, EntityRegistry
from ontology.errors import ActionRequiredError


def _registry_with(managed: bool):
    """构造一个最小 registry：Store（managed 可控）+ 一个自由类型 Region。"""
    store = ObjectType(
        id="Store", label="门店", label_zh="门店", comment="",
        properties=[PropertyDef(name="id", type="string")],
        storage_file="stores.json", status="active",
        edits_only_via_actions=managed,
    )
    reg = EntityRegistry()
    reg.object_types = {"Store": store}
    return reg


def test_read_filters_by_tenant(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    rows = repo.read("Store", tenant_id="tenant_default")
    assert len(rows) == 1
    assert rows[0]["id"] == "store_001"


def test_read_one_missing_returns_none(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    assert repo.read_one("Store", "tenant_default", "nope") is None


def test_write_stamps_tenant(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    repo.write("Store", "tenant_default",
               {"id": "store_002", "name": "新店"}, create=True)
    assert repo.read_one("Store", "tenant_default", "store_002")["tenant_id"] == "tenant_default"


def test_write_blocked_when_edits_only(tmp_data_dir):
    reg = _registry_with(managed=True)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    try:
        repo.write("Store", "tenant_default", {"id": "store_002"}, create=True)
        assert False, "应抛 ActionRequiredError"
    except ActionRequiredError:
        pass


def test_write_bypass_for_executor(tmp_data_dir):
    reg = _registry_with(managed=True)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    repo.write("Store", "tenant_default", {"id": "store_002"}, create=True,
               bypass_action_check=True)
    assert repo.read_one("Store", "tenant_default", "store_002") is not None


def test_tenant_isolation(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    repo.write("Store", "tenant_b", {"id": "store_002"}, create=True)
    assert len(repo.read("Store", "tenant_default")) == 1
    assert len(repo.read("Store", "tenant_b")) == 1
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'ontology.repository'`）。

- [ ] **Step 4: 实现 Repository**

创建 `backend/ontology/repository.py`：

```python
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
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python -m pytest tests/test_repository.py -v`
Expected: 6 passed。

> 注意：Task 2 的测试用了一个临时构造的 `ObjectType(..., edits_only_via_actions=...)`，该字段在 Task 5 才正式加到 dataclass。**本步骤需要先把 `parser.py` 的 `ObjectType` dataclass 补上字段**才能 import 通过——在 Step 4 之后、Step 5 之前，临时给 `backend/ontology/parser.py` 的 `ObjectType` 加上 `status: str = "active"`、`visibility: str = "normal"`、`edits_only_via_actions: bool = False` 三个字段（Task 5 会系统化处理 parser，这里先打通）。完成本任务后再进 Task 5。

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/errors.py backend/ontology/repository.py backend/ontology/parser.py backend/tests/test_repository.py
git commit -m "feat: Repository 抽象层 + JSONFileRepository（多租户/锁/原子写/edits-only）"
```

---

## Task 3: 重写 schemas.py（枚举与模型对齐）

**Files:**
- Modify: `backend/models/schemas.py`（整文件重写）
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_schemas.py`：

```python
import pytest
from pydantic import ValidationError
from models.schemas import (
    Task, NearExpiryProduct, LossReport,
    TaskStatus, NearExpiryProductStatus, TaskType, LossReportStatus,
)


def test_task_uses_task_type_not_type():
    t = Task(id="t1", task_type=TaskType.CLEARANCE, target_id="ne_1",
             store_id="s1", assignee_id="e1")
    assert t.task_type == TaskType.CLEARANCE
    assert t.status == TaskStatus.CREATED
    assert not hasattr(t, "type") or t.__fields__ and "type" not in t.__fields__


def test_task_default_quantities_zero():
    t = Task(id="t1", task_type=TaskType.CLEARANCE, target_id="ne_1",
             store_id="s1", assignee_id="e1", discount_percent=30, planned_quantity=10)
    assert t.sold_quantity == 0


def test_discount_percent_range():
    with pytest.raises(ValidationError):
        Task(id="t1", task_type=TaskType.CLEARANCE, target_id="ne_1",
             store_id="s1", assignee_id="e1", discount_percent=150, planned_quantity=10)


def test_near_expiry_status_enum():
    ne = NearExpiryProduct(
        id="ne_1", product_id="p1", store_id="s1", batch_no="b1",
        production_date="2026-06-01", expiry_date="2026-06-10",
        stock_quantity=10, days_left=5, discount_tier="T2",
        status=NearExpiryProductStatus.EXPIRING)
    assert ne.status == NearExpiryProductStatus.EXPIRING


def test_loss_report_requires_task_link():
    lr = LossReport(id="lr_1", task_id="t1", target_id="ne_1",
                    loss_quantity=3, loss_value=13.5, loss_reason="过期")
    assert lr.status == LossReportStatus.PENDING
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: FAIL（旧 `Task.type`、缺 `LossReport`、枚举名不符）。

- [ ] **Step 3: 重写 schemas.py**

整文件替换 `backend/models/schemas.py`：

```python
"""本体模型定义 - Pydantic Schemas（对齐 store.ttl，见建模规范 §7.3）。"""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ============ Enums ============

class EmployeeRole(str, Enum):
    CLERK = "clerk"
    MANAGER = "manager"
    ADMIN = "admin"


class DiscountTier(str, Enum):
    T1 = "T1"   # 即将过期
    T2 = "T2"   # 中期临期
    T3 = "T3"   # 初期临期


class NearExpiryProductStatus(str, Enum):
    EXPIRING = "expiring"
    CLEARANCE = "clearance"
    SOLD_OUT = "sold_out"
    EXPIRED = "expired"
    SCRAPPED = "scrapped"


class TaskStatus(str, Enum):
    CREATED = "created"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SCRAPPED = "scrapped"


class TaskType(str, Enum):
    CLEARANCE = "clearance"
    TRANSFER = "transfer"
    RESTOCK = "restock"


class LossReportStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============ Object Types ============

class Region(BaseModel):
    id: str
    name: str
    code: str


class Store(BaseModel):
    id: str
    name: str
    region_id: str
    address: str
    manager_id: str
    created_at: datetime = Field(default_factory=datetime.now)


class Employee(BaseModel):
    id: str
    name: str
    store_id: str
    role: EmployeeRole
    phone: str


class Product(BaseModel):
    id: str
    name: str
    category: str
    brand: str
    unit: str
    cost_price: float           # 单位：元
    retail_price: float         # 单位：元


class NearExpiryProduct(BaseModel):
    id: str
    product_id: str
    store_id: str
    batch_no: str
    production_date: date
    expiry_date: date
    stock_quantity: int         # 单位：件
    days_left: int              # 单位：天
    discount_tier: DiscountTier
    status: NearExpiryProductStatus

    def calc_days_left(self) -> int:
        return (self.expiry_date - date.today()).days


class Task(BaseModel):
    """出清任务（受治理工作流载体）。"""
    id: str
    task_type: TaskType
    target_id: str
    store_id: str
    assignee_id: str
    status: TaskStatus = TaskStatus.CREATED
    discount_percent: int = Field(0, ge=0, le=100, description="减扣百分比(0-100)，50=五折")
    planned_quantity: int = Field(0, ge=0, description="件")
    sold_quantity: int = Field(0, ge=0, description="件")
    params_json: dict = Field(default_factory=dict)
    result_json: dict = Field(default_factory=dict)
    priority: Priority = Priority.MEDIUM
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class LossReport(BaseModel):
    """报损单。"""
    id: str
    task_id: str
    target_id: str
    loss_quantity: int = Field(..., ge=0, description="件")
    loss_value: float = Field(..., ge=0, description="元")
    loss_reason: str
    status: LossReportStatus = LossReportStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
```

> 删除了旧 `ActionType` 枚举（被 `TaskType` 取代，Action 现由 YAML 加载）与旧 `LinkTypes` 常量类（违反建模规范 §7.3，与 TTL 不一致）。删除旧 `Task` 的 `type` 字段（违反命名规范，无业务含义）。

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/models/schemas.py backend/tests/test_schemas.py
git commit -m "refactor: schemas 对齐规范（新枚举/Task 字段重命名/LossReport/删 LinkTypes）"
```

---

## Task 4: 重写 store.ttl（7 Object + 10 Link + 元数据）

**Files:**
- Modify: `backend/ontology/store.ttl`（整文件重写）

> 这是数据文件，无单测；用 Task 5 的 parser 测试间接覆盖。本任务只改 TTL，T5 才能让解析通过。

- [ ] **Step 1: 整文件替换 `backend/ontology/store.ttl`**

```ttl
@prefix store: <http://example.org/store-ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# ============================================================
# Object Types（7 个）—— 元数据谓词：status / visibility / edits_only_via_actions
# ============================================================

store:Region a rdfs:Class ;
    rdfs:label "区域"@zh , "Region"@en ;
    rdfs:comment "地理区域，组织门店"@zh ;
    store:properties "id:string,name:string,code:string" ;
    store:storage "regions.json" ;
    store:status "active" .

store:Store a rdfs:Class ;
    rdfs:label "门店"@zh , "Store"@en ;
    rdfs:comment "零售门店"@zh ;
    store:properties "id:string,name:string,region_id:string,address:string,manager_id:string,created_at:datetime" ;
    store:storage "stores.json" ;
    store:status "active" .

store:Employee a rdfs:Class ;
    rdfs:label "员工"@zh , "Employee"@en ;
    rdfs:comment "门店员工"@zh ;
    store:properties "id:string,name:string,store_id:string,role:EmployeeRole,phone:string" ;
    store:storage "employees.json" ;
    store:status "active" .

store:Product a rdfs:Class ;
    rdfs:label "商品"@zh , "Product"@en ;
    rdfs:comment "销售商品"@zh ;
    store:properties "id:string,name:string,category:string,brand:string,unit:string,cost_price:float,retail_price:float" ;
    store:storage "products.json" ;
    store:status "active" .

store:NearExpiryProduct a rdfs:Class ;
    rdfs:label "临期商品"@zh , "Near Expiry Product"@en ;
    rdfs:comment "即将过期的商品批次实例，出清标的物"@zh ;
    store:properties "id:string,product_id:string,store_id:string,batch_no:string,production_date:date,expiry_date:date,stock_quantity:int,days_left:int,discount_tier:DiscountTier,status:NearExpiryProductStatus" ;
    store:storage "near_expiry_products.json" ;
    store:status "active" ;
    store:edits_only_via_actions "true" .

store:Task a rdfs:Class ;
    rdfs:label "出清任务"@zh , "Task"@en ;
    rdfs:comment "受治理工作流的载体。一次出清从建单到完成/报损的完整记录"@zh ;
    store:properties "id:string,task_type:TaskType,target_id:string,store_id:string,assignee_id:string,status:TaskStatus,discount_percent:int,planned_quantity:int,sold_quantity:int,params_json:dict,result_json:dict,priority:Priority,notes:string,created_at:datetime,started_at:datetime,completed_at:datetime" ;
    store:storage "tasks.json" ;
    store:status "active" ;
    store:visibility "prominent" ;
    store:edits_only_via_actions "true" .

store:LossReport a rdfs:Class ;
    rdfs:label "报损单"@zh , "Loss Report"@en ;
    rdfs:comment "到期未售罄的报损记录，由 create_loss_report 创建"@zh ;
    store:properties "id:string,task_id:string,target_id:float,loss_quantity:int,loss_value:float,loss_reason:string,status:LossReportStatus,created_at:datetime" ;
    store:storage "loss_reports.json" ;
    store:status "active" ;
    store:edits_only_via_actions "true" .

# ============================================================
# Link Types（10 个）—— via 归属见建模规范 §4.3
# ============================================================

store:located_in a rdfs:Property ;
    rdfs:label "位于"@zh , "located in"@en ;
    rdfs:comment "Store 通过 region_id（domain 侧）归属到 Region"@zh ;
    rdfs:domain store:Store ; rdfs:range store:Region ; store:via "region_id" .

store:has_employee a rdfs:Property ;
    rdfs:label "拥有员工"@zh , "has employee"@en ;
    rdfs:comment "Store 的员工集合。via store_id 在 Employee（range 侧）上，指回 Store"@zh ;
    rdfs:domain store:Store ; rdfs:range store:Employee ; store:via "store_id" .

store:has_near_expiry a rdfs:Property ;
    rdfs:label "拥有临期商品"@zh , "has near expiry product"@en ;
    rdfs:comment "Store 的临期商品集合。via store_id 在 NearExpiryProduct（range 侧）上"@zh ;
    rdfs:domain store:Store ; rdfs:range store:NearExpiryProduct ; store:via "store_id" .

store:is_instance_of a rdfs:Property ;
    rdfs:label "是...的实例"@zh , "is instance of"@en ;
    rdfs:comment "NearExpiryProduct 通过 product_id（domain 侧）指向 Product"@zh ;
    rdfs:domain store:NearExpiryProduct ; rdfs:range store:Product ; store:via "product_id" .

store:manages a rdfs:Property ;
    rdfs:label "管理"@zh , "manages"@en ;
    rdfs:comment "门店通过 manager_id（domain 侧）指向其店长 Employee。修正旧版反向 bug"@zh ;
    rdfs:domain store:Store ; rdfs:range store:Employee ; store:via "manager_id" .

store:has_task a rdfs:Property ;
    rdfs:label "有任务"@zh , "has task"@en ;
    rdfs:comment "Store 的任务集合。via store_id 在 Task（range 侧）上"@zh ;
    rdfs:domain store:Store ; rdfs:range store:Task ; store:via "store_id" .

store:created_for a rdfs:Property ;
    rdfs:label "针对"@zh , "created for"@en ;
    rdfs:comment "Task 通过 target_id（domain 侧）指向被操作的 NearExpiryProduct"@zh ;
    rdfs:domain store:Task ; rdfs:range store:NearExpiryProduct ; store:via "target_id" .

store:assigned_to a rdfs:Property ;
    rdfs:label "指派给"@zh , "assigned to"@en ;
    rdfs:comment "Task 通过 assignee_id（domain 侧）指向执行人 Employee"@zh ;
    rdfs:domain store:Task ; rdfs:range store:Employee ; store:via "assignee_id" .

store:has_loss_report a rdfs:Property ;
    rdfs:label "产生报损单"@zh , "has loss report"@en ;
    rdfs:comment "Task 的报损单。via task_id 在 LossReport（range 侧）上"@zh ;
    rdfs:domain store:Task ; rdfs:range store:LossReport ; store:via "task_id" .

store:written_off a rdfs:Property ;
    rdfs:label "核销"@zh , "written off"@en ;
    rdfs:comment "LossReport 通过 target_id（domain 侧）指向被核销的 NearExpiryProduct"@zh ;
    rdfs:domain store:LossReport ; rdfs:range store:NearExpiryProduct ; store:via "target_id" .
```

> 注意：`LossReport.target_id` 在 TTL 里我误标为 `target_id:float`——应为 `target_id:string`。**在写完后立即用 sed/编辑修正为 `target_id:string`**（下面 Step 2）。

- [ ] **Step 2: 修正 LossReport.target_id 类型**

把 `store:properties "id:string,task_id:string,target_id:float,loss_quantity:int...` 中的 `target_id:float` 改为 `target_id:string`。

- [ ] **Step 3: Commit**

```bash
git add backend/ontology/store.ttl
git commit -m "feat: 重写 store.ttl（7 Object+元数据/10 Link/修 manages 方向）"
```

---

## Task 5: 扩展 parser（新元数据谓词）

**Files:**
- Modify: `backend/ontology/parser.py`
- Test: `backend/tests/test_parser.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_parser.py`：

```python
from ontology.parser import OntologyParser


def test_parses_all_object_types():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    ids = set(p.registry.object_types.keys())
    assert {"Store", "NearExpiryProduct", "Task", "LossReport"}.issubset(ids)


def test_edits_only_flag_parsed():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    assert p.registry.object_types["NearExpiryProduct"].edits_only_via_actions is True
    assert p.registry.object_types["Store"].edits_only_via_actions is False


def test_status_parsed():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    assert p.registry.object_types["Task"].status == "active"
    assert p.registry.object_types["Task"].visibility == "prominent"


def test_link_count_and_manages_direction():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    assert len(p.registry.link_types) == 10
    m = p.registry.link_types["manages"]
    assert m.domain == "Store" and m.range == "Employee"  # 修正后方向


def test_new_links_present():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    for name in ["assigned_to", "has_loss_report", "written_off"]:
        assert name in p.registry.link_types
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_parser.py -v`
Expected: FAIL（元数据未解析、Object 数量/方向不符）。

- [ ] **Step 3: 重写 parser 的 dataclass 与解析逻辑**

整文件替换 `backend/ontology/parser.py`（注意：Action 解析移除——Action 改由 YAML loader 负责，T5/T7）：

```python
"""
本体解析器 —— 从 TTL 读取 Object/Link Type 定义，构建 EntityRegistry。
Action Type 不再在 TTL 定义，改由 ontology/actions/*.yaml 加载（见 action_loader.py）。
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def _to_bool(s: str) -> bool:
    return str(s).strip().lower() in ("true", "1", "yes")


@dataclass
class PropertyDef:
    name: str
    type: str


@dataclass
class ObjectType:
    id: str
    label: str
    comment: str
    properties: List[PropertyDef]
    storage_file: str
    label_zh: str = ""
    status: str = "active"
    visibility: str = "normal"
    edits_only_via_actions: bool = False


@dataclass
class LinkType:
    id: str
    label: str
    domain: str
    range: str
    via: str
    label_zh: str = ""
    comment: str = ""


@dataclass
class EntityRegistry:
    object_types: Dict[str, ObjectType] = field(default_factory=dict)
    link_types: Dict[str, LinkType] = field(default_factory=dict)
    action_types: Dict[str, dict] = field(default_factory=dict)  # 由 action_loader 填充


class OntologyParser:
    PREFIX = "store:"
    BOOLEAN_PROPS = {"edits_only_via_actions"}

    def __init__(self, ttl_path: str, data_dir: str):
        self.ttl_path = Path(ttl_path)
        self.data_dir = Path(data_dir)
        self.registry = EntityRegistry()
        self._parse()

    # ---- 通用：把 "key value ;" 片段抽成 dict ----
    @staticmethod
    def _extract_props(block: str) -> Dict[str, str]:
        out = {}
        # 形如 store:status "active" 或 store:via "x" 或 rdfs:label "a"@zh , "b"@en
        for m in re.finditer(r'(?:store|rdfs):(\w+)\s+("[^"]*"(?:@zh)?)', block):
            key, val = m.group(1), m.group(2)
            out.setdefault(key, val.strip('"').split('"')[0])
        return out

    def _parse(self):
        content = self.ttl_path.read_text(encoding="utf-8")
        # 按句号分块（粗粒度，足够当前 TTL 结构）
        blocks = re.split(r'\n\s*\.\s*\n', content)
        P = self.PREFIX

        # Object Types: store:X a rdfs:Class ;
        for m in re.finditer(
            rf'{P}(\w+)\s+a\s+rdfs:Class\s*;\s*(.*?)(?=\n\s*\.\s*\n|\Z)',
            content, re.DOTALL
        ):
            obj_id, body = m.group(1), m.group(2)
            label_zh = self._first(r'rdfs:label\s+"([^"]+)"@zh', body)
            label_en = self._first(r'rdfs:label\s+"[^"]+"@zh\s*,\s*"([^"]+)"@en', body)
            comment = self._first(r'rdfs:comment\s+"([^"]*)"@zh', body)
            props_str = self._first(r'properties\s+"([^"]*)"', body)
            storage = self._first(r'storage\s+"([^"]*)"', body)
            status = self._first(r'status\s+"([^"]*)"', body) or "active"
            visibility = self._first(r'visibility\s+"([^"]*)"', body) or "normal"
            edits = _to_bool(self._first(r'edits_only_via_actions\s+"([^"]*)"', body) or "false")
            if not props_str:
                continue
            self.registry.object_types[obj_id] = ObjectType(
                id=obj_id, label=f"{label_zh} ({label_en})", label_zh=label_zh,
                comment=comment, properties=self._parse_properties(props_str),
                storage_file=storage, status=status, visibility=visibility,
                edits_only_via_actions=edits,
            )

        # Link Types: store:X a rdfs:Property ;
        for m in re.finditer(
            rf'{P}(\w+)\s+a\s+rdfs:Property\s*;\s*(.*?)(?=\n\s*\.\s*\n|\Z)',
            content, re.DOTALL
        ):
            link_id, body = m.group(1), m.group(2)
            label_zh = self._first(r'rdfs:label\s+"([^"]+)"@zh', body)
            label_en = self._first(r'rdfs:label\s+"[^"]+"@zh\s*,\s*"([^"]+)"@en', body)
            comment = self._first(r'rdfs:comment\s+"([^"]*)"@zh', body)
            domain = self._first(r'domain\s+%s(\w+)' % P, body)
            range_ = self._first(r'range\s+%s(\w+)' % P, body)
            via = self._first(r'via\s+"([^"]*)"', body)
            if not domain:
                continue
            self.registry.link_types[link_id] = LinkType(
                id=link_id, label=f"{label_zh} ({label_en})", label_zh=label_zh,
                comment=comment, domain=domain, range=range_, via=via,
            )

    @staticmethod
    def _first(pattern: str, text: str) -> Optional[str]:
        m = re.search(pattern, text)
        return m.group(1) if m else None

    def _parse_properties(self, props_str: str) -> List[PropertyDef]:
        result = []
        for prop in props_str.split(","):
            prop = prop.strip()
            if ":" in prop:
                name, ptype = prop.split(":", 1)
                result.append(PropertyDef(name=name.strip(), type=ptype.strip()))
            elif prop:
                result.append(PropertyDef(name=prop, type="string"))
        return result

    def build_system_prompt(self) -> str:
        lines = ["你是门店临期商品管理助手。\n"]
        lines.append("可用实体（用 query_entity 查询）: "
                     + ", ".join(ot.label_zh for ot in self.registry.object_types.values()))
        lines.append("\n关系（用 traverse_relation）: "
                     + ", ".join(f"{lt.label_zh}({lt.domain}->{lt.range})"
                                 for lt in self.registry.link_types.values()))
        lines.append("\n操作（用 execute_action/confirm_action）: "
                     + ", ".join(self.registry.action_types.keys()))
        lines.append("\n用 query_task 查询任务。用中文回复。")
        return "\n".join(lines)


# ============ 单例 ============
_parser_instance = None


def get_ontology_parser(ttl_path: str = None, data_dir: str = None) -> OntologyParser:
    global _parser_instance
    if _parser_instance is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend/
        root = os.path.dirname(base)                                          # 项目根
        ttl_path = ttl_path or os.path.join(base, "ontology", "store.ttl")
        data_dir = data_dir or os.path.join(root, "data")
        _parser_instance = OntologyParser(ttl_path, data_dir)
    return _parser_instance
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_parser.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/parser.py backend/tests/test_parser.py
git commit -m "feat: parser 扩展元数据谓词 + Link/Object 重解析（Action 改 YAML）"
```

---

## Task 6: 创建 8 个 Action YAML 契约

**Files:**
- Create: `backend/ontology/actions/create_clearance_task.yaml`
- Create: `backend/ontology/actions/submit_for_approval.yaml`
- Create: `backend/ontology/actions/approve_clearance.yaml`
- Create: `backend/ontology/actions/accept_task.yaml`
- Create: `backend/ontology/actions/print_labels.yaml`
- Create: `backend/ontology/actions/deduct_stock.yaml`
- Create: `backend/ontology/actions/complete_task.yaml`
- Create: `backend/ontology/actions/create_loss_report.yaml`

> YAML 即契约本身（见建模文档 §5）。本任务为文件创建，无单测；Task 7 的 loader 测试会加载它们。
> **副作用格式约定（执行器实现见 Task 11）**：
> - 字段值中 `$name` → 取 params[name]；其余为字面量。
> - `match: {id: $task_id}` → 定位目标记录。
> - `fields` → 整字段覆盖；`transforms` → 结构化增减：`{op: increment|decrement|set, field, by: $x}`。

- [ ] **Step 1-8: 逐个创建 YAML（每个一条命令即可，内容见建模文档 §5.1-§5.8，**transform 改为结构化格式**）**

创建 `backend/ontology/actions/create_clearance_task.yaml`：

```yaml
api_name: create_clearance_task
display_name: 创建出清任务
description: 为临期商品建出清单，进入 created 态
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]
parameters:
  - { name: target_id,        type: string, required: true }
  - { name: store_id,         type: string, required: true }
  - { name: assignee_id,      type: string, required: true }
  - { name: discount_percent, type: int,    required: true, constraint: "0..100" }
  - { name: planned_quantity, type: int,    required: true, constraint: ">0" }
  - { name: priority,         type: string, required: false, default: medium }
  - { name: notes,            type: string, required: false }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is_not, value: expired,  fail_msg: "已过期商品不能出清" }
    - { field: target.status, operator: is_not, value: scrapped, fail_msg: "已报损商品不能出清" }
side_effects:
  - type: create_object
    object_type: Task
    fields:
      task_type: clearance
      target_id: $target_id
      store_id: $store_id
      assignee_id: $assignee_id
      status: created
      discount_percent: $discount_percent
      planned_quantity: $planned_quantity
      sold_quantity: 0
      priority: $priority
      notes: $notes
  - type: update_object
    object_type: NearExpiryProduct
    match: { id: $target_id }
    fields: { status: clearance }
  - type: notification
    template: clearance_task_created
    recipients: [$assignee_id]
```

创建 `backend/ontology/actions/submit_for_approval.yaml`：

```yaml
api_name: submit_for_approval
display_name: 提交审批
description: 出清任务提交审批，created -> pending_approval
status: active
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id, type: string, required: true }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is, value: created, fail_msg: "仅 created 态可提交审批" }
side_effects:
  - type: state_transition
    object_type: Task
    match: { id: $task_id }
    from: created
    to: pending_approval
  - type: notification
    template: approval_requested
    recipients: []
```

创建 `backend/ontology/actions/approve_clearance.yaml`：

```yaml
api_name: approve_clearance
display_name: 审批通过
description: 审批回调通过任务，pending_approval -> approved（后端自动化调用）
status: active
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id,     type: string, required: true }
  - { name: approver_id, type: string, required: true }
  - { name: comment,     type: string, required: false }
submission_criteria:
  roles: [region_cat_mgr]
  conditions:
    - { field: target.status, operator: is, value: pending_approval, fail_msg: "仅待审批任务可审批" }
side_effects:
  - type: state_transition
    object_type: Task
    match: { id: $task_id }
    from: pending_approval
    to: approved
  - type: notification
    template: clearance_approved
    recipients: []
```

创建 `backend/ontology/actions/accept_task.yaml`：

```yaml
api_name: accept_task
display_name: 接受任务
description: 执行人接单，approved -> accepted
status: active
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id,     type: string, required: true }
  - { name: assignee_id, type: string, required: true }
submission_criteria:
  roles: [store_manager, clerk]
  conditions:
    - { field: target.status, operator: is, value: approved }
side_effects:
  - type: state_transition
    object_type: Task
    match: { id: $task_id }
    from: approved
    to: accepted
```

创建 `backend/ontology/actions/print_labels.yaml`：

```yaml
api_name: print_labels
display_name: 打折签打印
description: 打印折扣签并陈列，accepted -> in_progress
status: active
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id,    type: string, required: true }
  - { name: label_count, type: int,   required: true, constraint: ">0" }
submission_criteria:
  roles: [store_manager, clerk]
  conditions:
    - { field: target.status, operator: is, value: accepted }
side_effects:
  - type: state_transition
    object_type: Task
    match: { id: $task_id }
    from: accepted
    to: in_progress
  - type: external_call
    service: printer
    action: print_discount_labels
```

创建 `backend/ontology/actions/deduct_stock.yaml`：

```yaml
api_name: deduct_stock
display_name: 扣减库存
description: POS 扫码扣库存并累计已售，不改任务状态（后端自动化调用）
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]
parameters:
  - { name: target_id, type: string, required: true }
  - { name: task_id,   type: string, required: true }
  - { name: quantity,  type: int,    required: true, constraint: ">0" }
submission_criteria:
  roles: [system_pos]
  conditions:
    - { field: target.status, operator: is, value: clearance }
    - { field: task.status,   operator: is, value: in_progress }
side_effects:
  - type: update_object
    object_type: NearExpiryProduct
    match: { id: $target_id }
    transforms:
      - { op: decrement, field: stock_quantity, by: $quantity }
  - type: update_object
    object_type: Task
    match: { id: $task_id }
    transforms:
      - { op: increment, field: sold_quantity, by: $quantity }
```

创建 `backend/ontology/actions/complete_task.yaml`：

```yaml
api_name: complete_task
display_name: 完成任务
description: 售罄结单，in_progress -> completed；商品 sold_out
status: active
target_object_type: Task
edits_object_types: [Task, NearExpiryProduct]
parameters:
  - { name: task_id,   type: string, required: true }
  - { name: target_id, type: string, required: true }
submission_criteria:
  roles: [store_manager, system_inventory]
  conditions:
    - { field: target.status, operator: is, value: in_progress }
side_effects:
  - type: state_transition
    object_type: Task
    match: { id: $task_id }
    from: in_progress
    to: completed
  - type: update_object
    object_type: NearExpiryProduct
    match: { id: $target_id }
    fields: { status: sold_out }
```

创建 `backend/ontology/actions/create_loss_report.yaml`：

```yaml
api_name: create_loss_report
display_name: 报损
description: 到期未售罄建报损单，in_progress -> scrapped；商品 scrapped
status: active
target_object_type: Task
edits_object_types: [Task, NearExpiryProduct, LossReport]
parameters:
  - { name: task_id,       type: string, required: true }
  - { name: target_id,     type: string, required: true }
  - { name: loss_quantity, type: int,    required: true, constraint: ">0" }
  - { name: loss_value,    type: float,  required: true, constraint: ">=0" }
  - { name: loss_reason,   type: string, required: true }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is, value: in_progress }
side_effects:
  - type: state_transition
    object_type: Task
    match: { id: $task_id }
    from: in_progress
    to: scrapped
  - type: update_object
    object_type: NearExpiryProduct
    match: { id: $target_id }
    fields: { status: scrapped }
  - type: create_object
    object_type: LossReport
    fields:
      task_id: $task_id
      target_id: $target_id
      loss_quantity: $loss_quantity
      loss_value: $loss_value
      loss_reason: $loss_reason
      status: pending
  - type: notification
    template: loss_report_created
    recipients: []
```

- [ ] **Step 9: Commit**

```bash
git add backend/ontology/actions/
git commit -m "feat: 8 个临期出清 Action YAML 契约"
```

---

## Task 7: ActionLoader

**Files:**
- Create: `backend/ontology/action_loader.py`
- Test: `backend/tests/test_action_loader.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_action_loader.py`：

```python
from ontology.action_loader import load_actions, ActionDefinition


def test_loads_eight_actions():
    actions = load_actions("ontology/actions")
    names = set(actions.keys())
    expected = {"create_clearance_task", "submit_for_approval", "approve_clearance",
                "accept_task", "print_labels", "deduct_stock",
                "complete_task", "create_loss_report"}
    assert expected.issubset(names)


def test_action_definition_fields():
    actions = load_actions("ontology/actions")
    a = actions["create_clearance_task"]
    assert isinstance(a, ActionDefinition)
    assert a.target_object_type == "NearExpiryProduct"
    assert "NearExpiryProduct" in a.edits_object_types
    assert a.submission_criteria["roles"] == ["store_manager", "region_cat_mgr"]


def test_param_constraint_parsed():
    actions = load_actions("ontology/actions")
    disc = [p for p in actions["create_clearance_task"].parameters
            if p["name"] == "discount_percent"][0]
    assert disc["constraint"] == "0..100"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_action_loader.py -v`
Expected: FAIL（无 action_loader 模块）。

- [ ] **Step 3: 实现 loader**

创建 `backend/ontology/action_loader.py`：

```python
"""加载 ontology/actions/*.yaml → ActionDefinition。"""
import os
from dataclasses import dataclass, field
from typing import Dict, List

import yaml


@dataclass
class ActionDefinition:
    api_name: str
    display_name: str
    description: str
    status: str
    target_object_type: str
    edits_object_types: List[str]
    parameters: List[dict]
    side_effects: List[dict]
    submission_criteria: dict = field(default_factory=dict)


def load_actions(actions_dir: str) -> Dict[str, ActionDefinition]:
    actions = {}
    for fname in sorted(os.listdir(actions_dir)):
        if not fname.endswith(".yaml") and not fname.endswith(".yml"):
            continue
        path = os.path.join(actions_dir, fname)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        actions[data["api_name"]] = ActionDefinition(
            api_name=data["api_name"],
            display_name=data["display_name"],
            description=data.get("description", ""),
            status=data.get("status", "active"),
            target_object_type=data["target_object_type"],
            edits_object_types=data.get("edits_object_types", []),
            parameters=data.get("parameters", []),
            side_effects=data.get("side_effects", []),
            submission_criteria=data.get("submission_criteria", {}) or {},
        )
    return actions
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_action_loader.py -v`
Expected: 3 passed。

- [ ] **Step 5: 让 parser 单例持有 actions**

修改 `backend/ontology/parser.py` 的 `get_ontology_parser`，在创建 parser 后填充 actions：

在 `get_ontology_parser` 函数内，`_parser_instance = OntologyParser(ttl_path, data_dir)` 之后追加：

```python
        from ontology.action_loader import load_actions
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        actions_dir = os.path.join(base, "ontology", "actions")
        _parser_instance.registry.action_types = load_actions(actions_dir)
```

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/action_loader.py backend/ontology/parser.py backend/tests/test_action_loader.py
git commit -m "feat: ActionLoader 加载 YAML 契约并注入 registry"
```

---

## Task 8: 折扣单一事实源

**Files:**
- Create: `backend/business/__init__.py`（空）
- Create: `backend/business/discount.py`
- Create: `backend/data/discount_rules.json`（种子，供测试；正式种子在 T13 复制到根 data/）
- Test: `backend/tests/test_discount.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_discount.py`：

```python
import json
from ontology.discount_stub import set_discount_source  # 见 Step 3 说明
from business.discount import calculate_discount


def test_t1_is_50():
    set_discount_source([{"tier": "T1", "discount_percent": 50}])
    assert calculate_discount("T1") == 50


def test_t3_is_10():
    set_discount_source([
        {"tier": "T1", "discount_percent": 50},
        {"tier": "T2", "discount_percent": 30},
        {"tier": "T3", "discount_percent": 10},
    ])
    assert calculate_discount("T3") == 10


def test_unknown_tier_raises():
    set_discount_source([])
    import pytest
    with pytest.raises(KeyError):
        calculate_discount("T9")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_discount.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 discount + 可替换数据源**

> 设计：`calculate_discount` 读一个"数据源"，默认是 `data/discount_rules.json`；测试通过 `set_discount_source` 注入内存源，避免触碰真实文件（单一事实源原则 + 可测）。

创建 `backend/ontology/discount_stub.py`：

```python
"""折扣数据源的进程内可替换入口。默认从磁盘加载，测试可注入。"""
import json
import os

_source = None  # None 表示用磁盘文件


def set_discount_source(rules):
    """测试用：注入内存折扣规则列表。传 None 恢复磁盘读取。"""
    global _source
    _source = rules


def get_discount_source():
    if _source is not None:
        return _source
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(root, "data", "discount_rules.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

创建 `backend/business/discount.py`：

```python
"""折扣计算 —— 全系统唯一事实源（见建模规范 §6.2、§8 反模式 1/8/9）。
其它处（tools/SKILL）只调用本函数，禁止重复定义折扣数值。"""
from ontology.discount_stub import get_discount_source


def calculate_discount(discount_tier: str) -> int:
    """返回减扣百分比（0-100 int）。50 表示五折（减 50%）。"""
    rules = get_discount_source()
    for r in rules:
        if r["tier"] == discount_tier:
            return int(r["discount_percent"])
    raise KeyError(f"未知 discount_tier: {discount_tier}")
```

创建 `backend/data/discount_rules.json`（测试默认数据源指向根 `data/`，这里先放一份供运行；T13 同步根目录）：

```json
[
  {"id": "rule_T1", "tier": "T1", "days_min": 0, "days_max": 3,  "discount_percent": 50, "description": "即将过期，5折(减50%)"},
  {"id": "rule_T2", "tier": "T2", "days_min": 4, "days_max": 7,  "discount_percent": 30, "description": "中期临期，7折(减30%)"},
  {"id": "rule_T3", "tier": "T3", "days_min": 8, "days_max": 14, "discount_percent": 10, "description": "初期临期，9折(减10%)"}
]
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_discount.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/business/ backend/ontology/discount_stub.py backend/data/discount_rules.json backend/tests/test_discount.py
git commit -m "feat: 折扣单一事实源 calculate_discount（统一减扣百分比）"
```

---

## Task 9: Task 状态机

**Files:**
- Create: `backend/ontology/state_machine.py`
- Test: `backend/tests/test_state_machine.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_state_machine.py`：

```python
import pytest
from ontology.state_machine import is_valid_transition, TASK_TRANSITIONS


def test_created_to_pending():
    assert is_valid_transition("created", "pending_approval") is True


def test_in_progress_to_completed():
    assert is_valid_transition("in_progress", "completed") is True


def test_invalid_skip():
    assert is_valid_transition("created", "in_progress") is False


def test_terminal_cannot_transition():
    assert is_valid_transition("completed", "scrapped") is False
    assert is_valid_transition("scrapped", "completed") is False


def test_all_in_progress_targets():
    assert set(TASK_TRANSITIONS["in_progress"]) == {"completed", "scrapped"}
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_state_machine.py -v`
Expected: FAIL（无模块）。

- [ ] **Step 3: 实现**

创建 `backend/ontology/state_machine.py`：

```python
"""Task 工作流状态机（架构 spec §1.5）。迁移只能由 Action 触发。"""

TASK_TRANSITIONS = {
    "created":          ["pending_approval", "scrapped"],
    "pending_approval": ["approved", "rejected", "scrapped"],
    "approved":         ["accepted", "scrapped"],
    "accepted":         ["in_progress", "scrapped"],
    "in_progress":      ["completed", "scrapped"],
}

TERMINAL_STATES = {"completed", "rejected", "scrapped"}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    if from_status in TERMINAL_STATES:
        return False
    return to_status in TASK_TRANSITIONS.get(from_status, [])
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_state_machine.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/state_machine.py backend/tests/test_state_machine.py
git commit -m "feat: Task 状态机 + 合法迁移校验"
```

---

## Task 10: Preview 缓存（preview→confirm 闭环）

**Files:**
- Create: `backend/ontology/preview_cache.py`
- Test: `backend/tests/test_preview_cache.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_preview_cache.py`：

```python
import time
import pytest
from ontology.preview_cache import PreviewCache


def test_store_and_retrieve():
    c = PreviewCache(ttl_seconds=60)
    pid = c.put({"action_type": "create_clearance_task", "target_id": "ne_1"})
    assert c.get(pid) == {"action_type": "create_clearance_task", "target_id": "ne_1"}


def test_get_consumes():
    c = PreviewCache(ttl_seconds=60)
    pid = c.put({"x": 1})
    c.get(pid)
    assert c.get(pid) is None  # 取走后失效


def test_expired_returns_none():
    c = PreviewCache(ttl_seconds=0)
    pid = c.put({"x": 1})
    time.sleep(0.01)
    assert c.get(pid) is None


def test_missing_returns_none():
    c = PreviewCache(ttl_seconds=60)
    assert c.get("nope") is None
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_preview_cache.py -v`
Expected: FAIL。

- [ ] **Step 3: 实现**

创建 `backend/ontology/preview_cache.py`：

```python
"""preview 记录缓存（架构 spec §1.6）。confirm 必须持有效 preview_id。
MVP 进程内 dict + TTL；v2 可换 Redis。"""
import time
import uuid


class PreviewCache:
    def __init__(self, ttl_seconds: int = 300):
        self._store = {}  # preview_id -> (data, expire_at)
        self.ttl_seconds = ttl_seconds

    def put(self, data: dict) -> str:
        preview_id = f"pv_{uuid.uuid4().hex[:12]}"
        self._store[preview_id] = (data, time.time() + self.ttl_seconds)
        return preview_id

    def get(self, preview_id: str):
        entry = self._store.get(preview_id)
        if not entry:
            return None
        data, expire_at = entry
        if time.time() > expire_at:
            del self._store[preview_id]
            return None
        del self._store[preview_id]  # 取走即失效
        return data
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_preview_cache.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/preview_cache.py backend/tests/test_preview_cache.py
git commit -m "feat: preview 缓存 + TTL（preview->confirm 治理闭环）"
```

---

## Task 11: ActionExecutor（核心瘦路由器）

**Files:**
- Create: `backend/ontology/executor.py`
- Test: `backend/tests/test_executor.py`

> 执行器是纯 Python（可单测）。职责：读契约 → 校验参数 → 校验 submission_criteria → 校验状态机 → 原子执行副作用 → 返回结果。所有受治理实体写操作走 `repository.write(..., bypass_action_check=True)`。

- [ ] **Step 1: 准备测试 fixture —— 在 conftest 增加一个出清场景数据目录**

在 `backend/tests/conftest.py` 末尾追加：

```python
@pytest.fixture
def clearance_data_dir(tmp_path):
    """完整出清场景种子数据：1 门店/员工/商品/临期商品。"""
    (tmp_path / "stores.json").write_text(json.dumps([{
        "id": "store_001", "name": "测试门店", "region_id": "region_001",
        "address": "x", "manager_id": "emp_001",
        "created_at": "2024-01-01T00:00:00"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "employees.json").write_text(json.dumps([{
        "id": "emp_001", "name": "张店长", "store_id": "store_001",
        "role": "manager", "phone": "1"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "products.json").write_text(json.dumps([{
        "id": "prod_001", "name": "酸奶", "category": "乳", "brand": "蒙牛",
        "unit": "盒", "cost_price": 4.5, "retail_price": 6.0}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "near_expiry_products.json").write_text(json.dumps([{
        "id": "ne_001", "product_id": "prod_001", "store_id": "store_001",
        "batch_no": "B1", "production_date": "2026-06-01", "expiry_date": "2026-06-10",
        "stock_quantity": 50, "days_left": 5, "discount_tier": "T2",
        "status": "expiring"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "tasks.json").write_text("[]", encoding="utf-8")
    (tmp_path / "loss_reports.json").write_text("[]", encoding="utf-8")
    return str(tmp_path)
```

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_executor.py`：

```python
import pytest
from ontology.repository import JSONFileRepository
from ontology.parser import OntologyParser
from ontology.action_loader import load_actions
from ontology.executor import ActionExecutor
from ontology.errors import ValidationError


def _exec(data_dir, actor_role="store_manager"):
    parser = OntologyParser(ttl_path="ontology/store.ttl", data_dir=data_dir)
    parser.registry.action_types = load_actions("ontology/actions")
    repo = JSONFileRepository(data_dir=data_dir, registry=parser.registry)
    return ActionExecutor(repository=repo, actions=parser.registry.action_types,
                          registry=parser.registry), repo


def test_create_clearance_task_creates_task_and_sets_status(clearance_data_dir):
    ex, repo = _exec(clearance_data_dir)
    result = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager", "id": "emp_001"},
       tenant_id="tenant_default")
    assert result["ok"] is True
    task = result["created"]["Task"][0]
    assert task["status"] == "created"
    assert task["discount_percent"] == 30
    ne = repo.read_one("NearExpiryProduct", "tenant_default", "ne_001")
    assert ne["status"] == "clearance"


def test_invalid_discount_rejected(clearance_data_dir):
    ex, _ = _exec(clearance_data_dir)
    with pytest.raises(ValidationError):
        ex.execute("create_clearance_task", {
            "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
            "discount_percent": 150, "planned_quantity": 50,
        }, actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_expired_product_blocked(clearance_data_dir):
    import json
    from pathlib import Path
    p = Path(clearance_data_dir) / "near_expiry_products.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    rows[0]["status"] = "expired"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    ex, _ = _exec(clearance_data_dir)
    with pytest.raises(ValidationError):
        ex.execute("create_clearance_task", {
            "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
            "discount_percent": 30, "planned_quantity": 50,
        }, actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_state_transition_enforced(clearance_data_dir):
    ex, repo = _exec(clearance_data_dir)
    r = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    task_id = r["created"]["Task"][0]["id"]
    # 跳过 submit 直接 accept：应被拒（created !-> accepted）
    with pytest.raises(ValidationError):
        ex.execute("accept_task", {"task_id": task_id, "assignee_id": "emp_001"},
                   actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_deduct_stock_decrements_and_increments(clearance_data_dir):
    ex, repo = _exec(clearance_data_dir)
    r = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    task_id = r["created"]["Task"][0]["id"]
    # 推到 in_progress
    for action, params in [("submit_for_approval", {"task_id": task_id}),
                           ("approve_clearance", {"task_id": task_id, "approver_id": "rcm_1"}),
                           ("accept_task", {"task_id": task_id, "assignee_id": "emp_001"}),
                           ("print_labels", {"task_id": task_id, "label_count": 50})]:
        ex.execute(action, params, actor={"role": "region_cat_mgr" if "approve" in action else "store_manager"},
                   tenant_id="tenant_default")
    ex.execute("deduct_stock", {"target_id": "ne_001", "task_id": task_id, "quantity": 10},
               actor={"role": "system_pos"}, tenant_id="tenant_default")
    ne = repo.read_one("NearExpiryProduct", "tenant_default", "ne_001")
    task = repo.read_one("Task", "tenant_default", task_id)
    assert ne["stock_quantity"] == 40
    assert task["sold_quantity"] == 10
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `python -m pytest tests/test_executor.py -v`
Expected: FAIL（无 executor）。

- [ ] **Step 4: 实现 ActionExecutor**

创建 `backend/ontology/executor.py`：

```python
"""ActionExecutor —— 声明式契约的瘦路由器（架构 spec §1.2 第6点）。
读 YAML 契约 → 校验 → 原子执行副作用。纯 Python，可单测。"""
import re
import uuid
from typing import Dict

from ontology.errors import ValidationError, EntityNotFoundError
from ontology.state_machine import is_valid_transition


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
        return (lo == "" or value >= int(lo)) and (hi == "" or value <= int(hi))
    m = re.match(r"^(>=|<=|>|<)\s*(\d+(\.\d+)?)$", c)
    if m:
        op, num = m.group(1), float(m.group(2))
        return {" >": value > num, ">=": value >= num,
                "<": value < num, "<=": value <= num}[op]
    return True  # 无可识别约束则放行


class ActionExecutor:
    def __init__(self, repository, actions: Dict[str, object], registry):
        self.repo = repository
        self.actions = actions
        self.registry = registry

    # ---------- 公共入口 ----------
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
        # 找定位参数：优先 target_id，其次 task_id
        ident = params.get("target_id") or params.get("task_id")
        if not ident or target_type not in self.registry.object_types:
            return None
        return self.repo.read_one(target_type, tenant_id, ident)

    def _check_submission(self, action, actor, target, params, tenant_id):
        sc = action.submission_criteria or {}
        roles = sc.get("roles", [])
        if roles and actor.get("role") not in roles:
            raise ValidationError(
                f"角色 {actor.get('role')} 无权提交 {action.api_name}（需 {roles}）")
        for cond in sc.get("conditions", []):
            # field 形如 "target.status" 或 "task.status"
            field_path = cond["field"]
            obj = self._resolve_condition_obj(field_path, target, params, tenant_id)
            if obj is None:
                raise ValidationError(f"submission 条件无法解析对象: {field_path}")
            key = field_path.split(".")[-1]
            actual = obj.get(key)
            op, want = cond["operator"], cond.get("value")
            ok = (op == "is" and actual == want) or \
                 (op == "is_not" and actual != want)
            if not ok:
                raise ValidationError(cond.get("fail_msg", "submission 条件不满足"))

    def _resolve_condition_obj(self, field_path, target, params, tenant_id):
        root = field_path.split(".")[0]
        if root == "target":
            return target
        if root == "task":
            tid = params.get("task_id")
            return self.repo.read_one("Task", tenant_id, tid) if tid else None
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
                if not is_valid_transition(rec.get("status"), eff["to"]):
                    raise ValidationError(
                        f"非法状态迁移: {rec.get('status')} -> {eff['to']}")
                rec["status"] = eff["to"]
                self.repo.write(obj_type, tenant_id, rec, bypass_action_check=True)
                updated.setdefault(obj_type, []).append(rec)
            elif t in ("notification", "external_call"):
                pass  # MVP 仅声明，不实际触发（v2 接对接层）
        return {"created": created, "updated": updated}
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python -m pytest tests/test_executor.py -v`
Expected: 5 passed。

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/executor.py backend/tests/test_executor.py backend/tests/conftest.py
git commit -m "feat: ActionExecutor 声明式瘦路由器（校验/状态机/副作用）"
```

---

## Task 12: 重写 tools.py（薄封装）

**Files:**
- Modify: `backend/ontology/tools.py`（整文件重写）
- Test: `backend/tests/test_tools.py`

> 现有 tools.py 直接读写文件、硬编码折扣、把 Action 逻辑塞进 `@tool`。重写为：读工具走 Repository；`execute_action`(preview)/`confirm_action` 走 Executor + PreviewCache；删 `tier_discount` 硬编码；`create_entity`/`update_entity` 降级（Repository 自然拦截受治理实体）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_tools.py`：

```python
from ontology.tools import query_entity, confirm_action, execute_action
from ontology import tools as T


def _setup(monkeypatch, data_dir):
    """把 tools 的 parser/repository/executor 指向临时数据目录。"""
    from ontology.parser import OntologyParser
    from ontology.action_loader import load_actions
    from ontology.repository import JSONFileRepository
    from ontology.executor import ActionExecutor
    parser = OntologyParser(ttl_path="ontology/store.ttl", data_dir=data_dir)
    parser.registry.action_types = load_actions("ontology/actions")
    repo = JSONFileRepository(data_dir=data_dir, registry=parser.registry)
    ex = ActionExecutor(repository=repo, actions=parser.registry.action_types,
                        registry=parser.registry)
    monkeypatch.setattr(T, "_get_repo", lambda tenant="tenant_default": repo)
    monkeypatch.setattr(T, "_get_executor", lambda: ex)


def test_query_entity_reads_store(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({"entity_type": "Store"})
    assert "store_001" in out


def test_execute_action_returns_preview_id(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = execute_action.invoke({
        "action_type": "create_clearance_task",
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50})
    assert "preview_id" in out or "preview" in out


def test_confirm_requires_preview(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = confirm_action.invoke({"preview_id": "bogus"})
    assert "preview" in out.lower() or "失败" in out or "无效" in out
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL。

- [ ] **Step 3: 重写 tools.py**

整文件替换 `backend/ontology/tools.py`：

```python
"""本体驱动工具 —— 薄封装层。
读工具走 Repository；execute_action(preview)/confirm_action 走 ActionExecutor + PreviewCache。
所有 @tool 仅做参数编排与结果包装，业务逻辑在 Executor/Repository（见架构 spec §1.2 第6点）。"""

import json
import uuid
from datetime import datetime
from typing import Optional, Any

from langchain_core.tools import tool

from ontology.parser import get_ontology_parser
from ontology.repository import JSONFileRepository
from ontology.action_loader import load_actions
from ontology.executor import ActionExecutor
from ontology.preview_cache import PreviewCache
from ontology.errors import OntologyError


# ============ 依赖装配（按 tenant 构造；测试用 monkeypatch 替换）============

_preview_cache = PreviewCache(ttl_seconds=300)


def _parser():
    return get_ontology_parser()


def _get_repo(tenant: str = "tenant_default") -> JSONFileRepository:
    p = _parser()
    return JSONFileRepository(data_dir=str(p.data_dir), registry=p.registry)


def _get_executor() -> ActionExecutor:
    p = _parser()
    if not p.registry.action_types:
        p.registry.action_types = load_actions(str(_parser_actions_dir()))
    repo = _get_repo()
    return ActionExecutor(repository=repo, actions=p.registry.action_types,
                          registry=p.registry)


def _parser_actions_dir() -> str:
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ontology", "actions")


def build_ontology_prompt() -> str:
    return _parser().build_system_prompt()


def _wrap(data: dict, summary: str) -> str:
    return f"{summary}\n<!--COPILOTKIT_DATA-->\n{json.dumps(data, ensure_ascii=False)}\n<!--/COPILOTKIT_DATA-->"


# ============ 读工具 ============

@tool
def query_entity(entity_type: str, entity_id: Optional[str] = None,
                 filter_field: Optional[str] = None,
                 filter_value: Optional[str] = None,
                 tenant_id: str = "tenant_default") -> str:
    """通用实体查询。entity_type: Store/Employee/Product/NearExpiryProduct/Task/LossReport。"""
    repo = _get_repo(tenant_id)
    if not _parser().registry.object_types.get(entity_type):
        return f"未知实体类型: {entity_type}"
    filters = {filter_field: filter_value} if filter_field else None
    rows = repo.read(entity_type, tenant_id, filters=filters)
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


@tool
def query_near_expiry(store_id: Optional[str] = None,
                      tenant_id: str = "tenant_default") -> str:
    """查询临期商品列表（折扣来自单一事实源 calculate_discount）。"""
    from business.discount import calculate_discount
    repo = _get_repo(tenant_id)
    rows = repo.read("NearExpiryProduct", tenant_id)
    if store_id:
        rows = [r for r in rows if r.get("store_id") == store_id]
    products = {p["id"]: p for p in repo.read("Product", tenant_id)}
    items = []
    for ne in rows[:20]:
        prod = products.get(ne.get("product_id"), {})
        tier = ne.get("discount_tier", "T3")
        items.append({
            **ne, "product_name": prod.get("name", ""),
            "discount_percent": calculate_discount(tier),  # 单一事实源
        })
    return _wrap({"type": "near_expiry_list", "total": len(rows), "items": items},
                 f"查询到 {len(rows)} 条临期商品。")


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
    """任务更新（status 字段受治理，只能经 Action 迁移；此处仅允许改非状态字段如 notes）。"""
    if "status" in kwargs:
        return _wrap({"type": "update_task_result", "success": False,
                      "error": "status 只能经 Action 迁移，不可直接更新"},
                     "状态迁移请走对应 Action。")
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
def execute_action(action_type: str, actor_role: str = "store_manager",
                   tenant_id: str = "tenant_default", **params) -> str:
    """执行 Action 预览。返回 preview_id，用户确认后用 confirm_action(preview_id) 提交。"""
    ex = _get_executor()
    actions = ex.actions
    if action_type not in actions:
        return _wrap({"type": "action_preview", "valid": False,
                      "error": f"未知 Action: {action_type}，可用: {list(actions.keys())}"},
                     f"未知操作: {action_type}")
    preview = {"action_type": action_type, "params": params,
               "actor_role": actor_role, "tenant_id": tenant_id}
    preview_id = _preview_cache.put(preview)
    return _wrap({"type": "action_preview", "valid": True, "preview_id": preview_id,
                  "action_type": action_type, "params": params},
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
```

- [ ] **Step 4: 运行工具测试**

Run: `python -m pytest tests/test_tools.py -v`
Expected: 3 passed。

- [ ] **Step 5: 运行全量测试，确保无回归**

Run: `python -m pytest tests/ -v`
Expected: 所有之前任务全绿。

- [ ] **Step 6: Commit**

```bash
git add backend/ontology/tools.py backend/tests/test_tools.py
git commit -m "refactor: tools 改为 Repository/Executor 薄封装，CRUD 降级"
```

---

## Task 13: 种子数据迁移与清理

**Files:**
- Modify: `data/tasks.json`（迁移到新 schema）
- Modify: `data/discount_rules.json`（迁移减扣百分比）
- Delete: `data/clearance_tasks.json`
- Create: `data/loss_reports.json`（空数组）
- Create: `data/near_expiry_products.json` 已存在但需补字段（见下）

> 数据迁移无单测；用验证脚本核对 schema 一致。

- [ ] **Step 1: 迁移 discount_rules.json 到减扣百分比**

整文件替换 `data/discount_rules.json`：

```json
[
  {"id": "rule_T1", "tier": "T1", "days_min": 0, "days_max": 3,  "discount_percent": 50, "description": "即将过期，5折(减50%)"},
  {"id": "rule_T2", "tier": "T2", "days_min": 4, "days_max": 7,  "discount_percent": 30, "description": "中期临期，7折(减30%)"},
  {"id": "rule_T3", "tier": "T3", "days_min": 8, "days_max": 14, "discount_percent": 10, "description": "初期临期，9折(减10%)"}
]
```

- [ ] **Step 2: 迁移 tasks.json 到新 schema**

把每条旧记录 `{action_type, near_expiry_product_id, input_params, output_result, actual_discount, quantity, ...}` 转为新 schema：

```json
[
  {"id": "task_2ff14c43", "task_type": "clearance", "target_id": "nep_001",
   "store_id": "store_001", "assignee_id": "emp_001", "status": "completed",
   "discount_percent": 50, "planned_quantity": 50, "sold_quantity": 50,
   "params_json": {}, "result_json": {}, "priority": "medium", "notes": "",
   "created_at": "2026-05-22T12:04:34", "started_at": null, "completed_at": "2026-05-22T12:04:34"}
]
```

（对现有每条记录逐一转换：`action_type→task_type`、`near_expiry_product_id→target_id`、`input_params→params_json`、`output_result→result_json`、`actual_discount`×100→`discount_percent`（取整）、`quantity→planned_quantity`、`status` 保持语义；若旧 status 值不在新枚举内，映射到最近态或 `completed`。）

- [ ] **Step 3: 删除残留文件，建空 loss_reports**

Run:
```bash
git rm data/clearance_tasks.json
```
创建 `data/loss_reports.json` 内容为 `[]`。

- [ ] **Step 4: 验证 schema 一致**

Run（在 `backend/` 下）:
```bash
python -c "
import json, sys
sys.path.insert(0, '.')
from models.schemas import Task
for t in json.load(open('../data/tasks.json')):
    Task(**{k:v for k,v in t.items() if k in Task.__fields__})
print('tasks.json OK')
"
```
Expected: `tasks.json OK`。

- [ ] **Step 5: Commit**

```bash
git add data/tasks.json data/discount_rules.json data/loss_reports.json
git commit -m "chore: 种子数据迁移到新 schema + 删 clearance_tasks.json"
```

---

## Task 14: SKILL.md 重写 + 修双层目录

**Files:**
- Move: `backend/skills/store-ontology/store-ontology/SKILL.md` → `backend/skills/store-ontology/SKILL.md`
- Rewrite: `backend/skills/store-ontology/clearance-workflow/SKILL.md`
- Delete: `backend/skills/store-ontology/store-ontology/`（空目录）

> SKILL.md 引用了幽灵实体（DiscountRule/get_near_expiry_products/belongs_to），违反规范 §8 反模式 5。重写为只引用真实本体与工具。

- [ ] **Step 1: 修复双层目录**

Run:
```bash
cd backend/skills/store-ontology
git mv store-ontology/SKILL.md SKILL.md
rmdir store-ontology
```
（若 git mv 报目标存在，先确认 `backend/skills/store-ontology/SKILL.md` 不存在；它当前在 `store-ontology/store-ontology/` 下。）

- [ ] **Step 2: 重写 store-ontology/SKILL.md**

整文件替换 `backend/skills/store-ontology/SKILL.md`：

```markdown
---
name: store-ontology
description: 门店临期商品管理本体知识与工具使用策略
type: domain_knowledge
---

# 门店临期商品管理

## 本体（7 Object / 10 Link）
- **Object**: Region、Store、Employee、Product、NearExpiryProduct、Task、LossReport
- 读实体用 `query_entity`，遍历关系用 `traverse_relation`。

## 折扣（单一事实源）
折扣由临期商品的 `discount_tier`（T1/T2/T3）决定，具体数值见本体数据 `data/discount_rules.json`（减扣百分比，0-100）。
**不要在本对话中重复定义折扣数值**；如需数值，调 `query_near_expiry` 查看。

## 状态
- NearExpiryProduct.status：expiring / clearance / sold_out / expired / scrapped
- Task.status：created / pending_approval / approved / accepted / in_progress / completed / rejected / scrapped

状态迁移只能经 Action，不可直接改写。
```

- [ ] **Step 3: 重写 clearance-workflow/SKILL.md**

整文件替换 `backend/skills/store-ontology/clearance-workflow/SKILL.md`：

```markdown
---
name: clearance-workflow
description: 临期出清跨天流程编排
type: workflow_orchestration
---

# 临期出清流程

出清是一条跨天工作流，由 Task 状态机驱动。每一步是一个 Action：先 `execute_action` 预览，再 `confirm_action(preview_id)` 执行。

## 步骤
1. **查询**：`query_near_expiry` 找临期商品。
2. **建单**：`execute_action(action_type="create_clearance_task", target_id, store_id, assignee_id, discount_percent, planned_quantity)`。
3. **提交审批**：`execute_action(action_type="submit_for_approval", task_id)`。
4. **审批**（后端回调，对话中可模拟）：`approve_clearance`。
5. **接单**：`accept_task`。
6. **打签陈列**：`print_labels`。
7. **POS 扣库存**（后端）：`deduct_stock`。
8. **售罄完成**：`complete_task`。
9. **到期未售罄**：`create_loss_report`。

## 折扣
`discount_percent` 是减扣百分比（0-100，50=五折），由 tier 决定，见 `discount_rules.json`。

## 非法迁移会被拒
状态机只允许相邻迁移（见 store-ontology SKILL）。跳步会被拒绝，请按顺序。
```

- [ ] **Step 4: Commit**

```bash
git add backend/skills/
git commit -m "docs: 重写 SKILL.md 对齐真实本体/工具，修双层目录"
```

---

## Task 15: main.py tenant 上下文接线

**Files:**
- Modify: `backend/main.py`

> MVP：tenant 上下文从请求 header 读取（默认 tenant_default），存入 contextvar 供后续扩展；prompt 中不再硬编码 store_001。无单测（接线层），用启动冒烟验证。

- [ ] **Step 1: 改 main.py**

在 `main.py` 的 import 区后、`app` 创建前，加入 tenant contextvar + middleware；并修改 `store_context` 为动态说明。具体改动：

把
```python
ontology_prompt = build_ontology_prompt()
store_context = """
当前用户选择的门店ID是: store_001。
...
"""
system_prompt = ontology_prompt + store_context
```
替换为：
```python
ontology_prompt = build_ontology_prompt()

import contextvars
tenant_ctx: contextvars.ContextVar = contextvars.ContextVar("tenant_id", default="tenant_default")


@app.middleware("http")
async def tenant_middleware(request, call_next):
    tid = request.headers.get("X-Tenant-ID", "tenant_default")
    token = tenant_ctx.set(tid)
    try:
        return await call_next(request)
    finally:
        tenant_ctx.reset(token)


store_context = """
当前租户上下文由请求 header X-Tenant-ID 注入（默认 tenant_default）。
**操作流程（Preview → Confirm）：**
1. 用户要求出清时，先 execute_action 获取预览（返回 preview_id）
2. 展示预览，询问确认
3. 用户确认后，confirm_action(preview_id) 执行
4. 出清是一条工作流（create_clearance_task -> submit_for_approval -> ... -> complete_task），状态机只允许相邻迁移
5. 用中文回复
"""

system_prompt = ontology_prompt + store_context
```

> 注：`@app.middleware` 必须在 `app = FastAPI(...)` 之后注册。请确保该代码块位于 `app = FastAPI(...)` 定义之后。

- [ ] **Step 2: 启动冒烟**

Run: `cd backend && python -c "import main; print('import OK')"`
Expected: `import OK`（可能因缺 API key 报错——若 `QWEN_API_KEY` 未设，临时 `QWEN_API_KEY=stub python -c "import main"` 仅验证语法/接线，不实际连 LLM）。

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: main.py tenant 上下文注入（X-Tenant-ID middleware + contextvar）"
```

---

## Task 16: 前端 tenant 选择器 + route.ts header（独立子系统）

**Files:**
- Modify: `frontend/app/api/copilotkit/route.ts`
- Modify: `frontend/app/home-page.tsx`

> 前端无测试基建；用浏览器手测验证。scope：route.ts 在转发请求时注入 `X-Tenant-ID` header（取自 co-agent state 的 selected_store）。

- [ ] **Step 1: route.ts 注入 header**

读 `frontend/app/api/copilotkit/route.ts` 当前实现，在转发 fetch 处增加 header 注入。最小改动：用 CopilotKit 的自定义 fetch wrapper。在创建 runtime 处：

```typescript
// 伪结构：在 POST handler 内，从 body 解析 state.selected_store，写入 header 转发
const tenantId = body?.state?.selected_store ?? "tenant_default";
// 转发到后端时：
headers: { ...原有headers, "X-Tenant-ID": tenantId }
```

> 因 CopilotKit 版本 API 差异，具体写法需对照 `frontend/node_modules/@copilotkit/` 的实际导出。**执行此任务时先读 route.ts 与 CopilotKit runtime 源码确认注入点**（`ExperimentalEmptyAdapter`/`LangGraphHttpAgent` 的 fetch 选项），再落地。若当前版本无 hook 能力，回退方案：用 Next.js 的 `rewrites` + 自定义代理路由手写转发（不经 CopilotKit runtime）。

- [ ] **Step 2: home-page.tsx tenant 选择器**

把硬编码的 store_001/store_002 按钮改为从一个 tenant 列表加载（MVP 可硬编码列表 `["tenant_default"]` 或从 `/api/tenants` 读取），选中后写入 co-agent state 的 `selected_store`。

- [ ] **Step 3: 手测**

启动前后端，切换 tenant，对话出清，确认后端日志的 tenant_ctx 与选中一致。

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: 前端 tenant 选择器 + route.ts 注入 X-Tenant-ID"
```

---

## Self-Review（计划自检，非执行步骤）

**1. 规范覆盖（对照建模文档 §1 违规 12 条）**
- 违规1 Action粒度→T6(8 YAML)+T11(executor) ✅
- 违规2/8/9 折扣→T8 ✅
- 违规3 manages方向→T4 ✅
- 违规4 LinkTypes→T3 删除 ✅
- 违规5 SKILL幽灵→T14 ✅
- 违规6 CRUD绕过→T2(edits-only)+T12(降级) ✅
- 违规7 Task状态→T9+T11 ✅
- 违规10 缺元数据→T4/T5 ✅
- 违规11 直读文件→T2(Repository)+T12 ✅
- 违规12 tasks.json旧schema→T13 ✅

**2. 占位符扫描**：T16 Step1 含"先读源码确认注入点"——这是因 CopilotKit 版本 API 不可预知而保留的真实探索步骤，非占位符；已给出回退方案。其余步骤均有完整代码。

**3. 类型一致性**：`Task.task_type`（T3）/TTL `task_type:TaskType`（T4）/executor 创建 `task_type: clearance`（T6）/YAML `$`-引用（T11 `_resolve`）一致。`discount_percent` 跨 schemas/TTL/YAML/executor 统一为减扣百分比 int。`edits_only_via_actions` 在 dataclass(T5)/TTL(T4)/Repository检查(T2) 三处一致。

**4. 依赖顺序**：T2→T3→T4→T5→T6→T7→T8→T9→T10→T11→T12→T13→T14→T15→T16，每步可独立提交、独立测试。
```
