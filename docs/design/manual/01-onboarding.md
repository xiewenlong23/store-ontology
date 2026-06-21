# 新业务场景接入手册（标准流程）

> **状态**：✅ 当前。
> **配套**：模板见 [`templates/`](./templates/)（填法见 [`02-templates.md`](./02-templates.md)）；完整例子见 [`03-worked-example-equipment-repair.md`](./03-worked-example-equipment-repair.md)。
> **依据**：[`40-ontology-modeling-spec.md`](../40-ontology-modeling-spec.md)（下称"建模规范"）。

---

## 0. 接入前的设计准备

动手前先回答（对照建模规范 §1.2、§3.4、§5.2）：
1. 这组业务实体有**独立生命周期 + 受治理写操作 + 多步工作流**吗？是 → 适合建工作目录。否 → 用内核 CRUD 工具即可（见 [`00-overview.md`](./00-overview.md) §4）。
2. 价值链流程的主对象是什么？（如 RepairTicket）—— 它决定 `ValueChainProcess.workflow_object_type`。
3. 哪些实体是**受治理**的（`:edits_only_via_actions "true"`）？通常是工作流对象 + 它操作的标的物。
4. 状态机的合法迁移图是什么？画出来。
5. 有没有类似折扣的"数值规则"？若有，定单一事实源 JSON + 计算函数（放某能力域的 `rules/` 下）。

---

## Phase A：能力域建模（Object / Link TTL）

**做什么**：填 [`templates/ontology.ttl.template`](./templates/ontology.ttl.template) → 产出 `<domain>.ttl`。
**放在**：`workspace/<pack>/ontology/domains/<域>/domain.ttl`（每个能力域一个 TTL）。

步骤：
1. 识别能力域。把实体按业务职能分组：营销相关 → `marketing`，组织相关 → `organization`，财务相关 → `finance`。一个工作目录可有多个能力域。
2. 每个能力域建 `domain.ttl`，列 Object Type（`:NewObject a :Class` 块，含 `properties` / `:storage` / `:labelZH`；受治理实体加 `:edits_only_via_actions "true"`）和 Link Type（`rdfs:Property` 块，domain/range/via）。
3. **核对建模规范 §9 检查清单**：
   - [ ] 命名：Object PascalCase 单数；Link snake_case；每个资源有中英文 label。
   - [ ] 主键 `id`（string）。
   - [ ] 属性类型取自白名单（建模规范 §6.1），无 string 存日期/数值。
   - [ ] 软引用字段 `{type}_id` 形式，与 Link 的 via 一致。
   - [ ] **via 归属**（建模规范 §4.3，最易错）：via 字段确实属于 range 对象。
   - [ ] 单位口径（建模规范 §6.2）：百分比=减扣百分比 int、金额=元、数量带单位。

**验证**：肉眼 + 检查清单。或写一个最小 parser 测试确认能解析（参考 `agent/tests/test_parser.py`）。

---

## Phase B：Action 契约（YAML）

**做什么**：每个 Action 填 [`templates/action.yaml.template`](./templates/action.yaml.template) → 产出 `*.yaml`。
**放在**：
- **域内 Action**（操作能力域实体）：`workspace/<pack>/ontology/domains/<域>/actions/<api_name>.yaml`
- **流程专属 Action**（状态迁移类，如 submit/approve）：`workspace/<pack>/skills/<process>/actions/<api_name>.yaml`（即 ValueChainProcess 的 `actions_dir`）

步骤：
1. 每个 Action 一个 YAML。必填：`api_name` / `target_object_type` / `edits_object_types` / `parameters`（带 constraint）/ `side_effects`。
2. **填 `locator_field`**：target 是工作流对象时填定位它的参数名（如 `ticket_id`）；target 是标的物填 `target_id`。
3. `submission_criteria`：roles 白名单 + conditions（field 用 `target.status` 或 `<workflow_object_lower>.status`）。
4. `side_effects` 声明式：`create_object` / `update_object` / `state_transition`（from/to）/ `notification` / `external_call`。

**核对**（建模规范 §5、§9）：
- [ ] Action 边界正确（受治理写走 Action，读不走，非业务数据走降级 CRUD）。
- [ ] `target_object_type` 与 `locator_field` 匹配。
- [ ] parameters 带声明式 constraint，数值参数注明单位。
- [ ] side_effects 声明式，不在执行器硬编码。
- [ ] 多 Object 写入保证原子性（executor 用 Repository 原子写）。

> **重要**：Action 是声明式的。新增 Action **只加 YAML，零改 executor 代码**——`ActionExecutor` 按 side_effects 数据驱动执行。

---

## Phase C：状态机（若有价值链流程）

**做什么**：填 [`templates/state_machine.py.template`](./templates/state_machine.py.template) → 产出 `state_machine.py`。
**放在**：`workspace/<pack>/skills/<process>/state_machine.py`（如 `workspace/customerA/skills/repair_workflow/state_machine.py`）。

步骤：
1. 定义 `<WORKFLOW_OBJECT>_TRANSITIONS` dict（键=当前状态，值=允许的下一状态列表）+ `TERMINAL_STATES` 集合。
2. `workspace.py` 会 import 这两个并填入 `ValueChainProcess.state_transitions` / `terminal_states`（见 Phase F）。
3. executor 的 `state_transition` 副作用自动查这张表校验。

**核对**（建模规范 §5.5、§8 反模式 7）：
- [ ] 所有状态迁移只能由 Action 触发，无直接改 status 的口子。
- [ ] 终态集合正确（终态不可再迁移）。

**无工作流的工作目录跳过本步**：不建 ValueChainProcess，只建 CapabilityDomain。

---

## Phase D：种子数据

**做什么**：填 [`templates/seed-object.json.template`](./templates/seed-object.json.template) → 产出 `*.json`。
**放在**：`workspace/<pack>/data/<entity_type>.json`（每个实体类型一个 JSON）。

步骤：
1. 每个 Object Type 对应一个 JSON 文件（空数组 `[]` 或含种子）。
2. 每条记录带 `workspace_name`（默认 `jjy`）；需 org 隔离的带 `org_unit_id`。
3. TTL 的 `:storage "<file>.json"` 与文件名一致。

---

## Phase E：价值链流程的专属工具与 Skill

### E.1 专属工具（可选）

**做什么**：填 [`templates/pack-tools.py.template`](./templates/pack-tools.py.template) → 产出 `tools.py`。
**放在**：`workspace/<pack>/skills/<process>/tools.py`。

导出 `TOOLS = [...]` 列表（`@tool` 函数）。被 `main._aggregate_pack_tools()` 自动聚合。工具经 `agent.tools.shared` 的 helper 装配（`_get_repo`/`_get_executor`）。

### E.2 Skill 文档

**做什么**：填 [`templates/skill-workflow.md.template`](./templates/skill-workflow.md.template)（流程编排）或 [`templates/skill-knowledge.md.template`](./templates/skill-knowledge.md.template)（领域知识）→ 产出 `SKILL.md`。
**放在**：`workspace/<pack>/skills/<topic>/SKILL.md`。

Skill 由 SkillsMiddleware 加载，2 级（workspace 高优先级 / 系统低优先级）。

---

## Phase F：注册与接线（建 workspace.py）

**做什么**：填 [`templates/workspace.py.template`](./templates/workspace.py.template) → 产出 `workspace.py`。
**放在**：`workspace/<pack>/workspace.py`。

```python
import os
from engine.pack import (工作目录（WorkspaceDef）, CapabilityDomain, ValueChainProcess, register_workspace_dir)
from workspace.<pack>.skills.<process>.state_machine import (
    <WORKFLOW>_TRANSITIONS, TERMINAL_STATES)

_BASE = os.path.dirname(os.path.abspath(__file__))

# 能力域
DOMAIN_A = CapabilityDomain(
    name="<domain_a>", display_name="<域A中文名>",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "<domain_a>", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "<domain_a>", "actions"),
    rules_dir=os.path.join(_BASE, "ontology", "domains", "<domain_a>", "rules"))  # 可选

# 价值链流程（若有工作流）
PROCESS_X = ValueChainProcess(
    name="<process_x>", display_name="<流程中文名>",
    workflow_object_type="<WorkflowObject>",
    workflow_object_id_field="<workflow_object>_id",
    state_transitions=<WORKFLOW>_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.<pack>.skills.<process>.tools",
    actions_dir=os.path.join(_BASE, "skills", "<process>", "actions"),  # 流程专属 Action
    system_prompt_intro="你是<场景>助手。")

# 工作目录
PACK = 工作目录（WorkspaceDef）(
    name="<pack>", display_name="<工作目录中文名>",
    domains=[DOMAIN_A, ...],
    processes=[PROCESS_X, ...],
    data_dir=os.path.join(_BASE, "data"))

register_workspace_dir(PACK)
```

**重启后端**：`bootstrap()` 自动发现 `workspace/<pack>/workspace.py`，注册进 pack 注册表。`main._aggregate_pack_tools()` 聚合工具，`_build_combined_prompt()` 合并本体提示，`_aggregate_skill_paths()` 收录 Skill。**零改内核，重启即生效。**

---

## 最终验证清单（对照建模规范 §9）

- [ ] TTL 可被 Parser 解析（启动无报错）
- [ ] 所有 Action YAML 能被 action_loader 加载
- [ ] 状态机迁移表覆盖所有业务状态
- [ ] 种子数据加载无 JSON 错误
- [ ] `query_entity("<NewObject>")` 能查到数据
- [ ] `execute_action("<new_action>", params)` → `confirm_action` 闭环跑通
- [ ] 受治理实体（edits-only）被 `create_entity`/`update_entity` 拒绝
- [ ] 状态机非法迁移被 executor 拒绝

---

## 常见坑

1. **via 归属反了**：`Store → Employee, via="manager_id"`，但 `manager_id` 在 Store 上 → 遍历巧合通过但语义错。正确：via 必须属于 range 对象。详见建模规范 §4.3。
2. **Action 忘填 locator_field**：target 是工作流对象（Task/RepairTicket）时必须填其 id 参数名（task_id/ticket_id），否则 executor 定位不到。
3. **受治理实体忘了 edits-only 标记**：导致 `update_entity` 能绕过审批直接改业务字段。
4. **状态机终态漏了**：终态不在 `TERMINAL_STATES` 里，会导致已完成的任务还能被迁移。
5. **种子数据没带 workspace_name**：跨 workspace 查询时会过滤掉。
