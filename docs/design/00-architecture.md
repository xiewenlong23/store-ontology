# OntologyAgent 平台架构（单一权威）

> **状态**：✅ 当前（已实现）。本文档是平台架构的**唯一**权威来源——定方向、消冲突、明边界。它回答"做什么/不做什么"。配套文档见 [`README.md`](./README.md)。
> **版本**：MVP（内核 + 零售临期行业包 + 设备维修行业包）
> **来源**：本文档由三份历史设计 reconcile 而来（见 [`archive/`](./archive/)），随实现滚动更新。

---

## 0. 定位

**OntologyAgent 是一个本体驱动的通用 AI Agent 平台。** 通用内核提供"本体元数据 + CRUD + 多租户抽象 + Agent harness + Tool/Skill 体系 + **多行业包注册表**"，各行业包（零售、物流、制造……）在本体之上声明式建模即可接入，**新增行业包零改内核**。**临期商品零售（retail/clearance）是第一个行业包；设备维修（equipment_repair/repair）是第二个，作为多行业包并存的 worked example。**

### 核心判断

> **Palantir 本体为前 LLM 时代的"人 + 应用"设计，LLM 时代 agent 的消费者变了，抽象就该变。**

- Palantir 的消费者是**人和应用**：人在 Object Explorer 填表单、在 Workshop 配应用；Action Type = 人执行的事务（表单、审批）；Function = 给 Workshop/派生列调用的命名计算。
- LLM 时代 agent 的消费者是 **LLM**：它通过 **Tool**（有 schema，可直接 invoke）操作世界，通过 **Skill**（可读的指令文档）理解何时怎么做。

由此得出取舍：
- **保留** Palantir"描述世界"的部分——Object/Link/Action Type 作为声明式契约。
- **降级/吸收**"执行/计算"的部分——Function 不作为本体元素；计算逻辑是普通 Python 模块，通过 Tool 暴露给 LLM。
- **新增** agent 特有的 Skill——给 LLM 读的流程/策略指令文档。

---

## 1. 五层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│  第5层：用户交互入口                                                      │
│  现状：CopilotKit v1.57（9 个 renderToolCalls，clearance 专用）           │
│  未来（v2）：A2UI 标准渲染、多行业包切换 UI、定时自动化作业 UI              │
├─────────────────────────────────────────────────────────────────────────┤
│  第4层：Agent 层                                                          │
│  现状：单 Agent（deepagents create_deep_agent + SkillsMiddleware）         │
│  系统提示 = 各行业包本体合并（_build_combined_prompt）                     │
│  未来（v2）：subagent / 多 Agent 协作（Planner/Tool/Reasoner/Reporter）   │
├─────────────────────────────────────────────────────────────────────────┤
│  第3层：Tools / Action Types / Skills / 计算逻辑                          │
│  内核工具（固定）：query_entity/create/update/traverse/execute_action/    │
│                   confirm_action/query_task/update_task                   │
│  行业包工具（聚合）：各价值链流程的 TOOLS（如 query_near_expiry、          │
│                     query_repair_tickets）                                 │
│  Action Type：声明式 YAML 契约（参数+submission_criteria+副作用+locator）  │
│  Skill：SKILL.md，从各行业包 skills/ 聚合加载                              │
│  计算逻辑：行业包私有 Python 模块（如 marketing/rules/discount）            │
├─────────────────────────────────────────────────────────────────────────┤
│  第2层：Ontology 层（通用内核 + 多行业包注册表）                           │
│  通用内核：IndustryPack + CapabilityDomain + ValueChainProcess +         │
│            注册表 + bootstrap 自动发现 + Repository                       │
│            （多 workspace 隔离/锁/原子写/edits-only）+ 声明式 ActionExecutor │
│  行业包（声明式接入，零改内核）：                                          │
│    retail: marketing/organization/finance 能力域 + clearance 价值链流程   │
│    equipment_repair: maintenance 能力域 + repair 价值链流程（worked example）│
│  未来（v2）：组织5级 / 品类5级 / DC / 职能域（零售行业包深化）              │
├─────────────────────────────────────────────────────────────────────────┤
│  第1层：LLM + 存储                                                        │
│  LLM：MiniMax-M2.7-highspeed（OpenAI 兼容，现有一套，未来多 provider）     │
│  存储：JSON 文件（现状）via Repository 抽象 → PostgreSQL+JSONB（v2）        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 四概念分工（核心）

整个设计的地基。混淆大多来自没区分清楚这四者。

| 概念 | 性质 | LLM 关系 | 何时用 |
|------|------|---------|--------|
| **Object / Link Type** | 本体定义 · 实体与关系 | 经 `build_ontology_prompt` 让 LLM 理解世界结构 | 建模领域实体与关系 |
| **Action Type** | 本体定义 · **声明式变更契约**（参数 + 约束 + submission criteria + 副作用声明） | LLM 不直接执行，经 `execute_action` Tool 调用；**后端自动化也调同一套** | 描述受治理的业务事务 |
| **Tool** | 执行机制 · LLM 直接调用的函数 | LLM 直接 invoke（schema 注入 prompt） | LLM 读数据、调 Action、与外部交互 |
| **Skill** | 执行机制 · 给 LLM 读的指令文档 | LLM 按需 `read_file` | 流程编排、领域知识、策略指南 |
| **计算逻辑** | 普通代码 · 命名 Python 模块 | LLM 不可见（除非包成 Tool） | 跨工具复用的纯计算（折扣、补货点） |
| **Interface Type** | 本体定义 · 抽象类型 | （v2，MVP 不实现，元数据预留） | 跨 Object 共享形状 |

### 2.1 不引入 Function 作为本体元素

Palantir 的 Function 是"注册到本体的、命名的、可被应用发现和绑定的计算单元"——它存在是因为 Palantir 的消费者是**各种应用**，应用需要一个本体内的命名计算来绑定。

agent 系统的消费者是 **LLM**。LLM 发现和调用计算的机制就是 **Tool**（schema 注入 prompt，LLM 决定调用）。所以计算的"接口"天然就是 Tool，不需要额外的本体 Function 元素。**Tool 就是 LLM 时代的 Function。**

Palantir Function 的可借鉴点（计算应命名、可复用、与 Action 解耦、单一事实源）通过**普通 Python 模块 + 本体数据**就实现了。重型特性（SemVer 版本、沙箱、provenance）本就不在 MVP。

### 2.2 Action Type 与 Tool 的关系（六条）

不在同一层级。

1. **层级不同**：Action Type 是业务事务维度（clearance、调拨、补货），Tool 是技术接口维度（query、execute_action）。
2. **1:N 映射**：一个 `execute_action` Tool 执行多个 Action Type。
3. **双消费者**：Action Type 被 LLM（经 `execute_action`）和后端自动化（直接调执行器）**共用**，走同一套校验/权限/审计。Tool 是 LLM 专用接口，后端不走 Tool——这是 Action Type 不可替代的原因。
4. **边界**：Action Type 只管"受治理的变更"（写）；读操作（query_*）是纯 Tool，无 Action Type。
5. **治理强制**：核心业务实体的写操作锁为 edits-only-via-actions；通用 CRUD 工具 `create_entity`/`update_entity` 降级，仅限非业务数据。
6. **execute_action 是瘦路由器**：读定义 → 校验 submission criteria → 校验参数约束 → 执行声明的变更 → 触发副作用 → 写审计 → 返回。业务逻辑全在 Action Type 定义里，不在 Tool 里。

### 2.3 治理强制（CRUD 降级）

通用 CRUD 工具能直接改任意实体的任意字段，**绕过所有 Action Type 治理**。生产环境下这是漏洞。

**已落地**：核心业务实体（NearExpiryProduct、Task、LossReport、Equipment、RepairTicket 等）的写操作锁为 edits-only-via-actions。`create_entity`/`update_entity`/`update_task` 降级为仅用于非业务数据；`update_task` 收紧为白名单字段（`notes`/`priority`），其余字段走 Action。

实现（`agent/engine/repository.py`、`agent/tools/`）：
1. **标记来源**：Object Type 在 TTL 元数据声明 `edits_only_via_actions "true"`，Parser 解析后存入 `ObjectType.edits_only_via_actions`。
2. **Repository 层检查**：`Repository.write(...)` 内部查 `edits_only_via_actions`，为 `True` 时拒绝写并抛 `ActionRequiredError`。
3. **Action 执行器绕过**：`Repository.write(..., bypass_action_check=True)`，**仅** `ActionExecutor` 内部传入。

### 2.4 长流程承载：工作流对象 + 状态机 + 自动化（不引入 BPM 引擎）

"生成任务是一个跨数天的流程"不靠单一 Skill 装下。它**涌现**自三样东西：
- **工作流 Object + 状态机**：clearance 用 `Task`（`created → pending_approval → approved → accepted → in_progress → completed`，或 `→ scrapped`）；equipment_repair 用 `RepairTicket`（`reported → diagnosed → assigned → repairing → resolved`，旁路 `→ cancelled`）。状态跨天持久化。
- **Action Type**：每个状态迁移是一个 Action。
- **后端自动化**：事件处理（POS）、定时器（到期检查）、审批回调——调 Action Type，不需要 LLM。

**决策**：用工作流对象状态机 + 后端自动化承载长流程，不引入独立 Workflow/BPM 引擎（那是 v2 可选增强）。

**状态机实现（per-process，数据驱动）**：状态迁移表不再全局硬编码，而是每个价值链流程自带一份（`ValueChainProcess.state_transitions`）。`is_valid_transition(from, to, transitions, terminals)` 接受 per-process 表。

**Action 定位键（locator_field）**：每个 Action 在 YAML 里声明 `locator_field`（如 `task_id` / `ticket_id`），executor 据此定位 target 记录（数据驱动，取代旧的硬编码）。

**后端自动化**（`agent/engine/scheduler.py` 内核 + 行业包 automation）：
- `AutomationScheduler`（封装 APScheduler）嵌入 FastAPI 进程，承载 inventory_check（售罄完成）与 expiry_check（到期报损）job。
- webhook 模拟端点：`/api/webhooks/approval`、`/api/webhooks/pos`。真实 POS/审批系统集成留 v2。
- LLM 唤醒（报损推理）🔜 v2；当前报损用计算式。

### 2.5 Preview→Confirm 治理闭环

`execute_action`（preview）和 `confirm_action`（执行）是两个独立 Tool。仅靠 Skill 指导 LLM "先 preview 再 confirm" 没有技术强制——LLM 或恶意调用者可直接调 `confirm_action` 绕过。

**已落地**：preview 记录 + confirm 校验（`agent/engine/preview_cache.py`）：
1. `execute_action` 将 preview（action_type + params + actor + tenant）存入进程内 `PreviewCache`，返回 `preview_id`。
2. `confirm_action(preview_id)` 查缓存，存在且未过期（TTL=300s）才执行；取走即失效（一次性）；不存在/过期则拒绝。
3. 存储：进程内 `dict` + TTL。🔜 v2 可升级 Redis / DB。

---

## 3. 第2层：Ontology 层（通用内核 + 行业包分层）

### 3.1 本体元数据模型（内核，对齐 Palantir）

每个本体资源携带完整元数据：

| 元数据 | 说明 |
|--------|------|
| `api_name` | 编程引用名（如 `near_expiry_product`） |
| `display_name` | UI 显示名（如"临期商品"） |
| `description` | 业务含义 |
| `status` | `active` / `experimental` / `deprecated` |
| `visibility` | `prominent` / `normal` / `hidden` |
| `workspace_name` | 多 workspace 归属 |
| `edits_only_via_actions` | 是否锁定为只能通过 Action 修改（治理强制，见 §2.3） |

**资源类型**：
- **Object Type**：业务实体类型定义
- **Link Type**：两 Object Type 间关系，支持 cardinality（1:1 / 1:N / N:N）
- **Action Type**：声明式变更契约，含 parameters + submission_criteria + side_effects
- **Interface Type**：抽象接口（v2，MVP 不实现，元数据预留）

**现状**：Parser（`agent/engine/parser.py`）从 TTL 动态读取 prefix，解析完整元数据到 `ObjectType`/`LinkType` dataclass。`EntityRegistry` 同时加载 Action（来自 YAML）。

### 3.2 行业包结构

**retail 行业包**：3 能力域（marketing/organization/finance）+ 1 价值链流程（clearance）。clearance 本体 7 Object（Region/Store/Employee/Product/NearExpiryProduct/Task/LossReport）+ 多 Link + 8 Action（create_clearance_task/submit_for_approval/approve_clearance/accept_task/print_labels/deduct_stock/complete_task/create_loss_report）。

**equipment_repair 行业包**（worked example）：1 能力域（maintenance）+ 1 价值链流程（repair）。4 Object（Equipment/RepairTicket/Technician/Vendor）+ 4 Link + 6 Action。证明多行业包并存 + 零改内核 + 无折扣概念也能跑。

详见 [`industry-packs/retail-clearance.md`](./industry-packs/retail-clearance.md) 与 [`manual/03-worked-example-equipment-repair.md`](./manual/03-worked-example-equipment-repair.md)。

### 3.3 多 workspace 抽象层（内核关键设计）

```
Repository 接口（内核）—— agent/engine/repository.py
    ├── 现状实现：JSONFileRepository
    │     workspace/<pack>/data/*.json
    │     所有读写强制带 workspace_name + org_unit_id 过滤 + fcntl 文件锁 + 原子写
    └── 未来实现（🔜 v2）：PostgresRepository（JSONB）、GraphRepository
```

**决策**：多租户通过 **workspace_name（硬隔离）+ org_unit_id（权限范围）** 双层抽象承载。上层（工具、Agent）经 `Repository` 接口，不直接碰文件。

**TenantContext 传递链路**：
```
前端 CopilotKit co-agent state (selected_store)
    → route.ts 注入 HTTP header (X-Workspace)              [现状: 静态默认 header]
    → 后端 middleware 读取 → contextvar (tenant_ctx)         [✅ 已实现]
    → Repository 所有读写强制带 workspace_name 过滤           [✅ 已实现]
```

`X-Workspace` 优先，回退 `X-Customer-ID`（旧前端兼容）。缺失/伪造处理：后端 middleware 从 header 解析存入 contextvar，默认 `customer_default`。

### 3.4 Action Type 契约强化（吸收 Palantir）

Action Type 用 YAML 定义（`workspace/<pack>/ontology/domains/<域>/actions/*.yaml` 或价值链流程的 `actions_dir`），含完整契约要素。以 clearance 的 `create_clearance_task` 为例：

```yaml
api_name: create_clearance_task
display_name: 创建出清任务
description: 为临期商品建出清单，进入 created 态
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]   # provenance：声明会改哪些 object
locator_field: target_id                         # 定位 target 的参数名（数据驱动）
parameters:
  - { name: discount_percent, type: int, required: true, constraint: "0..100" }
  - { name: planned_quantity, type: int, required: true, constraint: ">0" }
submission_criteria:                # 谁能提交（细粒度门控，独立于粗粒度 RBAC）
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is_not, value: expired, fail_msg: "已过期商品不能出清" }
side_effects:                       # 副作用声明（create_object/update_object/state_transition/...）
  - { type: create_object, object_type: Task, fields: { task_type: clearance, status: created, ... } }
  - { type: update_object, object_type: NearExpiryProduct, match: { id: $target_id }, fields: { status: clearance } }
```

**submission_criteria 是权限的细粒度补充**（独立于粗粒度 RBAC）：粗粒度 RBAC 答"谁能用 execute_action 工具"，submission_criteria 答"给定这个 user 和这组参数，这个 action 实例能不能提交"。

**现状**（`agent/engine/executor.py`）：submission_criteria 做 `roles` 白名单 + 条件（`is`/`is_not` 操作符）。🔜 复杂操作符（matches/includes/gte/value_ref）与嵌套逻辑留 v2。

**`locator_field`（数据驱动）**：声明 Action 用哪个参数定位 target 记录。target 是工作流对象时填其 id 参数（`task_id`/`ticket_id`）；target 是标的物填 `target_id`。

**存储格式决策**：Object/Link Type 用 TTL（声明式 schema），Action Type 用 YAML（行为契约）。Parser 按路径分别加载。

---

## 4. 第3层：Tool / Action / Skill / 计算逻辑

### 4.1 Tool 两类（内核固定 + 行业包聚合）

| 类别 | 定义 | 现状 |
|------|------|------|
| **内核工具（固定）** | 通用原子操作，所有行业包共享 | query_entity / create_entity / update_entity / traverse_relation / execute_action / confirm_action / query_task / update_task（共 8 个） |
| **行业包工具（聚合）** | 行业包专属读工具，从各 `workspace/<pack>/` 的 `tools_module` 聚合 | retail: `query_near_expiry`；equipment_repair: `query_repair_tickets` |

- **内核工具**：`main.tools = 内核8个 + _aggregate_pack_tools()`。读工具走 Repository；`execute_action`/`confirm_action` 走 ActionExecutor + PreviewCache；通用 CRUD 按 §2.3 降级。
- **行业包工具**：复用内核装配函数，但下沉到行业包内，不污染内核。新增行业包的专属工具自动聚合进 agent。

### 4.2 依赖装配（tool/webhook/agent 三路统一）

所有路径经 `bootstrap_workspace()` 装配（`agent/tools/shared.py`、`agent/engine/workspace_bootstrap.py`）：
```
_get_executor / _get_repo / _parser  （agent/tools/shared.py）
        │  从 main.tenant_ctx contextvar 解析 workspace_name
        ▼
bootstrap_workspace(workspace_name)  （agent/engine/workspace_bootstrap.py）
        │  返回缓存的 WorkspaceAgentInstance
        │  = {config, registry, repository, executor}
        ▼
executor.config = 该 workspace source_pack 的（第一个/指定）价值链流程
```

webhook 取 executor 用 `_get_executor(process_name="clearance")`（精确选价值链流程，workspace 由 contextvar 解析）。

### 4.3 Action Type（声明式变更契约）

clearance 拆为 8 个细粒度 Action，走 `execute_action`（Preview）→ HITL 确认 → `confirm_action`（执行）模式。equipment_repair 6 个 Action。每个 Action 含完整 YAML 契约（§3.4）。

### 4.4 Skill 多类型

**所有 Skill 都是 SKILL.md，由 deepagents SkillsMiddleware 加载，给 LLM 读。** Skill 按 frontmatter `type` 分类，从各行业包 `skills/` 聚合。**2 级加载**：workspace skills（高优先级）+ 系统 skills（`agent/skills/`，低优先级，所有 workspace 共享）。

| Skill 类型 | 内容 | 示例 |
|------------|------|------|
| **流程编排类** | 组合多个 Action/Tool 的步骤指南 | `clearance-workflow`、`repair-workflow` |
| **领域知识类** | 本体知识与工具使用策略 | `store-ontology`、`equipment-repair-knowledge` |

### 4.5 计算逻辑：行业包私有 Python 模块

计算逻辑不作为本体元素，是行业包私有 Python 模块，被多个 Tool/Action 复用。**关键**：计算模块属于行业包不属于内核——内核不 import 任何行业包符号。

```python
# workspace/retail/ontology/domains/marketing/rules/discount.py —— retail 行业包私有
def calculate_discount(discount_tier: str) -> int:
    """返回减扣百分比（0-100 int）。读 discount_rules.json。"""
    ...
```

equipment_repair 行业包无折扣概念 → 无计算模块 → 证明内核不依赖折扣计算。

### 4.6 折扣单一事实源

全系统折扣为**减扣百分比（0-100 int）**。单一事实源 = `discount_rules.json`（`discount_percent` 字段，T1=50/T2=30/T3=10）+ `calculate_discount()`（读它）。详见 [`industry-packs/retail-clearance.md`](./industry-packs/retail-clearance.md)。

---

## 5. 第4层：Agent 层

### 现状：单 Agent

继承现有 `create_deep_agent(model, tools, system_prompt, backend, skills)`，deepagents 自带工具循环 + SummarizationMiddleware + SkillsMiddleware。

**系统提示组装**（`_build_combined_prompt` 合并所有行业包本体）：
```
Layer 1: 各行业包本体知识合并（build_system_prompt 动态生成，多行业包共存）
Layer 2: 通用操作流程（Preview→Confirm + 状态机相邻迁移，领域无关）
Layer 3: 可用工具清单（deepagents 自动注入）
```

tenant 上下文经 `X-Workspace` middleware → contextvar 注入（§3.3）。

### 未来：subagent / 多 Agent（🔜 v2，架构预留）

---

## 6. 第5层：前端

**现状**：CopilotKit v1.57 + 9 个手写 renderToolCalls（clearance 专用，已验证可用）。workspace 选择器从硬编码两按钮升级为列表，选中写入 co-agent state。

**已落地**：
- `app/api/copilotkit/route.ts` 注入 `X-Workspace` header（现状：静态默认；🔜 v2：按选中门店动态注入）。
- `app/home-page.tsx` 切换门店按钮写入 co-agent state。

**🔜 v2**：A2UI 标准渲染、多行业包切换 UI、ECharts 图表、权限管理 UI、审计查询 UI。

---

## 7. 模块清单（as-built 路径）

```
store-ontology/
├── agent/                        # 后端（FastAPI + Deep Agents，内核 + 系统工具/skills）
│   ├── main.py                   # 入口（端口 8123）· Agent 创建 · AG-UI 端点 · webhook
│   ├── engine/                   # 核心引擎（内核）
│   │   ├── parser.py             # OntologyParser · EntityRegistry
│   │   ├── repository.py         # JSONFileRepository（workspace 隔离/锁/原子写/edits-only）
│   │   ├── executor.py           # 声明式 ActionExecutor（locator_field 数据驱动）
│   │   ├── action_loader.py      # YAML → ActionDefinition
│   │   ├── state_machine.py      # is_valid_transition（per-process 表）
│   │   ├── preview_cache.py      # preview→confirm 闭环
│   │   ├── pack.py               # IndustryPack / CapabilityDomain / ValueChainProcess + 注册表
│   │   ├── workspace.py          # WorkspaceConfig / OrgUnit + 注册表
│   │   ├── workspace_bootstrap.py # bootstrap_workspace → WorkspaceAgentInstance
│   │   ├── tenant.py             # TenantContext（workspace_name + org_unit_id 双层）
│   │   ├── bootstrap.py          # 自动发现 workspace/*/pack.py
│   │   ├── scheduler.py          # AutomationScheduler（APScheduler 封装）
│   │   ├── schemas.py            # Pydantic 模型
│   │   └── errors.py             # 通用异常
│   ├── tools/                    # 系统原子 Tool（query/crud/action，依赖 shared 装配）
│   └── skills/                   # 系统 Skill（platform-help，所有 workspace 共享）
│
├── workspace/                    # workspace 层（行业包 + 客户实例）
│   ├── customer_default/         # 默认 workspace（config.yaml，source_pack=retail）
│   ├── retail/                   # 零售行业包
│   │   ├── pack.py               # IndustryPack 声明（3 能力域 + clearance 流程）
│   │   ├── ontology/domains/     # 能力域本体（marketing/organization/finance，各 domain.ttl + actions/）
│   │   ├── data/                 # 种子数据
│   │   └── skills/               # 场景单元（clearance_workflow/ + store_ontology/）
│   └── equipment_repair/         # 设备维修行业包（同构）
│
├── frontend/                     # CopilotKit + Next.js
│   └── app/
│       ├── home-page.tsx         # 主内容 · workspace 选择器
│       └── api/copilotkit/route.ts # AG-UI 代理（注入 X-Workspace）
└── docs/design/                  # 本目录（权威设计文档）
```

---

## 8. 数据流

### 8.1 完整请求链路

```
用户输入 "帮我处理临期商品"
    │
    ▼
[第5层] CopilotKit React Client → route.ts（AG-UI 代理，注入 X-Workspace）
    ▼
[第4层] FastAPI middleware（X-Workspace → tenant_ctx contextvar）→ Deep Agent（工具循环）
    │   SkillsMiddleware 加载 clearance-workflow/SKILL.md；LLM 判断需查临期商品
    ▼
[第3层] query_near_expiry() → shared._get_repo(tc)（从 contextvar 解析 workspace）
    │   → bootstrap_workspace(workspace) → repository.read("NearExpiryProduct", tc)
    │   → 关联 Product + calculate_discount → 返回字符串 + <!--COPILOTKIT_DATA-->
    ▼
[第4层] LLM 展示结果 → 用户选择 → LLM 调 execute_action(action_type="create_clearance_task", ...)
    ▼
[第3层] execute_action() → 校验参数 → 存 PreviewCache → 返回 preview_id
    ▼
[第4层] LLM 展示预览 → 用户确认 → LLM 调 confirm_action(preview_id)
    ▼
[第3层] confirm_action() → 校验 preview_id → executor.execute（bypass_action_check=True）
    │   → repository.write("Task", ...) → 返回成功
    ▼
[第5层] renderToolCalls 提取 <!--COPILOTKIT_DATA--> → 渲染成功卡
```

### 8.2 Preview→Confirm 治理链路

```
execute_action(...)              confirm_action(preview_id)
       │                                │
       ▼                                ▼
  校验 Action Type 存在            校验 preview_id 存在
  校验 submission_criteria         查 PreviewCache
  校验参数约束                     检查未过期（5min TTL）
       │                                │
       ▼                                ▼
  存入 PreviewCache                 提取缓存的 preview
  返回 preview_id                  executor.execute（bypass=True）
                                   取走即失效（一次性）
```

---

## 9. 技术选型

| 层 | 技术 | 选型理由 |
|----|------|---------|
| 前端框架 | Next.js 15 | App Router + Server Components，与 CopilotKit 集成成熟 |
| Agent UI | CopilotKit 1.57.4 | Chat UI + Generative UI + Shared State + HITL |
| UI 协议 | AG-UI | CopilotKit 标准 Agent-UI 通信协议，SSE 流式 |
| 后端框架 | FastAPI 0.115+ | 异步、自动 OpenAPI、与 LangGraph 集成简单 |
| Agent 框架 | Deep Agents (cauchyturing) | LangGraph Agent，工具循环 + SkillsMiddleware + SummarizationMiddleware |
| LLM 接入 | langchain-openai ChatOpenAI | OpenAI 兼容协议，可切 MiniMax/Qwen/其他 provider |
| LLM 模型 | MiniMax-M2.7-highspeed | 中文能力强，高性价比，OpenAI 兼容 |
| 本体格式 | Turtle (TTL) | W3C 标准 RDF 格式，声明式 schema 定义 |
| Action 格式 | YAML | 嵌套结构友好，比 TTL 扩展更轻量 |
| 数据存储 | JSON 文件 | MVP 零依赖，未来通过 Repository 抽象迁移到 PostgreSQL+JSONB |

---

## 10. 部署

### 本地开发
```
前端 (Next.js) localhost:3000  ──SSE──→  后端 (FastAPI) localhost:8123
                                              │
                                         MiniMax API（外部 LLM）
```
启动：后端 `cd agent && python main.py`；前端 `cd frontend && npm run dev`。

### 生产部署（v2 预留）
前端 `next build` → Nginx 托管；后端 `uvicorn main:app --workers N`；Nginx 反向代理 `/api/copilotkit` → 后端。数据存储 v2 从 JSON 迁移到 PostgreSQL+JSONB（换 Repository 实现，上层接口不变）。

---

## 附录 A：错误处理（MVP）

### Tool 调用失败
| 场景 | 策略 |
|------|------|
| LLM 调用了不存在的 Action Type | `execute_action` 检查 `action_type` 是否在 `registry.action_types`，不存在返回明确错误 + 可用列表 |
| 参数校验失败 | 返回具体字段+约束的错误信息 |
| 数据不存在 | 查询/操作目标实体不存在返回 `EntityNotFoundError` |

### 数据一致性
| 场景 | 策略 |
|------|------|
| JSON 文件并发写入损坏 | Repository 层 `fcntl.flock` 文件锁（MVP，仅 Unix）；v2 换 PG 后由数据库事务保证 |
| `confirm_action` 执行到一半失败 | 原子写入：临时文件 → `os.rename` 覆盖；写入前 `.bak` 备份 |
| preview 与 confirm 状态不一致 | preview_id 缓存 TTL 机制（过期失效，LLM 必须重新 preview） |

### 数据文件损坏恢复
| 场景 | 策略 |
|------|------|
| JSON 解析失败 | `_load_json` 捕获 `JSONDecodeError`，返回空数据 + 结构化警告日志（不自动恢复，运维从 `.bak` 恢复） |
| 数据文件缺失 | Repository 初始化为空 `[]` + 写日志；首次启动自动创建缺失目录和空文件 |

---

## 附录 B：Palantir 参考关键收获

精读 `docs/palantir-ontology-docs/`（现位于 [`reference/palantir/`](./reference/palantir/)）后的收获：
1. **Action Type 结构 = parameters + rules + submission criteria + side effects**。本设计 MVP 补全 submission_criteria + side_effects。
2. **submission criteria 独立于粗粒度权限**——细粒度门控。本设计采纳。
3. **Function 是独立、有类型、版本化、沙箱化的计算单元**——但这是为"应用"消费者设计。agent 时代消费者是 LLM，计算通过 Tool 暴露，故**不引入 Function 本体元素**（§2.1）。
4. **Ontology Branching / Proposal / Change Management**——git 式本体变更管理，列为 v2。
5. **Object 标识符三件套**（typeId + primaryKey + rid）——MVP 沿用 `id` 字段，v2 可采纳更严谨模型。
6. **"edits only via actions"**——直接采纳为治理强制机制（§2.3）。
