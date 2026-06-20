# OntologyAgent 目标架构设计（三文档合一）

> **状态**：已实现内核多 vertical 架构 + 临期出清 vertical + 设备维修 vertical（worked example）。本文档随实现滚动更新。
> **日期**：2026-06-20（初版）｜最近修订：内核多 vertical 改造合并后
> **输入文档**：`docs/项目设计文档.md`（现有临期 demo 设计）、`docs/Harness-Design.md`（零售深度特化愿景）、`docs/ontologyagent-design-CN.md`（通用平台想法）、`docs/palantir-ontology-docs/`（本体参考）
> **配套文档**：
> - `docs/业务本体建模规范.md` —— 建模规范（怎么做合规）
> - `docs/manual/` —— 新业务场景接入手册（5 份）+ 8 个模板
> - `docs/superpowers/specs/2026-06-20-clearance-ontology-remodel.md` —— 临期出清重建模
> **性质**：本文件是三份设计文档 reconcile 后的**统一目标架构**。它不是重写，而是定方向、消冲突、明边界。标 ✅ 的条款已落地，标 🔜 的列为 v2。

---

## 0. 定位

**OntologyAgent 是一个本体驱动的通用 AI Agent 平台。** 通用内核提供"本体元数据 + CRUD + 多租户抽象 + 权限/审计/观测 + Agent harness + Tool/Skill 体系 + **多 vertical 注册表**"，各行业 vertical（零售、物流、制造……）在本体之上声明式建模即可接入，**新增 vertical 零改内核**。**临期商品零售（clearance）是第一个 vertical；设备维修（equipment_repair）是第二个，作为多 vertical 并存的 worked example。**

### 三文档 reconcile

| 文档 | 性质 | 在本设计中的定位 |
|---|---|---|
| `ontologyagent-design-CN.md` | 通用平台想法 | **目标主线**——五层架构、Palantir 对齐、通用内核 |
| `Harness-Design.md` | 零售深度特化愿景 | **零售 vertical 层 + 内核权限引擎的设计输入**；重型机制（6 层 cascade、快照冻结等）降为 v2 |
| `项目设计文档.md` | 临期 demo 设计 | **第一个 vertical 的已实现部分**——6 Object、9 @tool、Preview→Confirm 流程 |

三者原先最大的张力是定位相反：Harness 是"零售垂直深化"，CN 是"通用平台"。本设计以**通用内核 + vertical 分层**化解——通用部分可复用到任意行业，零售特化部分（组织/品类/DC/权限规则）是内核之上的一个 vertical 层。

### 核心判断（来自讨论）

> **Palantir 本体为前 LLM 时代的"人 + 应用"设计，LLM 时代 agent 的消费者变了，抽象就该变。**

- Palantir 的消费者是**人和应用**：人在 Object Explorer 填表单、在 Workshop 配应用；Action Type = 人执行的事务（表单、审批、submission criteria）；Function = 给 Workshop/派生列/聚合调用的命名计算（应用发现它、绑定它）。
- LLM 时代 agent 的消费者是 **LLM**：它通过 **Tool**（有 schema，可直接 invoke）操作世界，通过 **Skill**（可读的指令文档）理解何时怎么做。

由此得出本设计的取舍：
- **保留** Palantir"描述世界"的部分——Object/Link/Action Type 作为声明式契约。
- **降级/吸收**"执行/计算"的部分——Function 不作为本体元素；计算逻辑是普通 Python 模块，通过 Tool 暴露给 LLM。
- **新增** agent 特有的 Skill——给 LLM 读的流程/策略指令文档。

---

## 1. 四概念分工（核心）

整个设计的地基。混淆大多来自没区分清楚这四者。

| 概念 | 性质 | LLM 关系 | 何时用 |
|---|---|---|---|
| **Object / Link Type** | 本体定义 · 实体与关系 | 经 `build_ontology_prompt` 让 LLM 理解世界结构 | 建模领域实体与关系 |
| **Action Type** | 本体定义 · **声明式变更契约**（参数 + 约束 + submission criteria + 副作用声明） | LLM 不直接执行，经 `execute_action` Tool 调用；**后端自动化也调同一套** | 描述受治理的业务事务 |
| **Tool** | 执行机制 · LLM 直接调用的函数 | LLM 直接 invoke（schema 注入 prompt） | LLM 读数据、调 Action、与外部交互 |
| **Skill** | 执行机制 · 给 LLM 读的指令文档 | LLM 按需 `read_file` | 流程编排、领域知识、策略指南 |
| **计算逻辑** | 普通代码 · 命名 Python 模块 | LLM 不可见（除非包成 Tool） | 跨工具复用的纯计算（折扣、补货点） |
| **Interface Type** | 本体定义 · 抽象类型 | （v2，MVP 不实现，元数据预留） | 跨 Object 共享形状 |

### 1.1 不引入 Function 作为本体元素

Palantir 的 Function 是"注册到本体的、命名的、可被应用发现和绑定的计算单元"——它存在是因为 Palantir 的消费者是**各种应用**（Workshop、Object Explorer、派生列），应用需要一个本体内的命名计算来绑定。

agent 系统的消费者是 **LLM**。LLM 发现和调用计算的机制就是 **Tool**（schema 注入 prompt，LLM 决定调用）。所以计算的"接口"天然就是 Tool，不需要额外的本体 Function 元素。**Tool 就是 LLM 时代的 Function。**

Palantir Function 的可借鉴点（计算应命名、可复用、与 Action 解耦、单一事实源）通过**普通 Python 模块 + 本体数据**就实现了，不需要提升为本体元素。重型特性（SemVer 版本、沙箱、provenance）本就不在 MVP。

### 1.2 Action Type 与 Tool 的关系（六条）

这是最容易混淆的一对。它俩**不在同一层级**。

1. **层级不同**：Action Type 是业务事务维度（clearance、调拨、补货），Tool 是技术接口维度（query、execute_action）。粒度不同。
2. **1:N 映射**：一个 `execute_action` Tool 执行多个 Action Type（现有代码里它执行 clearance/transfer/restock 三个）。新增业务变更只加 Action Type 定义，不加 Tool。
3. **双消费者**：Action Type 被 LLM（经 `execute_action`）和后端自动化（直接调执行器）**共用**，走同一套校验/权限/审计。这是 Tool 做不到的——Tool 是 LLM 专用接口，后端不走 Tool。
4. **边界**：Action Type 只管"受治理的变更"（写）；读操作（query_*）是纯 Tool，无 Action Type。
5. **治理强制**：核心业务实体的写操作锁为 edits-only-via-actions；通用 CRUD 工具 `create_entity`/`update_entity` 降级，仅限非业务数据或管理/开发场景。这保证"出清必须走 clearance Action Type、必须审批"不被通用 CRUD 绕过。
6. **execute_action 是瘦路由器**：读定义 → 校验 submission criteria → 校验参数约束 → 执行声明的变更 → 触发副作用 → 写审计 → 返回。业务逻辑全在 Action Type 定义里，不在 Tool 里。

### 1.3 治理强制（CRUD 降级）✅ 已实现

通用 CRUD 工具 `create_entity`/`update_entity` 能直接改任意实体的任意字段，**绕过所有 Action Type 治理**。生产环境下这是漏洞——LLM 若能用 `update_entity` 直接改 NearExpiryProduct 的状态，"出清必须审批"就形同虚设。

**决策（已落地）**：核心业务实体（NearExpiryProduct、Task、LossReport、Equipment、RepairTicket 等）的写操作锁为 edits-only-via-actions。`create_entity`/`update_entity`/`update_task` 降级为：
- 仅用于**非业务数据**（如辅助配置、临时记录）
- `update_task` 收紧为白名单字段（`notes`/`priority`），其余字段（含 `status`）走 Action

**落地实现**（见 `backend/ontology/repository.py`、`tools.py`）：

1. **标记来源**：Object Type 在 TTL 元数据声明 `edits_only_via_actions "true"`。Parser 解析后存入 `ObjectType.edits_only_via_actions`。
2. **检查粒度**：整实体级别锁定（不做字段级）。命中标记的实体，任何字段的写操作都走 Action。
3. **Repository 层检查**：`Repository.write(...)` 内部查 `edits_only_via_actions`，为 `True` 时拒绝写并抛 `ActionRequiredError`。
4. **Action 执行器绕过**：`Repository.write(..., bypass_action_check=True)`，**仅** `ActionExecutor` 内部传入。通用 CRUD 工具不传，自然被拦截。
5. **CRUD 工具降级**：`create_entity`/`update_entity` 不传 bypass → 受治理实体被拒；`update_task` 白名单校验后 bypass（仅 notes/priority）。

### 1.4 生产场景验证：临期出清跨天流程

用"定时作业调用 LLM 生成打折出清任务"这个生产场景，把四概念 + 长流程承载一起压测。流程拆解为 13+ 步：

| # | 步骤 | 驱动者 | 归属 |
|---|---|---|---|
| 1 | 定时作业唤醒 agent | 调度器 | Agent 入口（headless 调用） |
| 2 | 取库存商品 + 生产日期 | LLM | Tool（query_inventory，读） |
| 3 | 取临期定义 | LLM | Tool（读本体数据 discount_rules） |
| 4 | 判断哪些商品多少数量要出清 | LLM 推理 | Skill 指导下的判断 |
| 5 | 计算折扣 | 代码 | 普通函数 `calculate_discount()`，被 Tool 内部调用 |
| 6 | 定执行人/起止时间 | LLM 推理 | Skill 指导 |
| 7 | 创建出清任务单 | LLM | Action Type: create_clearance_task（经 execute_action） |
| 8 | 发起审批 | LLM | Action Type: submit_for_approval（状态迁移） |
| 9 | 审批完成 | 系统 | 后端自动化（审批回调，无 LLM） |
| 10 | 接受任务 | 人/系统 | Action Type: accept_task |
| 11 | 打折扣签 + 陈列 | 人 | Action Type: print_labels（对接打印机） |
| 12 | POS 扫码扣减库存 | 系统 | 后端自动化（POS 事件）→ Action Type: deduct_stock |
| 13 | 全部售完标记完成 | 系统 | 后端自动化（盘点）→ Action Type: complete_task |
| 14 | 到期未售完 → 报损 | 系统→LLM | 后端自动化（定时器）→ 唤醒 LLM（报损 Skill）→ Action Type: create_loss_report |

**结论**：
- **tool + skill 完全覆盖所有"LLM 在环"段**（步骤 1-8、14 的 LLM 部分）。Skill（`clearance-workflow` / `loss-report-workflow`）指导 LLM 用 Tool 读数据、推理、经 `execute_action` 调 Action Type。
- **场景里有一半步骤没有 LLM 在环**（9 审批回调、12 POS 扣库存、13 盘点完成）——这些是后端自动化响应事件/定时器，同样去调 Action Type。
- **Action Type 是 LLM 和系统共用的"变更契约"**——这正是 Action Type 不可替代、Tool 无法取代它的原因。

### 1.5 长流程承载：工作流对象 + 状态机 + 自动化（不引入 BPM 引擎）✅ 状态机已实现（per-vertical）

"生成任务是一个跨数天的流程"这个认知，不靠单一 Skill 装下。它**涌现**自三样东西：

- **工作流 Object + 状态机**：clearance 用 `Task`（`created → pending_approval → approved → accepted → in_progress → completed`，或 `→ scrapped`）；equipment_repair 用 `RepairTicket`（`reported → diagnosed → assigned → repairing → resolved`，旁路 `→ cancelled`）。状态跨天持久化。
- **Action Type**：每个状态迁移是一个 Action（submit/accept/complete/loss_report；diagnose/assign/start/complete/cancel）。
- **后端自动化**：事件处理（POS）、定时器（到期检查）、审批回调——这些调 Action Type，不需要 LLM。

**Skill 只负责"LLM 段"的编排**（生成任务的对话、报损的对话），不负责跨天的整体流程。

**决策（已落地）**：用工作流对象状态机 + 后端自动化承载长流程，不引入独立 Workflow/BPM 引擎（那是 v2 可选增强）。

**状态机实现（per-vertical，数据驱动）**：状态迁移表不再全局硬编码，而是每个 vertical 自带一份，在 `VerticalConfig.state_transitions` 注册。`is_valid_transition(from, to, transitions, terminals)` 接受 per-vertical 表。executor 的 `state_transition` 副作用从当前 vertical 的 config 取表校验。这保证 clearance 的 Task 状态机和 equipment_repair 的 RepairTicket 状态机互不干扰。

```python
# clearance vertical（verticals/clearance/config.py 注册）
TASK_TRANSITIONS = {
    "created": ["pending_approval", "scrapped"],
    "pending_approval": ["approved", "rejected", "scrapped"],
    "approved": ["accepted", "scrapped"],
    "accepted": ["in_progress", "scrapped"],
    "in_progress": ["completed", "scrapped"],
}
# equipment_repair vertical 用 REPAIR_TICKET_TRANSITIONS（见 docs/manual/04）
```

**Action 定位键（locator_field）**：每个 Action 在 YAML 里声明 `locator_field`（如 `task_id` / `ticket_id`），executor 据此定位 target 记录。这是数据驱动的，取代旧的 `target_type == "Task"` 硬编码——使任意工作流对象（不止 Task）都能正确定位。

**后端自动化设计**（🔜 部分留 v2）：

| 组件 | 现状/方案 | 说明 |
|------|---------|------|
| **状态机** | ✅ 已实现：per-vertical `state_transitions` + executor 校验 | 数据驱动，多 vertical 并存 |
| **定时器** | 🔜 `APScheduler` | 轻量级，嵌入 FastAPI 进程。MVP 未接入，留实现 |
| **事件源** | 🔜 不接入外部事件 | POS 扣库存、审批回调等外部事件接入留 v2；MVP 通过 Action 直接调 |
| **LLM 唤醒** | 🔜 定时器回调中调 `agent.ainvoke()` | 后端自动化需要 LLM 段时（如报损推理），通过 headless 调用触发 |

### 1.6 Preview→Confirm 治理闭环 ✅ 已实现

`execute_action`（preview）和 `confirm_action`（执行）是两个独立 Tool。仅靠 Skill 指导 LLM "先 preview 再 confirm" 没有技术强制——LLM 或恶意调用者可直接调 `confirm_action` 绕过 preview。

**已落地方案：preview 记录 + confirm 校验**（见 `backend/ontology/preview_cache.py`、`tools.py`）：

1. **preview 记录**：`execute_action` 将 preview（action_type + params + actor + tenant）存入进程内 `PreviewCache`，返回 `preview_id`。
2. **confirm 校验**：`confirm_action(preview_id)` 查缓存，存在且未过期（TTL=300s）才执行；取走即失效（一次性）；不存在/过期则拒绝。
3. **存储**：进程内 `dict` + TTL。🔜 v2 可升级 Redis / DB 持久化。

```
execute_action(...) → 存 preview → 返回 preview_id + 预览
confirm_action(preview_id=...) → 查缓存 → 有效 → 执行变更（取走即失效）
                            → 无效/过期 → 拒绝（"请先 execute_action 获取预览"）
```

**与 Skill 的关系**：Skill 指导 LLM "先 preview 再 confirm"（行为层），preview_id 校验提供技术兜底（治理层）。两层互补——Skill 减少 LLM 触发拒绝的概率，preview_id 校验保证即使 Skill 未生效也不会绕过。

---

## 2. 五层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│  第5层：用户交互入口                                                      │
│  现状：CopilotKit v1.57（9 个 renderToolCalls，clearance 专用）           │
│  未来（v2）：A2UI 标准渲染、多 vertical 切换 UI、定时自动化作业 UI          │
├─────────────────────────────────────────────────────────────────────────┤
│  第4层：Agent 层                                                          │
│  现状：单 Agent（deepagents create_deep_agent + SkillsMiddleware）         │
│  系统提示 = 各 vertical 本体合并（_build_combined_prompt）                 │
│  未来（v2）：subagent / 多 Agent 协作（Planner/Tool/Reasoner/Reporter）   │
├─────────────────────────────────────────────────────────────────────────┤
│  第3层：Tools / Action Types / Skills / 计算逻辑                          │
│  内核工具（固定）：query_entity/create/update/traverse/execute_action/    │
│                   confirm_action/query_task/update_task                   │
│  vertical 工具（聚合）：各 vertical 的 TOOLS（如 query_near_expiry、       │
│                         query_repair_tickets）                             │
│  Action Type：声明式 YAML 契约（参数+submission_criteria+副作用+locator）  │
│  Skill：SKILL.md，从各 vertical skills/ 聚合加载                          │
│  计算逻辑：vertical 私有 Python 模块（如 business/discount）              │
├─────────────────────────────────────────────────────────────────────────┤
│  第2层：Ontology 层（通用内核 + 多 vertical 注册表）                       │
│  通用内核：VerticalConfig + 注册表 + bootstrap 自动发现 + Repository      │
│            （多租户/锁/原子写/edits-only）+ 声明式 ActionExecutor          │
│  vertical（声明式接入，零改内核）：                                         │
│    clearance: Task 工作流（8 Action）                                       │
│    equipment_repair: RepairTicket 工作流（6 Action，worked example）       │
│  未来（v2）：组织5级 / 品类5级 / DC / 职能域（零售 vertical 深化）          │
├─────────────────────────────────────────────────────────────────────────┤
│  第1层：LLM + 存储                                                        │
│  LLM：MiniMax-M2.7-highspeed（OpenAI 兼容，现有一套，未来多 provider）     │
│  存储：JSON 文件（现状）via Repository 抽象 → 🔜 PostgreSQL+JSONB（v2）     │
└─────────────────────────────────────────────────────────────────────────┘
```

五层骨架来自 CN 文档。第2层经多 vertical 改造后从"通用内核+一个零售 vertical"升级为"通用内核 + vertical 注册表（声明式接入）"。第3层 Tool/Skill/计算逻辑明确分为内核固定 + vertical 聚合。详见附录 D（多 vertical 内核架构）与 `docs/manual/`（接入手册）。

---

## 3. 第2层：Ontology 层（通用内核 + vertical 分层）

### 3.1 本体元数据模型（内核，对齐 Palantir）

每个本体资源携带完整元数据：

| 元数据 | 说明 |
|---|---|
| `api_name` | 编程引用名（如 `near_expiry_product`） |
| `display_name` | UI 显示名（如"临期商品"） |
| `description` | 业务含义 |
| `status` | `active` / `experimental` / `deprecated` |
| `visibility` | `prominent` / `normal` / `hidden` |
| `tenant_id` | 多租户归属 |
| `edits_only_via_actions` | 是否锁定为只能通过 Action 修改（治理强制，见 1.3） |

**资源类型**：
- **Object Type**：业务实体类型定义（现有 6 个 + 未来扩展）
- **Link Type**：两 Object Type 间关系（现有 7 个），支持 cardinality（1:1 / 1:N / N:N）
- **Action Type**：声明式变更契约（现有 3 个），含 parameters + submission_criteria + side_effects
- **Interface Type**：抽象接口（v2，MVP 不实现，元数据预留）

**现状（已实现）**：Parser（`backend/ontology/parser.py`）从 TTL 动态读取 prefix（不再硬编码 `store:`），解析上述完整元数据到 `ObjectType`/`LinkType` dataclass。`EntityRegistry` 同时加载 Action（来自 YAML）。`models.LinkTypes` 常量不一致的 bug 已修（删除该常量类，TTL 为准）。

### 3.2 vertical 本体

**clearance vertical（已重建模，见 `clearance-ontology-remodel.md`）**：7 Object（Region/Store/Employee/Product/NearExpiryProduct/Task/**LossReport**）+ 10 Link + 8 Action（原单体 clearance 拆为 create_clearance_task/submit_for_approval/approve_clearance/accept_task/print_labels/deduct_stock/complete_task/create_loss_report）。

**equipment_repair vertical（worked example，见 `docs/manual/04`）**：4 Object（Equipment/RepairTicket/Technician/Vendor）+ 4 Link + 6 Action。证明多 vertical 并存 + 零改内核 + 无折扣概念也能跑。

**Harness-Design 的零售全量本体列为后续 vertical 扩展（🔜 v2）**：
- 组织 5 级（Brand/OrgGroup/Channel/Region/Store）→ 收敛为现有 Region/Store，扩展留 v2
- 品类 5 级 → 现用 Product 的扁平 `category` 字符串，5 级树留 v2
- DC 配送中心 → 现不实现，留 v2
- 职能域 Domain → 现不实现，留 v2

### 3.3 多租户抽象层（内核关键设计）✅ 已实现

```
Repository 接口（内核）—— backend/ontology/repository.py
    ├── 现状实现：JSONFileRepository
    │     data/<vertical>/<entity_type>.json（vertical 独立子目录）
    │     所有读写强制带 tenant_id 过滤 + fcntl 文件锁 + 原子写
    └── 未来实现（🔜 v2）：PostgresRepository（JSONB）、GraphRepository
```

**决策（已落地）**：多租户通过 `tenant_id` 抽象承载，存储用 JSON 文件、未来扩展数据库。上层（工具、Agent）经 `Repository` 接口，不直接碰文件。

**tenant_id 传递链路**：

```
前端 CopilotKit co-agent state (selected_store)
    → route.ts 注入 HTTP header (X-Tenant-ID)         [现状: 静态默认 header]
    → 后端 middleware 读取 → contextvar (tenant_ctx)    [✅ 已实现]
    → Repository 所有读写强制带 tenant_id 过滤          [✅ 已实现]
```

- **现状**：route.ts 因 CopilotKit `LangGraphHttpAgent` 仅支持构造时静态 header，MVP 注入静态默认 `X-Tenant-ID`。🔜 v2 用自定义 fetch wrapper 实现按门店动态注入。
- **缺失/伪造处理**：后端 middleware 从 header 解析 tenant_id 存入 contextvar，默认 `tenant_default`。
- **数据隔离**：Repository 读写按 `tenant_id` 字段过滤（list comprehension）。

### 3.4 Action Type 契约强化（吸收 Palantir）✅ 已实现

Action Type 用 YAML 定义（`ontology/actions/*.yaml` 或 `verticals/<name>/ontology/actions/*.yaml`），含完整契约要素。以 clearance 的 `create_clearance_task` 为例：

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

**现状实现**（`backend/ontology/executor.py`）：submission_criteria 做 `roles` 白名单 + 条件（`is`/`is_not` 操作符）。🔜 复杂操作符（matches/includes/gte/value_ref）与嵌套逻辑留 v2。

**`locator_field`（新增，数据驱动）**：声明 Action 用哪个参数定位 target 记录。target 是工作流对象时填其 id 参数（`task_id`/`ticket_id`）；target 是标的物填 `target_id`。executor 据此定位，取代旧的 `target_type == "Task"` 硬编码。

**存储格式决策**：Object/Link Type 用 TTL（声明式 schema），Action Type 用 YAML（行为契约）。Parser 按路径分别加载。

---

## 4. 第3层：Tool / Action / Skill / 计算逻辑

### 4.1 Tool 两类（内核固定 + vertical 聚合）✅ 已实现

| 类别 | 定义 | 现状 |
|---|---|---|
| **内核工具（固定）** | 通用原子操作，所有 vertical 共享 | query_entity / create_entity / update_entity / traverse_relation / execute_action / confirm_action / query_task / update_task（共 8 个） |
| **vertical 工具（聚合）** | vertical 专属读工具，从各 `verticals/<name>/tools.py` 的 `TOOLS` 聚合 | clearance: `query_near_expiry`；equipment_repair: `query_repair_tickets` |
| **OS 原子工具** | 操作系统级底层操作 | 🔜 预留分类，未实现（http/db/file） |

- **内核工具**：`main.tools = 内核8个 + _aggregate_vertical_tools()`。读工具走 Repository；`execute_action`/`confirm_action` 走 ActionExecutor + PreviewCache；通用 CRUD（`create_entity`/`update_entity`）按 1.3 降级。
- **vertical 工具**：复用内核装配函数（`_get_repo`），但下沉到 `verticals/<name>/tools.py`，不污染内核。新增 vertical 的专属工具自动聚合进 agent。

### 4.2 Action Type（声明式变更契约）✅ 已实现

clearance 拆为 8 个细粒度 Action（见 3.2），走 `execute_action`（Preview）→ HITL 确认 → `confirm_action`（执行）模式。equipment_repair 6 个 Action（worked example）。每个 Action 含完整 YAML 契约（§3.4）。

🔜 transfer/restock 两个 Action 的契约补全留后续（当前 vertical 聚焦 clearance + equipment_repair）。

### 4.3 Skill 多类型 ✅ 已实现

**所有 Skill 都是 SKILL.md，由 deepagents SkillsMiddleware 加载，给 LLM 读。** Skill 按 frontmatter `type` 分类（流程编排类 / 领域知识类），从各 vertical `skills/` 聚合（`_aggregate_skill_paths` 只收含 SKILL.md 的目录）。

| Skill 类型 | 内容 | 示例 |
|---|---|---|
| **流程编排类** | 组合多个 Action/Tool 的步骤指南 | `clearance-workflow`、`repair-workflow` |
| **领域知识类** | 本体知识与工具使用策略 | `store-ontology`、`equipment-repair-knowledge` |

**已修的坑**：`store-ontology/SKILL.md` 重写对齐实际本体与工具（不再引用幽灵实体）；双层目录 `store-ontology/store-ontology/` 修复为单层。

### 4.4 计算逻辑：vertical 私有 Python 模块 ✅ 已实现

计算逻辑不作为本体元素，是 vertical 私有 Python 模块，被多个 Tool/Action 复用。**关键**：计算模块属于 vertical 不属于内核——内核不 import 任何 vertical 符号。

```python
# business/discount.py —— clearance vertical 私有，单一事实源
def calculate_discount(discount_tier: str) -> int:
    """返回减扣百分比（0-100 int）。读 discount_rules.json。"""
    rules = get_discount_source()
    return next(r["discount_percent"] for r in rules if r["tier"] == discount_tier)

# verticals/clearance/tools.py —— vertical 工具调用它
@tool
def query_near_expiry(...):
    ... "discount_percent": calculate_discount(tier) ...   # 复用
```

equipment_repair vertical 无折扣概念 → 无计算模块 → 证明内核不依赖 `business/discount`。

### 4.5 折扣单一事实源 ✅ 已实现

**已统一**：全系统折扣为**减扣百分比（0-100 int）**。单一事实源 = `discount_rules.json`（`discount_percent` 字段，值 T1=50/T2=30/T3=10）+ `calculate_discount()`（读它）。

**已删除的重复定义**：`tools.py` 的硬编码 `tier_discount`、SKILL.md 的折扣数值、`query_task` 的 `float→int` 转换 hack。SKILL.md 改为引用 `discount_rules.json`。详见 `clearance-ontology-remodel.md` §6。

---

## 5. 第4层：Agent 层

### 现状：单 Agent ✅ 已实现

继承现有 `create_deep_agent(model, tools, system_prompt, backend, skills)`，deepagents 自带工具循环 + SummarizationMiddleware + SkillsMiddleware。

**系统提示组装**（已实现，`_build_combined_prompt` 合并所有 vertical 本体）：

```
Layer 1: 各 vertical 本体知识合并（build_system_prompt 动态生成，多 vertical 共存）
         —— 每个 vertical 的实体/关系/Action 列表 + 该 vertical 的 intro
Layer 2: 通用操作流程（Preview→Confirm + 状态机相邻迁移，领域无关）
Layer 3: 可用工具清单（deepagents 自动注入）
```

**已落地**：`main.py` 的 `store_context` 去硬编码（不再写"出清"步骤），改为领域无关的 Preview→Confirm 说明。tenant 上下文经 `X-Tenant-ID` middleware → contextvar 注入（详见 §3.3）。tools/skills 从 vertical 注册表聚合（详见附录 D）。

### 未来：subagent / 多 Agent（🔜 v2，架构预留）

CN 文档的 Planner/Tool/Reasoner/Reporter 四角色协作列为 v2。deepagents 本身支持 subagent，架构上预留扩展点。

---

## 6. 权限 / 审计 / 观测

> **现状说明**：本节大部分机制🔜尚未实现。当前已落地的只有 Action 级 submission_criteria（角色白名单 + 条件，见 §3.4）和 Repository 的 tenant_id 隔离（§3.3）。独立的 RBAC 引擎、审计日志、Metrics 留后续迭代。

### 6.1 权限引擎 🔜 大部分未实现（仅 submission_criteria 已落地）

**已落地**：Action 的 `submission_criteria`（roles 白名单 + is/is_not 条件）在 executor 执行前校验；Repository 的 tenant_id 过滤实现租户隔离。

**🔜 目标设计**（未实现）：
```
PermissionEvaluator 接口（内核）
    └── RbacEvaluator 实现：
        - role → 允许的 tool 白名单
        - tenant_id 隔离（所有查询带 tenant 过滤）
        - resource_type + action 检查
        - submission_criteria 操作符全集（gte/matches/includes/value_ref）

每个工具调用前：permission_gate.check(tool, context)
失败 → PermissionDenied + 写审计（rejected）→ 不执行
```

**Harness-Design 的重型机制列为 v2**（不实现，接口预留）：
- 6 种 PermissionMode / 6 层 cascade
- Domain × OrgScope × CategoryScope 三维 scope
- DeepImmutable 快照冻结 + HMAC 校验
- 26 个生命周期钩子

### 6.2 审计日志 🔜 未实现

```yaml
AuditLogEntry（目标设计，Harness §4 的子集）:
  audit_id: AUD-{date}-{seq}
  timestamp: ISO8601
  tenant_id: <tenant>
  actor: { user_id, role }
  action: { tool_name, params }
  rule_matched: { rule_id } | null
  outcome: SUCCESS | REJECTED

存储: data/<vertical>/audit/{date}.jsonl（append-only）
触发: 每个工具调用（成功/失败）写一条
```

### 6.3 可观测性 🔜 大部分未实现

现状仅有 `/health` 端点。🔜 目标：结构化 JSON 日志（Harness §5.4 的 AppLog 格式）；Metrics（品类×组织双维度）、OpenTelemetry Trace、告警列为 v2。

---

## 7. 第5层：前端

**现状**：CopilotKit v1.57 + 9 个手写 renderToolCalls（clearance 专用，已验证可用）。tenant 选择器从硬编码两按钮升级为 STORES 列表，选中写入 co-agent state。

**已落地（配合多租户）**：
- `app/api/copilotkit/route.ts` 注入 `X-Tenant-ID` header（现状：静态默认；🔜 v2：按选中门店动态注入，因 CopilotKit `LangGraphHttpAgent` 仅支持构造时静态 header）。
- `app/home-page.tsx` 切换门店按钮从列表加载，写入 co-agent state。

**🔜 v2**：A2UI 标准渲染（node_modules 已有但未启用）、多 vertical 切换 UI、ECharts 图表、权限管理 UI、审计查询 UI。

---

## 8. 演进路线

| 阶段 | 目标 | 状态 |
|---|---|---|
| **已实现（内核 + clearance + equipment_repair）** | 内核多 vertical 架构（VerticalConfig + 注册表 + bootstrap 自动发现）+ Repository 多租户/锁/原子写/edits-only + 声明式 ActionExecutor（locator_field 数据驱动）+ per-vertical 状态机 + preview→confirm 闭环 + 折扣单一事实源 + Action YAML 契约 + CRUD 降级 + clearance 重建模（8 Action）+ equipment_repair worked example（6 Action）+ tenant 上下文注入 + 接入手册/模板 | ✅ 60/60 测试通过 |
| **🔜 v2-存储** | JSON → PostgreSQL+JSONB（换 Repository 实现） | 未开始 |
| **🔜 v2-权限** | 简化 submission_criteria → 完整 RBAC×ABAC（三维 scope、6 层 cascade、快照冻结、操作符全集 gte/matches/value_ref） | 接口预留 |
| **🔜 v2-本体** | 零售 vertical 深化（组织5级 / 品类5级 / DC / 职能域）；transfer/restock 契约补全 | 未开始 |
| **🔜 v2-自动化** | 定时器（APScheduler）+ 外部事件（POS/审批回调）+ LLM headless 唤醒 | 未开始 |
| **🔜 v2-Agent** | 单 Agent → subagent / 多 Agent 协作 | 架构预留 |
| **🔜 v2-UI** | 手写 renderToolCalls → A2UI 标准 + 多 vertical 切换 + 图表 + 审计 UI | 未开始 |
| **🔜 v2-长流程** | 后端自动化 → 可选 BPM/Workflow 引擎增强 | 未开始 |
| **🔜 v2-tenant动态** | route.ts 静态 header → 自定义 fetch wrapper 按门店动态注入 | 未开始 |

**新增 vertical 的接入**：纯增量，零改内核。见 `docs/manual/02-接入手册.md`（Phase A-F）。

---

## 附录 A：Bug 清单（全部已修 ✅）

> 本附录原为"MVP 待修 bug 清单"。临期出清 MVP 重构 + 内核多 vertical 改造后，下列全部修复。保留作变更追溯。

| Bug | 原现状 | 修法（已落地） |
|---|---|---|
| **三处折扣矛盾** | tools.py 减扣% / discount_rules.json 乘数 / SKILL.md 减扣% off —— 数值与语义维度均不一致 | ✅ 单一事实源 + 统一减扣百分比 int（见 4.5） |
| **LinkTypes 幽灵常量** | schemas.py 的 LinkTypes 与 TTL 不符 | ✅ 删除 LinkTypes 类，TTL 为准 |
| **tasks.json 旧 schema** | 种子用 action_type/near_expiry_product_id/input_params | ✅ 迁移到新 schema（task_type/target_id/params_json） |
| **SKILL.md 引用幽灵实体** | store-ontology/SKILL.md 引用 DiscountRule/get_near_expiry_products/belongs_to | ✅ 重写对齐实际本体与工具 |
| **CRUD 绕过治理** | update_entity 可改任意实体 | ✅ edits-only-via-actions 标记 + Repository 检查 + update_task 白名单（见 1.3） |
| **JSON 写无锁** | _save_json 无并发控制 | ✅ Repository 层 fcntl 文件锁 + 原子写 |
| **硬编码 store_001** | main.py 门店 ID 硬编码进 prompt | ✅ tenant 上下文动态注入（contextvar） |
| **route.ts 不带 tenant** | 前端直接转发无 header | ✅ 注入静态 X-Tenant-ID（🔜 v2 动态） |
| **clearance_tasks.json 残留** | 旧 schema 副本，无引用 | ✅ 删除 |
| **manages link 方向反转** | manages: Employee→Store via manager_id（manager_id 在 Store 上） | ✅ 修正为 Store→Employee |
| **Action 粒度过粗** | 单体 clearance 揉建单/提交/执行 | ✅ 拆为 8 个细粒度 Action |
| **Task 状态无约束** | update_task 可任意改 status | ✅ per-vertical 状态机 + 合法迁移校验 |
| **缺元数据字段** | Object/Action 无 status/visibility/edits_only | ✅ TTL 元数据 + parser 解析 |

---

## 附录 D：多 vertical 内核架构（新增）

> 内核多 vertical 改造的完整记录见 `docs/manual/01-内核多vertical改造.md`，接入手册见 `docs/manual/02-接入手册.md`。本附录是架构层面的速览。

### D.1 内核契约（scenario-agnostic）

内核只认三个东西，不认任何领域名词：
1. **`VerticalConfig`**（`backend/ontology/vertical.py`）：vertical 自报家门（路径 + 工作流 + 工具模块）。
2. **注册表**：`backend/verticals/*/config.py` import 时 `register_vertical`，`bootstrap()` 统一发现（排序保证默认 vertical 确定）。
3. **声明式契约**：TTL（Object/Link）+ YAML（Action，含 `locator_field`）+ JSON（种子）。

### D.2 vertical 侧契约

- 必须有 `config.py`，构造 `VerticalConfig` 并 `register_vertical`。
- 工作流 vertical 填 `workflow_object_type` / `workflow_object_id_field` / `state_transitions` / `terminal_states`。
- 专属工具放 `verticals/<name>/tools.py`，导出 `TOOLS` 列表。
- TTL prefix 自洽（动态读取）。
- 种子数据放 `data/<vertical_name>/*.json`（独立子目录）。

### D.3 内核泄漏点（已全部修复）

原内核有 8 处泄漏耦合到 clearance。修复一览：

| 泄漏点 | 修复 |
|---|---|
| L1 TTL/actions/data 路径硬编码 | `get_ontology_parser(vertical)` 参数化 |
| L2 TTL prefix 硬编码 `store:` | 动态读 `@prefix` 行 |
| L3 系统提示硬编码 clearance 文案 | `build_system_prompt(intro)` 参数化 |
| L4 executor `target_type == "Task"` | `locator_field` 数据驱动 |
| L5 状态机全局唯一 | per-vertical `state_transitions` |
| L6 内核 import clearance 折扣 | `query_near_expiry` 下沉到 vertical 包 |
| L7 tools/skills 硬编码 | 注册表聚合 |
| L8 store_context 出清文案 | 领域无关的 Preview→Confirm 说明 |

### D.4 接入新 vertical 的工作量

**纯增量，零改内核**：建 `backend/verticals/<name>/`（config + ontology + 可选 state_machine/tools/skills）+ `data/<name>/` 种子。重启即生效。详见 `docs/manual/02-接入手册.md` Phase A-F + 8 个模板。

---

## 附录 B：Palantir 参考关键收获

精读 `docs/palantir-ontology-docs/` 后，对本设计有参考价值的收获：

1. **Action Type 结构 = parameters + rules + submission criteria + side effects**。比现有代码的扁平参数丰富。本设计 MVP 补全 submission_criteria + side_effects 声明（rules 的声明式编辑规则集留 v2）。
2. **submission criteria 独立于粗粒度权限**——是"给定 user+parameter 能否提交"的细粒度门控。本设计采纳此分层。
3. **Function 是独立、有类型、版本化、沙箱化的计算单元**——但这是为"应用"消费者设计的。agent 时代消费者是 LLM，计算通过 Tool 暴露，故本设计**不引入 Function 本体元素**（见 1.1）。
4. **Ontology Branching / Proposal / Change Management**——git 式本体变更管理。本设计列为 v2（变更管理），MVP 不做。
5. **Object 标识符三件套**：`typeId`（必有）+ `primaryKey {propertyId: value}`（必有）+ `rid`（持久化后才有）。本设计 MVP 沿用现有 `id` 字段，未来 v2 可采纳更严谨的标识模型。
6. **Alias 层**（custom alias 配置 + model alias 模型引用）——运行时解析的间接层。对本设计的多 provider LLM 抽象有参考价值，列为 v2。
7. **Function-backed action**——复杂变更委托给 Function。本设计无 Function 元素，对应场景由"普通计算模块 + Action 副作用声明"覆盖。
8. **"edits only via actions"**——Object Type 可锁定为只能通过 Action 修改。本设计直接采纳为治理强制机制（见 1.3）。

---

## 附录 C：错误处理策略（MVP）

### C.1 Tool 调用失败

| 场景 | MVP 策略 |
|------|---------|
| LLM 调用了不存在的 Action Type | `execute_action` 开头检查 `action_type` 是否存在于 `registry.action_types`，不存在则返回明确错误信息（"Action Type 'xxx' 不存在，可用：clearance/transfer/restock"），LLM 根据错误信息自行修正 |
| 参数校验失败 | Action 定义中的 `parameters` 约束检查失败时，返回具体字段+约束的错误信息（"参数 discount 必须 ≤ 100，当前值 150"） |
| 数据不存在 | 查询/操作目标实体不存在时返回 `EntityNotFoundError`，LLM 可选择创建或告知用户 |

### C.2 数据一致性

| 场景 | MVP 策略 |
|------|---------|
| JSON 文件并发写入损坏 | Repository 层使用 `fcntl.flock` 文件锁（MVP，仅 Unix）；v2 换 PG 后由数据库事务保证 |
| `confirm_action` 执行到一半失败 | 使用**原子写入**：先写临时文件 → `os.rename` 覆盖原文件（rename 在同一文件系统上是原子操作）。写入前将原文件备份为 `.bak`，失败时可手动恢复 |
| preview 与 confirm 状态不一致 | §1.6 的 preview_id 缓存 TTL 机制保证——过期 preview 自动失效，LLM 必须重新 preview |

### C.3 数据文件损坏恢复

| 场景 | MVP 策略 |
|------|---------|
| JSON 文件解析失败 | `_load_json` 捕获 `json.JSONDecodeError`，返回空数据 + 写结构化警告日志（含文件路径、错误位置）。不自动恢复，由运维手动从 `.bak` 恢复 |
| 数据文件缺失 | Repository 检查文件是否存在，不存在则初始化为空 `[]` + 写日志。首次启动时自动创建缺失的数据目录和空文件 |
