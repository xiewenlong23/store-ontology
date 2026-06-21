> **🗄 归档说明**：brainstorming 产出（plan（实施计划）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# Workspace-First 目录重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `backend/` 重命名 + 重组为 `agent/`，将 `backend/packs/` + `customers/` 统一为 `workspace/`，废弃 `processes/`（其职责归入 `skills/`），并在前端加入 `X-Workspace` Header 路由——使目录与已确认的架构设计文档（`docs/superpowers/specs/2026-06-20-apaas-platform-architecture-design.md`）一致。

**Architecture:** 纯机械性目录迁移 + 导入路径/字符串字面量更新。**不改变任何运行时行为**——所有 147 个测试在重构后必须继续通过。两个关键技术约束：
1. **Python 模块名必须用下划线**（`clearance_workflow`，不能是 `clearance-workflow`）。SKILL.md 的 skill 名（用户可见的渐进式披露名）可保留连字符，但承载 Python 代码的目录必须用下划线。本计划统一用下划线目录名 `clearance_workflow`，同时保留 SKILL.md 中的 `name: clearance-workflow` 字段不变（这是 deepagents 渐进式披露用的逻辑名）。
2. **`workspace/` 必须是 Python 包**（含 `__init__.py`），否则 `from workspace.retail.skills.clearance_workflow.tools import ...` 无法工作。同样 `workspace/retail/`、`workspace/retail/skills/`、`workspace/retail/skills/clearance_workflow/` 都需要 `__init__.py`。

**Tech Stack:** Python 3.11 (FastAPI + LangGraph + deepagents), Next.js 15 (CopilotKit), pytest, uv

**Reference spec:** `docs/superpowers/specs/2026-06-20-apaas-platform-architecture-design.md`（§2 目录结构、§3 Agent 设计模式、§4.5 clearance 迁移示例）

**Scope boundary:** 本计划只做**目录形状**重构。下列内容**不在本计划范围**（留后续 spec+plan）：
- Action YAML 按域拆分（§4.5 说 clearance 的 4 个 action 按归属域拆到 marketing/supply_chain/finance）——保留 `processes/clearance/actions/` 现状，只是目录改名为 `skills/clearance_workflow/actions/`
- `discount.py` 实现代码迁为声明式 YAML（§3.1 说"复杂逻辑才写 Python"）——本计划只改路径不改实现
- `tenant_id` / `customer_id` 字段重命名为 `workspace_name`——本计划只改**目录名和路径字符串**，代码内的 `customer_id` 变量名/字段名保持不变（重命名是 P1 phase 的语义工作，不是机械重构）
- P3-P5 业务演进

**Verification gate:** 每个 Task 结束运行全套测试 `cd agent && .venv/bin/python -m pytest tests/ 2>&1 | tail -5`，必须 `147 passed`（重构后回归）。

---

## File Structure (target layout)

重构后项目根目录：

```
store-ontology/
├── agent/                           # 原 backend/（重命名 + 内部不重组，engine/ 保留）
│   ├── __init__.py
│   ├── engine/                      # 内核（不动）
│   │   ├── bootstrap.py             # 修改：扫描 "workspace" 而非 "packs"
│   │   ├── customer_bootstrap.py    # 修改：默认目录路径
│   │   ├── discount_stub.py         # 修改：路径字面量
│   │   └── ... (其他不动)
│   ├── tools/                       # 【新增空目录 + __init__.py】系统 Tool 占位（本计划只建目录）
│   │   └── __init__.py
│   ├── skills/                      # 【新增空目录 + __init__.py】系统 Skill 占位
│   │   └── __init__.py
│   ├── main.py                      # 修改：导入路径 + skills 根路径
│   ├── cli.py                       # 修改：路径字面量
│   ├── pyproject.toml               # 修改：packages=["agent"]
│   └── tests/                       # 跟随迁移，修改导入路径
│       ├── conftest.py              # 修改：BACKEND_DIR 注释 + packs 路径
│       ├── e2e/conftest.py          # 修改：packs 路径 → workspace 路径
│       ├── _clearance_helper.py     # 修改：packs 导入
│       └── (其他测试文件修改导入路径)
│
├── workspace/                       # 原 backend/packs/ + customers/ 合并
│   ├── __init.py                    # Python 包标记
│   ├── retail/                      # 原 backend/packs/retail/
│   │   ├── __init__.py
│   │   ├── pack.py                  # 修改：tools_module 路径 + 去掉 processes 路径
│   │   ├── ontology/                # 原 domains/ 重命名（纯 TTL + actions YAML）
│   │   │   └── domains/
│   │   │       ├── marketing/       # 含 domain.ttl + actions/ + 原 rules/
│   │   │       ├── organization/
│   │   │       └── finance/
│   │   ├── data/                    # 原 data/（不动）
│   │   └── skills/                  # 原 processes/clearance/* 合并到此
│   │       ├── __init__.py
│   │       └── clearance_workflow/  # 原 processes/clearance/（下划线！）
│   │           ├── __init__.py
│   │           ├── SKILL.md         # 原 processes/clearance/skills/clearance-workflow/SKILL.md
│   │           ├── tools.py         # 原 processes/clearance/tools.py
│   │           ├── automation.py    # 原 processes/clearance/automation.py
│   │           └── actions/         # 原 processes/clearance/actions/（4 YAML）
│   │       └── store_ontology/      # 原 processes/clearance/skills/store-ontology/（下划线！）
│   │           └── SKILL.md
│   ├── equipment_repair/            # 原 backend/packs/equipment_repair/
│   │   ├── __init__.py
│   │   ├── pack.py                  # 修改：tools_module 路径
│   │   ├── ontology/domains/maintenance/
│   │   ├── data/
│   │   └── skills/
│   │       ├── __init__.py
│   │       └── repair_workflow/     # 原 processes/repair/（下划线）
│   │           ├── __init__.py
│   │           ├── SKILL.md         # 原 processes/repair/skills/equipment-repair-knowledge/SKILL.md
│   │           ├── state_machine.py # 原 processes/repair/state_machine.py
│   │           ├── tools.py         # 原 processes/repair/tools.py（如有）
│   │           └── ...
│   │       └── equipment_repair_knowledge/  # 原 processes/repair/skills/equipment-repair-knowledge/
│   └── customer_default/            # 原 customers/customer_default/
│       ├── config.yaml              # 修改：data_dir 路径
│       └── (其他客户内容如有)
│
├── frontend/                        # 修改：route.ts + dashboard page.tsx 加 X-Workspace
│   └── app/
│       ├── api/copilotkit/route.ts  # 修改：加 X-Workspace header
│       └── dashboard/page.tsx       # 修改：fetch 加 X-Workspace header
│
├── README.md                        # 修改：路径引用
├── .env.example                     # 修改：注释路径
└── docs/                            # 历史文档不改（已 stale，标注即可）
```

---

## 关键设计决策（重构中不可动摇）

1. **Python 目录用下划线**：`clearance_workflow`（不是 `clearance-workflow`）。SKILL.md 的 frontmatter `name:` 字段可保留连字符（deepagents 渐进式披露的逻辑名），但承载 `.py` 文件的目录必须是合法 Python 标识符。
2. **`workspace/` 是 Python 包**：每层都有 `__init__.py`，使 `from workspace.retail.skills.clearance_workflow.tools import query_near_expiry` 可工作。
3. **`backend/engine/` → `agent/engine/`**：engine 目录名**不变**（只是父目录从 backend 变 agent），内部所有 `from engine.xxx import` 都不受影响（因为 sys.path 根仍是 agent/）。
4. **`packs` Python 包名 → `workspace` Python 包名**：所有 `from packs.xxx` → `from workspace.xxx`，字符串字面量 `"packs"` → `"workspace"`。
5. **`processes/` 目录物理废弃**：原 `processes/clearance/{tools,automation,state_machine}.py` 移入 `skills/clearance_workflow/`；原 `processes/clearance/skills/clearance-workflow/SKILL.md` 提升到 `skills/clearance_workflow/SKILL.md`。
6. **代码内 `customer_id` / `tenant_id` 变量名不改**：这是语义重命名，留 P1 phase。本计划只改**路径字符串**。
7. **测试必须全绿**：每步 commit 前跑 `cd agent && .venv/bin/python -m pytest tests/ 2>&1 | tail -5`，必须 `147 passed`。

---

## Task 1: 创建 git 分支并确认基线绿

**Files:** 无（git 操作）

- [ ] **Step 1: 创建重构分支**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git checkout -b refactor/workspace-first-layout
```

- [ ] **Step 2: 确认基线测试全绿**

```bash
cd backend && .venv/bin/python -m pytest tests/ 2>&1 | tail -5
```

Expected: `147 passed`（基线绿，重构后必须维持这个数字）

- [ ] **Step 3: 记录当前 venv 路径（重构后要重建）**

```bash
ls -la backend/.venv/bin/python | awk '{print $NF}'
```

记下输出（应为 `backend/.venv/bin/python` 的绝对路径）。重构后 `backend/.venv` 会随目录迁移到 `agent/.venv`，需要验证 uv 能否复用。

---

## Task 2: 迁移 retail 行业包到 workspace/retail/（含 processes→skills 合并）

**Files:**
- Create: `workspace/__init__.py`, `workspace/retail/__init__.py`, `workspace/retail/skills/__init__.py`, `workspace/retail/skills/clearance_workflow/__init__.py`, `workspace/retail/skills/store_ontology/__init__.py`
- Move: `backend/packs/retail/*` → `workspace/retail/*`
- Move: `backend/packs/retail/domains/` → `workspace/retail/ontology/domains/`
- Move: `backend/packs/retail/processes/clearance/tools.py` → `workspace/retail/skills/clearance_workflow/tools.py`
- Move: `backend/packs/retail/processes/clearance/automation.py` → `workspace/retail/skills/clearance_workflow/automation.py`
- Move: `backend/packs/retail/processes/clearance/actions/` → `workspace/retail/skills/clearance_workflow/actions/`
- Move: `backend/packs/retail/processes/clearance/skills/clearance-workflow/SKILL.md` → `workspace/retail/skills/clearance_workflow/SKILL.md`
- Move: `backend/packs/retail/processes/clearance/skills/store-ontology/SKILL.md` → `workspace/retail/skills/store_ontology/SKILL.md`
- Delete: `backend/packs/retail/processes/`（迁完后空目录）

**重要**：Skill 目录名用**下划线** `clearance_workflow` / `store_ontology`（Python 标识符），但 SKILL.md 文件**内部**的 frontmatter `name:` 字段保持原样（连字符 `clearance-workflow` / `store-ontology`）——这是 deepagents 渐进式披露的逻辑名，与文件系统目录名解耦。

- [ ] **Step 1: 创建 workspace 包结构 + 所有 `__init__.py`**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
mkdir -p workspace/retail/skills/clearance_workflow
mkdir -p workspace/retail/skills/store_ontology
touch workspace/__init__.py
touch workspace/retail/__init__.py
touch workspace/retail/skills/__init__.py
touch workspace/retail/skills/clearance_workflow/__init__.py
touch workspace/retail/skills/store_ontology/__init__.py
```

- [ ] **Step 2: 迁移 retail 顶层文件（pack.py, config 等）和 data/、domains/**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
# 顶层文件（pack.py 等）
git mv backend/packs/retail/pack.py workspace/retail/pack.py
git mv backend/packs/retail/data workspace/retail/data
# domains/ → ontology/domains/（重命名目录概念，但物理名仍是 domains/）
git mv backend/packs/retail/domains workspace/retail/ontology/domains
```

注：`domains/` 物理路径改为 `workspace/retail/ontology/domains/`（多套一层 `ontology/`，符合架构文档 §2）。`ontology/` 目录本身在迁移中由 `git mv domains ... ontology/domains` 隐式创建父目录（git mv 会创建中间目录）。

- [ ] **Step 3: 迁移 processes/clearance/* 到 skills/clearance_workflow/ 和 skills/store_ontology/**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
# Python 实现文件 → clearance_workflow/
git mv backend/packs/retail/processes/clearance/tools.py workspace/retail/skills/clearance_workflow/tools.py
git mv backend/packs/retail/processes/clearance/automation.py workspace/retail/skills/clearance_workflow/automation.py
git mv backend/packs/retail/processes/clearance/actions workspace/retail/skills/clearance_workflow/actions
# SKILL.md（原在 skills 子目录里）→ 提升到 skill 目录根
git mv backend/packs/retail/processes/clearance/skills/clearance-workflow/SKILL.md workspace/retail/skills/clearance_workflow/SKILL.md
git mv backend/packs/retail/processes/clearance/skills/store-ontology/SKILL.md workspace/retail/skills/store_ontology/SKILL.md
```

- [ ] **Step 4: 删除空的 processes/ 目录及残留**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
# 清理空的 skills 子目录和 processes 目录
rm -rf backend/packs/retail/processes/clearance/skills/clearance-workflow
rm -rf backend/packs/retail/processes/clearance/skills/store-ontology
rm -rf backend/packs/retail/processes/clearance/skills
rm -rf backend/packs/retail/processes/clearance
rm -rf backend/packs/retail/processes
# 确认 retail 目录已空（除了被 git mv 走的）
ls -la backend/packs/retail/ 2>&1 || echo "retail 目录已不存在或为空"
```

如果 `backend/packs/retail/` 还有残留文件（如 `__pycache__`），用 `rm -rf backend/packs/retail/__pycache__` 清理。

- [ ] **Step 5: 不 commit——本 Task 是纯文件移动，与 Task 3（equipment_repair）+ Task 4（代码导入更新）一起验证后再 commit**

---

## Task 3: 迁移 equipment_repair 行业包到 workspace/equipment_repair/

**Files:**
- Create: `workspace/equipment_repair/__init__.py`, `workspace/equipment_repair/skills/__init__.py`, `workspace/equipment_repair/skills/repair_workflow/__init__.py`, `workspace/equipment_repair/skills/equipment_repair_knowledge/__init__.py`
- Move: `backend/packs/equipment_repair/*` → `workspace/equipment_repair/*`
- Move: `backend/packs/equipment_repair/processes/repair/*` → `workspace/equipment_repair/skills/repair_workflow/*`（含 state_machine.py）

- [ ] **Step 1: 创建 equipment_repair 包结构**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
mkdir -p workspace/equipment_repair/skills/repair_workflow
mkdir -p workspace/equipment_repair/skills/equipment_repair_knowledge
touch workspace/equipment_repair/__init__.py
touch workspace/equipment_repair/skills/__init__.py
touch workspace/equipment_repair/skills/repair_workflow/__init__.py
touch workspace/equipment_repair/skills/equipment_repair_knowledge/__init__.py
```

- [ ] **Step 2: 迁移 equipment_repair 顶层 + domains + data**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv backend/packs/equipment_repair/pack.py workspace/equipment_repair/pack.py
git mv backend/packs/equipment_repair/data workspace/equipment_repair/data
git mv backend/packs/equipment_repair/domains workspace/equipment_repair/ontology/domains
```

- [ ] **Step 3: 迁移 processes/repair/* 到 skills/repair_workflow/ + skills/equipment_repair_knowledge/**

先探查 equipment_repair 的 processes/repair/ 实际内容（有 state_machine.py、tools.py、skills/ 子目录）：

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
find backend/packs/equipment_repair/processes -type f
```

预期看到：`state_machine.py`、`tools.py`（如有）、`skills/equipment-repair-knowledge/SKILL.md`、`skills/repair-workflow/SKILL.md`。

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
# Python 实现文件 → repair_workflow/
git mv backend/packs/equipment_repair/processes/repair/state_machine.py workspace/equipment_repair/skills/repair_workflow/state_machine.py
# 如有 tools.py
git mv backend/packs/equipment_repair/processes/repair/tools.py workspace/equipment_repair/skills/repair_workflow/tools.py 2>/dev/null || echo "无 tools.py，跳过"
# 如有 actions/
git mv backend/packs/equipment_repair/processes/repair/actions workspace/equipment_repair/skills/repair_workflow/actions 2>/dev/null || echo "无 actions 目录，跳过"
# SKILL.md 文件
git mv backend/packs/equipment_repair/processes/repair/skills/equipment-repair-knowledge/SKILL.md workspace/equipment_repair/skills/equipment_repair_knowledge/SKILL.md
git mv backend/packs/equipment_repair/processes/repair/skills/repair-workflow/SKILL.md workspace/equipment_repair/skills/repair_workflow/SKILL.md
```

- [ ] **Step 4: 清理 equipment_repair 残留 + packs/ 空目录**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
rm -rf backend/packs/equipment_repair/processes/repair/skills/equipment-repair-knowledge
rm -rf backend/packs/equipment_repair/processes/repair/skills/repair-workflow
rm -rf backend/packs/equipment_repair/processes
rm -rf backend/packs/equipment_repair/__pycache__
rmdir backend/packs/equipment_repair 2>/dev/null || echo "equipment_repair 目录非空，检查残留"
# packs/ 现在应该空了（除了 __init__.py）
ls backend/packs/
```

- [ ] **Step 5: 处理 backend/packs/__init__.py 和空的 packs/ 目录**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git rm backend/packs/__init__.py
rmdir backend/packs 2>/dev/null || rm -rf backend/packs
ls backend/ | head -20  # 确认 packs/ 已消失
```

- [ ] **Step 6: 不 commit——继续 Task 4 更新代码导入**

---

## Task 4: 迁移 customers/ 到 workspace/customer_default/

**Files:**
- Move: `customers/customer_default/` → `workspace/customer_default/`

- [ ] **Step 1: 迁移 customer_default**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv customers/customer_default workspace/customer_default
rmdir customers 2>/dev/null || rm -rf customers
ls workspace/  # 确认 retail/, equipment_repair/, customer_default/ 都在
```

注：`workspace/customer_default/` **不**加 `__init__.py`——客户目录是配置+数据，不是 Python 包（没有 `.py` 文件需要导入）。

- [ ] **Step 2: 不 commit——继续 Task 5 更新代码**

---

## Task 5: 重命名 backend/ → agent/ 并创建 tools/ 和 skills/ 子目录

**Files:**
- Move: `backend/` → `agent/`
- Create: `agent/tools/__init__.py`, `agent/skills/__init__.py`

- [ ] **Step 1: 重命名 backend → agent（git mv 整个目录）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv backend agent
ls agent/ | head -20  # 确认 engine/, main.py, cli.py, tests/, pyproject.toml 等都在
```

注：`.venv` 是 gitignored，不会随 git mv 移动，但物理目录会移动。需要在 Task 10 重建 venv。

- [ ] **Step 2: 创建 agent/tools/ 和 agent/skills/ 占位目录**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
mkdir -p agent/tools agent/skills
touch agent/tools/__init__.py
touch agent/skills/__init__.py
```

这两个目录本计划只建空壳（占位 + `__init__.py`），实际系统 Tool/Skill 迁移留后续 plan（涉及 `engine/tools.py` 拆分，是语义工作）。

- [ ] **Step 3: 不 commit——继续 Task 6 更新代码**

---

## Task 6: 更新 agent/engine/bootstrap.py（packs → workspace）

**Files:**
- Modify: `agent/engine/bootstrap.py:30`（`_discover_packages("packs", ...)` → `"workspace"`）

- [ ] **Step 1: 修改 bootstrap.py 的扫描包名**

文件 `agent/engine/bootstrap.py`，将第 30 行：

```python
_discover_packages("packs", "pack", "pack")
```

改为：

```python
_discover_packages("workspace", "pack", "pack")
```

同时删除第 31 行（verticals 兼容扫描，已无用）：

```python
_discover_packages("verticals", "config", "vertical")
```

整个 `bootstrap()` 函数变为：

```python
def bootstrap() -> None:
    """发现并注册所有 workspace 行业包（幂等，重复调用安全）。"""
    _discover_packages("workspace", "pack", "pack")
```

同时更新文件顶部 docstring（第 1-5 行）：

```python
"""启动时发现并注册所有 workspace 行业包（P2 升级，workspace 重构）。

扫描 workspace/*/pack.py 注册 IndustryPack。main.py 调用 bootstrap() 一次即可。幂等。
"""
```

- [ ] **Step 2: 不单独运行测试（导入会失败，因下游 pack.py 还没改）——继续 Task 7**

---

## Task 7: 更新 workspace/retail/pack.py（路径 + tools_module）

**Files:**
- Modify: `workspace/retail/pack.py`（整体重写路径部分）

- [ ] **Step 1: 重写 workspace/retail/pack.py**

完整新内容：

```python
"""retail 行业包声明（workspace 重构版）。

import 时注册到 pack 注册表。bootstrap() 自动发现。
retail-pack = 3 能力域（marketing/organization/finance）+ 1 价值链流程（clearance）。

目录结构（workspace 重构后）：
- ontology/domains/<domain>/domain.ttl + actions/  ← 本体声明
- data/                                            ← 种子数据
- skills/clearance_workflow/                       ← 场景单元（SKILL.md + tools.py + automation.py + actions/）
"""
import os

from engine.pack import IndustryPack, CapabilityDomain, ValueChainProcess, register_pack
from engine.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.abspath(__file__))  # workspace/retail/

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

RETAIL_PACK = IndustryPack(
    name="retail", display_name="零售行业包",
    domains=[MARKETING, ORGANIZATION, FINANCE],
    processes=[CLEARANCE],
    data_dir=os.path.join(_BASE, "data"))

register_pack(RETAIL_PACK)
```

关键变更：
- `domains/` → `ontology/domains/`（所有 ttl_path / actions_dir / rules_dir）
- `processes/clearance/skills` → `skills`（skills_dir 指向 `workspace/retail/skills/`，因为 skill 子目录直接挂在这里）
- `tools_module` 字符串：`"packs.retail.processes.clearance.tools"` → `"workspace.retail.skills.clearance_workflow.tools"`
- `actions_dir`：`processes/clearance/actions` → `skills/clearance_workflow/actions`
- `data_dir` 修复 bug：原 `os.path.join(_BASE, "packs", "retail", "data")` 双重嵌套 → `os.path.join(_BASE, "data")`

- [ ] **Step 2: 不单独测试——继续 Task 8**

---

## Task 8: 更新 workspace/equipment_repair/pack.py

**Files:**
- Modify: `workspace/equipment_repair/pack.py`

- [ ] **Step 1: 重写 workspace/equipment_repair/pack.py**

完整新内容：

```python
"""equipment_repair 行业包（workspace 重构版，从 verticals 迁移）。"""
import os
from engine.pack import IndustryPack, CapabilityDomain, ValueChainProcess, register_pack
from workspace.equipment_repair.skills.repair_workflow.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_BASE = os.path.dirname(os.path.abspath(__file__))

MAINTENANCE = CapabilityDomain(
    name="maintenance", display_name="维修域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "maintenance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "maintenance", "actions"))

REPAIR = ValueChainProcess(
    name="repair", display_name="设备维修",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.equipment_repair.skills.repair_workflow.tools",
    actions_dir=os.path.join(_BASE, "ontology", "domains", "maintenance", "actions"),
    system_prompt_intro="你是门店设备维修管理助手。")

EQUIPMENT_REPAIR_PACK = IndustryPack(
    name="equipment_repair", display_name="设备维修行业包",
    domains=[MAINTENANCE],
    processes=[REPAIR],
    data_dir=os.path.join(_BASE, "data"))

register_pack(EQUIPMENT_REPAIR_PACK)
```

关键变更：
- `from packs.equipment_repair.processes.repair.state_machine` → `from workspace.equipment_repair.skills.repair_workflow.state_machine`
- `domains/` → `ontology/domains/`
- `processes/repair/skills` → `skills`
- `tools_module`：`"packs.equipment_repair.processes.repair.tools"` → `"workspace.equipment_repair.skills.repair_workflow.tools"`
- `data_dir`：修复为 `os.path.join(_BASE, "data")`

- [ ] **Step 2: 不单独测试——继续 Task 9**

---

## Task 9: 更新 workspace/retail/skills/clearance_workflow/tools.py（内部导入）

**Files:**
- Modify: `workspace/retail/skills/clearance_workflow/tools.py:11`

- [ ] **Step 1: 修改 tools.py 的 discount 导入路径**

文件 `workspace/retail/skills/clearance_workflow/tools.py`，找到第 11 行（原 `from packs.retail.domains.marketing.discount import calculate_discount`），改为：

```python
from workspace.retail.ontology.domains.marketing.discount import calculate_discount
```

注：`discount.py` 文件随 `domains/` → `ontology/domains/` 一起迁移了，物理位置在 `workspace/retail/ontology/domains/marketing/discount.py`。

- [ ] **Step 2: 不单独测试——继续 Task 10**

---

## Task 10: 重建 venv 并更新 pyproject.toml

**Files:**
- Modify: `agent/pyproject.toml:35`（`packages = ["backend"]` → `["agent"]`）

- [ ] **Step 1: 更新 pyproject.toml 的 wheel 包名**

文件 `agent/pyproject.toml`，找到 `[tool.hatch.build.targets.wheel]` 段（约第 34-35 行）：

```toml
[tool.hatch.build.targets.wheel]
packages = ["backend"]
```

改为：

```toml
[tool.hatch.build.targets.wheel]
packages = ["agent"]
```

- [ ] **Step 2: 重建 venv（agent/ 下）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
# 删除可能残留的旧 venv（物理路径变了）
rm -rf .venv
# 用 uv 重建（会读 pyproject.toml + uv.lock）
uv sync --extra dev 2>&1 | tail -5
# 补装运行时缺失的依赖（pre-existing 问题，与重构无关）
VIRTUAL_ENV=$(pwd)/.venv uv pip install deepagents apscheduler 2>&1 | tail -3
```

- [ ] **Step 3: 验证 python 可用**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
.venv/bin/python -c "import fastapi, langgraph, deepagents; print('deps ok')"
```

Expected: `deps ok`

- [ ] **Step 4: 不 commit——继续 Task 11 跑测试看哪些还坏**

---

## Task 11: 修复 agent/main.py（导入路径 + skills 根路径）

**Files:**
- Modify: `agent/main.py:168-169`（skills 根路径）, `agent/main.py:335,355,374`（automation 导入）

- [ ] **Step 1: 修改 skills 根路径（第 168-169 行）**

文件 `agent/main.py`，找到：

```python
_clearance_skills_root = os.path.join(os.path.dirname(__file__),
    "packs", "retail", "processes", "clearance", "skills")
```

改为：

```python
_clearance_skills_root = os.path.join(os.path.dirname(__file__),
    "..", "workspace", "retail", "skills")
```

注：`agent/main.py` 的 `__file__` 是 `agent/main.py`，`..` 回到项目根，然后 `workspace/retail/skills/`。这个目录下现在有 `clearance_workflow/SKILL.md` 和 `store_ontology/SKILL.md`。

- [ ] **Step 2: 修改 automation 模块导入（第 335、355、374 行）**

文件 `agent/main.py`，找到所有三处：

```python
from packs.retail.processes.clearance.automation import register_clearance_automation
from packs.retail.processes.clearance.automation import handle_approval
from packs.retail.processes.clearance.automation import handle_pos_scan
```

分别改为：

```python
from workspace.retail.skills.clearance_workflow.automation import register_clearance_automation
from workspace.retail.skills.clearance_workflow.automation import handle_approval
from workspace.retail.skills.clearance_workflow.automation import handle_pos_scan
```

- [ ] **Step 3: 不单独测试——继续 Task 12**

---

## Task 12: 修复 agent/engine/customer_bootstrap.py（默认客户目录路径）

**Files:**
- Modify: `agent/engine/customer_bootstrap.py:31-33`（`_DEFAULT_CUSTOMER_DIR`）, `:46-47,57,62`（fallback 路径）

**路径分析（关键）**：`customer_bootstrap.py` 位于 `agent/engine/customer_bootstrap.py`。
- `os.path.abspath(__file__)` = `.../agent/engine/customer_bootstrap.py`
- 3× `os.path.dirname` = `.../`（项目根）：file → engine → agent → root
- 原代码 `_DEFAULT_CUSTOMER_DIR` 在 3× dirname（=项目根）之后又加了 `".."`，实际指向 `root/../customers`（项目根之上）——这是个**预存在 bug**，靠第 55-57 行的 fallback CustomerConfig 兜底才没暴露。重构时顺便修掉。

- [ ] **Step 1: 修改 `_DEFAULT_CUSTOMER_DIR`（第 31-33 行）——去掉多余的 `..`**

文件 `agent/engine/customer_bootstrap.py`，找到：

```python
_DEFAULT_CUSTOMER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..", "customers", "customer_default")
```

改为：

```python
_DEFAULT_CUSTOMER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "workspace", "customer_default")
```

关键：去掉 `".."`（3× dirname 已到项目根），`"customers"` → `"workspace"`。这样路径正确指向 `<root>/workspace/customer_default/`，不再依赖 fallback。

- [ ] **Step 2: 修改 fallback data_dir 路径（第 57、62 行）**

`base` 在第 46 行定义为 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` = `agent/`（2× dirname：file→engine→agent）。

找到第 57 行（fallback CustomerConfig）：

```python
data_dir=os.path.join(base, "packs", "retail", "data"))
```

改为：

```python
data_dir=os.path.join(base, "..", "workspace", "retail", "data"))
```

找到第 62 行：

```python
raw_data_dir = cfg.data_dir or os.path.join(base, "packs", "retail", "data")
```

改为：

```python
raw_data_dir = cfg.data_dir or os.path.join(base, "..", "workspace", "retail", "data")
```

注：`base` = `agent/`，`..` 回到项目根，`workspace/retail/data/`。

- [ ] **Step 3: 不单独测试——继续 Task 13**

---

## Task 13: 修复 agent/engine/discount_stub.py（路径字面量）

**Files:**
- Modify: `agent/engine/discount_stub.py:26,29`（hardcoded `backend/packs/retail/...`）

- [ ] **Step 1: 修改 `_find_rules_file` 的候选路径**

文件 `agent/engine/discount_stub.py`，找到第 23-30 行。

**路径分析**：`__file__` = `agent/engine/discount_stub.py`；`os.path.dirname(__file__)` = `agent/engine/`；`join(..., "..", "..")` = 项目根（engine→agent→root，两级上溯）。原代码的 root 计算是正确的，只需改 candidates 里的路径段。

将：

```python
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
candidates = [
    # pack rules（marketing 域规则源）
    os.path.join(root, "backend", "packs", "retail", "domains", "marketing",
                 "rules", "discount_rules.json"),
    # pack data（实例数据里的规则副本）
    os.path.join(root, "backend", "packs", "retail", "data", "discount_rules.json"),
]
```

改为：

```python
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
candidates = [
    # workspace rules（marketing 域规则源）
    os.path.join(root, "workspace", "retail", "ontology", "domains", "marketing",
                 "rules", "discount_rules.json"),
    # workspace data（实例数据里的规则副本）
    os.path.join(root, "workspace", "retail", "data", "discount_rules.json"),
]
```

注：root 计算保持不变（`../..` 两级 = 项目根），只改 candidates 内的路径段：`backend/packs/retail/domains` → `workspace/retail/ontology/domains`。

- [ ] **Step 2: 不单独测试——继续 Task 14**

---

## Task 14: 修复 agent/cli.py（路径字面量）

**Files:**
- Modify: `agent/cli.py:30`（pack_root）, `:35,50,72`（customer_root，顺便修复 data/customers bug）

- [ ] **Step 1: 修改 cmd_copy 的 pack_root（第 30 行）**

文件 `agent/cli.py`，找到：

```python
pack_root = os.path.join(base, "packs", args.pack)
```

改为：

```python
pack_root = os.path.join(base, "..", "workspace", args.pack)
```

- [ ] **Step 2: 修改三处 customer_root（第 35、50、72 行）——顺便修复 data/customers bug**

原代码三处都是：

```python
customer_root = os.path.join(base, "..", "data", "customers", args.customer_id)
```

这个路径本身就是 bug（写 `data/customers/` 但实际客户在 `customers/`）。统一改为指向新 workspace 结构：

```python
customer_root = os.path.join(base, "..", "workspace", args.customer_id)
```

三处（cmd_copy 第 35 行、cmd_seed 第 50 行、cmd_start 第 72 行）都改。

- [ ] **Step 3: 不单独测试——继续 Task 15 跑首次完整测试**

---

## Task 15: 首次跑测试，收集剩余失败

**Files:** 无（诊断步骤）

- [ ] **Step 1: 跑完整测试套件，收集所有失败**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
.venv/bin/python -m pytest tests/ 2>&1 | tail -40
```

预期：还会有失败，主要是测试文件里的 `from packs...` 导入和 `packs/retail/...` 路径字符串。记录所有失败的测试文件名。

- [ ] **Step 2: 用 grep 精确定位所有剩余的 `packs` 引用**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
grep -rn "packs\." tests/ --include="*.py" | grep -v ".venv"
grep -rn '"packs"' tests/ --include="*.py" | grep -v ".venv"
grep -rn 'packs/retail' tests/ --include="*.py" | grep -v ".venv"
grep -rn 'packs/equipment_repair' tests/ --include="*.py" | grep -v ".venv"
grep -rn 'processes/clearance' tests/ --include="*.py" | grep -v ".venv"
grep -rn 'processes/repair' tests/ --include="*.py" | grep -v ".venv"
```

记录每个 file:line。这些将在 Task 16-20 逐个修复。

---

## Task 16: 修复 agent/tests/conftest.py

**Files:**
- Modify: `agent/tests/conftest.py:11`（注释）, `:105`（equipment_repair data 路径）

- [ ] **Step 1: 修改 equipment_repair data 路径（第 105 行）**

文件 `agent/tests/conftest.py`，找到：

```python
src = Path(__file__).resolve().parent.parent / "packs" / "equipment_repair" / "data"
```

改为：

```python
src = Path(__file__).resolve().parent.parent.parent / "workspace" / "equipment_repair" / "data"
```

注：`parent.parent` 是 `agent/`，再 `.parent` 是项目根，然后 `workspace/equipment_repair/data`。

- [ ] **Step 2: 更新注释（第 10 行，可选但推荐）**

```python
# 以 agent/ 为 sys.path 根，使 from engine... / from workspace... 可用
BACKEND_DIR = Path(__file__).resolve().parent.parent
```

变量名 `BACKEND_DIR` 可保留（改名会扩散到所有用它的测试），只改注释。

---

## Task 17: 修复 agent/tests/e2e/conftest.py

**Files:**
- Modify: `agent/tests/e2e/conftest.py:135`（retail data 路径）, `:178`（query_near_expiry 导入）, `:183`（skills 根路径）

- [ ] **Step 1: 修改 retail data 路径（第 135 行）**

```python
src = BACKEND_DIR / "packs" / "retail" / "data"
```

改为：

```python
src = BACKEND_DIR.parent / "workspace" / "retail" / "data"
```

注：`BACKEND_DIR` 是 `agent/`（第 17 行定义 `.parent.parent.parent` 从 e2e/conftest.py 算），`.parent` 是项目根。

- [ ] **Step 2: 修改 query_near_expiry 导入（第 178 行）**

```python
from packs.retail.processes.clearance.tools import query_near_expiry
```

改为：

```python
from workspace.retail.skills.clearance_workflow.tools import query_near_expiry
```

- [ ] **Step 3: 修改 skills 根路径（第 183 行）**

```python
root_dir=str(BACKEND_DIR / "packs" / "retail" / "processes" / "clearance" / "skills"),
```

改为：

```python
root_dir=str(BACKEND_DIR.parent / "workspace" / "retail" / "skills"),
```

---

## Task 18: 修复 agent/tests/_clearance_helper.py

**Files:**
- Modify: `agent/tests/_clearance_helper.py:29-30`（packs 导入）

- [ ] **Step 1: 修改 packs 导入**

文件 `agent/tests/_clearance_helper.py`，找到：

```python
import packs.retail.pack
from packs.retail.pack import RETAIL_PACK
```

改为：

```python
import workspace.retail.pack
from workspace.retail.pack import RETAIL_PACK
```

---

## Task 19: 批量修复其余测试文件的 `from packs...` 导入和路径字符串

**Files:**（根据 Task 15 grep 结果逐个修）
- `agent/tests/test_clearance_automation.py`（多处 `from packs.retail.processes.clearance.automation`）
- `agent/tests/test_discount.py:2`（`from packs.retail.domains.marketing.discount`）
- `agent/tests/test_equipment_repair.py:16`（`from packs.equipment_repair.processes.repair.state_machine`）
- `agent/tests/test_pack_bootstrap.py:11,12,36,37`（`import packs.equipment_repair.pack` / `packs.retail.pack`）
- `agent/tests/test_pack_integration.py`（间接通过 tools_module 字符串，已在 pack.py 改过）
- `agent/tests/test_action_loader.py:5,14,23`（cwd-relative `"packs/retail/processes/clearance/actions"` 字符串）
- `agent/tests/test_parser.py:5,11,17,23,30`（cwd-relative `"packs/retail/domains/..."` 字符串）
- `agent/tests/test_vertical.py:31,37,46,51`（`os.path.join(base, "packs", "retail", ...)`）
- `agent/tests/test_onboarding_e2e.py:27-28,82-83`（`os.path.join(base, "packs", "retail")`）

- [ ] **Step 1: 用 sed 批量替换 `from packs.` → `from workspace.` 和 `import packs.` → `import workspace.`**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
# 批量替换导入语句（仅 tests/ 目录）
find tests/ -name "*.py" -exec sed -i '' \
    -e 's/from packs\./from workspace./g' \
    -e 's/import packs\./import workspace./g' \
    -e 's/packs\.retail\.processes\.clearance/workspace.retail.skills.clearance_workflow/g' \
    -e 's/packs\.equipment_repair\.processes\.repair/workspace.equipment_repair.skills.repair_workflow/g' \
    {} \;
```

注：macOS 的 sed 需要 `-i ''`（空字符串备份后缀）。

- [ ] **Step 2: 手动修复 cwd-relative 路径字符串（sed 替换不到的）**

逐文件处理（这些是字符串字面量，需要手动改，因为路径结构变了，不只是 packs→workspace）：

`agent/tests/test_action_loader.py`（3 处 `"packs/retail/processes/clearance/actions"`）：
改为 `"workspace/retail/skills/clearance_workflow/actions"`（或用 os.path 相对构造）。

`agent/tests/test_parser.py`（5 处 `"packs/retail/domains/..."` 和 `"packs/retail/data"`）：
改为 `"workspace/retail/ontology/domains/..."` 和 `"workspace/retail/data"`。

`agent/tests/test_vertical.py`（4 处 `os.path.join(base, "packs", "retail", ...)`）：
改为 `os.path.join(base, "..", "workspace", "retail", "ontology", "domains", ...)`（注意 base 是 `agent/`，要 `..` 回项目根）。

`agent/tests/test_onboarding_e2e.py`（2 处 `os.path.join(base, "packs", "retail")`）：
改为 `os.path.join(base, "..", "workspace", "retail")`。

逐个 Read 文件确认上下文后用 Edit 修改。

- [ ] **Step 3: 修复 test_onboarding_e2e.py 的 _build_registry 路径（如果有 processes 引用）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
grep -n "processes" tests/test_onboarding_e2e.py
```

如有 `processes/clearance/actions` 字符串引用，改为 `skills/clearance_workflow/actions`。

---

## Task 20: 跑完整测试，修复剩余失败直到 147 passed

**Files:** 根据失败信息动态修复

- [ ] **Step 1: 跑完整测试**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
.venv/bin/python -m pytest tests/ 2>&1 | tail -30
```

- [ ] **Step 2: 对每个失败，Read 失败的测试文件 + 用 Edit 修复**

典型剩余失败：
- 某个测试用了 `"customer_default"` 但路径推导变了 → 修路径
- `test_repository_tenant.py` / `test_tenant.py` 用 `customer_id` 字段 → 不改（语义重命名留 P1）
- `test_dashboard_api.py` / `test_main_tenant.py` 用 URL `/api/admin/customers/customer_default/...` → 不改（URL 路由没变，只是目录变了）

循环 Step 1-2 直到 `147 passed`。

- [ ] **Step 3: 跑 e2e 测试单独确认**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
.venv/bin/python -m pytest tests/e2e/ -v 2>&1 | tail -15
```

Expected: `5 passed`（clearance_workflow 的 3 个 + query_clearance + tenant_isolation）

- [ ] **Step 4: Commit 重构**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git add -A
git status | head -30  # 确认变更范围（应该都是 rename + modify）
git commit -m "refactor: workspace-first 目录重构

- backend/ → agent/（重命名 + 新增 tools/ skills/ 占位）
- backend/packs/ + customers/ → workspace/（统一）
  - workspace/retail/（行业基础包，含 ontology/domains + data + skills）
  - workspace/equipment_repair/
  - workspace/customer_default/
- 废弃 processes/ 目录：
  - processes/clearance/{tools,automation,actions} → skills/clearance_workflow/
  - processes/clearance/skills/*/SKILL.md → skills/clearance_workflow/SKILL.md + skills/store_ontology/SKILL.md
  - processes/repair/* → skills/repair_workflow/*
- domains/ → ontology/domains/（多套一层，符合架构文档 §2）
- 所有 from packs.* → from workspace.*，路径字面量同步更新
- engine/bootstrap.py 扫描 workspace 而非 packs
- 修复 cli.py 的 data/customers bug（改指 workspace/）
- 修复 retail/pack.py 的 data_dir 双重嵌套 bug
- 全部 147 测试通过（含 5 e2e），无行为变更"
```

---

## Task 21: 修改 workspace/customer_default/config.yaml 的 data_dir

**Files:**
- Modify: `workspace/customer_default/config.yaml:6`

- [ ] **Step 1: 修改 data_dir 路径**

文件 `workspace/customer_default/config.yaml`，找到第 6 行：

```yaml
  data_dir: backend/packs/retail/data
```

改为：

```yaml
  data_dir: workspace/retail/data
```

- [ ] **Step 2: 验证 customer_default 仍能 bootstrap**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
.venv/bin/python -c "
import sys, os
sys.path.insert(0, '.')
from engine.customer_bootstrap import bootstrap_customer
inst = bootstrap_customer('customer_default')
print('Objects:', sorted(inst.registry.object_types.keys())[:5])
print('Actions:', len(inst.registry.action_types))
print('data_dir:', inst.repository.data_dir)
"
```

Expected: 打印出 Object 列表（Product, NearExpiryProduct...）、Action 数量、data_dir 指向 `workspace/retail/data`。

- [ ] **Step 3: Commit**

```bash
git add workspace/customer_default/config.yaml
git commit -m "fix: customer_default config 指向新 workspace/retail/data 路径"
```

---

## Task 22: 前端加 X-Workspace Header（CopilotKit route + dashboard fetch）

**Files:**
- Modify: `frontend/app/api/copilotkit/route.ts`（加 X-Workspace 默认 header）
- Modify: `frontend/app/dashboard/page.tsx`（fetch 加 X-Workspace header）

**设计决策**：按架构文档 §3.4，前端通过 `X-Workspace` header 传递 workspace 标识。MVP 阶段先用**静态默认值**（`DEFAULT_WORKSPACE` 环境变量，默认 `customer_default`），与现有 `X-Tenant-ID` 静态注入模式一致。动态 per-request 注入需要重构 CopilotRuntime 为 per-request 构造（route.ts docstring 第 13-14 行已说明），留后续 plan。

- [ ] **Step 1: 修改 route.ts 加 X-Workspace header**

Read `frontend/app/api/copilotkit/route.ts` 确认当前内容（已知第 16、20-27、24 行结构）。

找到第 16 行附近：

```typescript
const DEFAULT_TENANT = process.env.DEFAULT_TENANT_ID || "tenant_default";
```

在其后加一行：

```typescript
const DEFAULT_WORKSPACE = process.env.DEFAULT_WORKSPACE || "customer_default";
```

找到第 24 行（LangGraphHttpAgent 的 headers）：

```typescript
headers: { "X-Tenant-ID": DEFAULT_TENANT },
```

改为：

```typescript
headers: { "X-Tenant-ID": DEFAULT_TENANT, "X-Workspace": DEFAULT_WORKSPACE },
```

- [ ] **Step 2: 修改 dashboard/page.tsx 的 fetch 加 header**

Read `frontend/app/dashboard/page.tsx` 确认第 55-58 行。

找到（约第 55-58 行）：

```typescript
const cid = 'customer_default'
// ...
fetch(`${API_BASE}/api/dashboard/${cid}/metrics`)
fetch(`${API_BASE}/api/dashboard/${cid}/todos`)
```

改为（加 headers 参数）：

```typescript
const cid = 'customer_default'
const workspace = process.env.NEXT_PUBLIC_DEFAULT_WORKSPACE || 'customer_default'
// ...
fetch(`${API_BASE}/api/dashboard/${cid}/metrics`, { headers: { 'X-Workspace': workspace } })
fetch(`${API_BASE}/api/dashboard/${cid}/todos`, { headers: { 'X-Workspace': workspace } })
```

- [ ] **Step 3: 前端 build 验证（不跑 dev server）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/frontend
npm run build 2>&1 | tail -15
```

如果有 TypeScript 错误，修复。如果 build 成功（或只是 lint warning），继续。

- [ ] **Step 4: Commit**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git add frontend/
git commit -m "feat(frontend): 加 X-Workspace header（MVP 静态默认值）

- route.ts: LangGraphHttpAgent headers 加 X-Workspace: DEFAULT_WORKSPACE
- dashboard/page.tsx: fetch 加 X-Workspace header
- DEFAULT_WORKSPACE 环境变量（默认 customer_default）
- 动态 per-request 注入留后续 plan（需重构 CopilotRuntime 为 per-request 构造）"
```

---

## Task 23: 更新 README.md 和 .env.example 的路径引用

**Files:**
- Modify: `README.md`（backend/ → agent/，结构树更新）
- Modify: `.env.example:2`（注释路径）

- [ ] **Step 1: 更新 README.md 的运行命令和结构树**

Read `README.md`，更新：
- `cd backend` → `cd agent`（第 19、21 行）
- `backend/.env` → `agent/.env` 或项目根 `.env`（第 20、53、57、72 行）
- 项目结构树（第 40-49 行）更新为新的 workspace/ + agent/ 结构

- [ ] **Step 2: 更新 .env.example 注释**

文件 `.env.example`，第 2 行：

```
# Copy to backend/.env and fill in your real key.
```

改为：

```
# Copy to .env (project root) and fill in your real key.
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: 更新 README 和 .env.example 的路径引用（backend→agent, packs→workspace）"
```

---

## Task 24: 最终全量验证 + 合并到 main

**Files:** 无

- [ ] **Step 1: 最终全量测试**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology/agent
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -10
```

Expected: `147 passed`

- [ ] **Step 2: 确认 git 状态干净**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git status
```

Expected: `nothing to commit, working tree clean`

- [ ] **Step 3: 确认目录结构正确**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
echo "=== 项目根 ==="
ls -d */ 2>/dev/null
echo "=== workspace/ ==="
ls workspace/
echo "=== workspace/retail/ ==="
ls workspace/retail/
echo "=== workspace/retail/skills/ ==="
ls workspace/retail/skills/
echo "=== workspace/retail/skills/clearance_workflow/ ==="
ls workspace/retail/skills/clearance_workflow/
echo "=== agent/ ==="
ls agent/ | head -15
```

Expected:
- 项目根：`agent/  docs/  frontend/  workspace/`（无 backend/、packs/、customers/）
- workspace/：`customer_default/  equipment_repair/  retail/`
- workspace/retail/：`data/  ontology/  skills/  __init__.py  pack.py`
- workspace/retail/skills/：`clearance_workflow/  store_ontology/  __init__.py`
- workspace/retail/skills/clearance_workflow/：`SKILL.md  __init__.py  actions/  automation.py  tools.py`
- agent/：`__init__.py  cli.py  engine/  main.py  pyproject.toml  skills/  tests/  tools/`

- [ ] **Step 4: 合并到 main（用户要求自主执行，按推荐方案合并）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git checkout main
git merge --no-ff refactor/workspace-first-layout -m "Merge refactor/workspace-first-layout: workspace-first 目录重构

backend/→agent/，packs/+customers/→workspace/，废弃 processes/。
详见 docs/superpowers/specs/2026-06-20-apaas-platform-architecture-design.md。
147 测试全绿，无行为变更。"
```

- [ ] **Step 5: 删除重构分支**

```bash
git branch -d refactor/workspace-first-layout
```

---

## Self-Review Checklist（实施者完成后自检）

- [ ] **Spec coverage**：架构文档 §2 目录结构、§3.4 X-Workspace 路由已实现。§3.1 声明式执行、§3.2 Skill 2 级加载、§4.5 Action 按域拆分——这些是语义工作，明确标注不在本计划范围。
- [ ] **测试全绿**：`147 passed`（含 5 e2e）。
- [ ] **无行为变更**：重构前后 agent 的对话/自动化/看板行为完全一致。
- [ ] **目录结构匹配架构文档**：`workspace/retail/{ontology/domains, data, skills}` 三层。
- [ ] **Python 导入合法**：所有 skill 目录用下划线（`clearance_workflow`），有 `__init__.py`。
- [ ] **无残留 packs/ 或 processes/ 引用**：`grep -rn "packs\.\|processes/" agent/ workspace/ --include="*.py" | grep -v .venv` 应为空。

---

## 不在本计划范围（留后续 spec+plan）

1. **§3.1 声明式执行**：`discount.py` → Action YAML（需要设计 YAML step 语法）
2. **§3.2 Skill 2 级加载机制**：当前是单级（workspace skills），需要加 `agent/skills/` 系统级 + 加载合并逻辑
3. **§4.5 Action 按域拆分**：clearance 的 4 个 action 按归属域拆到 marketing/supply_chain/finance
4. **`agent/tools/` 系统 Tool 迁移**：把 `engine/tools.py` 的 8 个 tool 按 CRUD/查询/本体浏览/运维分类迁到 `agent/tools/`（语义拆分）
5. **`customer_id` → `workspace_name` 字段重命名**：全代码语义重命名（P1 phase）
6. **前端动态 X-Workspace**：per-request header 注入（需重构 CopilotRuntime）
7. **P3-P5 业务演进**
