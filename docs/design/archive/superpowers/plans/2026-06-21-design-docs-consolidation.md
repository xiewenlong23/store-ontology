> **🗄 归档说明**：brainstorming 产出（plan（实施计划）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# 设计文档归并整理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把分散在 6 处、3 个时代、术语漂移、路径失效的设计文档归并为单一权威 `docs/design/` 结构，并删除半退役的 `agent/engine/vertical.py`、统一术语到活代码 pack/workspace 模型。

**Architecture:** 6 阶段顺序执行——先做代码重构（pytest 全绿为硬门槛），再建文档骨架、合并/治愈/重写内容、归档移动、最后链接修复与全局验证。每阶段独立 commit，便于回滚。核心约束：代码没稳就不写文档。

**Tech Stack:** Python 3.11 / pytest / FastAPI（代码侧）；Markdown 文档（文档侧）。

**关联 spec:** `docs/superpowers/specs/2026-06-21-design-docs-consolidation-design.md`

**术语基线（贯穿全文）:** workspace（硬隔离，旧 customer/tenant）/ org_unit（权限范围）/ TenantContext（双层上下文，代码类名保留）/ 行业包 IndustryPack（旧 vertical）/ 能力域 CapabilityDomain / 价值链流程 ValueChainProcess。`agent/engine/`（旧 backend/ontology/）、`workspace/<pack>/`（旧 verticals/）。

**阶段 0 基线:** `cd agent && python -m pytest -q` → 当前 **150 tests collected**。所有重构后的验证以此通过数不减为门槛。

---

## File Structure

**代码改动文件（阶段 1）：**
- 删除：`agent/engine/vertical.py`
- 修改：`agent/engine/parser.py`（删方式1 + get_vertical import）、`agent/tools/shared.py`（走 workspace 装配）、`agent/engine/workspace_bootstrap.py`（接通 executor）、`agent/main.py`（webhook 接线 + 注释）、`agent/engine/state_machine.py`（注释）、`agent/engine/executor.py`（注释）
- 改名/改写：`agent/tests/test_vertical.py`→`test_pack_registry.py`、`agent/tests/_clearance_helper.py`、`agent/tests/test_equipment_repair.py`

**文档新结构（阶段 2-5）：**
- 新建目录：`docs/design/{,industry-packs/,manual/templates/,reference/palantir/,archive/superpowers/{specs,plans}/}`
- 新建文档：`docs/design/{README,00-architecture,20-api-data-contract,30-development-guide,40-ontology-modeling-spec,roadmap}.md`、`docs/design/industry-packs/retail-clearance.md`、`docs/design/manual/{00-overview,01-onboarding,02-templates,03-worked-example-equipment-repair}.md`、8 个 manual 模板、`docs/design/archive/README.md`
- 移动：`docs/palantir-ontology-docs/*`→`docs/design/reference/palantir/`；3 份旧文档+`docs/manual/*`+`docs/architecture/*`+`docs/项目设计文档.md` 等→`docs/design/archive/` 或新位置
- 修改：根 `README.md`、`CLAUDE.md`（指针修复）

---

# 阶段 1：vertical.py 真删 + 内核重构（代码）

> **硬门槛：本阶段所有任务完成后 `pytest` 必须 150 全绿、vertical 零残留 grep，否则不进阶段 2。**

## Task 1.1：接通 workspace_bootstrap 的 executor 字段

**Files:**
- Modify: `agent/engine/workspace_bootstrap.py`（`WorkspaceAgentInstance.executor` 构建逻辑）

- [ ] **Step 1: 写失败测试——验证 bootstrap_workspace 返回的实例 executor 非 None**

在 `agent/tests/test_pack_bootstrap.py` 末尾追加（如文件不存在则新建并加 import）：

```python
def test_workspace_instance_has_executor():
    """bootstrap_workspace 返回的实例应已接通 executor（非 None）。"""
    from engine.workspace_bootstrap import bootstrap_workspace
    inst = bootstrap_workspace("retail")
    assert inst.executor is not None, "executor 应已接通，不再为 None"
    # executor 能执行状态机相关查询（有 config 提供 transitions）
    assert inst.executor.config is not None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd agent && python -m pytest tests/test_pack_bootstrap.py::test_workspace_instance_has_executor -v`
Expected: FAIL — `assert None is not None`

- [ ] **Step 3: 实现——在 bootstrap_workspace 中构建 executor**

修改 `agent/engine/workspace_bootstrap.py` 的 `bootstrap_workspace()` 函数，在 `inst = WorkspaceAgentInstance(...)` 调用处，先构建 executor 再传入。在 `repo = JSONFileRepository(...)` 之后、`inst = WorkspaceAgentInstance(...)` 之前插入：

```python
    # 接通 executor：取该 workspace source_pack 的 process 作为 config（架构 spec §5.3）
    from engine.executor import ActionExecutor
    from engine.pack import get_pack
    process_config = None
    pack = get_pack(cfg.source_pack) if cfg.source_pack else None
    if pack and pack.processes:
        process_config = pack.processes[0]  # 取第一个 process；多 process 通用化列为 v2
    executor = ActionExecutor(
        repository=repo, actions=registry.action_types,
        registry=registry, config=process_config)
```

然后把 `WorkspaceAgentInstance(...)` 的 `executor=None` 改为 `executor=executor`。

- [ ] **Step 4: 运行测试验证通过**

Run: `cd agent && python -m pytest tests/test_pack_bootstrap.py::test_workspace_instance_has_executor -v`
Expected: PASS

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `cd agent && python -m pytest -q`
Expected: 150 passed（与基线一致）

- [ ] **Step 6: Commit**

```bash
git add agent/engine/workspace_bootstrap.py agent/tests/test_pack_bootstrap.py
git commit -m "refactor(workspace_bootstrap): 接通 WorkspaceAgentInstance.executor（spec §5.3）"
```

## Task 1.2：重构 shared.py 走 workspace 装配

**Files:**
- Modify: `agent/tools/shared.py`（依赖装配层重写）

- [ ] **Step 1: 写失败测试——验证 _get_executor 走 workspace、签名变 workspace_name+process_name**

在 `agent/tests/test_tools.py` 末尾追加：

```python
def test_get_executor_uses_workspace_and_process(monkeypatch):
    """_get_executor 走 workspace 装配，签名 (workspace_name, process_name)。"""
    from agent.tools.shared import _get_executor
    import inspect
    sig = inspect.signature(_get_executor)
    params = list(sig.parameters)
    assert params[0].endswith("workspace_name"), f"第一参应为 workspace_name，实际: {params}"
    # process_name 应为可选第二参
    assert any(p.endswith("process_name") for p in params), "应有 process_name 参数"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd agent && python -m pytest tests/test_tools.py::test_get_executor_uses_workspace_and_process -v`
Expected: FAIL — 当前签名是 `vertical: str = None`

- [ ] **Step 3: 重写 shared.py 依赖装配层**

把 `agent/tools/shared.py` 的装配函数段（`_preview_cache` 定义之后、`_wrap` 之前）整体替换为：

```python
from engine.workspace_bootstrap import bootstrap_workspace


def _get_workspace_instance(workspace_name: str):
    """统一依赖装配入口：所有路径（tool/webhook/agent）共用 workspace 装配（spec §5.3）。"""
    return bootstrap_workspace(workspace_name)


def _get_repo(workspace_name: str):
    """取某 workspace 的 Repository。"""
    return _get_workspace_instance(workspace_name).repository


def _get_executor(workspace_name: str, process_name: str = None) -> ActionExecutor:
    """取某 workspace（+某价值链流程）的 executor。

    process_name 指定时，从该 workspace source_pack 的 processes 里精确匹配；
    未指定时取 bootstrap_workspace 已装配的 executor（默认 process[0]）。
    """
    inst = _get_workspace_instance(workspace_name)
    if process_name is None:
        return inst.executor
    # 精确匹配 process：从 source_pack 的 processes 取
    from engine.pack import get_pack
    pack = get_pack(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if pack is None:
        return inst.executor
    for proc in pack.processes:
        if proc.name == process_name:
            return ActionExecutor(
                repository=inst.repository, actions=inst.registry.action_types,
                registry=inst.registry, config=proc)
    return inst.executor


def _parser(workspace_name: str = None):
    """兼容旧调用：返回某 workspace 的 registry 包装（逐步淘汰，新代码用 _get_executor/_get_repo）。"""
    inst = _get_workspace_instance(workspace_name or "retail")
    # 返回一个带 registry/data_dir/config/build_system_prompt 的轻量对象
    class _P:
        registry = inst.registry
        data_dir = inst.repository.data_dir
        config = inst.config
        def build_system_prompt(self, intro):
            from engine.parser import OntologyParser
            return OntologyParser(ttl_path=None, data_dir=str(self.data_dir)).build_system_prompt(intro)
    return _P()


def build_ontology_prompt(workspace_name: str = None) -> str:
    """为本体注入 system prompt。"""
    p = _parser(workspace_name)
    intro = ""
    from engine.pack import get_pack
    inst = _get_workspace_instance(workspace_name or "retail")
    pack = get_pack(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if pack and pack.processes:
        intro = pack.processes[0].system_prompt_intro
    return p.build_system_prompt(intro)
```

> 注：`_parser`/`build_ontology_prompt` 保留为兼容壳，因为可能有调用点仍依赖。Step 4 后用 grep 确认调用点。

- [ ] **Step 4: 查找并修正所有 _parser/_get_repo/_get_executor 调用点**

Run: `cd agent && grep -rn '_parser(\|_get_repo(\|_get_executor(\|build_ontology_prompt(' agent/tools --include='*.py'`

逐一核对调用点，把 `vertical=` 关键字改为 `workspace_name=`。当前已知调用点都在 `agent/tools/{query_tools,crud_tools,action_tools}.py`（默认值 `workspace_name: str = "customer_default"`，这些是 @tool 函数的参数，不改签名，只改传给 shared 的实参名映射）。如果某个 @tool 函数内部调 `_get_repo(tenant=None, vertical=...)`，改为 `_get_repo(workspace_name=...)`。

- [ ] **Step 5: 运行全量测试**

Run: `cd agent && python -m pytest -q`
Expected: 150 passed（若有失败，根据失败信息修正调用点实参）

- [ ] **Step 6: Commit**

```bash
git add agent/tools/shared.py agent/tools/*.py agent/tests/test_tools.py
git commit -m "refactor(tools/shared): 依赖装配统一走 bootstrap_workspace（spec §5.3 决策2）"
```

## Task 1.3：webhook handler 接线

**Files:**
- Modify: `agent/main.py:430, 449`（webhook 调用 `_get_executor`）

- [ ] **Step 1: 写失败测试——验证 webhook 调用走 workspace+process**

在 `agent/tests/test_webhooks.py` 末尾追加（若该文件测了 webhook 行为则加断言）：

```python
def test_webhook_approval_uses_workspace_executor():
    """approval webhook 应通过 workspace+process 取 executor（不再传 vertical=）。"""
    import inspect, agent.main
    src = inspect.getsource(agent.main.webhook_approval)
    assert "vertical=" not in src, "webhook_approval 不应再用 vertical= 关键字"
    assert "workspace_name=" in src and "process_name=" in src
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd agent && python -m pytest tests/test_webhooks.py::test_webhook_approval_uses_workspace_executor -v`
Expected: FAIL — 当前含 `vertical="clearance"`

- [ ] **Step 3: 修改 main.py 两处 webhook 调用**

`agent/main.py:430`:
```diff
-    ex = _get_executor(vertical="clearance")
+    ex = _get_executor(workspace_name="retail", process_name="clearance")
```

`agent/main.py:449`:
```diff
-    ex = _get_executor(vertical="clearance")
+    ex = _get_executor(workspace_name="retail", process_name="clearance")
```

- [ ] **Step 4: 运行 webhook + automation 测试验证行为不变**

Run: `cd agent && python -m pytest tests/test_webhooks.py tests/test_clearance_automation.py -v`
Expected: PASS（headless 执行 clearance 行为不变）

- [ ] **Step 5: Commit**

```bash
git add agent/main.py agent/tests/test_webhooks.py
git commit -m "refactor(main): webhook 经 workspace+process 取 executor（spec §5.3）"
```

## Task 1.4：删除 parser.py 方式1 + 修注释

**Files:**
- Modify: `agent/engine/parser.py`（删方式1 代码块）、`agent/main.py`/`state_machine.py`/`executor.py`（注释，§5.2）

- [ ] **Step 1: 删除 parser.py 方式1 代码块**

在 `agent/engine/parser.py` 的 `get_ontology_parser` 函数中，删除"方式1：vertical name"整段（从 `if vertical is not None:` 到其对应 return 的代码块，含 `from engine.vertical import get_vertical`）。保留方式2（显式路径）和方式3（默认兜底）。同步修改函数 docstring：删去方式1 的说明行（`1. get_ontology_parser("clearance") ...` 那行）。

- [ ] **Step 2: 修 §5.2 列出的全部过时注释**

按 spec §5.2 的 diff，修改：
- `agent/main.py`：5 处注释（line 31/139/151 的 vertical→行业包；line 299 description 文案；line 407 docstring）
- `agent/engine/state_machine.py`：4 处注释（VerticalConfig→ValueChainProcess、vertical→行业包/价值链流程）
- `agent/engine/executor.py`：1 处注释（`# Optional[VerticalConfig]`→价值链流程上下文）
- `agent/engine/parser.py`：剩余注释中的 `Optional[VerticalConfig]`→`Optional[IndustryPack/ValueChainProcess 上下文]`、`来自 VerticalConfig`→`来自 ValueChainProcess`

- [ ] **Step 3: 运行全量测试**

Run: `cd agent && python -m pytest -q`
Expected: 150 passed

- [ ] **Step 4: Commit**

```bash
git add agent/engine/parser.py agent/engine/state_machine.py agent/engine/executor.py agent/main.py
git commit -m "refactor(engine): 删 parser 方式1 + 修 vertical 过时注释为行业包/价值链流程（spec §5.2/§5.3 决策1）"
```

## Task 1.5：改写 3 个测试（去 VerticalConfig）

**Files:**
- Modify: `agent/tests/_clearance_helper.py`、`agent/tests/test_equipment_repair.py`
- Rename: `agent/tests/test_vertical.py` → `agent/tests/test_pack_registry.py`

- [ ] **Step 1: 改写 _clearance_helper.py——用 ValueChainProcess 替代 VerticalConfig**

把 `agent/tests/_clearance_helper.py` 中的 `from engine.vertical import VerticalConfig` 删除，`CLEARANCE_TEST_CONFIG = VerticalConfig(...)` 改为：

```python
from engine.pack import ValueChainProcess

CLEARANCE_TEST_PROCESS = ValueChainProcess(
    name="clearance",
    display_name="出清",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    system_prompt_intro="你是门店临期商品管理助手。",
)
```

`build_clearance_executor` 中的 `config=CLEARANCE_TEST_CONFIG` 改为 `config=CLEARANCE_TEST_PROCESS`。

- [ ] **Step 2: 改写 test_equipment_repair.py——同理**

把 `from engine.vertical import VerticalConfig` 删除，`_REPAIR_CFG = VerticalConfig(...)` 改为：

```python
from engine.pack import ValueChainProcess

_REPAIR_PROCESS = ValueChainProcess(
    name="repair",
    display_name="设备维修",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
)
```

文件内所有 `_REPAIR_CFG` 引用改为 `_REPAIR_PROCESS`。

- [ ] **Step 3: 重命名 test_vertical.py → test_pack_registry.py 并删死 import**

```bash
cd agent && git mv tests/test_vertical.py tests/test_pack_registry.py
```

编辑 `tests/test_pack_registry.py`：删除 `from engine.vertical import VerticalConfig  # 类仍保留...` 这一行（line 4，死 import）。同时修正 docstring 里的"原 vertical 测试"措辞。

- [ ] **Step 4: 运行这 3 个测试文件相关测试**

Run: `cd agent && python -m pytest tests/test_pack_registry.py tests/test_equipment_repair.py tests/ -k clearance -v`
Expected: PASS

- [ ] **Step 5: 运行全量测试**

Run: `cd agent && python -m pytest -q`
Expected: 150 passed

- [ ] **Step 6: Commit**

```bash
git add agent/tests/_clearance_helper.py agent/tests/test_equipment_repair.py agent/tests/test_pack_registry.py
git commit -m "test: 3 测试去 VerticalConfig，改用 ValueChainProcess；test_vertical→test_pack_registry（spec §5.4）"
```

## Task 1.6：删除 vertical.py + 阶段 1 验收

**Files:**
- Delete: `agent/engine/vertical.py`

- [ ] **Step 1: 删除 vertical.py**

```bash
git rm agent/engine/vertical.py
```

- [ ] **Step 2: 运行全量测试验证删除无回归**

Run: `cd agent && python -m pytest -q`
Expected: 150 passed

- [ ] **Step 3: vertical 零残留 grep（成功标准 6）**

Run: `cd /Users/xiewenlong/Documents/code/store-ontology && grep -rn 'from engine.vertical\|VerticalConfig\|register_vertical\|get_vertical\|all_verticals' agent --include='*.py' | grep -v '.venv'`
Expected: 零命中

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(engine)!: 删除半退役的 vertical.py（spec §5.3）

BREAKING: 移除 VerticalConfig/vertical registry。tool/webhook/agent 三路
统一走 bootstrap_workspace 装配。"
```

> **阶段 1 门槛检查：** pytest 150 全绿 + grep 零残留。两项都过才进阶段 2。任一项不过，停下排查，不进文档阶段。

---

# 阶段 2：建 docs/design/ 骨架

## Task 2.1：创建目录结构 + 状态徽章图例

- [ ] **Step 1: 创建所有目录**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
mkdir -p docs/design/industry-packs
mkdir -p docs/design/manual/templates
mkdir -p docs/design/reference/palantir
mkdir -p docs/design/archive/superpowers/specs
mkdir -p docs/design/archive/superpowers/plans
```

- [ ] **Step 2: 写 docs/design/README.md（导航 + 徽章图例 + 阅读路线）**

新建 `docs/design/README.md`，内容包括：
- 标题 `# OntologyAgent 设计文档`
- 状态徽章图例：`✅ 当前（已实现）` / `🔮 前瞻（未实现）` / `🗄 归档（历史）` / `📚 参考（第三方）`
- 导航表（4 列：文档、路径、状态、一句话说明），列出 `00-architecture` / `20-api-data-contract` / `30-development-guide` / `40-ontology-modeling-spec` / `roadmap` / `industry-packs/retail-clearance` / `manual/` / `reference/palantir` / `archive/`
- 阅读路线（第一次接入 / 后续接入 / 想理解架构 / 想看前瞻）

> 内容详细写法参照 spec §2.1 的目录结构与现有 `docs/architecture/README.md` 的导航表风格。**先写完整内容**，不要占位。

- [ ] **Step 3: Commit**

```bash
git add docs/design/
git commit -m "docs(design): 建 docs/design/ 骨架 + README 导航（spec §2.1）"
```

---

# 阶段 3：合并 / 治愈 / 重写文档内容

> 本阶段每个 Task 产出一份文档，独立校验路径/术语/徽章。**每份文档顶部必须有状态徽章行。**

## Task 3.1：合并 → 00-architecture.md（权威·单一）

**Files:**
- Create: `docs/design/00-architecture.md`
- Sources: `docs/superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md`（✅ 条款）⊕ `docs/architecture/system-architecture.md`

- [ ] **Step 1: 合并两源，去重，统一术语/路径**

读两源。合并规则：
- target-arch spec 是 reconcile 主体（已标 ✅/🔜），其 ✅ 部分（§0-§5、附录 A/D、错误处理 C）进 `00-architecture.md`。
- system-architecture.md 的五层/概念/模块/数据流章节与 spec 重复 → **去重，不复制**；其独有的工程细节（如模块设计的 file:line、Repository 接口签名表）补进 00 的相应章节。
- 🔜 部分（spec §6 权限/审计/观测、§8 演进路线的 v2 项）**不进 00**，留给 Task 3.5 的 roadmap。
- 术语统一：vertical→行业包、VerticalConfig→IndustryPack/ValueChainProcess、`backend/ontology/`→`agent/engine/`、`verticals/`→`workspace/<pack>/`、customer→workspace。
- 顶部加：`> **状态**：✅ 当前（已实现）。本文档是平台架构的单一权威来源。`

- [ ] **Step 2: 校验——路径/术语/grep**

Run: `cd /Users/xiewenlong/Documents/code/store-ontology && grep -n 'backend/\|verticals/\|VerticalConfig\|customer_id\|多 vertical' docs/design/00-architecture.md`
Expected: 零命中（或仅在"兼容说明"语境的 customer_id，需人工确认）

- [ ] **Step 3: Commit**

```bash
git add docs/design/00-architecture.md
git commit -m "docs(design): 00-architecture 单一权威（合并 target-spec ⊕ system-arch，去重+术语治愈）"
```

## Task 3.2：治愈 → 20-api-data-contract.md

**Files:**
- Create: `docs/design/20-api-data-contract.md`
- Source: `docs/architecture/api-and-data-spec.md`

- [ ] **Step 1: 拷贝并治愈路径/术语**

把 `api-and-data-spec.md` 内容拷入 `20-api-data-contract.md`，做：
- `backend/`→`agent/engine/` 或 `agent/`（按语境）
- `X-Tenant-ID`/`X-Customer-ID` header 说明对齐代码实际（`X-Workspace` 优先，回退 `X-Customer-ID`，见 `agent/engine/tenant.py:from_headers`）
- `tenant_id` 字段名保留，但文档解释补"workspace_name + org_unit_id 双层"
- 顶部加状态徽章 `> **状态**：✅ 当前（已实现）。`

- [ ] **Step 2: 校验 grep**

Run: `grep -n 'backend/' docs/design/20-api-data-contract.md`
Expected: 零命中

- [ ] **Step 3: Commit**

```bash
git add docs/design/20-api-data-contract.md
git commit -m "docs(design): 20-api-data-contract（治愈 backend/ 路径 + 术语对齐 X-Workspace）"
```

## Task 3.3：治愈 → 30-development-guide.md

**Files:**
- Create: `docs/design/30-development-guide.md`
- Source: `docs/architecture/development-guide.md`

- [ ] **Step 1: 拷贝并对齐 pack 装配**

把内容拷入，重点改：
- "新增 Object Type 步骤"里的 `backend/ontology/store.ttl`→`workspace/<pack>/ontology/domains/<域>/domain.ttl`；`backend/models/schemas.py`→`agent/engine/schemas.py`
- 本体开发步骤章节改为**引用 `manual/01-onboarding.md`**（不重复流程，只保留工程规范）
- 顶部加状态徽章

- [ ] **Step 2: 校验 grep + Commit**

```bash
grep -n 'backend/\|verticals/' docs/design/30-development-guide.md   # 期望零命中
git add docs/design/30-development-guide.md
git commit -m "docs(design): 30-development-guide（治愈路径 + 本体开发引用 manual）"
```

## Task 3.4：治愈 → 40-ontology-modeling-spec.md

**Files:**
- Create: `docs/design/40-ontology-modeling-spec.md`
- Source: `docs/业务本体建模规范.md`

- [ ] **Step 1: 拷贝 + 治愈路径/术语 + 改模板引用**

建模硬规范原样保留（高质量）。改：
- §11 附录里对模板的引用，从 `docs/manual/templates/` 改指 `manual/templates/`
- `backend/ontology/store.ttl`→`workspace/retail/ontology/domains/<域>/domain.ttl`
- vertical→行业包（建模规范里 vertical 出现少）
- 顶部加状态徽章 `> **状态**：✅ 当前（生效中的建模硬规范）。`

- [ ] **Step 2: 校验 grep + Commit**

```bash
grep -n 'backend/\|verticals/' docs/design/40-ontology-modeling-spec.md
git add docs/design/40-ontology-modeling-spec.md
git commit -m "docs(design): 40-ontology-modeling-spec（治愈路径 + 模板引用改指 manual/）"
```

## Task 3.5：抽 → roadmap.md（前瞻·未实现）

**Files:**
- Create: `docs/design/roadmap.md`
- Sources: target-arch spec §6/§8 的 🔜 项 + `docs/Harness-Design.md` 重型机制摘要

- [ ] **Step 1: 编写 roadmap，醒目标"未实现"**

结构：
- 顶部 `> **状态**：🔮 前瞻（未实现）。本文件描述的机制**均未落地**，仅供方向参考。`
- 分节：v2-存储 / v2-权限 / v2-本体 / v2-自动化 / v2-Agent / v2-UI / v2-长流程 / v2-tenant动态
- 每节：从 target-arch spec §8 演进路线表 + Harness §3（RBAC×ABAC 六层 cascade、快照冻结、26 钩子等）摘要。**明确写"当前实现仅 X，本节描述目标 Y"**。
- 来源标注：每节末注明"详见 archive/legacy-Harness-Design.md §X"。

- [ ] **Step 2: Commit**

```bash
git add docs/design/roadmap.md
git commit -m "docs(design): roadmap（前瞻·未实现，抽 target-spec §6/§8 + Harness 重型机制）"
```

## Task 3.6：抽 → industry-packs/retail-clearance.md

**Files:**
- Create: `docs/design/industry-packs/retail-clearance.md`
- Source: `docs/项目设计文档.md` 有效部分（临期行业包 as-built）

- [ ] **Step 1: 抽取零售临期行业包的 as-built 细节**

从 `项目设计文档.md` 抽取**仍有效**的内容：6 Object（Region/Store/Employee/Product/NearExpiryProduct/Task）定义、8 Action（clearance 拆分后）、折扣规则（单一事实源 discount_rules.json）、CopilotKit 接入要点。
- 舍弃：已被取代的"系统架构/技术选型/端口规划"（这些进 00）、过时的 `backend/` 路径。
- 顶部加 `> **状态**：✅ 当前（零售临期行业包 as-built）。本包是第一个行业包，作为内核验证场景。`
- 术语：vertical→行业包、路径治愈。

- [ ] **Step 2: Commit**

```bash
git add docs/design/industry-packs/retail-clearance.md
git commit -m "docs(design): industry-packs/retail-clearance（抽项目设计文档有效部分，as-built）"
```

## Task 3.7：重写 manual 4 文档

**Files:**
- Create: `docs/design/manual/{00-overview,01-onboarding,02-templates,03-worked-example-equipment-repair}.md`
- Sources: 现有 `docs/manual/00-04`（重写，非治愈）+ `workspace/{retail,equipment_repair}/pack.py`（对照真实结构）

- [ ] **Step 1: 写 00-overview.md（kernel/行业包边界表 + 定位 + 阅读路线）**

重写要点（spec §4）：
- 一句话定位：OntologyAgent = 本体驱动通用 AI Agent 平台；通用内核固定，每个业务场景作为**行业包**声明式接入，零改内核。
- 一个行业包 = 多个**能力域**（CapabilityDomain，原子 Object/Link/Action）+ 多个**价值链流程**（ValueChainProcess，跨域编排带状态机+Skill+工具）。
- **kernel/行业包边界表**重做：列 `agent/engine/{parser,repository,executor,action_loader,state_machine,preview_cache,pack,workspace_bootstrap,tenant}.py` 为内核；`workspace/<pack>/` 为行业包。口诀"提到领域名词=行业包，只认 IndustryPack=kernel"。
- 何时建行业包/何时不建。
- 顶部加状态徽章。

- [ ] **Step 2: 写 01-onboarding.md（Phase A-F 重定义）**

接入流程基于活代码 `workspace/retail/pack.py` 对照：
- Phase A 本体建模：建 `workspace/<pack>/ontology/domains/<域>/domain.ttl`（每个能力域一个 TTL）
- Phase B Action 契约：Action 放 `domains/<域>/actions/*.yaml`（域内）或 `process.actions_dir`（流程专属）
- Phase C 状态机：填 `ValueChainProcess.state_transitions`/`terminal_states`
- Phase D 种子数据：放 `workspace/<pack>/data/`
- Phase E 工具/Skill：工具 `process.tools_module`；Skill 放 `process.skills_dir`
- Phase F 注册：建 `workspace/<pack>/pack.py`，声明 `IndustryPack(domains=[...], processes=[...])` 并 `register_pack(...)`。bootstrap 自动发现 `workspace/*/pack.py`，重启即生效，零改内核。
- 顶部加状态徽章。

- [ ] **Step 3: 写 02-templates.md（占位符填法）**

新增 `pack.py` 的 `CapabilityDomain`/`ValueChainProcess` 填法说明；`workflow_object_type`→`ValueChainProcess.workflow_object_type`；`locator_field`（保留，仍数据驱动）；每个模板的常见错误。顶部加状态徽章。

- [ ] **Step 4: 写 03-worked-example-equipment-repair.md（对照真实 pack.py）**

对照 `workspace/equipment_repair/pack.py` 实际结构重写（MAINTENANCE 能力域 + REPAIR 价值链流程），包括目录结构、locator_field: ticket_id、config.py 工作流字段、submission_criteria、端到端验证。顶部加状态徽章。

- [ ] **Step 5: 校验——manual 对照 main.py/pack.py 可核对（成功标准 7）**

人工核对：manual 描述的装配路径（bootstrap 发现 `workspace/*/pack.py`、`all_packs()` 聚合、`pack_to_registry`）与 `agent/main.py`、`agent/engine/bootstrap.py`、`agent/engine/pack.py` 实际逻辑一致。

- [ ] **Step 6: Commit**

```bash
git add docs/design/manual/
git commit -m "docs(design/manual): 重写 4 文档为 workspace+能力域/价值链流程（对照活代码 pack.py）"
```

## Task 3.8：重写 8 个 manual 模板

**Files:**
- Create: `docs/design/manual/templates/{pack.py,pack-tools.py,action.yaml.template,ontology.ttl.template,seed-object.json.template,skill-knowledge.md.template,skill-workflow.md.template,state_machine.py.template}`
- Sources: 现有 `docs/manual/templates/*`（vertical-config→pack，vertical-tools→pack-tools）

- [ ] **Step 1: 重写 vertical-config.py.template → pack.py**

新模板基于 `workspace/retail/pack.py` 真实结构，含 `IndustryPack(domains=[CapabilityDomain(...)], processes=[ValueChainProcess(...)])` + `register_pack(...)`。

- [ ] **Step 2: 重写 vertical-tools.py.template → pack-tools.py**

对齐 pack 模型的工具模块（`TOOLS = [...]` 列表，被 `process.tools_module` 引用）。

- [ ] **Step 3: 治愈其余 6 模板**

`action.yaml.template`（locator_field 保留）、`ontology.ttl.template`（路径注释放 `domains/<域>/domain.ttl`）、`seed-object.json.template`（加 workspace_name 字段说明）、`skill-{knowledge,workflow}.md.template`、`state_machine.py.template`（注释改 per-process）。术语对齐行业包。

- [ ] **Step 4: Commit**

```bash
git add docs/design/manual/templates/
git commit -m "docs(design/manual/templates): 重写 8 模板对齐 pack/能力域/价值链流程"
```

---

# 阶段 4：归档 + 移动参考库

## Task 4.1：移动 palantir 参考库（整体，不编辑）

- [ ] **Step 1: git mv 整个目录**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv docs/palantir-ontology-docs docs/design/reference/palantir/palantir-ontology-docs
```

> 注：如 git mv 对含特殊字符子目录报错，用 `mkdir -p docs/design/reference/palantir && git mv docs/palantir-ontology-docs docs/design/reference/palantir/`。

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs(design): 移动 palantir 参考库到 reference/palantir/（整体，不编辑）"
```

## Task 4.2：归档 3 份被取代文档（加头注）

**Files:**
- Move: `docs/项目设计文档.md`→`docs/design/archive/legacy-项目设计文档.md`；`docs/ontologyagent-design-CN.md`→`docs/design/archive/legacy-ontologyagent-design-CN.md`；`docs/Harness-Design.md`→`docs/design/archive/legacy-Harness-Design.md`

- [ ] **Step 1: 移动 3 文档并加头注**

每份文档**顶部**插入取代说明（原文保留在头注之下，不动）：

`legacy-项目设计文档.md` 头注：
```
> **🗄 归档说明**：本文档为「AI 门店大脑-临期商品管理」原始设计，已被取代。
> - 架构/平台部分 → `docs/design/00-architecture.md`
> - 零售临期行业包 as-built → `docs/design/industry-packs/retail-clearance.md`
> 保留作历史追溯。请勿据此文档实施。
```

`legacy-ontologyagent-design-CN.md` 头注：
```
> **🗄 归档说明**：本文档为平台转型期设计规格，已被 `docs/design/00-architecture.md`（三文档 reconcile 的单一权威）取代。保留作历史追溯。
```

`legacy-Harness-Design.md` 头注：
```
> **🗄 归档说明**：本文档为零售深度特化愿景（多组织/RBAC×ABAC/审计/观测），其前瞻机制已摘要进 `docs/design/roadmap.md`（标"未实现"）。保留作历史追溯。
```

```bash
git mv docs/项目设计文档.md docs/design/archive/legacy-项目设计文档.md
git mv docs/ontologyagent-design-CN.md docs/design/archive/legacy-ontologyagent-design-CN.md
git mv docs/Harness-Design.md docs/design/archive/legacy-Harness-Design.md
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs(archive): 归档 3 份被取代文档（加'被谁取代'头注）"
```

## Task 4.3：归档 brainstorming 产出（specs+plans）

**Files:**
- Move: `docs/superpowers/specs/*`→`docs/design/archive/superpowers/specs/`；`docs/superpowers/plans/*`→`docs/design/archive/superpowers/plans/`；`docs/architecture/*`→`docs/design/archive/`（其中 3 篇已被治愈版替代）

- [ ] **Step 1: 移动 superpowers specs/plans**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
git mv docs/superpowers/specs/2026-06-20-apaas-platform-architecture-design.md docs/design/archive/superpowers/specs/
git mv docs/superpowers/specs/2026-06-20-clearance-ontology-remodel.md docs/design/archive/superpowers/specs/
git mv docs/superpowers/specs/2026-06-20-e2e-test-cases.md docs/design/archive/superpowers/specs/
git mv docs/superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md docs/design/archive/superpowers/specs/
git mv docs/superpowers/specs/2026-06-20-p2-industry-pack-design.md docs/design/archive/superpowers/specs/
git mv docs/superpowers/specs/2026-06-21-design-docs-consolidation-design.md docs/design/archive/superpowers/specs/
git mv docs/superpowers/plans/*.md docs/design/archive/superpowers/plans/
```

> 注：本 plan 自身（2026-06-21-...consolidation...）创建在 `docs/superpowers/plans/`，实现期间它本身也在移动。如已创建，一并 mv；保持引用一致性。

- [ ] **Step 2: 移动 docs/architecture/ 与 docs/manual/ 与 docs/业务本体建模规范.md**

这些已被治愈版替代：
```bash
git mv docs/architecture/system-architecture.md docs/design/archive/legacy-system-architecture.md
git mv docs/architecture/api-and-data-spec.md docs/design/archive/legacy-api-and-data-spec.md
git mv docs/architecture/development-guide.md docs/design/archive/legacy-development-guide.md
git mv docs/architecture/README.md docs/design/archive/legacy-architecture-README.md
git mv docs/业务本体建模规范.md docs/design/archive/legacy-业务本体建模规范.md
# docs/manual/ 已被重写版替代
git mv docs/manual docs/design/archive/legacy-manual
```

每份加头注（类似 4.2 格式，注明被 design/ 下哪份取代）。`docs/architecture/` 目录移动后会变空，删空目录。

- [ ] **Step 3: 写 docs/design/archive/README.md（归档说明 + 取代映射表）**

列：归档文档列表、每份的"被谁取代"、归档原则（只读历史、不据此实施）。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs(archive): 归档 brainstorming specs/plans + 已被治愈版替代的 architecture/manual 文档"
```

---

# 阶段 5：链接修复 + 全局验证

## Task 5.1：修根 README + CLAUDE.md 指针

- [ ] **Step 1: 修根 README.md 的"详细设计"指针**

`README.md` 中 `> 详细设计见 [docs/项目设计文档.md](docs/项目设计文档.md)。` 改为 `> 详细设计见 [docs/design/README.md](docs/design/README.md)。`

- [ ] **Step 2: 检查并修 CLAUDE.md 对旧文档的链接**

Run: `grep -n '项目设计文档\|ontologyagent-design\|Harness-Design\|docs/architecture\|docs/manual\|业务本体建模规范\|backend/' CLAUDE.md`

对每个命中：如指向已移动文档，改为 design/ 下新路径或 archive/ 路径。

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: 修根 README + CLAUDE.md 指针指向 docs/design/"
```

## Task 5.2：全局验证（成功标准 1-9）

- [ ] **Step 1: 路径/术语零残留 grep（成功标准 3）**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
grep -rn 'backend/ontology\|backend/verticals\|backend/main\|backend/models\|backend/skills' \
  docs/design --include='*.md' | grep -v 'archive/' | grep -v 'reference/palantir/'
# 期望：零命中

grep -rn 'verticals/\|VerticalConfig\|多 vertical' docs/design --include='*.md' \
  | grep -v 'archive/' | grep -v 'reference/palantir/'
# 期望：零命中

grep -rn 'customer_id' docs/design --include='*.md' \
  | grep -v 'archive/' | grep -v 'reference/palantir/'
# 期望：仅在"兼容说明"语境（人工确认）
```

- [ ] **Step 2: 代码 vertical 零残留 + pytest（成功标准 6）**

```bash
grep -rn 'from engine.vertical\|VerticalConfig\|register_vertical\|get_vertical\|all_verticals' \
  agent --include='*.py' | grep -v '.venv'
# 期望：零命中

cd agent && python -m pytest -q
# 期望：150 passed
```

- [ ] **Step 3: 断链检查（成功标准 8）**

Run: `grep -rn '](docs/' README.md CLAUDE.md docs/design/README.md docs/design/00-architecture.md 2>/dev/null`

人工抽样核对 design/ 内互链 + 根指针均指向存在的文件。

- [ ] **Step 4: 人工核对成功标准 1/2/4/5/7/9**

- 标准 1：README 唯一入口 + 每份 .md（archive/reference 外）有状态徽章。
- 标准 2：单一 `00-architecture.md`，无独立重叠 system-architecture。
- 标准 4：roadmap.md 独立、醒目标"未实现"。
- 标准 5：archive 每份有头注。
- 标准 7：manual 对照 main.py/pack.py 一致（阶段 3.7 已核）。
- 标准 9：旧文档每个实质章节有归属。

- [ ] **Step 5: 如有遗漏，修复后 amend 或补 commit**

```bash
git add -A
git commit -m "docs(design): 全局验证修复（链接/术语/徽章收尾）"
```

- [ ] **Step 6: 最终全量验证 + 收尾**

```bash
cd /Users/xiewenlong/Documents/code/store-ontology
cd agent && python -m pytest -q   # 150 passed
cd .. && git log --oneline -20    # 确认 6 阶段 commit 齐整
```

---

## Self-Review

**1. Spec 覆盖检查：**
- §1.2 范围 In 1-9 → 阶段 2-5 覆盖（结构/合并/治愈/术语/删vertical/重写manual/徽章/归档/链接）✅
- §1.4 成功标准 1-9 → 阶段 5.2 逐条验证 ✅
- §2.1 目录结构 → Task 2.1 ✅
- §2.2 内容映射表 → 阶段 3（每份文档一个 Task）+ 阶段 4 归档 ✅
- §3 术语表 → 贯穿阶段 3 所有 Task 的"术语治愈"步骤 + 阶段 5.2 grep ✅
- §4 manual 重写 → Task 3.7/3.8 ✅
- §5 代码清理 → 阶段 1 全部（1.1-1.6）✅
- §6 执行顺序 → 本 plan 6 阶段顺序一致 ✅
- §7 风险 → 阶段 1 以 pytest 为门槛（Task 1.6 门槛检查）✅

**2. 占位扫描：** 无 TBD/TODO。文档内容 Task（3.x）描述了"写什么"但具体文字需作者基于源文档产出——这是文档写作的本质（非代码可预写），已在 Task 内给出抽取规则与校验 grep，非占位失败。

**3. 类型/命名一致性：**
- `_get_executor(workspace_name, process_name)` —— Task 1.2 定义、1.3 调用、5.2 一致 ✅
- `_REPAIR_PROCESS`/`CLEARANCE_TEST_PROCESS` —— Task 1.5 定义，与 `ValueChainProcess` 字段一致 ✅
- `bootstrap_workspace` 接通 executor —— Task 1.1 定义字段、1.2 消费 ✅
- 文档文件名（00-/20-/30-/40-/roadmap/industry-packs/manual/archive/reference）—— spec §2.1 与本 plan 全程一致 ✅
