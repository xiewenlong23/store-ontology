# workspace 自洽 + agent 隔离 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉 IndustryPack 中间层，工作目录自洽化（customer_default→jjy、equipment_repair→customerA），agent per-workspace 实例隔离，更新设计文档。

**Architecture:** 每个工作目录直接声明 CapabilityDomain[] + ValueChainProcess[]（经 workspace.py 注册），无 IndustryPack 包装。每个工作目录独立 agent 实例（只含该目录工具/skill/本体）。endpoint 网关按 X-Workspace 路由。

**Tech Stack:** Python 3.11 / FastAPI / langgraph / deepagents / pytest。

**关联 spec:** `docs/superpowers/specs/2026-06-21-v2-agent-isolation-design.md`

**术语基线:** 工作目录（=原 pack，如 retail/jjy/customerA）/ CapabilityDomain（能力域）/ ValueChainProcess（价值链流程）。**无 IndustryPack**。

**基线:** `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q` → 当前 156 passed。所有 WP 以此为门槛。

**强制顺序:** WP1 → WP2 → WP3 → WP4 → Docs。前一个 WP 的 pytest 不全绿，不进下一个。

---

## File Structure

**WP1（去 IndustryPack）:**
- Modify: `agent/engine/pack.py`（删 IndustryPack/注册表，保留 CapabilityDomain/ValueChainProcess，新增 WorkspaceDef + 注册表 + domains_to_registry）
- Modify: `agent/engine/bootstrap.py`（扫 workspace.py 取代 pack.py）
- Rename: `workspace/retail/pack.py` → `workspace/retail/workspace.py`
- Rename: `workspace/equipment_repair/pack.py` → `workspace/equipment_repair/workspace.py`
- Modify: `agent/main.py`（all_packs → all_workspace_dirs，pack_to_registry → domains_to_registry）
- Modify: `agent/engine/workspace_bootstrap.py`（get_pack → get_workspace_dir）
- Modify: `agent/tools/shared.py`（process_config 取自 workspace_dir）
- Modify: 7 个测试（import + 调用点）

**WP2（改名自洽）:**
- Rename: `workspace/customer_default/` → `workspace/jjy/`（+ 拷贝 retail 内容自洽）
- Rename: `workspace/equipment_repair/` → `workspace/customerA/`
- Modify: 兜底常量（tenant.py/shared.py/main.py/workspace_bootstrap.py）
- Modify: 12 个测试 + 数据文件 workspace_name

**WP3（agent 隔离）:**
- Modify: `agent/main.py`（新增 build_workspace_graph + 缓存 + 自写 endpoint）
- Delete: `add_langgraph_fastapi_endpoint` 绑定 + 全局 deep_agent_graph 单例

**WP4 + Docs:** 重写 manual 4+8，更新 11 份 design 文档。

---

# WP1：去 IndustryPack

## Task 1.1：重构 engine/pack.py（去 IndustryPack，新增 WorkspaceDef）

**Files:**
- Modify: `agent/engine/pack.py`

- [ ] **Step 1: 重写 pack.py——删 IndustryPack + 注册表，新增 WorkspaceDef + domains_to_registry**

把 `agent/engine/pack.py` 全文替换为：

```python
"""工作目录定义：CapabilityDomain + ValueChainProcess + WorkspaceDef。

去掉 IndustryPack 中间层：每个工作目录直接是一组能力域 + 价值链流程的扁平集合。
工作目录经 workspace/*/workspace.py 的 register_workspace_dir 注册。
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.parser import OntologyParser, EntityRegistry
from engine.action_loader import load_actions


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
    actions_dir: Optional[str] = None
    system_prompt_intro: str = ""
    description: str = ""


@dataclass
class WorkspaceDef:
    """工作目录定义：一组能力域 + 价值链流程（取代原 IndustryPack 容器）。"""
    name: str
    display_name: str
    domains: List[CapabilityDomain] = field(default_factory=list)
    processes: List[ValueChainProcess] = field(default_factory=list)
    data_dir: str = ""


# ============ 工作目录注册表 ============

_workspace_dirs: Dict[str, WorkspaceDef] = {}


def register_workspace_dir(ws_def: WorkspaceDef) -> None:
    _workspace_dirs[ws_def.name] = ws_def


def get_workspace_dir(name: str) -> Optional[WorkspaceDef]:
    return _workspace_dirs.get(name)


def all_workspace_dirs() -> List[WorkspaceDef]:
    return list(_workspace_dirs.values())


def clear_workspace_dirs() -> None:
    _workspace_dirs.clear()


def domains_to_registry(ws_def: WorkspaceDef, data_dir: str = ".") -> EntityRegistry:
    """合并工作目录下所有 domain + process 的定义为一个 EntityRegistry。

    取代原 pack_to_registry。入参从 IndustryPack 改为 WorkspaceDef（结构相同）。
    """
    registry = EntityRegistry()

    for domain in ws_def.domains:
        if not os.path.exists(domain.ttl_path):
            continue
        p = OntologyParser(ttl_path=domain.ttl_path, data_dir=data_dir)
        registry.object_types.update(p.registry.object_types)
        registry.link_types.update(p.registry.link_types)

    for domain in ws_def.domains:
        if domain.actions_dir and os.path.isdir(domain.actions_dir):
            registry.action_types.update(load_actions(domain.actions_dir))
    for proc in ws_def.processes:
        if proc.actions_dir and os.path.isdir(proc.actions_dir):
            registry.action_types.update(load_actions(proc.actions_dir))

    return registry


# ============ 向后兼容别名（迁移期，WP1 完成后可逐步移除）============
# 旧代码 import IndustryPack/register_pack/all_packs/pack_to_registry 的临时桥接。
# 这些在 WP1 测试改完后应无调用者；若 grep 确认零引用，可在后续清理。

IndustryPack = WorkspaceDef  # type: ignore[misc,assignment]

def register_pack(ws_def) -> None:
    """deprecated: 用 register_workspace_dir。"""
    register_workspace_dir(ws_def)

def get_pack(name: str):
    """deprecated: 用 get_workspace_dir。"""
    return get_workspace_dir(name)

def all_packs() -> List[WorkspaceDef]:
    """deprecated: 用 all_workspace_dirs。"""
    return all_workspace_dirs()

def clear_packs() -> None:
    """deprecated: 用 clear_workspace_dirs。"""
    clear_workspace_dirs()

def pack_to_registry(ws_def, data_dir: str = ".") -> EntityRegistry:
    """deprecated: 用 domains_to_registry。"""
    return domains_to_registry(ws_def, data_dir)
```

> 兼容别名让本次重构分步进行：pack.py 先改，调用者（main/bootstrap/workspace_bootstrap/tests）随后逐个改。最后一步删别名。

- [ ] **Step 2: 跑测试，确认兼容别名让现有测试仍过**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 156 passed（兼容别名生效，暂不破坏调用者）

- [ ] **Step 3: Commit**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git add agent/engine/pack.py
git commit -m "refactor(engine/pack): 去 IndustryPack，新增 WorkspaceDef（兼容别名过渡）

删 IndustryPack 类，新增 WorkspaceDef（同结构）。新增 register_workspace_dir/
get_workspace_dir/all_workspace_dirs/domains_to_registry。旧名 register_pack/all_packs/
pack_to_registry 等作 deprecated 别名保留，供分步迁移。"
```

## Task 1.2：bootstrap 扫 workspace.py + retail/equipment_repair 改 workspace.py

**Files:**
- Modify: `agent/engine/bootstrap.py`
- Rename: `workspace/retail/pack.py` → `workspace/retail/workspace.py`
- Rename: `workspace/equipment_repair/pack.py` → `workspace/equipment_repair/workspace.py`

- [ ] **Step 1: bootstrap 扫 workspace.py**

把 `agent/engine/bootstrap.py` 的 `bootstrap()` 改为扫 workspace.py（同时保留 pack.py 兼容）：

```python
def bootstrap() -> None:
    """发现并注册所有 workspace 工作目录（幂等）。

    扫描 workspace/*/workspace.py（新）+ workspace/*/pack.py（兼容旧）。
    """
    _discover_packages("workspace", "workspace", "workspace")
    _discover_packages("workspace", "pack", "workspace")  # 兼容尚未改名的
```

同步更新文件顶部 docstring："扫描 workspace/*/workspace.py 注册工作目录"。

- [ ] **Step 2: retail/pack.py → retail/workspace.py，改声明**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv workspace/retail/pack.py workspace/retail/workspace.py
```

编辑 `workspace/retail/workspace.py`：把 import 从 `IndustryPack, CapabilityDomain, ValueChainProcess, register_pack` 改为 `WorkspaceDef, CapabilityDomain, ValueChainProcess, register_workspace_dir`；把 `RETAIL_PACK = IndustryPack(...)` 改为 `RETAIL_WS = WorkspaceDef(...)`；`register_pack(RETAIL_PACK)` → `register_workspace_dir(RETAIL_WS)`。display_name 改"零售（示例）"。docstring 去"行业包"措辞。

完整文件：
```python
"""retail 工作目录（示例）。3 能力域 + 1 价值链流程（clearance）。

目录结构：ontology/domains/<域>/ + data/ + skills/。
"""
import os

from engine.pack import WorkspaceDef, CapabilityDomain, ValueChainProcess, register_workspace_dir
from engine.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.abspath(__file__))

MARKETING = CapabilityDomain(
    name="marketing", display_name="营销域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "marketing", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "marketing", "actions"),
    rules_dir=os.path.join(_BASE, "ontology", "domains", "marketing", "rules"))

ORGANIZATION = CapabilityDomain(
    name="organization", display_name="组织域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "organization", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "organization", "actions"))

FINANCE = CapabilityDomain(
    name="finance", display_name="财务域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "finance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "finance", "actions"))

CLEARANCE = ValueChainProcess(
    name="clearance", display_name="出清",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.retail.skills.clearance_workflow.tools",
    actions_dir=os.path.join(_BASE, "skills", "clearance_workflow", "actions"),
    system_prompt_intro="你是门店临期商品管理助手。")

RETAIL_WS = WorkspaceDef(
    name="retail", display_name="零售（示例）",
    domains=[MARKETING, ORGANIZATION, FINANCE],
    processes=[CLEARANCE],
    data_dir=os.path.join(_BASE, "data"))

register_workspace_dir(RETAIL_WS)
```

- [ ] **Step 3: equipment_repair/pack.py → equipment_repair/workspace.py，同样改**

```bash
git mv workspace/equipment_repair/pack.py workspace/equipment_repair/workspace.py
```

编辑 `workspace/equipment_repair/workspace.py`：同 retail 的改法。`EQUIPMENT_REPAIR_PACK = IndustryPack(...)` → `EQUIPMENT_REPAIR_WS = WorkspaceDef(name="equipment_repair", display_name="设备维修（示例）", ...)`；`register_pack(...)` → `register_workspace_dir(...)`。

- [ ] **Step 4: 跑测试**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 156 passed

- [ ] **Step 5: Commit**

```bash
git add agent/engine/bootstrap.py workspace/retail/workspace.py workspace/equipment_repair/workspace.py
git commit -m "refactor: bootstrap 扫 workspace.py + retail/equipment_repair 改 workspace.py（去 IndustryPack 声明）"
```

## Task 1.3：main.py 调用点改 all_workspace_dirs/domains_to_registry

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: _aggregate_pack_tools / _aggregate_skill_paths / _build_combined_prompt 改用 all_workspace_dirs + domains_to_registry**

`agent/main.py`：

`_aggregate_pack_tools`：`from engine.pack import all_packs` → `from engine.pack import all_workspace_dirs`；`for pack in all_packs()` → `for ws in all_workspace_dirs()`；`pack.processes` → `ws.processes`；`pack.name` → `ws.name`。函数名保留（后续 WP3 会重构）。

`_aggregate_skill_paths`：同上改 `all_workspace_dirs()` + `ws.processes`。

`_build_combined_prompt`：`from engine.pack import all_packs, pack_to_registry` → `from engine.pack import all_workspace_dirs, domains_to_registry`；`for pack in all_packs()` → `for ws in all_workspace_dirs()`；`pack.processes` → `ws.processes`；`pack.display_name` → `ws.display_name`；`pack_to_registry(pack, data_dir=pack.data_dir)` → `domains_to_registry(ws, data_dir=ws.data_dir)`。

- [ ] **Step 2: 跑测试**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 156 passed

- [ ] **Step 3: Commit**

```bash
git add agent/main.py
git commit -m "refactor(main): _aggregate_*/_build_combined_prompt 改 all_workspace_dirs/domains_to_registry"
```

## Task 1.4：workspace_bootstrap + shared 改 get_workspace_dir

**Files:**
- Modify: `agent/engine/workspace_bootstrap.py`
- Modify: `agent/tools/shared.py`

- [ ] **Step 1: workspace_bootstrap 的 get_pack/pack_to_registry 改 get_workspace_dir/domains_to_registry**

`agent/engine/workspace_bootstrap.py` line 80-88 区域：
```python
        from engine.pack import get_workspace_dir, domains_to_registry
        from engine.bootstrap import bootstrap
        bootstrap()
        ws = get_workspace_dir(cfg.source_pack or "retail")
        if ws:
            registry = domains_to_registry(ws, data_dir=data_dir)
        else:
            from engine.parser import EntityRegistry
            registry = EntityRegistry()
```

line 96-102（executor config）：
```python
    from engine.executor import ActionExecutor
    from engine.pack import get_workspace_dir
    process_config = None
    if cfg.source_pack:
        ws = get_workspace_dir(cfg.source_pack)
        if ws and ws.processes:
            process_config = ws.processes[0]
```

- [ ] **Step 2: shared.py 的 get_pack 改 get_workspace_dir（_get_executor 的 process 匹配段）**

`agent/tools/shared.py` `_get_executor` 里：
```python
    from engine.pack import get_pack
    pack = get_pack(inst.config.source_pack) if inst.config and inst.config.source_pack else None
```
改为：
```python
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if ws is None:
        warnings.warn(...)
        return inst.executor
    for proc in ws.processes:
        ...
```
（把后续 `pack.processes` 改 `ws.processes`）

- [ ] **Step 3: 跑测试**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 156 passed

- [ ] **Step 4: Commit**

```bash
git add agent/engine/workspace_bootstrap.py agent/tools/shared.py
git commit -m "refactor: workspace_bootstrap/shared 改 get_workspace_dir/domains_to_registry"
```

## Task 1.5：测试改 import + 删兼容别名

**Files:**
- Modify: `agent/tests/test_pack.py`, `test_pack_bootstrap.py`, `test_pack_integration.py`, `_clearance_helper.py`, `test_equipment_repair.py`, `test_bootstrap.py`, `test_pack_registry.py`

- [ ] **Step 1: 批量改测试 import + 调用点**

把测试里所有：
- `from engine.pack import IndustryPack` → `from engine.pack import WorkspaceDef`
- `IndustryPack(...)` → `WorkspaceDef(...)`
- `register_pack` → `register_workspace_dir`
- `get_pack` → `get_workspace_dir`
- `all_packs` → `all_workspace_dirs`
- `clear_packs` → `clear_workspace_dirs`
- `pack_to_registry` → `domains_to_registry`

用脚本批量替换：
```bash
cd /Users/xiewenlong/Documents/code/store-ontology
python3 - <<'PY'
import re, glob
for f in glob.glob("agent/tests/*.py"):
    s = open(f, encoding="utf-8").read()
    o = s
    s = s.replace("IndustryPack", "WorkspaceDef")
    s = s.replace("register_pack(", "register_workspace_dir(")
    s = s.replace("get_pack(", "get_workspace_dir(")
    s = s.replace("all_packs(", "all_workspace_dirs(")
    s = s.replace("clear_packs(", "clear_workspace_dirs(")
    s = s.replace("pack_to_registry(", "domains_to_registry(")
    # RETAIL_PACK/EQUIPMENT_REPAIR_PACK 变量名已改，测试里若引用也改
    s = s.replace("RETAIL_PACK", "RETAIL_WS")
    s = s.replace("EQUIPMENT_REPAIR_PACK", "EQUIPMENT_REPAIR_WS")
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print(f"updated {f}")
PY
```

> `test_pack_registry.py` 里的 `import workspace.retail.pack` 也要改 `import workspace.retail.workspace`（包模块改名了）。

- [ ] **Step 2: 跑测试，逐个修剩余问题**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -5`
Expected: 可能个别测试因 import workspace.retail.pack 失败。逐一修（`import workspace.retail.pack` → `workspace.retail.workspace`，`from workspace.retail.pack import RETAIL_PACK` → `from workspace.retail.workspace import RETAIL_WS`）。直到 156 passed。

- [ ] **Step 3: 删 pack.py 的兼容别名**

确认无调用者后，删 `agent/engine/pack.py` 末尾的兼容别名段（IndustryPack/register_pack/get_pack/all_packs/clear_packs/pack_to_registry 的 deprecated 别名）。grep 确认：
```bash
grep -rn 'IndustryPack\|register_pack\|get_pack\b\|all_packs\|clear_packs\|pack_to_registry' agent --include='*.py' | grep -v __pycache__ | grep -v '.venv'
# 期望零命中（或仅在 pack.py 的删后残留）
```

- [ ] **Step 4: 跑全套**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 156 passed

- [ ] **Step 5: WP1 验收 grep**

```bash
grep -rn 'IndustryPack\|all_packs\|register_pack\|get_pack\|pack_to_registry' agent --include='*.py' | grep -v __pycache__ | grep -v '.venv'
# 期望零命中
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(tests): 测试改 WorkspaceDef/register_workspace_dir + 删兼容别名

WP1 完成：去 IndustryPack。agent/ 内零 IndustryPack/all_packs/register_pack 残留。
pytest 156 passed。"
```

> **WP1 门槛：pytest 156 passed + grep 零残留。两项都过才进 WP2。**

---

# WP2：工作目录改名 + 自洽化

## Task 2.1：customer_default → jjy 自洽化

**Files:**
- Rename: `workspace/customer_default/` → `workspace/jjy/`
- Create: `workspace/jjy/workspace.py`, `ontology/`, `data/`, `skills/`（从 retail 拷贝）

- [ ] **Step 1: 目录改名 + 拷贝 retail 内容自洽**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv workspace/customer_default workspace/jjy
# 从 retail 拷贝 ontology/data/skills（jjy 自洽，不再依赖 retail）
cp -r workspace/retail/ontology workspace/jjy/ontology
cp -r workspace/retail/data workspace/jjy/data
cp -r workspace/retail/skills workspace/jjy/skills
cp workspace/retail/workspace.py workspace/jjy/workspace.py
```

- [ ] **Step 2: 改 jjy/workspace.py（name=jjy，工具模块路径）**

编辑 `workspace/jjy/workspace.py`：把 `name="retail"` → `name="jjy"`；`display_name` → "客户 jjy"；`tools_module="workspace.retail.skills.clearance_workflow.tools"` → `"workspace.jjy.skills.clearance_workflow.tools"`；`RETAIL_WS` → `JJY_WS`。其余（domain TTL 路径，因拷贝到 jjy/ 下，`_BASE` 自动是 jjy/）不变。

- [ ] **Step 3: 数据文件 workspace_name 字段改 jjy**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
python3 - <<'PY'
import json, glob
for f in glob.glob("workspace/jjy/data/*.json"):
    d = json.load(open(f))
    for rec in d:
        if isinstance(rec, dict) and rec.get("workspace_name") == "customer_default":
            rec["workspace_name"] = "jjy"
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=2)
    print(f"updated {f}")
PY
```

- [ ] **Step 4: 删 jjy/config.yaml 的 source_pack 依赖（jjy 自洽，不再指向 retail）**

编辑 `workspace/jjy/config.yaml`：
```yaml
workspace_name: jjy
name: 客户 jjy
storage:
  type: json_files
  data_dir: workspace/jjy/data
enabled_domains: [marketing, organization, finance]
enabled_processes: [clearance]
org_tree:
  - { id: brand_jjy, parent: null }
  - { id: store_001, parent: brand_jjy }
  - { id: store_002, parent: brand_jjy }
```
（删 source_pack 行；data_dir 指向 jjy/data）

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(workspace): customer_default→jjy 自洽化（拷贝 retail 内容）

jjy 现在是独立工作目录（自己的 ontology/data/skills），不再 source_pack 指向 retail。
数据 workspace_name 字段改 jjy。"
```

## Task 2.2：equipment_repair → customerA

**Files:**
- Rename: `workspace/equipment_repair/` → `workspace/customerA/`

- [ ] **Step 1: 目录改名**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv workspace/equipment_repair workspace/customerA
```

- [ ] **Step 2: 改 customerA/workspace.py（name=customerA）+ import 路径**

编辑 `workspace/customerA/workspace.py`：`name="equipment_repair"` → `name="customerA"`；`display_name` → "客户 A"；`from workspace.equipment_repair.skills...` → `from workspace.customerA.skills...`；`tools_module="workspace.equipment_repair..."` → `"workspace.customerA..."`；`EQUIPMENT_REPAIR_WS` → `CUSTOMERA_WS`。

- [ ] **Step 3: 全局改 workspace.equipment_repair → workspace.customerA（import 路径）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
grep -rln 'workspace.equipment_repair\|workspace\.equipment_repair' agent tests workspace --include='*.py' | grep -v __pycache__
# 逐一改 import 路径
python3 - <<'PY'
import glob
for f in glob.glob("agent/**/*.py", recursive=True) + glob.glob("workspace/**/*.py", recursive=True):
    if '__pycache__' in f: continue
    s = open(f, encoding="utf-8").read()
    o = s
    s = s.replace("workspace.equipment_repair", "workspace.customerA")
    s = s.replace("workspace/equipment_repair", "workspace/customerA")
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print(f"updated {f}")
PY
```

- [ ] **Step 4: 跑测试，修剩余 import**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -5`
Expected: 可能 test_equipment_repair.py 的 import 失败。改 `from workspace.equipment_repair` → `from workspace.customerA`。直到通过。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(workspace): equipment_repair→customerA 改名 + import 路径更新"
```

## Task 2.3：兜底常量 customer_default → jjy

**Files:**
- Modify: `agent/engine/tenant.py`, `agent/tools/shared.py`, `agent/main.py`, `agent/engine/workspace_bootstrap.py`

- [ ] **Step 1: 批量改兜底常量**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
python3 - <<'PY'
import glob
files = ["agent/engine/tenant.py", "agent/tools/shared.py", "agent/main.py",
         "agent/engine/workspace_bootstrap.py"]
for f in files:
    s = open(f, encoding="utf-8").read()
    o = s
    s = s.replace('"customer_default"', '"jjy"')
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print(f"updated {f}")
PY
```

> `workspace_bootstrap.py` 的 `_DEFAULT_WORKSPACE_DIR` 路径 `"workspace", "customer_default"` → `"workspace", "jjy"`；`if workspace_name == "customer_default"` → `== "jjy"`。手动核对这些是否被上面的脚本覆盖（路径字符串里的 customer_default 也要改）。

- [ ] **Step 2: 测试 fixture 改 customer_default → jjy**

```bash
python3 - <<'PY'
import glob
for f in glob.glob("agent/tests/*.py"):
    if '__pycache__' in f: continue
    s = open(f, encoding="utf-8").read()
    o = s
    s = s.replace('"customer_default"', '"jjy"')
    s = s.replace("'customer_default'", "'jjy'")
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print(f"updated {f}")
PY
```

- [ ] **Step 3: 跑全套**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 156 passed（或微调后全绿）

- [ ] **Step 4: WP2 验收 grep**

```bash
grep -rn 'customer_default\|equipment_repair' agent workspace --include='*.py' --include='*.yaml' --include='*.json' | grep -v __pycache__ | grep -v '.venv'
# 期望零命中（除历史注释）
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: 兜底常量+测试 customer_default→jjy

WP2 完成：workspace/ 下是 retail/jjy/customerA 三个自洽工作目录。
代码零 customer_default/equipment_repair 残留。pytest 通过。"
```

> **WP2 门槛：pytest 通过 + grep 零残留。两项都过才进 WP3。**

---

# WP3：agent per-workspace 隔离

## Task 3.1：新增 build_workspace_graph + per-workspace agent 缓存

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: 新增 build_workspace_graph(ws_name) 函数**

在 `agent/main.py` 的 `_build_combined_prompt` 之后新增：

```python
def _build_workspace_tools(ws_name: str):
    """聚合指定工作目录的专属工具（内核8 + 该目录的 process.tools_module）。"""
    import importlib
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(ws_name)
    if not ws:
        return []
    collected = []
    for proc in ws.processes:
        if not proc.tools_module:
            continue
        try:
            mod = importlib.import_module(proc.tools_module)
            collected.extend(getattr(mod, "TOOLS", []))
        except Exception as e:  # noqa: BLE001
            print(f"[main] 加载工作目录 '{ws_name}' process '{proc.name}' 工具失败: {e}")
    return collected


def _build_workspace_skills(ws_name: str):
    """聚合指定工作目录的 skill 路径。"""
    paths = []
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(ws_name)
    if not ws:
        return [], []
    sys_names = []
    for proc in ws.processes:
        if not proc.skills_dir or not os.path.isdir(proc.skills_dir):
            continue
        for name in os.listdir(proc.skills_dir):
            if name in ("tmp", "__pycache__"):
                continue
            skill_path = os.path.join(proc.skills_dir, name)
            if os.path.isdir(skill_path) and os.path.exists(os.path.join(skill_path, "SKILL.md")):
                paths.append(f"/{name}/")
    return paths


def _build_workspace_prompt(ws_name: str) -> str:
    """构建指定工作目录的本体提示（只含该目录的实体/关系/Action）。"""
    from engine.pack import get_workspace_dir, domains_to_registry
    ws = get_workspace_dir(ws_name)
    if not ws:
        return ""
    parts = []
    for proc in ws.processes:
        intro = proc.system_prompt_intro or ws.display_name
        registry = domains_to_registry(ws, data_dir=ws.data_dir or ".")
        lines = [f"{intro}\n"]
        lines.append("可用实体（用 query_entity 查询）: "
                     + ", ".join(ot.label_zh for ot in registry.object_types.values()))
        lines.append("\n关系（用 traverse_relation）: "
                     + ", ".join(f"{lt.label_zh}({lt.domain}->{lt.range})"
                                 for lt in registry.link_types.values()))
        lines.append("\n操作（用 execute_action/confirm_action）: "
                     + ", ".join(registry.action_types.keys()))
        lines.append("\n用中文回复。")
        parts.append("\n".join(lines))
    return "\n\n---\n\n".join(parts) if parts else ""


def build_workspace_graph(ws_name: str):
    """构建指定工作目录的 deep agent graph（per-workspace 隔离）。"""
    ws_tools = _KERNEL_TOOLS + _build_workspace_tools(ws_name)
    # 去重
    seen = set()
    tools = []
    for t in ws_tools:
        n = getattr(t, "name", "")
        if n in seen:
            continue
        seen.add(n)
        tools.append(t)

    ws_skill_paths = _build_workspace_skills(ws_name) or []
    sys_skill_names = _list_system_skill_dirs()
    skill_paths = [f"/system/{n}/" for n in sys_skill_names] + ws_skill_paths

    ws_prompt = _build_workspace_prompt(ws_name) + _STORE_CONTEXT

    ws_skills_backend = _build_ws_skills_backend(ws_name, sys_skill_names)
    return create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=ws_prompt,
        checkpointer=MemorySaver(),
        backend=ws_skills_backend,
        skills=skill_paths,
    )
```

> 需把原 module 级的 `tools`/`_skill_paths`/`system_prompt`/`skills_backend` 重构为函数内构建。`_KERNEL_TOOLS` = `[query_entity, create_entity, update_entity, traverse_relation, execute_action, confirm_action, query_task, update_task]`（原 line 140-149 的内核 8 个）。`_STORE_CONTEXT` = 原 store_context 字符串。`_build_ws_skills_backend` = 原 skills_backend 构建逻辑参数化（workspace skills root 按 ws_name 解析）。

- [ ] **Step 2: 新增 per-workspace agent 缓存**

```python
from ag_ui_langgraph import LangGraphAgent
_ws_agents: dict = {}

def get_or_build_ws_agent(ws_name: str) -> LangGraphAgent:
    """per-workspace agent 缓存。graph 按工作目录隔离。"""
    if ws_name not in _ws_agents:
        graph = build_workspace_graph(ws_name)
        _ws_agents[ws_name] = LangGraphAgent(name=ws_name, graph=graph)
    return _ws_agents[ws_name]
```

- [ ] **Step 3: 跑测试（确认重构没破坏 import）**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 通过（或修剩余引用）

- [ ] **Step 4: Commit**

```bash
git add agent/main.py
git commit -m "feat(main): 新增 build_workspace_graph + per-workspace agent 缓存"
```

## Task 3.2：自写 endpoint 网关路由 + 删全局单例

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: 替换 add_langgraph_fastapi_endpoint 为自写 endpoint**

删 `agent/main.py` 的 `deep_agent_graph = create_deep_agent(...)` 全局单例（原 line 223-231）+ `add_langgraph_fastapi_endpoint(...)` 绑定（原 line 298-306）。

新增自写 endpoint：
```python
from ag_ui.core import EventEncoder
from starlette.responses import StreamingResponse
from ag_ui.langgraph import RunAgentInput

@app.post("/api/copilotkit")
async def copilotkit_endpoint(input_data: RunAgentInput, request: Request):
    """AG-UI 网关：按 X-Workspace 路由到 per-workspace agent 实例。"""
    ws_name = _resolve_workspace_name(request)
    agent = get_or_build_ws_agent(ws_name)
    request_agent = agent.clone()  # per-request 状态隔离
    accept = request.headers.get("accept")
    encoder = EventEncoder(accept=accept)

    async def event_generator():
        async for event in request_agent.run(input_data):
            yield encoder.encode(event)
    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())
```

> `EventEncoder`/`RunAgentInput` 的 import 路径需实现时核实（`ag_ui.core` / `ag_ui_langgraph` / `ag_ui.langgraph`）。参考 add_langgraph_fastapi_endpoint 源码的 import。

- [ ] **Step 2: 跑测试**

Run: `cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3`
Expected: 通过（test_main_tenant/test_webhooks 等可能需调）

- [ ] **Step 3: 启动后端 + playwright 验证 SSE 流式**

```bash
cd agent && /opt/miniconda3/envs/store-ontology/bin/python main.py &  # 后台
sleep 4
curl -s http://localhost:8123/health  # 预期 healthy
```

playwright（用现有 /tmp/pw_test.py 或新写）：打开 localhost:3000，发消息，确认流式响应正常、AI 回复不空。

- [ ] **Step 4: 验证隔离——jjy 只见 retail 类实体，customerA 只见维修实体**

playwright 脚本：设 X-Workspace: jjy 发消息 → AI 只提零售实体；设 X-Workspace: customerA → AI 只提维修实体。

- [ ] **Step 5: kill 后端**

```bash
lsof -nP -iTCP:8123 -sTCP:LISTEN | tail -1 | awk '{print $2}' | xargs kill
```

- [ ] **Step 6: Commit**

```bash
git add agent/main.py
git commit -m "feat(main): 自写 endpoint 网关路由（per-workspace agent）+ 删全局单例

WP3 完成：agent per-workspace 隔离。jjy/customerA 各自独立 agent 实例，
工具/skill/本体只含该工作目录内容。SSE 流式经验证正常。"
```

> **WP3 门槛：pytest 通过 + playwright 验证隔离生效 + SSE 正常。**

---

# WP4：重写 manual

## Task 4.1：重写 manual 4 文档 + 8 模板（去 IndustryPack）

**Files:**
- Modify: `docs/design/manual/00-overview.md`, `01-onboarding.md`, `02-templates.md`, `03-worked-example-equipment-repair.md`
- Rename: `templates/pack.py.template` → `workspace.py.template`，`pack-tools.py.template` → `ws-tools.py.template`

- [ ] **Step 1: 批量改 manual 里的术语**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
python3 - <<'PY'
import glob
for f in glob.glob("docs/design/manual/**/*.md", recursive=True) + glob.glob("docs/design/manual/templates/*"):
    s = open(f, encoding="utf-8").read()
    o = s
    s = s.replace("IndustryPack", "工作目录（WorkspaceDef）")
    s = s.replace("行业包", "工作目录")
    s = s.replace("pack.py", "workspace.py")
    s = s.replace("pack_to_registry", "domains_to_registry")
    s = s.replace("register_pack", "register_workspace_dir")
    s = s.replace("all_packs", "all_workspace_dirs")
    s = s.replace("equipment_repair", "customerA")
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print(f"updated {f}")
PY
git mv docs/design/manual/templates/pack.py.template docs/design/manual/templates/workspace.py.template
git mv docs/design/manual/templates/pack-tools.py.template docs/design/manual/templates/ws-tools.py.template
```

- [ ] **Step 2: 核对 manual 内容与代码一致**

人工核对：`01-onboarding.md` 描述的接入流程（建 workspace.py + domains + processes）与代码一致；`03-worked-example` 用 customerA 对照真实 `workspace/customerA/workspace.py`。

- [ ] **Step 3: WP4 验收 grep**

```bash
grep -rn 'IndustryPack\|pack\.py\|pack_to_registry\|all_packs\|行业包' docs/design/manual/ | grep -v archive
# 期望零残留
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs(manual): 重写 4 文档+8模板（去 IndustryPack，对齐 workspace 自洽）"
```

---

# Docs：更新设计文档

## Task 5.1：更新 11 份 design 文档（去 IndustryPack + 改名）

**Files:**
- Modify: `docs/design/00-architecture.md`, `20-api-data-contract.md`, `30-development-guide.md`, `40-ontology-modeling-spec.md`, `README.md`, `roadmap.md`, `industry-packs/retail-clearance.md`

- [ ] **Step 1: 批量改 design 文档术语**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
python3 - <<'PY'
import glob
files = ["docs/design/00-architecture.md", "docs/design/20-api-data-contract.md",
         "docs/design/30-development-guide.md", "docs/design/40-ontology-modeling-spec.md",
         "docs/design/README.md", "docs/design/roadmap.md",
         "docs/design/industry-packs/retail-clearance.md"]
for f in files:
    s = open(f, encoding="utf-8").read()
    o = s
    s = s.replace("IndustryPack", "工作目录（WorkspaceDef）")
    s = s.replace("行业包", "工作目录")
    s = s.replace("pack.py", "workspace.py")
    s = s.replace("pack_to_registry", "domains_to_registry")
    s = s.replace("register_pack", "register_workspace_dir")
    s = s.replace("all_packs", "all_workspace_dirs")
    s = s.replace("customer_default", "jjy")
    s = s.replace("equipment_repair", "customerA")
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print(f"updated {f}")
PY
```

- [ ] **Step 2: 更新 roadmap §8/§9 状态（v2-agent 隔离已完成）**

`docs/design/roadmap.md`：§9 v2-agent 隔离标记 ✅ 完成；§8 v2-tenant 补充说明 agent 层也隔离了。

- [ ] **Step 3: 更新 00-architecture §3.2（工作目录结构，去 IndustryPack）**

人工核对 `docs/design/00-architecture.md` §3.2"行业包结构"改为"工作目录结构"，去 IndustryPack 表述，用 jjy/customerA/retail 作例。

- [ ] **Step 4: 全局 grep 验收**

```bash
grep -rn 'IndustryPack\|行业包\|customer_default\|equipment_repair\|pack\.py' docs/design --include='*.md' | grep -v 'archive/' | grep -v 'reference/palantir'
# 期望零残留（除 archive/ 历史）
```

- [ ] **Step 5: 最终全套验证**

```bash
cd agent && /opt/miniconda3/envs/store-ontology/bin/python -m pytest -q 2>&1 | tail -3  # 全绿
cd .. && git log --oneline -20  # 确认 WP1-4 + Docs commit 齐整
```

- [ ] **Step 6: Commit + push**

```bash
git add -A
git commit -m "docs: 更新 11 份设计文档（去 IndustryPack + 改名 jjy/customerA + workspace 自洽）

全 spec 完成：去 IndustryPack + workspace 自洽化 + agent per-workspace 隔离 + 文档更新。
roadmap §9 v2-agent 隔离标记完成。"
git push origin main
```

---

## Self-Review

**1. Spec 覆盖：**
- WP1 去 IndustryPack → Task 1.1-1.5 ✅
- WP2 改名自洽 → Task 2.1-2.3 ✅
- WP3 agent 隔离 → Task 3.1-3.2 ✅
- WP4 重写 manual → Task 4.1 ✅
- 文档更新 → Task 5.1 ✅
- 成功标准 1-7 → 各 WP 验收 grep + pytest + playwright ✅

**2. 占位扫描：** Task 3.1 的 `_KERNEL_TOOLS`/`_STORE_CONTEXT`/`_build_ws_skills_backend` 引用了需从原 main.py 重构出来的常量/逻辑——已在步骤内说明来源（原 line 140-149/store_context/skills_backend）。Task 3.2 EventEncoder import 路径标注"实现时核实"。这俩是技术核实点，非占位（给了明确来源）。

**3. 类型/命名一致性：**
- `WorkspaceDef`/`register_workspace_dir`/`get_workspace_dir`/`all_workspace_dirs`/`domains_to_registry` —— WP1 定义，WP2-4 + 测试消费，一致 ✅
- `build_workspace_graph`/`get_or_build_ws_agent` —— Task 3.1 定义，3.2 消费 ✅
- 工作目录名 retail/jjy/customerA —— WP2 定义，WP3-4 一致 ✅
- `workspace.py`（取代 pack.py）—— WP1 定义，WP2-4 一致 ✅
