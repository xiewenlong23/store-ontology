> **🗄 归档说明**：brainstorming 产出（spec（设计决策）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# 设计文档归并整理设计

> **状态**：设计已确认，待实现
> **日期**：2026-06-21
> **性质**：本文档不是业务设计，而是**文档工程 + 代码清理**的实施 spec。它规定"如何把分散的设计文档归并为单一权威结构"以及"如何清理半退役的 vertical.py"。
> **产出**：`docs/design/` 新结构 + 删除 `agent/engine/vertical.py` + 重写 `docs/manual/`。

---

## 0. 问题陈述

项目"自己的"设计文档分散在 6 处、横跨 3 个时代，存在三类病灶：

1. **3 份互相竞争的平台设计重叠且部分矛盾**：
   - `docs/项目设计文档.md`(716 行) ——「AI 门店大脑-临期商品管理」原始设计（README 仍指向它），引用 `backend/ontology/store.ttl` 等已不存在的路径。
   - `docs/ontologyagent-design-CN.md`(1825 行) ——「OntologyAgent 设计规格说明书」，已被 superpowers target-architecture spec 取代（architecture/README 明确称后者为"权威设计文档"）。
   - `docs/Harness-Design.md`(3608 行) ——「Harness 工程」多组织/RBAC×ABAC 六层权限瀑布/审计/观测，**远超当前 MVP 实现**。
2. **路径全面过时**：14 份文档引用已不存在的 `backend/ontology|verticals|models|main`，4 份引用 `verticals/<name>`。连"当前"的 `architecture/*` 3 篇和 `业务本体建模规范.md` 都中招。真实结构是 `agent/engine/`、`agent/tools/`、`workspace/<行业包>/ontology/domains/<域>/`。
3. **术语漂移**：代码已从 `customer`/`vertical` 迁移到 `workspace_name`/`IndustryPack`(commit d3d7b3b、workspace-first 重构)，但 105 处 `customer_id`、15 处 `vertical`(英文)散落文档未跟；代码里 `vertical.py` 半退役（注册表零调用、但 `get_vertical` 仍被 parser.py 引用、3 个测试仍实例化 `VerticalConfig`）。

读者从任何入口进来都无法分清"什么是当前在跑的、什么是前瞻、什么是历史"。

---

## 1. 目标 / 范围 / 成功标准

### 1.1 目标

把分散在 6 处、3 个时代、术语漂移、路径失效的设计文档，重组为**单一权威设计 + 独立路线图 + 归档**的 `docs/design/` 结构，并让文档术语、手册流程、代码符号三者**对齐到活代码的 pack/workspace 模型**。

### 1.2 范围 — In

1. 新建 `docs/design/`，分类法重组所有有效内容（authority / 契约 / 规范 / 手册 / 行业包 / 参考 / 路线图 / 归档）。
2. **合并**两篇重叠架构文档（target-arch spec ⊕ system-architecture）→ 单一 `00-architecture.md`。
3. **治愈所有死路径**：`backend/`→`agent/engine/`、`verticals/`→`workspace/<行业包>/`。
4. **术语彻底统一**：customer→workspace、vertical→行业包/能力域/价值链流程，全文档（`archive/`、`reference/palantir/` 除外）。
5. **删 `agent/engine/vertical.py`**（含 parser.py 方式1 删除、shared.py 重构走 workspace、3 测试改写、注释修正），使代码符号与文档一致。
6. **重写 `docs/manual/`**（4 文档 + 8 模板）为 workspace + pack/能力域/价值链流程 的新接入流程。
7. 每份文档加**状态徽章**（✅当前 / 🔮前瞻未实现 / 🗄归档历史）。
8. **归档** 3 份被取代文档 + brainstorming specs/plans，各附"被谁取代"。
9. 修所有内部链接 + 根 `README.md` 指针（`docs/项目设计文档.md` → `docs/design/README.md`）+ `CLAUDE.md` 若有指向旧文档的链接。

### 1.3 范围 — Out

- ❌ 不改业务设计决策（只重组/合并/统一术语，不引入新架构决定）。
- ❌ 不编辑 palantir 参考库内容（~300 篇整体移动）。
- ❌ 不改 SKILL.md 业务逻辑（只顺带修其引用的文档路径/术语）。
- ❌ 除删 vertical.py + shared.py 装配重构 + 修注释外，**不重构其他代码**。

### 1.4 成功标准（可逐条验收）

1. `docs/design/README.md` 唯一入口；`docs/design/` 内每个 `.md`（`archive/`、`reference/` 除外）顶部有状态徽章。
2. 有且仅有一份权威架构 `00-architecture.md`；无独立重叠的 system-architecture。
3. `docs/design/` 内（`archive/`、`reference/palantir/` 除外）**零** `backend/`、`verticals/`、`customer_id`、`vertical`（作为行业包义）出现。
4. `roadmap.md` 独立、醒目标"未实现"，与权威严格分离。
5. 3 份被取代文档 + brainstorming 产出均在 `archive/`，每份开头有"已被 X 取代"指引。
6. `agent/engine/vertical.py` 已删；`agent/` 内（排除 `.venv`）`from engine.vertical`/`VerticalConfig`/`register_vertical`/`get_vertical`/`all_verticals` 零残留；**全套 `pytest` 通过，且通过数 ≥ 阶段 0 基线**。
7. `docs/manual/` 4 文档 + 8 模板全部基于 workspace + pack/能力域/价值链流程，**与 main.py 实际装配逻辑一致**（可对照 main.py 核对）。
8. 所有内部 `.md` 互链 + 根 README + CLAUDE.md 指针均能正确跳转（无断链）。
9. 无内容丢失：旧文档每个实质章节要么并入 authority/roadmap/industry-packs/manual，要么显式留 archive。

---

## 2. 目标目录结构与内容映射

### 2.1 目录结构

```
docs/design/
├── README.md                       【✅ 唯一入口】导航表 + 状态徽章图例 + 阅读路线
├── 00-architecture.md              【✅ 权威·单一】← 合并 target-arch spec ⊕ system-architecture
├── 20-api-data-contract.md         【✅】← api-and-data-spec（治愈路径/术语）
├── 30-development-guide.md         【✅】← development-guide（治愈 + 对齐 pack 装配）
├── 40-ontology-modeling-spec.md    【✅】← 业务本体建模规范（治愈路径/术语 + 模板引用改指 manual/）
├── roadmap.md                      【🔮 前瞻·未实现】← 抽 target-arch spec §6/§8 + Harness 重型机制（6层cascade/快照/26钩子等），醒目标"未实现"
├── industry-packs/
│   └── retail-clearance.md         【✅】← 抽 项目设计文档 有效部分（临期行业包 as-built：6 Object/8 Action/折扣规则）
├── manual/                         【✅ 重写】4 文档 + 8 模板，基于 workspace + pack/能力域/价值链流程
│   ├── 00-overview.md
│   ├── 01-onboarding.md
│   ├── 02-templates.md
│   ├── 03-worked-example-equipment-repair.md
│   └── templates/   （8 模板，见 §4）
├── reference/
│   └── palantir/                   【🗄 参考·只读移动】← palantir-ontology-docs/ 整体移入（~300篇，不编辑）
└── archive/                        【🗄 归档·只读历史】
    ├── README.md                   归档说明 + 旧→新 取代映射表
    ├── legacy-项目设计文档.md       ← docs/项目设计文档.md（头注：已被 00 + industry-packs/retail-clearance 取代）
    ├── legacy-ontologyagent-design-CN.md  ← docs/ontologyagent-design-CN.md（头注：已被 00 取代）
    ├── legacy-Harness-Design.md     ← docs/Harness-Design.md（头注：前瞻部分已进 roadmap）
    └── superpowers/                brainstorming 过程历史（specs+plans，头注：产物已进 authority）
        ├── specs/   （5）
        └── plans/   （4）
```

> manual 文档从原 5 篇重排为 4 篇：原 `01-内核多vertical改造` 讲的是已完成的改造、不再是接入者要做的步骤，其"内核契约"内容并入 `00-overview.md` 的 kernel/行业包边界表。

### 2.2 内容映射表（谁并入谁，确保无丢失）

| 现有文档 | 去向 | 处理 |
|---------|------|------|
| **target-arch spec**（575 行） | `00-architecture.md`（主）+ `roadmap.md`（§6/§8 🔜 部分） | **合并主体**；✅ 条款进 00，🔜 条款进 roadmap；术语/路径统一 |
| **system-architecture.md**（647 行） | `00-architecture.md`（与上合并，去重） | 重复章节（五层/概念/模块/数据流）合二为一；**消除重叠** |
| **api-and-data-spec.md**（654 行） | `20-api-data-contract.md` | 治愈 `backend/` 路径；术语 vertical→pack；Tool Schema/Action 契约内容保留 |
| **development-guide.md**（585 行） | `30-development-guide.md` | 重做"新增 Object/Link/Action 步骤"对齐 `workspace/<pack>/ontology/domains/<域>/`；本体开发步骤改为引用 manual/ |
| **业务本体建模规范.md**（550 行） | `40-ontology-modeling-spec.md` | 建模硬规范原样保留（高质量）；治愈 `backend/` 路径+术语；§11 模板引用改指 `manual/templates/` |
| **项目设计文档.md**（716 行） | `industry-packs/retail-clearance.md`（有效部分）+ `archive/`（全文） | 临期行业包的 6 Object/9 Action/折扣规则/CopilotKit 接入 → retail-clearance.md；**全文归档** |
| **ontologyagent-design-CN.md**（1825 行） | `archive/`（全文）+ 少量未覆盖的通用概念进 00 | 全文归档（已被 target-arch spec reconcile 取代）；核对 00 是否遗漏其通用概念，补缺 |
| **Harness-Design.md**（3608 行） | `roadmap.md`（前瞻部分）+ `archive/`（全文） | 重型机制（多组织/RBAC×ABAC/审计/观测）摘要进 roadmap 并醒目标"未实现"；**全文归档** |
| **manual/ 00-04 + 8 模板** | `manual/ 00-03 + 8 模板`（重写） | **全量重写**为 workspace+pack 模型（见 §4） |
| **architecture/README.md** | 并入 `docs/design/README.md`（导航） | 文档导航表升级为全 design 的导航+状态徽章 |
| **palantir-ontology-docs/** | `reference/palantir/` | **整体移动，不编辑** |
| **superpowers/ specs+plans** | `archive/superpowers/` | 过程历史归档；头注指明产物已进 authority |
| 根 `README.md` | 指针 `docs/项目设计文档.md` → `docs/design/README.md` | 修链接 |
| `CLAUDE.md` | 若有指向旧文档的链接则顺手修 | 检查后修 |

---

## 3. 术语统一规范表

基于已确认基准（对齐活代码 pack/workspace 模型），全文档（`archive/`、`reference/palantir/` 除外）的旧→新映射：

| # | 旧术语 | 新术语（规范） | 说明 / 例外 |
|---|--------|-------------|------------|
| 1 | customer / customer_id | **workspace / `workspace_name`** | 硬隔离边界。代码已完成（d3d7b3b），文档 105 处 customer_id 待跟。兼容说明保留（"旧数据 customer_id 视为 customer_default"） |
| 2 | tenant（笼统） | **workspace（隔离）+ org_unit（权限范围）** | tenant 不作孤立词。`tenant_id` 作为字段名**保留**（代码字段），但解释为"workspace_name + org_unit_id 双层" |
| 3 | TenantContext | **TenantContext（保留）** | 代码类名不动；文档解释为"workspace 硬隔离 + org_unit 权限范围"双层上下文 |
| 4 | vertical / verticals | **行业包 / IndustryPack** | `workspace/<name>/pack.py` 声明。`VerticalConfig`→`IndustryPack`（代码随之删改） |
| 5 | （vertical 内部概念，缺） | **能力域 / CapabilityDomain** | 原子 Object/Link/Action，`ontology/domains/<域>/` |
| 6 | （vertical 内部概念，缺） | **价值链流程 / ValueChainProcess** | 跨域编排（状态机+Skill+工具），如 clearance/repair |
| 7 | `backend/ontology/*.py` | **`agent/engine/*.py`** | 路径治愈。14 份文档中招 |
| 8 | `backend/verticals/<name>/` | **`workspace/<name>/`** | 路径治愈。4 份文档中招 |
| 9 | `backend/main.py` | **`agent/main.py`** | 路径治愈 |
| 10 | `backend/models/schemas.py` | **`agent/engine/schemas.py`** | 路径治愈 |
| 11 | `backend/skills/` | **`workspace/<pack>/skills/` + `agent/skills/`** | 2 级 Skill（workspace > 系统） |
| 12 | multi-vertical / 多 vertical | **多行业包** | 含义不变，术语对齐 |
| 13 | kernel / 内核 | **内核**（保留，与"行业包"对举） | "内核只认 IndustryPack，不认领域名词" |

**统一原则**：凡描述"业务场景包"的，一律用"行业包（IndustryPack）"；凡涉及它的内部结构，用"能力域/价值链流程"。`vertical` 一词**仅**保留在 `archive/`（历史文档）和必要的兼容说明里。

---

## 4. manual 重写要点（基于活代码可对照）

核心变化：接入单位从"vertical"改为**"行业包（IndustryPack）= 多个能力域（CapabilityDomain）+ 多个价值链流程（ValueChainProcess）"**。

| 文档 | 重写要点 |
|------|---------|
| `00-overview.md` | **kernel/行业包边界表**重做——基于 `agent/engine/{parser,repository,executor,action_loader,state_machine,preview_cache,pack,workspace_bootstrap,tenant}.py` 列"内核 vs 行业包"；口诀改为"提到领域名词=行业包，只认 IndustryPack=kernel" |
| `01-onboarding.md` | 接入流程改为：**建 `workspace/<pack_name>/pack.py` 声明 `IndustryPack`（含 CapabilityDomain[] + ValueChainProcess[]）** + 本体放 `ontology/domains/<域>/domain.ttl` + Action 放 `domains/<域>/actions/` + 流程 Action 放 `process.actions_dir` + Skill 放 `process.skills_dir` + 种子放 `data/`。bootstrap 自动发现 `workspace/*/pack.py`。**Phase A-F 重新定义** |
| `02-templates.md` | 占位符填法：新增 `pack.py` 的 CapabilityDomain/ValueChainProcess 填法；`workflow_object_type`→`ValueChainProcess.workflow_object_type`；`locator_field` 保留 |
| `03-worked-example-equipment-repair.md` | 对照 `workspace/equipment_repair/pack.py` 实际结构重写（真实而非臆造） |
| `templates/` | `vertical-config.py`→`pack.py`；`vertical-tools.py`→`pack-tools.py`；8 模板内容全部对齐 pack/能力域/价值链流程 |

---

## 5. 代码清理与内核重构

### 5.1 关键事实（已核实，决定重构边界）

- **vertical registry 在生产 agent 路径零使用**：`main.py` 构建 agent 走 pack（`all_packs`/`pack_to_registry`），不碰 vertical registry。
- **`get_vertical`/`VerticalConfig` 的仅存活用途**：`shared.py` 的 `_get_executor(vertical="clearance")`，只服务于 **2 个 webhook handler**（approval/pos）的 headless 执行。
- **`workspace_bootstrap.bootstrap_workspace()` 已是正确的 pack/workspace 装配路径**，但 `WorkspaceAgentInstance.executor=None`（注释"P1 先不接 executor"）。
- `register_vertical`/`all_verticals` 生产零调用。

### 5.2 注释级清理（机械、低风险）

```diff
# agent/main.py（5 处）
- # ===== 内核通用工具（与 vertical 无关）=====
+ # ===== 内核通用工具（与行业包无关）=====
- # ============ 工具清单（内核固定 + vertical 聚合）===========
+ # ============ 工具清单（内核固定 + 行业包聚合）===========
- # 去重：同名工具只保留第一个（vertical 与 pack 共存期避免冲突）
+ # 去重：同名工具只保留第一个（行业包工具聚合去重）
- description="本体驱动业务助手（多 vertical + Deep Agents）",
+ description="本体驱动业务助手（多行业包 + Deep Agents）",
- """启动时注册各 vertical 的定时 job 并启动 scheduler。"""
+ """启动时注册各行业包的定时 job 并启动 scheduler。"""

# agent/engine/state_machine.py（4 处注释）
- 多 vertical 改造后：状态迁移表来自 VerticalConfig（per-vertical）...
+ 多行业包改造后：状态迁移表来自 ValueChainProcess（per-process）...
  （其余 3 处类推：VerticalConfig→ValueChainProcess、vertical→行业包/价值链流程）

# agent/engine/executor.py
- self.config = config  # Optional[VerticalConfig]：提供状态机表与工作流对象类型
+ self.config = config  # 价值链流程上下文：提供状态机表与工作流对象类型
```

> `parser.py` 的方式1 代码块、`main.py:430/449` 的 webhook 调用属活代码，归入 5.3 内核重构。

### 5.3 vertical.py 真删 + 内核重构

**设计决策 1：删除 `get_ontology_parser(vertical=)` 方式1。**

理由：方式1 的 `get_vertical(name)` 在 pack 模型下无等价物（parser 由 `pack_to_registry(pack)` 构建）。唯一消费者是 `shared.py:_parser/_get_executor`，而这些函数本身要重构成走 workspace。删方式1 后：
- `get_ontology_parser` 只保留方式2（显式路径，测试用）+ 方式3（默认兜底）。
- `parser.py` 删 `from engine.vertical import get_vertical` 及方式1 代码块。
- 删除 `agent/engine/vertical.py` 文件。

**设计决策 2：webhook/tool/agent 三路统一走 `bootstrap_workspace()`，并接通 executor。**

重写 `shared.py` 依赖装配层，消除"tool/webhook 走 vertical registry、agent 走 pack registry"的双轨：

```python
# agent/tools/shared.py（重构后骨架）
from engine.workspace_bootstrap import bootstrap_workspace

def _get_workspace_instance(workspace_name: str):
    """统一依赖装配入口：所有路径（tool/webhook/agent）共用 workspace 装配。"""
    return bootstrap_workspace(workspace_name)

def _get_executor(workspace_name: str, process_name: str = None) -> ActionExecutor:
    """取某 workspace（+某价值链流程）的 executor。"""
    inst = bootstrap_workspace(workspace_name)
    return inst.executor

def _get_repo(workspace_name: str):
    return bootstrap_workspace(workspace_name).repository
```

配套：
- **`workspace_bootstrap.py`**：`WorkspaceAgentInstance.executor` 从 `None` 改为真实构建（`ActionExecutor(repository=repo, actions=registry.action_types, registry=registry, config=<ValueChainProcess>)`）。
  - **config 解析链**（实施者必读）：`WorkspaceAgentInstance.config`(=`WorkspaceConfig`)有 `source_pack` 字段 → 经 `get_pack(cfg.source_pack)` 取 `IndustryPack` → 在 `pack.processes` 里按 `process_name` 匹配取目标 `ValueChainProcess`（未指定 process_name 时取 `pack.processes[0]`）→ 该 process 作为 executor 的 `config`。executor 用它的 `state_transitions`/`workflow_object_type` 做状态机校验。
  - 现状 webhook 只服务 clearance（retail 包单 process），未指定 process_name 取 `[0]` 足够；多 process webhook 通用化列为 v2。
- **`main.py:430/449` webhook**：`_get_executor(vertical="clearance")` → `_get_executor(workspace_name="retail", process_name="clearance")`。

**设计决策（webhook 定位语义）：采用 (b) workspace + process 双参。** 精确，且为将来多 process webhook 留好口子。签名 `_get_executor(workspace_name, process_name)`。

### 5.4 3 个测试改写方案

| 测试 | 现状 | 改写 |
|------|------|------|
| `test_vertical.py` | `VerticalConfig` 是死 import；实际测 pack registry | **删 line4 import**；文件改名 `test_pack_registry.py`（内容已是 pack 测试） |
| `_clearance_helper.py` | `CLEARANCE_TEST_CONFIG = VerticalConfig(...)` | 改为用真实 workspace 装配：`bootstrap_workspace("retail")` 或构造 `IndustryPack`/`ValueChainProcess` |
| `test_equipment_repair.py` | `_REPAIR_CFG = VerticalConfig(...)` | 改为 `bootstrap_workspace("equipment_repair")` 或构造 IndustryPack |

---

## 6. 执行顺序

**遵循"先止血、再重构、最后文档收尾"——代码重构放在文档之前，这样文档写完就能反映最终真相，不必返工。**

| 阶段 | 内容 | 风险 | 验证门槛 |
|------|------|------|---------|
| **阶段 0：基线确认** | 跑一次 `pytest` 记录当前通过数作为基线 | 无 | 记录基线 pass 数 |
| **阶段 1：vertical.py 真删 + 内核重构（代码）** | §5.3：接通 executor → 重构 shared.py 走 workspace → 删方式1 → 删 vertical.py → 改 3 测试 → 修注释（§5.2） | 🔴 **最高** | `pytest` 全绿（≥基线）；vertical 零残留 grep |
| **阶段 2：建 `docs/design/` 骨架** | 创建目录结构 + `README.md` 导航 + 状态徽章图例 | 低 | 目录结构成形 |
| **阶段 3：合并/治愈/重写文档内容** | 合并 target-spec⊕system-arch→00；治愈 api-spec/dev-guide/建模规范；重写 manual；抽 industry-packs/retail-clearance；写 roadmap | 中 | 每份文档独立校验（路径/术语/徽章） |
| **阶段 4：归档 + 移动参考库** | 3 份旧文档+superpowers→archive（加头注）；palantir→reference/（整体移动） | 低 | archive 每份有"被取代"头注 |
| **阶段 5：链接修复 + 全局验证** | 修根 README/CLAUDE.md 指针；所有内部互链；跑断链检查；术语 grep 清零 | 低 | 成功标准 1-9 全过 |

> **关键约束：阶段 1 必须先做完且 `pytest` 全绿，才进阶段 2。** 代码没稳就写文档，文档会基于错误事实。每阶段一个 commit，便于回滚。若阶段 1 卡住，整个 spec 暂停而非带病推进文档。

---

## 7. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 删除 vertical.py 导致测试大面积红 | 🔴 高 | 阶段1 以 pytest 全绿为硬门槛，不过则不进阶段2；3 个测试改写先单独跑通再删文件；git 每步可回滚 |
| shared.py 重构影响 tool 运行时行为 | 🔴 高 | 现有 `test_tools*.py`（多份）+ `test_clearance_automation.py`/`test_webhooks.py` 覆盖 tool+webhook 路径，必须保持绿 |
| 文档合并丢内容 | 🟡 中 | 内容映射表（§2.2）逐项核对；旧文档全文归档不删，可追溯；Spec 自检含"无丢失"检查 |
| manual 重写与 main.py 不一致 | 🟡 中 | manual 写完对照 `main.py`/`pack.py`/`workspace_bootstrap.py` 逐条核对（成功标准 #7） |
| 术语统一遗漏 | 🟡 中 | 阶段5 用 grep 机械化扫：`backend/`、`verticals/`、`customer_id`、`vertical`（作为包义）在 design/ 内（除 archive/reference）零命中 |
| 断链 | 🟡 中 | 阶段5 跑链接检查（grep + 人工抽样） |
| 范围蔓延（写文档时顺手改业务设计） | 🟡 中 | Out 范围明确；写作时只在"统一术语/治愈路径/合并重叠/重写manual"四类动作内 |

---

## 8. 验收检查清单

对应成功标准 1-9，可机械化检查的用 grep，人工核的列入。

### 8.1 机械化检查

```bash
# 成功标准 3：路径/术语零残留（archive/、reference/palantir/ 除外）
grep -rn 'backend/ontology\|backend/verticals\|backend/main\|backend/models\|backend/skills' \
  docs/design --include='*.md' | grep -v 'archive/' | grep -v 'reference/palantir/'
# 期望：零命中

grep -rn 'customer_id\|verticals/' docs/design --include='*.md' \
  | grep -v 'archive/' | grep -v 'reference/palantir/'
# 期望：零命中（customer_id 作为兼容说明除外，需人工确认语境）

# 成功标准 6：代码 vertical 零残留
grep -rn 'from engine.vertical\|VerticalConfig\|register_vertical\|get_vertical\|all_verticals' \
  agent --include='*.py' | grep -v '.venv'
# 期望：零命中

# 成功标准 6：pytest 全绿
cd agent && python -m pytest -q
# 期望：全通过，且通过数 ≥ 阶段0 基线
```

### 8.2 人工核对

- 成功标准 1：README 唯一入口 + 每份 .md 状态徽章。
- 成功标准 2：单一 `00-architecture.md`，无独立重叠 system-architecture。
- 成功标准 4：roadmap.md 独立、醒目标"未实现"。
- 成功标准 5：archive 每份有"被取代"头注。
- 成功标准 7：manual 对照 main.py/pack.py/workspace_bootstrap.py 逐条一致。
- 成功标准 8：内部互链 + 根 README + CLAUDE.md 指针无断链。
- 成功标准 9：旧文档每个实质章节有归属（并入或归档）。

---

## 9. 本次不含、标注为"后续任务"的项

- palantir 参考库的二次整理（本次仅移动）。
- v2 前瞻项的具体设计（本次仅从 Harness 摘要进 roadmap，不展开）。
- manual 模板之外的接入工具开发。

---

## 附录 A：决策溯源（brainstorming 期间的澄清与纠正）

- **方案选择**：归并为单一权威设计（非"目录+索引"或"全量重写"）；新建 `docs/design/` 重构；权威只写已实现 + 路线图独立。
- **术语基准**：对齐到活代码 pack/workspace 模型（非保留 vertical 术语）。
- **vertical.py 事实纠正**：brainstorming 初期误判 vertical.py 为"零调用可删死代码"。核实后发现 `get_vertical` 被 parser.py 引用、3 个测试实例化 `VerticalConfig`，属"半退役 + 测试依赖"的中间态。基于正确事实，用户选择"本次全做（含内核重构）"。
- **webhook 定位语义**：在 (a) workspace / (b) workspace+process / (c) 模块路径推导 中选 (b)，签名 `_get_executor(workspace_name, process_name)`。

---

## 附录 B：执行期偏离与事后纠正（实现后回填）

本附录记录实现期间与原 spec/plan 不一致之处，以及最终审查发现并修复的问题，供后续追溯。

### B.1 执行期偏离 plan 的两处

1. **基线测试需 conda Python（plan 写"150 passed"为门槛，未指明解释器）**
   plan 与 spec 均以"pytest 150 passed"为阶段 1 门槛，但未指明用哪个 Python。实现时首次用系统 Python 3.9 跑，因缺 `langgraph` 等依赖报 19 errors + 7 failed，一度误判基线不绿。**纠正**：必须用 `/opt/miniconda3/envs/store-ontology/bin/python`（3.11，README 指定的 conda env）。真实基线确为 150 passed。**教训**：凡涉及测试门槛的 spec，应显式写明解释器/环境。

2. **shared.py 装配签名偏离 plan 预设**
   plan §Task 1.2 预设 `_get_executor/_get_repo/_parser` 应改为接受 `workspace_name` 参数。实现时核实代码发现：真实调用签名是 `_get_repo(tc)`（`tc` 是 `TenantContext`）和 `_get_executor()`（无参，从 contextvar 解析），且多个测试 monkeypatch 用 `vertical=` 关键字。强行改签名会连锁改大量测试 monkeypatch。**纠正**：保留原签名（`vertical=` 作为废弃 no-op 参数保留以兼容 monkeypatch），改为内部从 `main.tenant_ctx` contextvar 解析 workspace。webhook 调用点改用 `process_name=`。最终签名 `_get_executor(vertical=None, process_name=None)`、`_get_repo(tenant=None, vertical=None)`。**教训**：plan 的文件级预设需在实现前对照真实调用点核实，否则易低估工作量或引入不必要的连锁改动。

### B.2 最终独立审查发现并修复的问题

实现完成后派两个 Explore reviewer 做整体审查（代码 + 文档），发现以下 plan/spec 未预见的问题，均已修复：

**代码（2 Critical + 2 Important + 3 Minor）**：
- **C1（生产 bug）**：`workspace/equipment_repair/skills/repair_workflow/tools.py` 的 `query_repair_tickets` 调 `_get_repo(字符串, vertical=...)`，新 `_get_repo` 期望 `TenantContext` → 运行时 `AttributeError`，工具完全不可用。根因：该工具是 pre-refactor 遗留，未对齐 retail 的 `query_near_expiry` 模式，且无测试覆盖。修复：改为 `workspace_name`+`TenantContext` 模式 + 加回归测试。
- **C2（脆弱依赖）**：clearance automation 的 scheduler 闭包仍调 `_get_executor(vertical="clearance")`，靠 `customer_default→retail→processes[0]` 巧合命中 clearance。修复：改 `process_name="clearance"` 显式指定 + 加源码契约测试。
- **I4（根因）**：废弃的 `vertical=` 参数静默忽略，导致 C1/C2 漏网。修复：加 `DeprecationWarning`。
- I1（未知 `process_name` 静默回退→加 warning）、M1-M4（docstring/死代码/测试名 misnomer）。

**文档（5 Critical + 3 Important）**：
- **DC1**：`00-architecture §4.5` 折扣模块路径错（实际在 `skills/clearance_workflow/discount.py`）。
- **DC2**：`retail-clearance §2` Task 域归属错（实际 organization 域，非 finance）。
- **DC3**：`03-worked-example §2` equipment_repair 目录树错（Action 在 maintenance/actions，非 skills/.../actions）。
- **DC4**：`20-api §3.2` + `03-worked-example` equipment Action api_name 全错（`diagnose`→`diagnose_ticket` 等）。
- **DC5**：`40-ontology-modeling-spec` 的"架构文档 §1.X"引用系统性偏移（实际 §2.X，且 §1.5 不存在）。
- **DI1-DI3**：建模规范描述 3 个"现有 bug"（manages 方向/LinkTypes 常量/缺元数据），但代码里这些早已修复——文档会误导读者去"修"正常代码。改为历史标注。

**教训**：grep 能验证路径/术语表层一致，但**无法核实内容准确性**（Action 名是否真存在、域归属对不对、引用的章节是否存在）。独立审查（读真实代码逐条对照）是内容准确性唯一可靠的验证手段。本次审查抓到的 2 个生产 bug（C1/C2）是 grep/自检都漏掉的——这正是 plan 流程要求"派 final reviewer"的价值。

