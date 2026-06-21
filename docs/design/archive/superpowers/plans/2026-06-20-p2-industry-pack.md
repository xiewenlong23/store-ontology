> **🗄 归档说明**：brainstorming 产出（plan（实施计划）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# P2 行业包 + 能力域/价值链流程双轴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把扁平 `VerticalConfig` 重构为 `IndustryPack` > `CapabilityDomain`（原子）+ `ValueChainProcess`（跨域编排）三级结构，迁移 clearance 为 retail-pack 的 clearance 流程，保持 117 测试全绿。

**Architecture:** 新增三级 dataclass（IndustryPack/CapabilityDomain/ValueChainProcess）+ pack 注册表 + bootstrap 扫 packs。clearance 的 TTL 按域拆 3 份、Action 按归属域分到 3 个 actions 目录。VerticalConfig 保留作 equipment_repair 兼容。`pack_to_registry` 合并 pack 下所有 domain+process 的定义为一个 EntityRegistry 供 executor 用。

**Tech Stack:** Python ≥3.11、Pydantic、pytest（TDD）、现有内核。

**依据 spec：** `docs/superpowers/specs/2026-06-20-p2-industry-pack-design.md`

**约定：** 解释器 `/opt/miniconda3/envs/store-ontology/bin/python`；测试从 `backend/` 跑；每任务 TDD。

---

## File Structure

| 文件 | 职责 | 任务 |
|---|---|---|
| `backend/ontology/pack.py` | IndustryPack/CapabilityDomain/ValueChainProcess dataclass + pack 注册表 + pack_to_registry | T1 |
| `backend/ontology/bootstrap.py` | 升级：扫 packs/*/pack.py + 兼容扫 verticals | T2 |
| `backend/packs/retail/pack.py` | retail IndustryPack 声明（3 domain + clearance process） | T3 |
| `backend/packs/retail/domains/*/domain.ttl` | 拆分 store.ttl 为 3 个域 TTL | T3 |
| `backend/packs/retail/domains/*/actions/*.yaml` | Action 按域分到 3 个 actions 目录 | T3 |
| `backend/packs/retail/processes/clearance/process.py` | clearance ValueChainProcess 声明 | T3 |
| `backend/packs/retail/processes/clearance/tools.py` | query_near_expiry（从 verticals/clearance 迁移） | T3 |
| `backend/packs/retail/processes/clearance/skills/` | clearance SKILL.md（迁移） | T3 |
| `backend/main.py` | 从注册表聚合 pack + vertical 的工具/skill/prompt | T4 |

**不动的**：`ontology/store.ttl`（保留作兼容）、`ontology/actions/*.yaml`（保留）、`verticals/equipment_repair/`（不动）、`verticals/clearance/`（保留作兼容，新旧并存验证）。

---

## Task 1: 三级数据结构 + pack_to_registry

**Files:**
- Create: `backend/ontology/pack.py`
- Test: `backend/tests/test_pack.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_pack.py`：

```python
"""测试三级结构 IndustryPack/CapabilityDomain/ValueChainProcess（P2）。"""
import pytest
from ontology.pack import (
    IndustryPack, CapabilityDomain, ValueChainProcess,
    register_pack, get_pack, all_packs, clear_packs, pack_to_registry,
)


def test_capability_domain_basic():
    d = CapabilityDomain(name="marketing", display_name="营销域",
                         ttl_path="/tmp/m.ttl", actions_dir="/tmp/m/actions")
    assert d.name == "marketing"
    assert d.display_name == "营销域"


def test_value_chain_process_basic():
    p = ValueChainProcess(name="clearance", display_name="出清",
                          workflow_object_type="Task")
    assert p.name == "clearance"
    assert p.workflow_object_type == "Task"
    assert p.state_transitions == {}


def test_industry_pack_aggregates():
    d = CapabilityDomain(name="marketing", display_name="营销",
                         ttl_path="/tmp/m.ttl", actions_dir="/tmp/m/a")
    p = ValueChainProcess(name="clearance", display_name="出清",
                          workflow_object_type="Task")
    pack = IndustryPack(name="retail", display_name="零售行业包",
                        domains=[d], processes=[p])
    assert len(pack.domains) == 1
    assert len(pack.processes) == 1
    assert pack.domains[0].name == "marketing"
    assert pack.processes[0].name == "clearance"


def test_pack_registry():
    clear_packs()
    pack = IndustryPack(name="retail", display_name="零售")
    register_pack(pack)
    assert get_pack("retail") is pack
    assert len(all_packs()) == 1
    clear_packs()


def test_pack_to_registry_merges_domains(tmp_path):
    """pack_to_registry 合并 pack 下所有 domain 的 TTL + action。"""
    import os, json
    # 构造两个域，各一个 TTL + 一个 action
    d1_dir = tmp_path / "marketing"
    d1_dir.mkdir()
    (d1_dir / "domain.ttl").write_text(
        '@prefix m: <http://x#> .\n'
        'm:Product a <http://www.w3.org/2000/01/rdf-schema#Class> ;\n'
        '    m:properties "id:string,name:string" ;\n'
        '    m:storage "products.json" .\n', encoding="utf-8")
    a1_dir = d1_dir / "actions"
    a1_dir.mkdir()
    (a1_dir / "test_action.yaml").write_text(
        'api_name: test_action\ndisplay_name: 测试\ntarget_object_type: Product\n'
        'edits_object_types: [Product]\nparameters: []\nside_effects: []\n',
        encoding="utf-8")

    d2_dir = tmp_path / "organization"
    d2_dir.mkdir()
    (d2_dir / "domain.ttl").write_text(
        '@prefix o: <http://x#> .\n'
        'o:Store a <http://www.w3.org/2000/01/rdf-schema#Class> ;\n'
        '    o:properties "id:string,name:string" ;\n'
        '    o:storage "stores.json" .\n', encoding="utf-8")

    d1 = CapabilityDomain(name="marketing", display_name="营销",
                          ttl_path=str(d1_dir / "domain.ttl"),
                          actions_dir=str(a1_dir))
    d2 = CapabilityDomain(name="organization", display_name="组织",
                          ttl_path=str(d2_dir / "domain.ttl"),
                          actions_dir=str(d2_dir / "actions"))  # 无 action
    pack = IndustryPack(name="retail", display_name="零售", domains=[d1, d2])

    registry = pack_to_registry(pack)
    assert "Product" in registry.object_types
    assert "Store" in registry.object_types
    assert "test_action" in registry.action_types
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_pack.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 pack.py**

创建 `backend/ontology/pack.py`：

```python
"""行业包三级结构（P2）：IndustryPack > CapabilityDomain + ValueChainProcess。

CapabilityDomain 提供原子 Object/Link/Action；ValueChainProcess 跨域编排。
pack_to_registry 合并 pack 下所有 domain 的定义为一个 EntityRegistry。
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ontology.parser import OntologyParser, EntityRegistry
from ontology.action_loader import load_actions


@dataclass
class CapabilityDomain:
    """能力域：提供原子 Object/Link/Action + 域内规则源。不含工作流/状态机。"""
    name: str
    display_name: str
    ttl_path: str
    actions_dir: str
    rules_dir: Optional[str] = None
    description: str = ""


@dataclass
class ValueChainProcess:
    """价值链流程：跨域编排，有自己的状态机 + Skill + 专属工具。"""
    name: str
    display_name: str
    workflow_object_type: str
    workflow_object_id_field: str = "task_id"
    state_transitions: Dict[str, List[str]] = field(default_factory=dict)
    terminal_states: List[str] = field(default_factory=list)
    skills_dir: Optional[str] = None
    tools_module: Optional[str] = None
    actions_dir: Optional[str] = None  # 流程专属 Action（如 submit/approve/accept）
    system_prompt_intro: str = ""
    description: str = ""


@dataclass
class IndustryPack:
    """行业包：聚合多个 CapabilityDomain + 多个 ValueChainProcess。"""
    name: str
    display_name: str
    domains: List[CapabilityDomain] = field(default_factory=list)
    processes: List[ValueChainProcess] = field(default_factory=list)
    data_dir: str = ""


# ============ pack 注册表 ============

_packs: Dict[str, IndustryPack] = {}


def register_pack(pack: IndustryPack) -> None:
    _packs[pack.name] = pack


def get_pack(name: str) -> Optional[IndustryPack]:
    return _packs.get(name)


def all_packs() -> List[IndustryPack]:
    return list(_packs.values())


def clear_packs() -> None:
    _packs.clear()


def pack_to_registry(pack: IndustryPack, data_dir: str = ".") -> EntityRegistry:
    """合并 pack 下所有 domain + process 的定义为一个 EntityRegistry。

    - 每个 domain 的 TTL 解析出 Object/Link
    - 每个 domain + process 的 actions_dir 加载 Action
    - executor/tools 不关心 Action 来自哪里，按名路由
    """
    registry = EntityRegistry()

    # 解析所有 domain TTL（各自独立 parser，合并 object/link_types）
    for domain in pack.domains:
        if not os.path.exists(domain.ttl_path):
            continue
        p = OntologyParser(ttl_path=domain.ttl_path, data_dir=data_dir)
        registry.object_types.update(p.registry.object_types)
        registry.link_types.update(p.registry.link_types)

    # 加载所有 domain + process 的 Action
    for domain in pack.domains:
        if domain.actions_dir and os.path.isdir(domain.actions_dir):
            registry.action_types.update(load_actions(domain.actions_dir))
    for proc in pack.processes:
        if proc.actions_dir and os.path.isdir(proc.actions_dir):
            registry.action_types.update(load_actions(proc.actions_dir))

    return registry
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_pack.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/pack.py backend/tests/test_pack.py
git commit -m "feat(pack) P2-T1: IndustryPack/Domain/Process 三级结构 + pack_to_registry"
```

---

## Task 2: bootstrap 升级（扫 packs + 兼容 verticals）

**Files:**
- Modify: `backend/ontology/bootstrap.py`
- Test: `backend/tests/test_pack_bootstrap.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_pack_bootstrap.py`：

```python
"""测试 bootstrap 扫 packs + 兼容 verticals（P2）。"""
import pytest
from ontology.bootstrap import bootstrap
from ontology.pack import all_packs, clear_packs
from ontology.vertical import all_verticals


@pytest.fixture(autouse=True)
def _clean():
    clear_packs()
    yield
    clear_packs()


def test_bootstrap_discovers_packs():
    """bootstrap 后 retail pack 被发现注册。"""
    bootstrap()
    pack_names = [p.name for p in all_packs()]
    # retail pack 应被注册（如果 packs/retail/pack.py 存在）
    assert "retail" in pack_names


def test_bootstrap_still_discovers_verticals():
    """兼容：verticals 仍被发现（equipment_repair）。"""
    bootstrap()
    vert_names = [v.name for v in all_verticals()]
    assert "equipment_repair" in vert_names


def test_bootstrap_idempotent():
    bootstrap()
    n1 = len(all_packs()) + len(all_verticals())
    bootstrap()
    n2 = len(all_packs()) + len(all_verticals())
    assert n1 == n2
```

- [ ] **Step 2: 运行测试，确认失败（retail pack 不存在）**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_pack_bootstrap.py -v`
Expected: `test_bootstrap_discovers_packs` FAIL（"retail" not in []）

- [ ] **Step 3: 升级 bootstrap + 创建 packs 目录**

修改 `backend/ontology/bootstrap.py`，在现有 `_discover_verticals` 逻辑前加 `_discover_packs`：

```python
import importlib
import os
import pkgutil


def _discover_packs() -> None:
    """扫描 packs/*/pack.py 注册 IndustryPack。"""
    try:
        import packs
    except ImportError:
        return
    pkg_path = os.path.dirname(packs.__file__)
    names = sorted(name for _, name, ispkg in pkgutil.iter_modules([pkg_path]) if ispkg)
    for name in names:
        try:
            importlib.import_module(f"packs.{name}.pack")
        except ModuleNotFoundError:
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[bootstrap] 注册 pack '{name}' 失败: {e}")


def _discover_verticals() -> None:
    """扫描 verticals/*/config.py 注册 VerticalConfig（兼容期保留）。"""
    try:
        import verticals
    except ImportError:
        return
    pkg_path = os.path.dirname(verticals.__file__)
    names = sorted(name for _, name, ispkg in pkgutil.iter_modules([pkg_path]) if ispkg)
    for name in names:
        try:
            importlib.import_module(f"verticals.{name}.config")
        except ModuleNotFoundError:
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[bootstrap] 注册 vertical '{name}' 失败: {e}")


def bootstrap() -> None:
    """发现并注册所有 pack + vertical（幂等）。"""
    _discover_packs()
    _discover_verticals()
```

创建空 `backend/packs/__init__.py`。

- [ ] **Step 4: 运行测试**

此时 retail pack 还没建（T3 建），`test_bootstrap_discovers_packs` 仍失败。先验兼容：
Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_pack_bootstrap.py::test_bootstrap_still_discovers_verticals -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/bootstrap.py backend/packs/__init__.py backend/tests/test_pack_bootstrap.py
git commit -m "feat(pack) P2-T2: bootstrap 升级（扫 packs + 兼容 verticals）"
```

---

## Task 3: retail-pack 搭建（3 domain TTL 拆分 + clearance process + Action 迁移）

> 这是最复杂的任务：把 store.ttl 拆成 3 个 domain.ttl，8 个 Action 按域分到 3 目录 + process 目录，迁移 skills/tools。纯文件创建 + 验证（无单测，靠 pack_to_registry 解析验证）。

**Files:**
- Create: `backend/packs/retail/__init__.py`
- Create: `backend/packs/retail/pack.py`
- Create: `backend/packs/retail/domains/marketing/{__init__.py,domain.ttl,actions/create_clearance_task.yaml,actions/deduct_stock.yaml,rules/discount_rules.json}`
- Create: `backend/packs/retail/domains/supply_chain/{__init__.py,domain.ttl}`（空域，预留）
- Create: `backend/packs/retail/domains/organization/{__init__.py,domain.ttl}`
- Create: `backend/packs/retail/domains/finance/{__init__.py,domain.ttl,actions/create_loss_report.yaml,actions/complete_task.yaml,actions/update_task_notes.yaml}`
- Create: `backend/packs/retail/processes/clearance/{__init__.py,process.py,tools.py,skills/clearance-workflow/SKILL.md,skills/store-ontology/SKILL.md,actions/submit_for_approval.yaml,actions/approve_clearance.yaml,actions/accept_task.yaml,actions/print_labels.yaml}`

- [ ] **Step 1: 创建目录结构 + __init__.py**

```bash
cd backend
mkdir -p packs/retail/domains/{marketing/actions,marketing/rules,supply_chain,organization,finance/actions}
mkdir -p packs/retail/processes/clearance/{actions,skills/clearance-workflow,skills/store-ontology}
touch packs/retail/__init__.py
touch packs/retail/domains/{marketing,supply_chain,organization,finance}/__init__.py
touch packs/retail/processes/clearance/__init__.py
```

- [ ] **Step 2: domain TTL 拆分**

**marketing/domain.ttl**（Product, NearExpiryProduct + 相关 Link）：
从 store.ttl 复制 Product、NearExpiryProduct 的 Class 块 + is_instance_of、has_near_expiry 的 Property 块。prefix 改为各自域或保留 store:（统一用 store: 避免改 parser 逻辑——多个 TTL 文件用同 prefix 不冲突，因为 pack_to_registry 各自解析后合并 dict）。

实际操作：用 `store:` prefix（现有 parser 动态读取，同 prefix 合并不冲突）。复制相关块到各 domain.ttl。

**organization/domain.ttl**（Region, Store, Employee, Task + 相关 Link）：
located_in, has_employee, manages, has_task, assigned_to, created_for。

**finance/domain.ttl**（LossReport + 相关 Link）：
has_loss_report, written_off。

**supply_chain/domain.ttl**（预留，暂无 Object——留空或加 Inventory 预留注释）。

- [ ] **Step 3: Action 按域迁移**

把现有 `backend/ontology/actions/*.yaml` 复制到对应域/流程的 actions 目录：

| Action | 目标目录 | 理由 |
|---|---|---|
| create_clearance_task | marketing/actions | target=NearExpiryProduct（营销域） |
| deduct_stock | marketing/actions | target=NearExpiryProduct |
| create_loss_report | finance/actions | 建 LossReport |
| complete_task | finance/actions | 终态结算 |
| update_task_notes | finance/actions | 非业务字段更新 |
| submit_for_approval | clearance/actions | 流程状态迁移 |
| approve_clearance | clearance/actions | 流程状态迁移 |
| accept_task | clearance/actions | 流程状态迁移 |
| print_labels | clearance/actions | 流程步骤 |

- [ ] **Step 4: 创建 pack.py + process.py**

`backend/packs/retail/pack.py`：

```python
"""retail 行业包声明。"""
import os
from ontology.pack import (IndustryPack, CapabilityDomain, ValueChainProcess,
                           register_pack)
from ontology.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.abspath(__file__))  # packs/retail/

MARKETING = CapabilityDomain(
    name="marketing", display_name="营销域",
    ttl_path=os.path.join(_BASE, "domains", "marketing", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "domains", "marketing", "actions"),
    rules_dir=os.path.join(_BASE, "domains", "marketing", "rules"))

ORGANIZATION = CapabilityDomain(
    name="organization", display_name="组织域",
    ttl_path=os.path.join(_BASE, "domains", "organization", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "domains", "organization", "actions"))

FINANCE = CapabilityDomain(
    name="finance", display_name="财务域",
    ttl_path=os.path.join(_BASE, "domains", "finance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "domains", "finance", "actions"))

CLEARANCE = ValueChainProcess(
    name="clearance", display_name="出清",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "processes", "clearance", "skills"),
    tools_module="packs.retail.processes.clearance.tools",
    actions_dir=os.path.join(_BASE, "processes", "clearance", "actions"),
    system_prompt_intro="你是门店临期商品管理助手。")

RETAIL_PACK = IndustryPack(
    name="retail", display_name="零售行业包",
    domains=[MARKETING, ORGANIZATION, FINANCE],
    processes=[CLEARANCE])

register_pack(RETAIL_PACK)
```

`backend/packs/retail/processes/clearance/process.py`：保留 process 配置（如需独立引用）。
`backend/packs/retail/processes/clearance/tools.py`：从 `verticals/clearance/tools.py` 复制 query_near_expiry + TOOLS。

- [ ] **Step 5: 迁移 skills + discount_rules**

复制 `backend/skills/store-ontology/{SKILL.md,clearance-workflow/SKILL.md}` → `packs/retail/processes/clearance/skills/`。
复制 `data/discount_rules.json` → `packs/retail/domains/marketing/rules/discount_rules.json`。

- [ ] **Step 6: 验证 pack_to_registry 解析正确**

Run:
```bash
/opt/miniconda3/envs/store-ontology/bin/python -c "
import sys; sys.path.insert(0,'.')
from ontology.bootstrap import bootstrap; bootstrap()
from ontology.pack import get_pack, pack_to_registry
pack = get_pack('retail')
reg = pack_to_registry(pack, data_dir='../data')
print('Objects:', sorted(reg.object_types.keys()))
print('Links:', len(reg.link_types))
print('Actions:', sorted(reg.action_types.keys()))
assert {'Product','NearExpiryProduct','Store','Employee','Task','LossReport','Region'}.issubset(reg.object_types)
assert {'create_clearance_task','deduct_stock','submit_for_approval','create_loss_report'}.issubset(reg.action_types)
print('OK')
"
```
Expected: 7 Object + 10 Link + 8+ Action 解析成功。

- [ ] **Step 7: 运行 bootstrap 测试**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_pack_bootstrap.py -v`
Expected: 3 passed（retail pack 被发现）

- [ ] **Step 8: Commit**

```bash
git add backend/packs/
git commit -m "feat(pack) P2-T3: retail-pack 搭建（3 domain TTL 拆分 + clearance process + Action 迁移）"
```

---

## Task 4: main.py 聚合 pack + vertical

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_pack_integration.py`

> main.py 的工具/skill/prompt 聚合从"仅 vertical"升级为"pack + vertical"。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_pack_integration.py`：

```python
"""测试 main.py 聚合 pack + vertical（P2 集成）。"""
import pytest


def test_retail_pack_registered_after_bootstrap():
    from ontology.bootstrap import bootstrap
    from ontology.pack import get_pack
    bootstrap()
    assert get_pack("retail") is not None


def test_clearance_process_has_tools():
    """clearance process 的 tools_module 能 import。"""
    from ontology.bootstrap import bootstrap
    from ontology.pack import get_pack
    bootstrap()
    pack = get_pack("retail")
    clearance = next(p for p in pack.processes if p.name == "clearance")
    import importlib
    mod = importlib.import_module(clearance.tools_module)
    assert hasattr(mod, "TOOLS")
    assert len(mod.TOOLS) >= 1


def test_pack_to_registry_all_objects():
    """pack_to_registry 合并后含全部 7 Object。"""
    from ontology.bootstrap import bootstrap
    from ontology.pack import get_pack, pack_to_registry
    bootstrap()
    pack = get_pack("retail")
    reg = pack_to_registry(pack, data_dir="../data")
    assert len(reg.object_types) == 7
```

- [ ] **Step 2: 运行测试，确认通过（T3 已建 pack，应基本通过）**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_pack_integration.py -v`
Expected: 3 passed

- [ ] **Step 3: main.py 聚合升级**

修改 `backend/main.py` 的 `_aggregate_vertical_tools` / `_aggregate_skill_paths` / `_build_combined_prompt`，增加 pack 来源：

在现有聚合函数中追加 pack 的 process tools / skills：
```python
def _aggregate_pack_tools():
    """从各 pack 的 process.tools_module 聚合专属工具。"""
    import importlib
    from ontology.pack import all_packs
    collected = []
    for pack in all_packs():
        for proc in pack.processes:
            if not proc.tools_module:
                continue
            try:
                mod = importlib.import_module(proc.tools_module)
                collected.extend(getattr(mod, "TOOLS", []))
            except Exception as e:
                print(f"[main] 加载 pack '{pack.name}' process '{proc.name}' 工具失败: {e}")
    return collected
```

在 `tools = [...] + _aggregate_vertical_tools()` 后追加 `+ _aggregate_pack_tools()`。
在 `_aggregate_skill_paths` 中追加 pack process 的 skills_dir。

- [ ] **Step 4: 运行全量测试**

Run: `/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/ -q`
Expected: 全部通过（117+ 新测试）

- [ ] **Step 5: main import 冒烟**

Run: `QWEN_API_KEY=stub /opt/miniconda3/envs/store-ontology/bin/python -c "import sys; sys.path.insert(0,'.'); import main; print('OK', len(main.tools))"`

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_pack_integration.py
git commit -m "feat(pack) P2-T4: main.py 聚合 pack + vertical 的工具/skill/prompt"
```

---

## Self-Review

**1. Spec 覆盖：**
- 三级结构（IndustryPack/Domain/Process）→ T1 ✅
- pack 注册表 + pack_to_registry → T1 ✅
- bootstrap 扫 packs → T2 ✅
- clearance 迁移（TTL 拆分 + Action 按域 + 状态机归 process）→ T3 ✅
- equipment_repair 不动（兼容验证）→ T2 的 `test_bootstrap_still_discovers_verticals` ✅
- main.py 聚合 → T4 ✅

**2. 占位符：** T3 的 TTL 拆分是"从 store.ttl 复制相关块"，具体内容在执行时从现有文件取——这是合理的（现有 store.ttl 内容已确认）。其余步骤有完整代码。

**3. 类型一致性：** `CapabilityDomain(name, display_name, ttl_path, actions_dir)` 在 T1 定义，T3 引用一致；`ValueChainProcess(name, workflow_object_type, state_transitions)` 一致；`pack_to_registry(pack, data_dir)` 签名 T1 定义、T3/T4 调用一致。
