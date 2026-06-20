# OntologyAgent 目标架构设计（三文档合一）

> **状态**：已与用户逐项确认，待 review
> **日期**：2026-06-20
> **输入文档**：`docs/项目设计文档.md`（现有临期 demo 设计）、`docs/Harness-Design.md`（零售深度特化愿景）、`docs/ontologyagent-design-CN.md`（通用平台想法）、`docs/palantir-ontology-docs/`（本体参考）
> **性质**：本文件是上面三份设计文档 reconcile 后的**统一目标架构**。它不是重写，而是定方向、消冲突、明边界。

---

## 0. 定位

**OntologyAgent 是一个本体驱动的通用 AI Agent 平台。** 通用内核提供"本体元数据 + CRUD + 多租户抽象 + 权限/审计/观测 + Agent harness + Tool/Skill 体系"，各行业 vertical（零售、物流、制造……）在本体之上构建领域实体与工作流。**临期商品零售是第一个 vertical，作为内核能力的验证场景与首个落地 demo。**

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

### 1.3 治理强制（CRUD 降级）

现有代码有通用 CRUD 工具 `create_entity`/`update_entity`，它们能直接改任意实体的任意字段，**绕过所有 Action Type 治理**。生产环境下这是漏洞——LLM 若能用 `update_entity` 直接改 NearExpiryProduct 的状态，"出清必须审批"就形同虚设。

**决策**：核心业务实体（NearExpiryProduct、Task 等）的写操作锁为 edits-only-via-actions。`create_entity`/`update_entity` 降级为：
- 仅用于**非业务数据**（如辅助配置、临时记录）
- 仅用于**管理/开发场景**（受 admin 角色限制）
- **不用于受治理实体的写**

MVP 落地方式：

1. **标记来源**：Object Type 在 TTL 元数据中声明 `edits_only_via_actions: true`（如 NearExpiryProduct、Task）。Parser 解析后存入 `ObjectType` dataclass。
2. **检查粒度**：整实体级别锁定（MVP 不做字段级）。命中标记的实体，任何字段的写操作都走 Action。
3. **Repository 层检查**：`Repository.write(entity_type, entity_id, data)` 内部查 `ObjectType.edits_only_via_actions`，为 `True` 时拒绝写操作并抛出 `ActionRequiredError`。
4. **Action 执行器绕过**：Repository 接口提供 `Repository.write(entity_type, entity_id, data, bypass_action_check=True)` 参数，**仅** `confirm_action` 等 Action 执行器内部传入此参数。通用 CRUD 工具（`create_entity`/`update_entity`）不传此参数，自然被拦截。
5. **MVP 重构范围**：`confirm_action` 内部的 `_save_json` 调用需改走 Repository（因此 Repository 抽象是 `edits_only_via_actions` 的前置依赖，两者应同步实现）。

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

### 1.5 长流程承载：Task 状态机 + 自动化（不引入 BPM 引擎）

"生成任务是一个跨数天的流程"这个认知，不靠单一 Skill 装下。它**涌现**自三样东西：

- **Task Object + 状态机**：`created → pending_approval → approved → accepted → in_progress → completed`（或 `→ scrapped`）。状态跨天持久化。
- **Action Type**：每个状态迁移是一个 Action（submit/accept/complete/loss_report）。
- **后端自动化**：事件处理（POS）、定时器（到期检查）、审批回调——这些调 Action Type，不需要 LLM。

**Skill 只负责"LLM 段"的编排**（生成任务的对话、报损的对话），不负责跨天的整体流程。

**决策**：MVP 用 Task 状态机 + 后端自动化承载长流程，不引入独立 Workflow/BPM 引擎（那是 v2 可选增强）。

**MVP 后端自动化设计**：

| 组件 | MVP 方案 | 说明 |
|------|---------|------|
| **定时器** | `APScheduler`（`BackgroundScheduler`） | 轻量级，嵌入 FastAPI 进程，支持 interval/cron 触发。如"每 30 分钟检查到期未售完商品" |
| **状态机** | Action 执行器内的状态转换表（dict mapping） | 不单独建模块。在 `confirm_action` 执行前检查当前状态是否允许目标转换，不允许则拒绝 |
| **事件源** | MVP 不接入外部事件 | POS 扣库存、审批回调等外部事件接入留 v2；MVP 通过定时轮询模拟（如轮询 Task 列表检查超时） |
| **LLM 唤醒** | 定时器回调中调 `agent.ainvoke()` | 后端自动化需要 LLM 段时（如报损推理），通过 headless 调用触发，不走前端 UI |

**Task 状态转换表（MVP）**：

```python
TASK_TRANSITIONS = {
    "created": ["pending_approval", "scrapped"],
    "pending_approval": ["approved", "rejected", "scrapped"],
    "approved": ["accepted", "scrapped"],
    "accepted": ["in_progress", "scrapped"],
    "in_progress": ["completed", "scrapped"],
}
# confirm_action 在执行前查此表，from_status 不在 target_status 对应的 key 中则拒绝
```

### 1.6 Preview→Confirm 治理闭环

当前代码中 `execute_action`（preview）和 `confirm_action`（执行）是两个独立 Tool，仅靠 Skill 指导 LLM "先 preview 再 confirm"。但 **没有任何技术强制机制**——LLM 或恶意调用者可直接调 `confirm_action` 绕过 preview，与"出清必须审批"的治理目标矛盾。

**问题本质**：preview 是一个有状态的操作（生成预览数据），confirm 依赖 preview 的结果。当前两者之间没有状态关联。

**MVP 方案：preview 记录 + confirm 校验**

1. **preview 记录**：`execute_action` 执行后，将 preview 结果存入内存缓存（key = `{action_type}:{target_id}:{timestamp_hash}`），并返回 `preview_id` 给 LLM。
2. **confirm 校验**：`confirm_action` 必须接收 `preview_id` 参数，内部检查缓存中是否存在对应记录且未过期（TTL = 5 分钟）。校验通过后执行变更并删除 preview 记录；校验失败则拒绝执行。
3. **存储**：MVP 用进程内 `dict` + TTL 过期清理。v2 可升级为 Redis / 数据库持久化。

```
execute_action(...) → 生成 preview → 存入缓存 → 返回 preview_id + 预览数据
confirm_action(preview_id=...) → 查缓存 → 存在且未过期 → 执行变更 → 删除缓存
                            → 不存在或已过期 → 拒绝（"请先执行 execute_action 获取预览"）
```

**与 Skill 的关系**：Skill 仍指导 LLM "先 preview 再 confirm"（行为层），preview_id 校验提供技术兜底（治理层）。两层互不冲突——Skill 减少 LLM 触发拒绝的概率，preview_id 校验保证即使 Skill 未生效也不会绕过。

---

## 2. 五层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│  第5层：用户交互入口                                                      │
│  MVP：CopilotKit v1.57（现有 9 个 renderToolCalls）                       │
│  未来（v2）：A2UI 标准渲染、ECharts 图表、定时自动化作业 UI                 │
├─────────────────────────────────────────────────────────────────────────┤
│  第4层：Agent 层                                                          │
│  MVP：单 Agent（deepagents create_deep_agent，工具循环 + SkillsMiddleware）│
│  未来（v2）：subagent / 多 Agent 协作（Planner/Tool/Reasoner/Reporter）   │
├─────────────────────────────────────────────────────────────────────────┤
│  第3层：Tools / Action Types / Skills / 计算逻辑                          │
│  Tool（两类）：OS 原子（http/db/file） + 业务原子（entity_*/execute_action）│
│  Action Type：声明式变更契约（参数 + submission criteria + 副作用）        │
│  Skill（多类型，SKILL.md，deepagents 加载）：流程编排类 / 领域知识类       │
│  计算逻辑：普通 Python 模块（如 calculate_discount）                      │
├─────────────────────────────────────────────────────────────────────────┤
│  第2层：Ontology 层（通用内核 + vertical 分层）                            │
│  通用内核：Object/Link/Action/Interface Type 元数据 + CRUD + 多租户抽象   │
│  零售 vertical：Region/Store/Employee/Product/NearExpiryProduct/Task      │
│  未来（v2）：组织5级 / 品类5级 / DC / 职能域                               │
├─────────────────────────────────────────────────────────────────────────┤
│  第1层：LLM + 存储                                                        │
│  LLM：MiniMax-M2.7-highspeed（OpenAI 兼容，现有一套，未来多 provider）     │
│  存储：JSON 文件（MVP）→ Repository 抽象层 → PostgreSQL+JSONB（未来）      │
└─────────────────────────────────────────────────────────────────────────┘
```

五层骨架来自 CN 文档；第3层 Tool/Skill 的具体形态采用讨论确认的"两类 Tool + 多类型 Skill + 无 Function 元素"决策；第2层是通用内核 + vertical 的分层；第1层存储强调抽象层（渐进路线）。

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

**现有代码 reconcile**：当前 `store.ttl` 用正则解析、缺元数据字段。目标是 Parser + EntityRegistry 扩展为带完整元数据的结构，TTL 仍是存储格式（符合"存储抽象"原则）。`models.LinkTypes` 常量与 TTL 不一致的 bug 要修（见附录 A）。

### 3.2 零售 vertical 本体（MVP 范围）

**MVP 直接用现有 6 Object**：Region / Store / Employee / Product / NearExpiryProduct / Task。

**Harness-Design 的零售全量本体列为后续 vertical 扩展（不在 MVP）**：
- 组织 5 级（Brand/OrgGroup/Channel/Region/Store）→ 收敛为现有 Region/Store，扩展留 v2
- 品类 5 级 → MVP 用 Product 的扁平 `category` 字符串，5 级树留 v2
- DC 配送中心 → MVP 不实现，留 v2
- 职能域 Domain → MVP 不实现，留 v2

### 3.3 多租户抽象层（内核关键设计）

```
Repository 接口（内核）
    ├── MVP 实现：JSONFileRepository
    │     data/tenant/{tenant_id}/{entity_type}.json
    │     所有读写强制带 tenant_id 过滤
    └── 未来实现：PostgresRepository（JSONB）、GraphRepository
```

**决策**：多租户通过 `tenant_id` 抽象承载，存储先用 JSON 文件、未来扩展数据库。关键是不让上层（工具、Agent）直接碰文件，而是经 `Repository` 接口——这样未来换 DB 只换实现，上层接口不变。

**tenant_id 传递链路（MVP）**：

```
前端 CopilotKit co-agent state (selected_store)
    → route.ts 提取为 HTTP header (X-Tenant-ID)
    → 后端 middleware 读取 → 注入请求上下文 (RequestContext)
    → Agent system prompt (Layer 3: 当前 tenant 上下文)
    → Repository 所有读写强制带 tenant_id 过滤
```

- **缺失/伪造处理**：后端 middleware 校验 `X-Tenant-ID` header 是否存在且在合法租户列表中；缺失返回 HTTP 401，伪造/非法返回 HTTP 403。不降级到默认租户。
- **现有数据迁移**：MVP 不迁移现有 `data/*.json` 到 `data/tenant/{tenant_id}/` 目录结构。Repository 层通过 `tenant_id` 过滤逻辑实现隔离——MVP 阶段所有现有数据默认属于 `tenant_default`，tenant_id 过滤在 Repository 查询时加 `WHERE tenant_id == current_tenant`（JSON 实现为 list comprehension 过滤）。

**现有代码 reconcile**：`tools.py` 直接 `_load_json`/`_save_json`，是 MVP 要重构的点。重构后工具调用 `repository.read(entity_type, tenant_id, ...)` / `repository.write(...)`。

### 3.4 Action Type 契约强化（吸收 Palantir）

现有 3 个 action（clearance/transfer/restock）的 TTL 定义只有参数，缺契约要素。MVP 补全：

```yaml
# Action Type: clearance（YAML 格式，存储于 ontology/actions/clearance.yaml）
api_name: clearance
display_name: 出清
description: 对临期商品进行出清处理，创建 Task 记录
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]   # provenance：声明会改哪些 object
parameters:
  - { name: discount, type: integer, required: true, constraint: "0..100" }
  - { name: quantity, type: integer, required: true }
  - { name: notes, type: string, required: false }
submission_criteria:                # 谁能提交
  roles: [store_manager, region_cat_mgr]
  conditions:                       # 参数级条件（Palantir 式）
    - { field: target.status, operator: is_not, value: expired, fail_msg: "已过期商品不能出清" }
side_effects:                       # 副作用声明
  - { type: notification, template: clearance_created, recipients: [assignee_id, manager_id] }
```

**submission_criteria 是权限的细粒度补充**（独立于粗粒度 RBAC）：粗粒度 RBAC 答"谁能用 execute_action 工具"，submission_criteria 答"给定这个 user 和这组参数，这个 action 实例能不能提交"。这让权限声明式、写在 Action 定义里，而非引擎里硬编码 6 层。

MVP 实现：submission_criteria 只做 `roles` 白名单 + 简单参数条件；复杂的 Palantir 式操作符全集（is/matches/includes/...）和嵌套逻辑留 v2。

**存储格式决策**：Action Type 定义使用 **YAML** 格式（存储于 `ontology/actions/*.yaml`），不扩展 TTL。理由：Action Type 的契约要素（parameters/submission_criteria/side_effects）是嵌套结构，TTL 的扁平三元组表达力不足、扩展语法较重；YAML 对嵌套结构更友好，且与现有 TTL Parser 并行——Object/Link Type 继续用 TTL（声明式 schema），Action Type 用 YAML（行为契约），Parser 按扩展名分别加载。

---

## 4. 第3层：Tool / Action / Skill / 计算逻辑

### 4.1 Tool 两类

| 类别 | 定义 | 示例 | 权限 |
|---|---|---|---|
| **OS 原子工具** | 操作系统级底层操作 | `http_call` / `db_query` / `file_read` / `file_write` | 仅 admin |
| **业务原子工具** | 业务级原子操作 | `entity_search` / `execute_action` / `query_task` / `query_near_expiry` 等 | RBAC 白名单 |

- **OS 原子工具** MVP 不必全实现（临期 demo 用不到 http/db/file），但内核注册表预留这个分类。
- **业务原子工具** = 现有 9 个 `@tool`。读工具（query_*）保持不变；写工具（`execute_action`/`confirm_action`）强化为走 Action 契约；通用 CRUD（`create_entity`/`update_entity`）按 1.3 降级。

### 4.2 Action Type（声明式变更契约）

保留现有 3 个（clearance/transfer/restock），走 `execute_action`（Preview）→ HITL 确认 → `confirm_action`（执行，创建 Task）模式。按 3.4 补全契约要素。

MVP 阶段，临期出清生产场景需要的新 Action Type（见 1.4）：create_clearance_task / submit_for_approval / accept_task / print_labels / deduct_stock / complete_task / create_loss_report。这些是 v2 零售 vertical 深化时补全，MVP 先保证 clearance 三个的契约完整。

### 4.3 Skill 多类型

**所有 Skill 都是 SKILL.md，由 deepagents SkillsMiddleware 加载，给 LLM 读。** Skill 按"内容类型"分类（frontmatter 的 `type` 字段区分），加载机制统一：

| Skill 类型 | 内容 | 示例 |
|---|---|---|
| **流程编排类** | 组合多个 Action/Tool 的步骤指南 | `clearance-workflow`（出清流程） |
| **领域知识类** | 本体知识与工具使用策略 | `store-ontology`（现有） |

**现有 SKILL.md 的坑要修**：`store-ontology/SKILL.md` 引用了 TTL 里不存在的实体和工具名（DiscountRule、get_near_expiry_products、belongs_to），要重写对齐实际本体与工具（见附录 A）。

**Skill 目录结构问题**：现有目录 `backend/skills/store-ontology/store-ontology/SKILL.md` 存在两层 `store-ontology` 嵌套（疑为创建时失误），deepagents 的 `FilesystemBackend` 按 `skills_root/{skill_name}/SKILL.md` 路径查找。MVP 需修复为 `backend/skills/store-ontology/SKILL.md`（一层），同时确保 `clearance-workflow` 目录也平级于 `store-ontology` 下。

### 4.4 计算逻辑：普通 Python 模块

计算逻辑不作为本体元素，是普通命名 Python 模块，被多个 Tool/Action 复用。例：

```python
# business/discount.py —— 单一事实源
def calculate_discount(ne: NearExpiryProduct) -> DiscountInfo:
    rules = load_discount_rules()   # 读本体数据 discount_rules.json
    tier = ne.discount_tier
    return DiscountInfo(tier=tier, rate=rules[tier], suggested_price=...)

# tools.py —— 工具调用它
@tool
def query_near_expiry(...):
    ... ne.discount = calculate_discount(ne) ...   # 复用

@tool
def execute_action(action_type="clearance", ...):
    ... preview.discount = calculate_discount(ne) ...  # 复用
```

### 4.5 修复折扣三处矛盾（必须修的 bug）

现状：`tools.py` 硬编码 `{T1:60,T2:40,T3:20}`（减扣百分比）、`discount_rules.json` 是 `{T1:0.5,T2:0.7,T3:0.9}`（乘数，0.5=付50%）、`clearance-workflow/SKILL.md` 是 `{T1:70%,T2:50%,T3:30% off}`（减扣百分比）——三处不仅数值矛盾，**语义维度也不一致**（乘数 vs 减扣百分比）。

**语义统一约定**：全系统统一使用**减扣百分比（0-100 整数）**，即"减 X%"。此约定与现有 `tools.py` 和 SKILL.md 的 `% off` 表述对齐。

**单一事实源** = `discount_rules.json`（本体数据，迁移后格式）+ 单一计算函数 `calculate_discount()`（读它）：

```python
# business/discount.py —— 单一事实源
from backend.ontology.tools import get_registry

def calculate_discount(discount_tier: str) -> int:
    """返回减扣百分比（0-100 整数）。如 T1 → 50 表示五折（减 50%）。"""
    rules = load_discount_rules()  # 读本体数据 discount_rules.json
    return rules[discount_tier]["discount_percent"]  # 统一为减扣百分比
```

`discount_rules.json` 迁移后格式（语义统一）：

```json
[
  {"id": "rule_T1", "tier": "T1", "days_min": 0, "days_max": 3, "discount_percent": 50, "description": "即将过期，5折（减50%）"},
  {"id": "rule_T2", "tier": "T2", "days_min": 4, "days_max": 7, "discount_percent": 30, "description": "中期临期，7折（减30%）"},
  {"id": "rule_T3", "tier": "T3", "days_min": 8, "days_max": 14, "discount_percent": 10, "description": "初期临期，9折（减10%）"}
]
```

**迁移要点**：
- `discount_rules.json`：字段 `discount_rate`（乘数）→ `discount_percent`（减扣百分比），值 `0.5→50, 0.7→30, 0.9→10`
- `tools.py`：删除硬编码 `tier_discount = {"T1": 60, "T2": 40, "T3": 20}`，改为调 `calculate_discount(tier)`
- `SKILL.md`：删除重复的折扣数值定义，改为引用 `discount_rules.json`（"折扣由 discount_tier 决定，具体数值见本体数据"）
- `query_task` 的 `float→int` 转换 hack 不再需要（所有折扣统一为 int）

---

## 5. 第4层：Agent 层

### MVP：单 Agent

继承现有 `create_deep_agent(model, tools, system_prompt, backend, skills)`，deepagents 自带工具循环 + SummarizationMiddleware + SkillsMiddleware。

**系统提示组装**（MVP 简化版，吸收 Harness §13 的分层思想但不全做）：

```
Layer 1: Agent 身份与核心原则（固定）
Layer 2: 本体知识（build_ontology_prompt 动态生成）
Layer 3: 当前 tenant 上下文（替代现有硬编码 store_001）
Layer 4: 可用工具清单（deepagents 自动注入）
```

**现有代码 reconcile**：`main.py` 硬编码 `store_context = "当前用户选择的门店ID是: store_001"` 要改为从请求上下文动态注入。具体实现：后端 middleware 从 `X-Tenant-ID` header 解析 tenant_id，存入 `RequestContext`（每个请求一个，类似 FastAPI 的 `Depends`），Agent 构建时从 `RequestContext` 读取 tenant_id 生成 Layer 3 内容。headless 调用（后端自动化定时器）时，由定时器任务指定 tenant_id。

### 未来：subagent / 多 Agent（v2，架构预留）

CN 文档的 Planner/Tool/Reasoner/Reporter 四角色协作列为 v2。deepagents 本身支持 subagent，架构上预留扩展点，MVP 不实现。

---

## 6. 权限 / 审计 / 观测（MVP 简化版）

### 6.1 权限引擎（MVP）

```
PermissionEvaluator 接口（内核）
    └── MVPRbacEvaluator 实现：
        - role → 允许的 tool 白名单
        - tenant_id 隔离（所有查询带 tenant 过滤）
        - resource_type + action 检查
        - Action Type 的 submission_criteria（角色白名单 + 简单参数条件）

每个工具调用前：permission_gate.check(tool, context)
失败 → PermissionDenied + 写审计（rejected）→ 不执行
```

**Harness-Design 的重型机制列为 v2**（不实现，接口预留）：
- 6 种 PermissionMode / 6 层 cascade
- Domain × OrgScope × CategoryScope 三维 scope
- DeepImmutable 快照冻结 + HMAC 校验
- 26 个生命周期钩子

MVP 能跑通"谁（role）能用什么（tool）操作什么（resource）"的闭环 + 审计，重型 RBAC×ABAC 留扩展点。

### 6.2 审计日志（MVP）

```yaml
AuditLogEntry（精简版，Harness §4 的子集）:
  audit_id: AUD-{date}-{seq}
  timestamp: ISO8601
  tenant_id: <tenant>
  actor: { user_id, role }
  action: { tool_name, params }
  rule_matched: { rule_id } | null
  outcome: SUCCESS | REJECTED

存储: data/tenant/{tenant_id}/audit/{date}.jsonl（append-only）
触发: 每个工具调用（成功/失败）写一条
```

### 6.3 可观测性（MVP）

MVP 只做结构化 JSON 日志（Harness §5.4 的 AppLog 格式）+ 现有 `/health` 端点。Metrics（品类×组织双维度）、OpenTelemetry Trace、告警列为 v2。

---

## 7. 第5层：前端

**MVP 保持现有 CopilotKit v1.57 + 9 个手写 renderToolCalls**（已验证可用）。

**新增（MVP，配合多租户）**：
- tenant/门店选择器从现有两个硬编码按钮升级为从 tenant 列表加载
- 选中后写入 co-agent state，经请求传给后端注入 tenant 上下文
- 修 `app/api/copilotkit/route.ts` 当前直接转发请求、不带 tenant header 的问题：route.ts 需从 CopilotKit co-agent state 中提取 `selected_store`，写入 `X-Tenant-ID` header 后转发给后端。当前 route.ts 使用 `ExperimentalEmptyAdapter` + `LangGraphHttpAgent` 直接转发，无 hook 修改 header 的能力——需改为使用 CopilotKit 的中间件或自定义 fetch wrapper 在转发时注入 header。

**v2**：A2UI 标准渲染（node_modules 已有但未启用）、ECharts 图表、权限管理 UI、审计查询 UI。

---

## 8. 演进路线

| 阶段 | 目标 | 来源 |
|---|---|---|
| **现状** | 单 Agent + 9 @tool + JSON + 临期本体 + 无权限/审计 | 项目设计文档（已实现） |
| **MVP（本轮）** | + 内核本体元数据 + CRUD + Repository 多租户抽象 + 简化 RBAC + 审计 + 结构化日志 + tenant 选择器 + 修折扣 bug + Action Type 契约强化 + CRUD 降级（edits-only-via-actions） + 后端自动化（Task 状态机/定时器） | 三文档 reconcile |
| **v2-存储** | JSON → PostgreSQL+JSONB（换 Repository 实现） | Harness §6 / CN |
| **v2-权限** | 简化 RBAC → 完整 RBAC×ABAC（三维 scope、6 层 cascade、快照冻结） | Harness §3 |
| **v2-本体** | + 组织5级 / 品类5级 / DC / 职能域 零售 vertical | Harness §1-2 |
| **v2-Agent** | 单 Agent → subagent / 多 Agent 协作 | CN §第4层 |
| **v2-UI** | 手写 renderToolCalls → A2UI 标准 + 图表 | CN §第5层 |
| **v2-长流程** | 后端自动化 → 可选 BPM/Workflow 引擎增强 | 生产场景 |

---

## 附录 A：与现有代码的差距盘点 + Bug 清单

### A.1 已实现且可保留

- 单文件 FastAPI + Deep Agent（`backend/main.py`）
- 正则 TTL 解析器 + EntityRegistry（`backend/ontology/parser.py`）
- 6 Object / 7 Link / 3 Action types（`backend/ontology/store.ttl`）
- 9 个 `@tool` 函数操作 JSON（`backend/ontology/tools.py`）
- Preview→Confirm 出清流程
- 2 个 SKILL.md（`backend/skills/`）
- CopilotKit AG-UI 端点 + 前端 9 个 renderToolCalls

### A.2 文档写了但完全未实现（Harness-Design 的 75% 空缺）

多组织层级、DC、职能域、品类 5 级树、RBAC×ABAC 权限引擎、审计日志、Metrics、Trace、多租户隔离、26 个生命周期钩子、三层工具接口、多 provider LLM 工厂——全部列为 v2。

### A.3 必须修的 Bug（MVP 范围）

| Bug | 现状 | 修法 |
|---|---|---|
| **三处折扣矛盾** | tools.py `{T1:60,T2:40,T3:20}`（减扣百分比）/ discount_rules.json `{T1:0.5,T2:0.7,T3:0.9}`（乘数，语义不同）/ clearance-workflow/SKILL.md `{T1:70%,T2:50%,T3:30% off}`（减扣百分比）——三处不仅数值矛盾，语义维度也不一致 | 单一事实源 + 语义统一：discount_rules.json 统一为减扣百分比 + `calculate_discount()` 函数（见 4.5） |
| **clearance-workflow/SKILL.md 折扣值矛盾** | 该文件声明的折扣值（T1=70%, T2=50%, T3=30%）与 tools.py 硬编码（T1=60, T2=40, T3=20）不一致，也与 discount_rules.json 语义不匹配 | 同上，统一后 SKILL.md 不再重复定义数值 |
| **LinkTypes 常量不一致** | `models/schemas.py` 的 `LinkTypes` 常量（`HAS_NEAR_EXPIRY_PRODUCT`/`BELONGS_TO`/`SUBJECT_TO`）与 TTL 实际定义（`has_near_expiry`，无 `belongs_to`/`subject_to`）不符 | 对齐 TTL，或删除未使用的 LinkTypes 类 |
| **tasks.json 遗留 schema** | 种子 `tasks.json` 用旧 schema（`action_type`/`near_expiry_product_id`/`input_params`），与新 `Task` model（`type`/`target_id`/`params_json`）不符；`query_task` 在读取时 `setdefault` 打补丁 | 迁移种子数据到新 schema；移除打补丁代码 |
| **SKILL.md 引用不存在实体** | `store-ontology/SKILL.md` 引用 `DiscountRule`、`get_near_expiry_products`、`belongs_to` 等本体/工具里不存在的东西 | 重写 SKILL.md 对齐实际本体与工具 |
| **CRUD 绕过治理** | `create_entity`/`update_entity` 可改任意实体任意字段，绕过 Action 治理 | edits-only-via-actions 标记 + Repository 检查（见 1.3） |
| **JSON 写无锁** | `_save_json` 无并发控制，并发写会损坏文件 | Repository 层加文件锁（MVP）或事务（PG，v2） |
| **硬编码 store_001** | `main.py` 把门店 ID 硬编码进 system prompt | 改为从 tenant 上下文动态注入（见 §5） |
| **route.ts 不带 tenant** | 前端 API 代理直接转发请求，不带 tenant header | 加 tenant 上下文传递（见 §7） |
| **clearance_tasks.json 残留文件** | `data/clearance_tasks.json` 是 `tasks.json` 旧 schema 条目的子集副本，代码中无任何引用 | 删除该文件 |
| **manages link 方向语义反转** | `store.ttl` 定义 `manages: Employee → Store, via="manager_id"`，但 `manager_id` 是 Store 的字段（不是 Employee 的）。`traverse_relation("Employee", "emp_001", "manages")` 能工作纯属巧合（store_001.manager_id == "emp_001"） | 修正 TTL：`manages: Store → Employee, via="manager_id"`（店长是 Store 的属性，不是 Employee 的） |

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
