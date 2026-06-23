# Palantir 功能需求的项目侧实现识别

> **徽章**：📚 参考 / 评估
> **目的**：对 [`palantir-ontology-functional-requirements.md`](./palantir-ontology-functional-requirements.md)（36 节、~350 条 F-XX-NN）逐节判定本项目（store-ontology）应当**完全实现 / 部分实现 / 转换实现 / 不建议实现**，给出每档的现状证据与理由，并在末尾按优先级排序、给出与现有设计文档的联动建议。
> **v2 修订（2026-06-22）**：v1 仅从"临期出清单场景 + LLM 消费"两轴评估，把多个**企业零售 agent 平台**的必备能力（时序/地理/批量规则/多跳遍历）和 **agent 治理/运维**的必备能力（Decision Lineage/Usage Limits/Metrics/notification 投递/渐进自治）误判为"不建议"。v2 引入**三轴评估方法论**（§0.2），对 v1 的 16 处保守判定上浮。变化集中在 §9/§10/§11/§14/§15/§16/§19/§20/§21/§22/§23/§24 及 §36 的 4 条、§37 优先级全表重排。
> **定位区分**：
> - [`palantir-ontology-functional-requirements.md`](./palantir-ontology-functional-requirements.md) — **只描述 Palantir 侧能力**，不涉本仓库现状（其 §5 明确声明）。
> - 本文档 — **只评估本仓库侧实现取向**，对需求文档做"要不要 / 怎么做"的项目侧识别。
> **证据来源**：`agent/engine/` + `agent/tools/` + `agent/skills/` + `workspace/{retail,customerA,jjy}/` 活代码 + [`roadmap.md`](./roadmap.md) 的 ✅/🔜 标记。

---

## §0 评估方法论

### 0.1 四档判定定义

| 档位 | 缩写 | 定义 |
|---|---|---|
| **完全实现** | ✅ 完全 | 应当按 Palantir 能力完整对标建设 |
| **部分实现** | 🟡 部分 | 建设简化子集，满足企业零售 + agent 场景即可 |
| **转换实现** | 🔄 转换 | 不照搬 Palantir 概念，映射到本项目原生抽象 |
| **不建议实现** | ⛔ 不建议 | 不建设，并给出理由 |

### 0.2 决策依据——三轴评估（v2 核心修订）

[`00-architecture.md`](./00-architecture.md) §0 核心论断：

> "Palantir 本体为前 LLM 时代的'人 + 应用'设计，LLM 时代 agent 的消费者变了，抽象就该变。"

v1 只用了这条论断引出的单轴（KEEP/DEMOTE/DROP）。v2 扩展为**三轴**，每节判定必须同时过三轴：

#### 轴 1：架构轴（沿用 v1）

Palantir 抽象按"描述世界 / 执行计算展示 / 专有前端或重型治理"分三档：

1. **KEEP**（→ 完全）：描述世界的语义原语 + 治理原语——Object/Link/Action Type、submission criteria、RBAC×ABAC、RLS。与消费者是人还是 LLM 无关。
2. **DEMOTE/ABSORB**（→ 转换）：执行/计算/展示层映射到本项目原生抽象——Function → Tool+Skill+compute module；Object Explorer → query tools + generative UI；Object View → renderToolCalls；Multi-Ontology → multi-workspace。
3. **DROP**（→ 不建议）：专有人/应用前端或重型治理机制。

#### 轴 2：场景轴（v2 新增）⚠️ v1 盲区

**不按 clearance 单场景判，按"零售企业 agent 平台最小能力集"判。** 零售本质是：时序密集（POS 流/库存周转/价格历史）、地理分布（门店网络/配送范围）、供应链穿透（供应商→商品→门店→库存）、批量规则（补货点/合规扫描/临期预警）、多角色协作（店长/区经理/运营/采购）。

v1 错误地把"clearance 不需要"等同于"零售平台不需要"。轴 2 强制每条判定过一遍："去掉 clearance，这套能力在零售企业平台是不是标配？"

#### 轴 3：建模 vs 可视化分离轴（v2 新增）⚠️ v1 盲区

Palantir 多个能力把**数据建模**（轻、必要）和**可视化 UI**（重、给人看）耦合在一起卖。v1 看到重的就整条⛔。

轴 3 强制拆分：**数据建模部分**按轴 1/2 判定（通常 🟡 部分）；**可视化前端部分**按"是不是 LLM 或人用操作台的刚需"判（通常 ⛔ 或转换）。典型适用：§15 Vertex（图建模 vs 图可视化）、§16 Events（时序建模 vs timeline 回放）、§21 Map（地理建模 vs 地图前端）。

#### 轴 4：agent 治理/运维轴（v2 新增）⚠️ v1 盲区

**agent 替人做决策，谁来管 agent？agent 跑起来，怎么知道它健康？** v1 几乎只有"权限"一轴，漏了决策追溯、成本治理、自治分级、人机协同通知。

轴 4 强制每个"⛔"过一遍："agent 上生产后，这项能力是不是治理/运维刚需？" 若是，上浮判定。典型适用：§24 Usage/Limits（LLM 成本）、§7 Action Metrics（可观测）、§9 notification（人机协同底线）、§36 Decision Lineage（治理第一问）。

### 0.3 粒度说明（混合粒度）

- 34 个主题节（§0–§33）每节给一个节级判定。
- **判定有内部分化的核心节**（§1/§2/§4/§7/§8/§10/§14/§16/§19/§20/§21/§23）在 §35 额外拆到 F-XX-NN 条目级。
- 判定一致的节只给节级理由，不展开条目。

### 0.4 优先级标记

| 标记 | 含义 |
|---|---|
| **P0** | MVP 补齐——治理/运维闭环或架构已要求但实现缺失，必须优先 |
| **P1** | V1 增强——显著提升 agent 能力或企业零售覆盖度，应在 V1 周期纳入 |
| **P2** | V2 方向——`roadmap.md` 已列 🔜 的前瞻项 |
| **P3** | 远期 / 按需——场景驱动，当前不排期 |

---

## §1 总览矩阵（34 节判定一览）

> 单行双判定格式（如"⛔图可视化 / 🟡多跳遍历"）表示该节按轴 3 拆分。

| § | 主题 | 判定 | 现状一句话 | 关键理由 | 优先级 |
|---|---|---|---|---|---|
| 0 | 决策为中心模型 | 🔄 转换 | 4 组件框架已采纳 | Logic→Tool、Action→ActionType、Security→RBAC×ABAC | — |
| 1 | Object Type / Object / Object Set | 🟡 部分 | Object Type✅ / Object Set 仅等值过滤 | 描述世界的语义原语 KEEP；MDO/Writeback 非场景 | P1 |
| 2 | Property | 🟡 部分 | Local✅ / Shared·Value Type·Reducer·Derived 缺 | Local 是基础；高级类型收益待场景验证 | P1/P2 |
| 3 | Structs | ⛔ 不建议 | 无 | 建模复杂度高；`params_json:dict` 已是逃生舱 | — |
| 4 | Link Type | 🟡 部分 | Link✅ / Cardinality 显式声明缺 / N:M join 缺 | Link KEEP；显式基数 v2 | P2 |
| 5 | Interface | ⛔ 不建议→V2 | 架构明确 v2 元数据预留 | 命名约定当前替代；多态非 MVP | P2 |
| 6 | Type Groups | 🔄 转换 | `domain.ttl` 已按业务域分组 | LLM 不需 Group 浏览导航 | — |
| 7 | Action Type | ✅ 完全 | 已大量落地（clearance 9 + repair 6） | Action 是治理核心；补 Log/Revert/Metrics | P0 |
| 8 | Function | 🔄 转换 | 无 Function 元素；Tool+Skill+compute module 替代 | 架构 §2.1 明确 Tool = LLM 时代的 Function | — |
| 9 | Side Effects | 🟡 部分（拆分） | notification/external_call 声明但 no-op | notification 投递→P0（人机协同底线）；external_call→P1 | P0/P1 |
| 10 | Permission | ✅ 完全 | RBAC×ABAC + RLS + 列级✅ | 治理原语 KEEP；补 agent 身份（P1）；Marking/Purpose 重型不建议 | P0/P1 |
| 11 | Object Explorer | 🔄 转换（+补） | query tools + generative UI cards | 人/应用前端→LLM 工具化；**补人用操作台**（P1） | P1 |
| 12 | Ontology Search | 🟡 部分 | Tool filter 仅等值 | 搜索语法可纳入 Tool filter 增强 | P2 |
| 13 | Semantic Search | 🟡 部分(V2) | schema 预留 vector，代码无 | RAG 场景启用时补 | P2 |
| 14 | Object View | 🔄 转换（+补） | renderToolCalls 9 个 | Workshop 配置层→generative UI；**补人用操作台**（P1） | P1 |
| 15 | Vertex / Graphs | ⛔图可视化 / 🟡多跳遍历 | 仅单跳 `traverse_relation` | 图可视化非 LLM 核心；**多跳遍历 API** 供应链穿透刚需（P2） | P2 |
| 16 | Events and Time Series | 🟡时序建模 / ⛔timeline回放 | 无 | **零售是时序密集业务**（POS/库存/价格）；timeline 回放 UI 不建 | P1 |
| 17 | Scenarios | ⛔ 不建议 | 无 | Preview→Confirm 已部分覆盖"先看后写" | — |
| 18 | Machinery | ⛔ 不建议 | 无 | 流程挖掘非本平台定位 | — |
| 19 | Foundry Rules | 🔄 转换（+补批量层） | submission_criteria + automation.py + scheduler | 规则引擎→声明式条件；**补批量声明式规则层**（无 LLM 在环的确定性扫描，P1） | P1 |
| 20 | Object Monitors [Sunset] | 🔄 转换 | 无 Monitor 对象 | Palantir 已 Sunset；但 condition→检测→告警→Action 模式投影为 **agent ops 仪表盘**（P1） | P1 |
| 21 | Map | 🟡地理建模 / ⛔Map可视化 | `Store.address` 纯字符串 | **门店网络/配送范围**需地理建模（P2）；地图前端不建 | P2 |
| 22 | Dynamic Scheduling | 🟡 部分 | 仅 APScheduler 间隔任务 | **排班/补货/档期**需时间分配原语（P2）；Gantt+suggestion 不建 | P2 |
| 23 | Branching / Change Mgmt | 🟡 部分 | status+deprecation + admin CRUD | **生产本体安全演进**是治理刚需：补安全变更机制（P1）；Git 式分支仍 V2 | P1/P2 |
| 24 | Usage / Limits | 🟡 部分 | 无 | **LLM 成本治理 + 速率/配额/熔断**是 agent 运维标配（P1），非 SaaS 计费专属 | P1 |
| 25 | Indexing | 🔄 转换 | `import_to_pg.py` 一次性导入 | Palantir pipeline → 一次性脚本 | — |
| 26 | Object Edits / Materializations | 🟡 部分 | edits-only-via-actions✅ / edit history·materialization 缺 | 治理✅；物化非场景；edit history 随 Action Log | P2 |
| 27 | Aliases | ⛔ 不建议 | 无 | 配置用 `.env` + `config.yaml` | — |
| 28 | Marketplace | ⛔ 不建议(MVP) | industry pack 目录 + onboarding CLI | 分发模型已由 pack 目录替代 | P3 |
| 29 | SDK / External Integration | 🔄 转换 | Tool schema (AG-UI) + Agentic Tool Surfacing✅ | SDK→Tool schema；Tool Surfacing 是本平台核心 | — |
| 30 | TS / Python Function 生态 | 🔄 转换 | Python compute module + `@tool` | 多语言 Function → 单一 Python + Tool | — |
| 31 | Multi-Ontology | 🔄 转换 | multi-workspace (`workspace_name` 硬隔离) | 多 Ontology → 多 workspace | — |
| 32 | Metadata | 🟡 部分 | status/visibility✅ / type classes·render hints 缺 | 基础元数据✅；渲染提示转换到 UI | P2 |
| 33 | 跨切能力 | 🟡 混合 | Multi-tenancy✅ / Tool Surfacing✅ / Decision Lineage🔜 | 见 §36 拆解 | P0/P1/P2 |

**统计**：完全 2 节、部分 15 节（含部分 V2/混合/拆分）、转换 11 节、不建议 6 节（含"不建议→V2"/"不建议(MVP)"）。完全+部分共 17 节需投入建设（v1 为 12 节），转换 11 节已有原生替代，不建议 6 节明确不做。

> **对比 v1**：不建议从 12 节降到 6 节（§16/§20/§21/§22/§24 上浮，§15 拆分），部分从 10 升到 15。反映"企业零售 + agent 治理/运维"视角下，平台需要的能力面更宽。

---

## §2 逐节详评（§0–§34，对应需求文档节号）

### §0 决策为中心模型 — 🔄 转换

**现状**：架构 §0 已采纳 Palantir 的 4 组件框架（Data / Logic / Action / Security），但每个组件的具体形态都做了 LLM 时代映射。

**理由**：4 组件作为思维框架普适，但 Palantir 把 Logic 实现为独立 Function 元素、把展示层实现为 Workshop 配置，是面向"人填表单、人配应用"的。本平台消费者是 LLM，Logic 应由 LLM 直接消费的 Tool 承载、展示由 generative UI 承载。

**映射**：

| Palantir 4 组件 | 本平台对应 |
|---|---|
| Data | Object/Link/Action Type（TTL + YAML） |
| Logic | Tool + Skill + Python compute module |
| Action | Action Type（submission criteria + side effects） |
| Security | PermissionEvaluator（RBAC×ABAC + RLS + 列级） |

### §1 Object Type / Object / Object Set — 🟡 部分

**现状**：Object Type 完整落地（`engine/parser.py:OntologyParser._parse` + `engine/pg_ontology_repo.py`）；Object 实例化✅；Object Set 仅支持等值过滤（`Repository.read(ot, tenant, filters)`），无聚合/集合运算/排序分页。

**理由**：Object Type 是"描述世界"的语义原语，KEEP。Object Set 的全量代数（filter DSL / search-around / aggregation / KNN）面向 Workshop 图表分析，LLM 场景通过 query Tool 取数 + LLM 推理即可，无需全量。但**聚合能力**（count/sum/groupby）是企业零售基础（"多少/总量"类问题），列为 P1。

**建议**：见 §35-§1 条目拆解。

### §2 Property — 🟡 部分

**现状**：Local Property✅（`PropertyDef(name, type, read_roles, ...)`）；per-property ACL✅（`read_except`/`write_except`）；Shared Property / Value Type / Struct / Reducer / Derived 全缺；Render Hints / Type Classes 缺。

**理由**：Local Property 是建模基础，KEEP。Shared Property / Value Type 是 DRY 治理工具，当前用命名约定替代（架构 §3.3 列 v2）。Derived Property 的计算能力由 Tool 承载（如 `query_near_expiry` 计算折扣）。

**建议**：见 §35-§2 条目拆解。

### §3 Structs — ⛔ 不建议

**现状**：无 Struct 类型系统；`Task.params_json:dict` / `result_json:dict` 是不透明逃生舱。

**理由**：(a) Struct 建模复杂度高（定义 + automapping + main fields + 嵌套 Action）；(b) 当前所有结构化数据都可用具名 Property + JSON 逃生舱表达；(c) 架构/规范/roadmap 三份文档均未提及 Struct，说明非设计意图。

**建议**：保持不引入。若未来出现强结构化参数需求，先评估能否用具名 Property + Action parameter 解决。

### §4 Link Type — 🟡 部分

**现状**：Link Type✅（`rdfs:Property` + domain/range/via）；虚拟外键实现（无独立边表）；Cardinality 无显式字段（由 `via` 外键数据形态隐式决定）；N:M join table 缺；Link Merging 无（属 Map 功能）。

**理由**：Link 是"描述世界"的语义原语，KEEP。显式 Cardinality 声明 + 校验是建模规范 §4.4 列 v2 的项。N:M join table 在临期/维修场景均未出现。

**建议**：见 §35-§4 条目拆解。

### §5 Interface — ⛔ 不建议→V2

**现状**：无 Interface；架构 §2 / 建模规范 §1.3 / §3.4 均明确"v2，MVP 不实现，元数据预留"。

**理由**：(a) 多态需求当前用命名约定（id/parent_id/store_id/status 跨类型复用）替代；(b) Interface 价值依赖 Shared Property + Function Interface API，三者需协同引入，单引入 Interface 收益有限；(c) 三份权威文档一致列为 v2。

**建议**：维持 v2 元数据预留。引入时机取决于是否出现"跨 Object Type 统一处理"的强烈需求（如多零售子流程的统一审批）。**v2 提示**：零售平台多子流程（出清/补货/退货/调拨）的统一处理会早遇到 Interface 需求，优先级上浮关注。

### §6 Type Groups — 🔄 转换

**现状**：无 Group 资源；但 `domain.ttl` 已按业务域分组（organization/personnel/category/identity/marketing/finance/maintenance），`CapabilityDomain` 就是事实上的 Group。

**理由**：Palantir Type Groups 服务 Object Explorer 侧边栏导航——给人看的。LLM 通过 ontology system prompt（`build_system_prompt` 已按 domain 组织）即可获得分组信息，不需独立 Group 资源。

**建议**：维持 `CapabilityDomain` 作为隐式 Group，不引入显式 Group 资源。

### §7 Action Type — ✅ 完全

**现状**：Action Type 大量落地。clearance 9 个 + repair 6 个，覆盖 create/modify/state_transition/notification/external_call 五类副作用。submission_criteria（roles + conditions）✅；参数约束（0..100 / >0 / in:...）✅；Preview→Confirm 治理环✅；locator_field 数据驱动路由✅。

**缺**：Action Log（决策即数据）/ Action Revert（Undo）/ Action Metrics（成功率/时延监控）。

**理由**：Action Type 是治理核心，应当完全对标。当前缺失项（Log/Revert/Metrics）是补齐而非方向调整。**v2 强调**：Action Metrics 从 P1 上浮到 P0——agent 运维的可观测性核心，生产环境 agent 不能是黑箱。

**建议**：见 §35-§7 条目拆解。

### §8 Function — 🔄 转换（核心）

**现状**：无 Function 作为 ontology 元素。计算逻辑分布在三处：(1) `@tool` 函数（LLM 调用）；(2) Skill 的 `tools.py` / `automation.py`（后台自动化）；(3) 普通 Python module（如 `discount.py`）。

**理由**：架构 §2.1 明确论断——"Tool 就是 LLM 时代的 Function"。Palantir Function 服务 Workshop 派生列/图表聚合/Slate 后端，这些消费场景在本平台由 Tool + LLM 推理替代。引入 Function 为 ontology 元素会重复 Tool 的职责。

**建议**：见 §35-§8 条目拆解。维持转换判定，不引入 Function 元素。

### §9 Side Effects — 🟡 部分（v2 拆分）

**现状**：五类副作用类型已声明（`create_object/update_object/state_transition/notification/external_call`）；前三类✅；`notification` 引用模板名但**无模板定义、投递为 no-op**；`external_call` 仅 `print_labels` 一处声明、投递 no-op。

**理由**（v2 修订）：副作用骨架✅，是 Action 治理的一部分。v2 把投递拆成两档：
- **notification 投递 → P0**：agent 做了关键操作（改价、报废、审批）**必须通知到人**——这是人机协同治理的底线，当前 no-op 是真实风险。auth 事件已有 `auth_audit.py`，Action 关键事件无人知是生产事故源。
- **external_call 投递 → P1**：真实 webhook sink 是集成前提（见 §29 Writeback Connectors）。

**建议**：P0 先补 notification 模板系统 + 平台内消息投递；P1 补 external_call webhook sink 配置。

### §10 Permission — ✅ 完全（v2 补子点）

**现状**：RBAC×ABAC✅（`PermissionEvaluator`，5 资源类型：tool/object_type/property/action/link）；RLS✅（`workspace_name` 硬隔离 + `org_unit_id` 经 `OrgTree.visible_units` 范围过滤）；列级✅（`readable_properties`/`denied_properties` 掩码 + `can_write_property`）；`system_admin` 短路；allow-by-default + deny-wins；运行时 `permission_grants.json` 覆盖 TTL 默认。

**缺**（v2 补）：**agent 身份**。当前 actor 从 `auth_ctx`（用户）推导，agent 自己没有独立身份。企业需要 **agent 作为一等主体**被授权/审计/限流（服务账号）。

**理由**：权限是治理核心，KEEP。Marking/Purpose/Dynamic Security 是 Palantir 面向政府/金融客户的重型合规机制，与零售场景不成比例。但 **agent 身份**是 agent 平台的治理刚需——agent 自己做的事要能和用户做的事区分开追溯（见 §36 Decision Lineage）。

**建议**：见 §35-§10 条目拆解。当前 RBAC×ABAC+RLS+列级已覆盖零售场景权限需求；agent 身份补为 P1。

### §11 Object Explorer — 🔄 转换（v2 补子点）

**现状**：无独立 Explorer 应用；查询通过 `query_entity` / `traverse_relation` / `query_task` / `query_near_expiry` Tool 暴露给 LLM；前端 generative UI（9 个 `renderToolCalls`）渲染结果卡片；admin 数据浏览器（`/admin/data-browser.tsx`）只读浏览 6 类基础实体。

**理由**：Palantir Object Explorer 是"非技术用户的搜索/分析入口"——给人在 UI 上点选过滤、画图表、做对比。LLM 时代，用户用自然语言提问，LLM 调 Tool 取数 + 推理 + generative UI 呈现，省掉整个 Explorer 交互层。**但 v2 补充**：企业平台还需要**人（店长/区经理/运营）的操作面**——不是 agent 对话面，是看板/数据探索/报表。当前 dashboard 只读、admin 只读浏览 6 实体，远不够零售运营。这是另一条线，与 generative UI 并行。

**建议**：维持转换（不建 Explorer 点选式交互）；**补人用操作台**（dashboard 增强 + 数据探索 + 报表）列为 P1。

### §12 Ontology Search — 🟡 部分

**现状**：无搜索语法；`query_entity` Tool 支持单字段等值过滤（`filter_field`/`filter_value`）。

**理由**：搜索语法服务 Object Explorer 的点选过滤，属转换范畴。但简单多字段/范围过滤对 LLM 取数有用，可纳入 Tool filter 增强。

**建议**：P2 给 `query_entity` 加多字段 + 范围 + 排序 + 分页参数（而非引入独立搜索语法层）。

### §13 Semantic Search — 🟡 部分(V2)

**现状**：`sql/schema.sql` 已 `CREATE EXTENSION vector`，`entities.embedding` 列注释预留但未启用；无 embedding 写入或 KNN 查询代码。

**理由**：语义检索（RAG）是 LLM 时代高价值能力，但当前临期/维修场景是结构化查询驱动，非语义检索驱动。`roadmap.md` §1 明确"待语义检索场景启用"。

**建议**：P2 按场景驱动启用。典型触发场景：商品/故障的模糊匹配、跨工作目录知识问答。

### §14 Object View — 🔄 转换（v2 补子点）

**现状**：无 Object View 配置层；实体详情通过 `query_entity` Tool 返回 `entity_detail` JSON，前端 `renderToolCalls` 渲染为键值网格卡片。

**理由**：Palantir Object View 是"Workshop module + 多 tab + widget 编排"——给人配的。LLM 时代，实体呈现由 generative UI 根据 Tool 返回数据动态渲染，无需配置层。**v2 补充**（与 §11 同理）：人用操作台需要结构化的实体详情页（不是对话气泡里的卡片），这是 P1 的一部分。

**建议**：见 §35-§14 条目拆解。维持转换。

### §15 Vertex / Graphs — ⛔图可视化 / 🟡多跳遍历（v2 拆分）

**现状**：仅 `traverse_relation` 单跳遍历；无图存储、无图可视化。

**理由**（v2 拆分）：
- **图可视化（Vertex 前端）→ ⛔**：图可视化是给人探索关系网的，LLM 通过多跳 traverse + 推理即可；图可视化前端复杂度极高。
- **多跳遍历 API → 🟡 P2**：零售供应链穿透（供应商→商品→门店→库存）是真实需求，当前单跳 `traverse_relation` 够 clearance 但**不够供应链**。多跳遍历是数据建模/查询能力，与图可视化前端是两回事。

**建议**：图可视化不建；多跳遍历 API（`traverse_relation` 扩展到 N 跳 + 路径返回）列为 P2。

### §16 Events and Time Series — 🟡时序建模 / ⛔timeline回放（v2 重大修订）

**现状**：无 Event Object Type、无时序 Property；POS 事件仅作为 webhook 无状态调用（`routers/webhooks.py`）。

**理由**（v2 重大修订，原 v1 ⛔）：**零售本质是时序密集型业务**——POS 交易流、日销趋势、库存周转、促销效果、价格历史、损耗曲线。clearance 的 `days_left` 恰恰是因为没有时序建模才退化成每次重算的快照。
- **时序建模 → 🟡 P1**：引入 timestamped Event Object Type + 时序 Property（measure over time）。区别于"可视化"。
- **timeline 回放 UI（Vertex 时间游标）→ ⛔**：那是给人探索时序的，LLM 用时序数据推理即可。

**建议**：见 §35-§16 条目拆解。P1 引入时序建模原语；timeline 回放 UI 不建。

### §17 Scenarios — ⛔ 不建议

**现状**：无 Scenario 沙盒；Preview→Confirm 治理环（`preview_cache.py` 300s TTL）已提供"先看后写"能力。

**理由**：Scenario 的核心价值是"what-if 模拟不污染生产数据"，用于排程优化、财务预测等重计算场景。本平台的 Preview→Confirm 已覆盖 Action 级别的"先预览再确认"，而 retail/customerA 均无重计算 what-if 需求。

**建议**：维持 Preview→Confirm 作为轻量替代。

### §18 Machinery — ⛔ 不建议

**现状**：无流程挖掘；价值链流程由 `ValueChainProcess` + 状态机 + Skill 编排。

**理由**：流程挖掘（process mining）是从事件日志反向挖掘流程，与本平台"正向声明流程 + LLM 编排"的定位相反。

**建议**：不引入。

### §19 Foundry Rules — 🔄 转换（v2 补批量层）

**现状**：无独立规则引擎；规则逻辑分布在三处：(1) Action 的 `submission_criteria.conditions`（声明式条件）；(2) `automation.py` 的后台 job（定时检查 + 触发 Action）；(3) JSON 规则文件（如 `discount_rules.json`）由 Python module 消费。

**理由**（v2 修订）：转换方向对，但 v1 转错了——`submission_criteria` 是**单次 Action 提交时**的校验，无法表达"**扫描全量数据找出所有低于安全库存的商品并触发补货**"这类**批量声明式规则**。企业零售需要**无 LLM 在环**也能跑的声明式批量规则（合规扫描、补货点巡检、临期预警）。v1 把规则全塞进 LLM 触发路径，丢失了批量确定性执行。

**建议**（v2 补）：转换判定保留，但补一个**轻量声明式规则层**（声明 condition + scope + 触发的 Action，由 scheduler 批量评估），区别于 Action 内的 submission_criteria。见 §35-§19 条目拆解。批量声明式规则层列为 P1。

### §20 Object Monitors [Sunset] — 🔄 转换（v2 修订）

**现状**：无 Monitor；`AutomationScheduler`（APScheduler 包装）+ Action 已覆盖定时检查 + 触发动作的需求（如 `clearance_expiry_check` job）。

**理由**（v2 修订，原 v1 ⛔）：Palantir 自身已将 Object Monitors 标记 Sunset。但 **condition→检测→告警→Action 这个模式**正是 **agent 行为监控**——agent 有没有在异常时间改数据？有没有批量失败？不要 Monitor 对象，但要把这个能力以**agent ops 仪表盘 + 告警规则**的形式投影进来。与 §7 Metrics、§9 notification 协同。

**建议**：见 §35-§20 条目拆解。投影为 agent ops 仪表盘列为 P1。

### §21 Map — 🟡地理建模 / ⛔Map可视化（v2 拆分）

**现状**：无地理可视化；`Store.address` 是纯字符串。

**理由**（v2 拆分）：
- **地理数据建模 → 🟡 P2**：零售门店网络分析、配送范围、区域绩效对比都需要。Store 经纬度、区域多边形、商圈 catchment 是建模原语。当前 `Store.address` 纯字符串是建模缺口。
- **Map 可视化应用 → ⛔**：地图前端（图层/标注/轨迹）复杂度极高，非 LLM 核心。

**建议**：见 §35-§21 条目拆解。地理建模 P2；地图前端不建。

### §22 Dynamic Scheduling — 🟡 部分（v2 修订）

**现状**：仅 `AutomationScheduler` 支持间隔任务（`interval=1800`）；无 Gantt、无资源排程、无 suggestion/search/validation function。

**理由**（v2 修订，原 v1 ⛔）：零售有：员工排班、补货周期、促销档期窗口、配送路线。不是 Palantir 那种带 suggestion function + validation rule 的 Gantt，但**时间分配 + 周期触发**的建模原语是零售标配。

**建议**：保留 AutomationScheduler 间隔任务（已有），**补**：周期/窗口概念（promo window、shift slot）、资源-时间分配的基础表达。P2。Gantt + suggestion function 不建。

### §23 Branching / Change Management — 🟡 部分（v2 上浮）

**现状**：无 Ontology 分支；admin CRUD（`routers/admin.py` 9 个写端点 + `pg_ontology_repo`）已支持运行时 schema 增删改；`status`（experimental/active/deprecated）+ 建模规范 §7 deprecation 流程 + 代码 review 替代分支治理；`invalidate_workspace` 做 schema 变更后缓存失效。

**理由**（v2 修订，原 v1 P2 远期）：企业平台里，**生产环境本体如何安全演进**是治理刚需：改了 Object Type 会不会破坏在跑的 agent？新增 Action 怎么灰度？不需要完整 Git 式分支 + Proposal 审查，但需要**安全变更机制**（变更前校验下游引用、灰度发布、快速回滚——与 §26 edit history 和回滚是同一件事）。这是 P1，不是 P2 远期。

**建议**：见 §35-§23 条目拆解。**安全变更机制 P1**（轻量：变更校验 + 回滚）；Git 式分支 + Proposal 仍 V2。

### §24 Usage / Limits — 🟡 部分（v2 重大修订）

**现状**：无计量。

**理由**（v2 重大修订，原 v1 ⛔）：v1 以"单租户不计费"为由⛔是**最离谱的误判**。任何 **LLM 平台**都需要：token 成本追踪、每工作目录/每用户速率限制、配额、异常调用熔断。这是 **agent 运维和成本治理的标配**，不是 SaaS 计费才需要。**LLM 成本是企业上 agent 的第一道门槛**。

**建议**：P1 引入 token 成本追踪 + 速率限制 + 配额 + 熔断。

### §25 Indexing — 🔄 转换

**现状**：`agent/scripts/import_to_pg.py` 一次性导入（TTL/YAML/JSON → PG upsert）；PG schema 有 `(workspace_name, org_unit_id)` 索引 + JSONB GIN。

**理由**：Palantir Funnel batch/streaming pipeline 服务流式增量索引，面向高频数据变更。本平台数据变更由 Action 驱动（实时写 PG），无需独立索引 pipeline。

**建议**：维持一次性导入 + Action 实时写。

### §26 Object Edits / Materializations — 🟡 部分

**现状**：`edits_only_via_actions`✅（NearExpiryProduct/Task/LossReport/Equipment/RepairTicket/User 强制走 Action）；无 user edit history（仅 `entities.updated_at` 触发器）；无 materialization（物化到外部 dataset）。

**理由**：edits-only 是治理核心✅。edit history 在当前规模用 `updated_at` + Action Log（§7 待补）覆盖；materialization 非场景（无外部 BI 消费）。

**建议**：P2 edit history 随 Action Log 一并补；materialization 不引入。

### §27 Aliases — ⛔ 不建议

**现状**：无 Alias 系统；配置用 `.env`（`QWEN_API_KEY` 等）+ `config.yaml`（workspace 级）。

**理由**：Alias 服务 Marketplace 安装期配置覆盖（§28）。本平台无 Marketplace，配置需求由 `.env` + `config.yaml` 直接满足。

**建议**：不引入。

### §28 Marketplace — ⛔ 不建议(MVP)

**现状**：无 Marketplace；分发模型 = industry pack 目录（`workspace/<pack>/`）+ `engine/onboarding.py` 的 `copy_pack_to_workspace` + CLI（`cli.py copy`）。

**理由**：(a) Marketplace 是 Palantir 跨组织分发产品的商业化基础设施；(b) 本平台当前是单组织多工作目录，pack 目录 + onboarding CLI 已覆盖"从模板创建工作目录"需求；(c) Marketplace 涉及产品打包/安装期重映射/版本依赖，复杂度极高。

**建议**：P3 远期。若未来转为多组织 SaaS + 产品化分发，再评估。

### §29 SDK / External Integration — 🔄 转换

**现状**：无独立 SDK；客户端通过 AG-UI（`/api/copilotkit` SSE）+ REST（`/api/admin`、`/api/auth`、`/api/dashboard`、`/api/webhooks`）访问；Tool schema（8 内核 + workspace 聚合）即事实上的"Ontology SDK"——LLM 直接消费。

**理由**：Palantir Ontology SDK 服务外部程序编程式访问。本平台消费者是 LLM，Tool schema 就是 LLM 的 SDK。`Agentic Tool Surfacing`（F-XC-03）反而是本平台的核心能力——自动把 Object/Property/Action 暴露为 Tool。**v2 补充**：Writeback Connectors（F-XC-05）从 P2 上浮 P1——企业零售必须接 ERP/WMS/POS/OMS，mock webhook 在 demo 够，真实场景第一天就要真集成。

**建议**：维持转换。若未来需要外部程序集成（如 ERP 同步），再补 REST SDK。Writeback Connectors 见 §36 P1。

### §30 TypeScript v1/v2 / Python Function 生态 — 🔄 转换

**现状**：仅 Python；compute module（`discount.py`）+ `@tool`（`tools.py`）+ Skill（`automation.py`）三处承载所有计算。

**理由**：多语言 Function 是 Palantir 服务不同开发者偏好的设施。本平台单一 Python 已足够，且 LLM 时代 Tool schema 比 Function 语言更重要。

**建议**：维持单一 Python。

### §31 Multi-Ontology — 🔄 转换

**现状**：单 Ontology 概念；多 workspace（`workspace_name` 硬隔离）事实就是"多 Ontology 容器"；每个 workspace 独立 registry/repository/executor/agent（`bootstrap_workspace` 缓存）；Link 不跨 workspace（与 Palantir Link 不跨 Ontology 约束一致）。

**理由**：Palantir Multi-Ontology 服务大型组织分域建模。本平台 multi-workspace 已覆盖"每个客户/行业独立本体"需求。

**建议**：维持 multi-workspace。Shared Ontology（跨 workspace 共享元素）若未来出现公共本体需求，再评估。

### §32 Metadata — 🟡 部分

**现状**：`status`（active/experimental/deprecated）✅；`visibility`（prominent/normal/hidden）✅（值已定义但 UI 未消费）；`display_name` + 双语 `label`✅；`description`✅；type classes / render hints 缺。

**理由**：基础元数据✅。type classes（PII/Finance 标签）在无 Marking/Purpose 体系下价值有限；render hints 服务 UI 渲染，本平台由 generative UI 动态决定。

**建议**：P2 把 `visibility` 接入 system prompt 生成（让 LLM 优先关注 prominent 实体）；type classes/render hints 不引入。

### §33 跨切能力 — 🟡 混合

见 §36 横切能力评估拆解。

### §34 对标方向（需求文档已有） — 不评估

需求文档 §34 是"对标映射参考表"，非功能需求，跳过。

---

## §35 核心节条目级拆解

> 对判定有内部分化的核心节，展开到 F-XX-NN 条目级。v2 新增 §35-16 / §35-19 / §35-20 / §35-21 四个拆解。

### §35-1 Object Type / Object / Object Set（对应需求 §1）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-OT-01 | Object Type 定义 | ✅ 完全 | `parser.py` TTL 解析✅ |
| F-OT-02 | Object 实例化 | ✅ 完全 | Repository read/write✅ |
| F-OT-03 | Object Set 聚合 | 🟡 部分→P1 | 仅等值过滤；建议加聚合（count/sum/groupby） |
| F-OT-04 | Backing Datasource | ✅ 完全 | PG/JSON 双后端✅ |
| F-OT-05 | MDO 多源 | ⛔ 不建议 | 单后端 per workspace |
| F-OT-06 | Primary Key | ✅ 完全 | 强制 `id` PK |
| F-OT-07 | 编辑允许开关 | ✅ 完全 | `edits_only_via_actions`✅ |
| F-OT-08 | Marketplace 发布 | ⛔ 不建议 | 见 §28 |
| F-OT-09 | Type Groups | 🔄 转换 | `CapabilityDomain` 隐式分组 |
| F-OT-10 | Gaia 集成 | ⛔ 不建议 | Palantir 专有 |
| F-OT-11 | Gotham 集成 | ⛔ 不建议 | Palantir 专有 |
| F-OT-12 | 元数据 | ✅ 完全 | status/visibility/label✅ |
| F-OT-13 | Export/Import | 🟡 部分→P2 | admin CRUD 已支持运行时；整体导出导入可补 |
| F-OB-01/02 | Object 来源 | ✅ 完全 | Action + import 双通道✅ |
| F-OB-03 | Writeback Dataset | ⛔ 不建议 | OSv2 原生编辑模式，本平台天然支持 |
| F-OB-04 | 冲突解决 | ⛔ 不建议 | 单写者 upsert，无并发冲突 |
| F-OB-05 | 用户编辑历史 | 🟡 部分→P2 | `updated_at` + 未来 Action Log |
| F-OB-06 | Schema Migrations | 🟡 部分 | `db.migrate()` 幂等 CREATE IF NOT EXISTS；无增量迁移框架 |
| F-OBDB-01/02/03 | Object Storage V1/V2/迁移 | ⛔ 不建议 | 无 V1 包袱 |

### §35-2 Property（对应需求 §2）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-PR-01 | Local Property | ✅ 完全 | `PropertyDef`✅ |
| F-PR-02 | Shared Property | ⛔ 不建议→V2 | 命名约定替代（建模规范 §3.3 v2） |
| F-PR-03 | Value Type | ⛔ 不建议 | `type` 是自由字符串，枚举未声明 |
| F-PR-04 | Base Types | 🟡 部分 | string/int/float/bool/date/datetime/dict✅；GeoPoint/Media/Attachment 缺 |
| F-PR-05 | Struct Property | ⛔ 不建议 | 见 §3 |
| F-PR-06 | Required Property | 🟡 部分→P1 | 无 per-property required；Action parameter 有 required |
| F-PR-07 | Edit-only Property | ✅ 完全 | `edits_only_via_actions` + per-property `write_except`✅ |
| F-PR-08 | Mandatory Control | ⛔ 不建议 | 业务校验由 submission_criteria 承载 |
| F-PR-09 | Property Reducers | 🟡 部分→P1 | 无框架；dashboard 手写 groupby；建议纳入 Tool |
| F-PR-10/11 | Derived Property | 🔄 转换 | 由 Tool 计算（如 `query_near_expiry` 算折扣） |
| F-PR-12 | Value Formatting | ⛔ 不建议 | generative UI 动态格式化 |
| F-PR-13 | Conditional Formatting | ⛔ 不建议 | 同上 |
| F-PR-14/15 | Property Metadata / Render Hints | ⛔ 不建议 | generative UI 决定渲染 |
| F-PR-16 | Statuses 标识 | 🟡 部分 | 枚举类型引用但未声明 |
| F-PR-17 | Type Classes | ⛔ 不建议 | 无 Marking 体系，价值有限 |
| F-VT-01/02/03 | Value Type 细节 | ⛔ 不建议 | 见 F-PR-03 |
| F-SP-01~04 | Shared Property 细节 | ⛔ 不建议→V2 | 见 F-PR-02 |

### §35-4 Link Type（对应需求 §4）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-LT-01 | Link Type 定义 | ✅ 完全 | `rdfs:Property` + domain/range/via✅ |
| F-LT-02 | Link 实例 | ✅ 完全 | 虚拟外键实现✅ |
| F-LT-03 | Cardinality | 🟡 部分→P2 | 无显式字段；由 via 数据形态隐式决定；建模规范 §4.4 列 v2 |
| F-LT-04 | 外键 Link | ✅ 完全 | 1:1/1:N via 外键✅ |
| F-LT-05 | N:M join table | ⛔ 不建议 | 场景未出现；当前 N:M 用中间实体表达 |
| F-LT-06 | 自引用 Link | ✅ 完全 | `parent_of`（OrgUnit→OrgUnit）✅ |
| F-LT-07 | Link Metadata | ✅ 完全 | label/comment/status✅ |
| F-LT-08 | Link 编辑权限 | ✅ 完全 | `can_traverse_link`✅ |
| F-LT-09 | Marketplace 打包 | ⛔ 不建议 | 见 §28 |
| F-LT-10 | Interface Link 约束 | ⛔ 不建议→V2 | 见 §5 |
| F-LT-11 | Link Merging | ⛔ 不建议 | 属 Map 功能 |

### §35-7 Action Type（对应需求 §7）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-AT-01 | Action 定义（原子） | ✅ 完全 | 声明式 + 顺序副作用✅ |
| F-AT-02 | Action Type 模板 | ✅ 完全 | YAML + `ActionDefinition`✅ |
| F-AT-03 | 多 Object 多 Property 编辑 | ✅ 完全 | `edits_object_types[]` + 多副作用✅ |
| F-AT-04 | 创建/修改 Action Type | ✅ 完全 | admin CRUD + YAML✅ |
| F-AT-05 | Object View 嵌入 | 🔄 转换 | generative UI 按钮区✅ |
| F-AT-06 | 默认值/隐藏字段 | 🟡 部分 | parameter default✅；current-object 隐藏未实现 |
| F-AT-07 | Action 表单 | 🔄 转换 | generative UI 预览卡片✅ |
| F-AT-08~14 | Parameters 全系 | 🟡 部分 | 类型/required/default/constraint✅；dropdown 过滤/override 缺 |
| F-AT-15~21 | Rules（Create/Modify/Delete/Link/Function） | 🟡 部分 | create/modify/delete object + state_transition✅；create/delete link via update_object✅；Function rule 转换（见 §8） |
| F-AT-22 | Rules 值来源 | 🟡 部分 | parameter/static✅；current-user/current-time 缺 |
| F-AT-23 | Rules 顺序 | ✅ 完全 | 顺序副作用✅ |
| F-AT-24 | Interface Rules | ⛔ 不建议→V2 | 见 §5 |
| F-AT-25~28 | Submission Criteria | ✅ 完全 | roles + conditions + 全操作符（is/is_not/gte/lte/gt/lt/matches/includes/value_ref）✅；嵌套 AND/OR 列 v3 |
| F-AT-29/30 | Trigger Schedule Build | ⛔ 不建议 | 排程非场景 |
| F-AT-31 | Action Permissions | ✅ 完全 | `can_execute_action`✅ |
| F-AT-32 | Action 调用审计 | 🟡 部分→**P0** | **缺 Action Log**（关键补齐项） |
| F-AT-33 | Configure Sections | ⛔ 不建议 | generative UI 动态分组 |
| F-AT-34/35 | Media/Attachment Upload | ⛔ 不建议 | 场景未出现 |
| F-AT-36 | **Action Log** | ⛔ 缺→**P0** | **核心补齐**：每次 Action 物化为可查询 object（决策即数据） |
| F-AT-37 | **Action Reverts** | ⛔ 缺→P1 | Undo 能力；依赖 Action Log |
| F-AT-38 | User Edit History | 🟡 部分→P2 | 见 F-OB-05 |
| F-AT-39 | Conflict Resolution | ⛔ 不建议 | 单写者无冲突 |
| F-AT-40/41 | **Action Monitoring/Metrics** | ⛔ 缺→**P0**（v2 上浮） | **成功率/时延监控——agent 运维可观测性核心** |
| F-AT-42 | Inline Edits | 🔄 转换 | Preview→Confirm 已覆盖 |
| F-AT-43 | Scale & Property Limits | 🟡 部分 | 无显式上限；当前规模无需 |
| F-AT-44 | Marketplace 打包 | ⛔ 不建议 | 见 §28 |
| F-AT-45 | Branching Action Types | ⛔ 不建议→V2 | 见 §23 |

### §35-8 Function（对应需求 §8）— 整体转换

> 49 条 F-FN 条目不逐条展开，整体判定为 🔄 转换。映射关系：

| Palantir Function 用例 | 本平台替代 |
|---|---|
| 返回 Object Set 供 Workshop | `query_*` Tool（LLM 调用取数） |
| function-backed column（派生列） | `@tool` 计算（如 `query_near_expiry` 算折扣） |
| Workshop 图表聚合 | LLM 推理 + generative UI（或 Tool 聚合增强） |
| function-backed action（复杂跨对象编辑） | `automation.py` 后台 job + Action 编排 |
| 外部系统查询 | `external_call` 副作用 + webhook |
| Pipeline sidecar | Python compute module（`discount.py`） |
| LLM 调用（Language Models） | LLM 是本平台核心，直接由 agent 调用 |

**不引入**：Function 版本化 / Function monitoring / Function branching / Unit testing 框架——这些服务 Function 作为 ontology 元素的治理，既然不引入 Function 元素，配套治理亦不引入。Python compute module 的测试用标准 pytest 即可。

### §35-10 Permission（对应需求 §10）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-PM-01 | Ontology Permissions（schema 层） | ✅ 完全 | `can_use_tool`/`can_execute_action` 等✅ |
| F-PM-02 | Ontology Roles | ✅ 完全 | role + read/write_except✅ |
| F-PM-03/05 | Project-Based Permissions | ⛔ 不建议 | 单项目部署 |
| F-PM-04 | Legacy Ontology Roles | ⛔ 不建议 | 无遗留 |
| F-PM-06 | Value Type Permissions | ⛔ 不建议 | 无 Value Type |
| F-PM-07 | Object Security Policies | ⛔ 不建议 | 重型动态策略 |
| F-PM-08 | Restricted-View-Backed | ⛔ 不建议 | 用 org_unit_id RLS 替代 |
| F-PM-09 | MDO 权限 | ⛔ 不建议 | 无 MDO |
| F-PM-10 | Object Security 管理 UI | 🟡 部分→P2 | admin 数据浏览器只读；权限管理 UI 缺 |
| F-PM-11 | Marking | ⛔ 不建议 | MAC/CBAC 重型 |
| F-PM-12 | Purpose | ⛔ 不建议 | 用途控制重型 |
| F-PM-13 | 行级/列级限制 | ✅ 完全 | org_unit_id RLS + property 掩码✅ |
| F-PM-14 | Dynamic Security | ⛔ 不建议 | 运行时动态策略重型 |
| F-PM-15 | Log Access Control | ⛔ 不建议 | 无独立日志系统 |
| F-PM-16 | Tool Invocation Security | ✅ 完全 | 5 资源类型权限评估✅ |
| F-PM-17 | Action Permission Checks | ✅ 完全 | `_check_submission`✅ |
| **F-PM-18**（v2 新增） | **Agent 身份**（服务账号） | 🟡 部分→**P1** | 当前 actor 仅从用户推导；**agent 需作为一等主体被授权/审计/限流** |

### §35-14 Object View（对应需求 §14）— 整体转换

> 23 条 F-OV 条目整体判定 🔄 转换。核心映射：

| Palantir Object View 概念 | 本平台替代 |
|---|---|
| Standard Object View | `query_entity` → `entity_detail` → generative UI 键值卡片 |
| Configured Object View（Workshop module） | 不需要——generative UI 动态渲染 |
| Full vs Panel 形态 | 单一卡片形态，前端按场景布局 |
| Properties Widget | generative UI 键值网格 |
| Links Widget | `traverse_relation` → 关系卡片 |
| Actions Widget | `execute_action` → 预览/确认卡片 |
| Tabs/Profiles/Sidebar | 不需要——LLM 对话流替代固定 tab |
| Comment on Objects | 🟡 部分→P2 | 可作为 Action + object 补 |
| Marketplace 打包 | ⛔ 不建议 | 见 §28 |

**v2 补充**：generative UI 服务 agent 对话面；**人用操作台的实体详情页**（结构化、非对话气泡）是另一条线（P1，与 §11 联动）。

**不引入**：Object View 版本化 / branching / 配置层——这些服务 Workshop 配置编排，generative UI 无需配置层。

### §35-16 Events and Time Series（对应需求 §16）— v2 新增拆解

> v1 整节⛔；v2 按轴 3（建模 vs 可视化分离）拆分。

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-EV-01 | Event Object Type 定义 | 🟡 部分→**P1** | 引入 timestamped Event Object Type（start/end 时间戳 + severity type class） |
| F-EV-02 | Event 配置 | 🟡 部分→P1 | Ontology Manager/admin CRUD 配置（已有运行时建模入口） |
| F-EV-03 | Time Series Property | 🟡 部分→**P1** | 引入时序 Property（measure over time）；零售 POS/库存/价格刚需 |
| F-EV-04 | Thresholds | 🟡 部分→P2 | 时序 measure 上配阈值指示穿越 |
| F-EV-05 | Linked-event 探索 | 🔄 转换 | LLM 通过 Tool 取事件 + 推理；非图badge |
| F-EV-06 | Time Series 探索 | 🔄 转换 | LLM 通过 Tool 取时序 + 推理 |
| F-EV-07 | Time Selection & Compare | ⛔ 不建议 | timeline UI 不建；LLM 用时间参数查询 |
| F-EV-08 | Timeline Widget | ⛔ 不建议 | Vertex 前端，不建 |
| F-EV-09 | Timeline Playback | ⛔ 不建议 | 时间游标 UI，不建 |

**核心**：P1 引入时序建模原语（Event Object Type + Time Series Property），让 POS/库存/价格历史成为一等数据；timeline 可视化 UI 全部⛔。

### §35-19 Foundry Rules（对应需求 §19）— 整体转换 + v2 补批量层

> 30 条 F-FR 条目整体判定 🔄 转换。v2 修订：补**轻量声明式批量规则层**。

核心映射：

| Palantir Foundry Rules 概念 | 本平台替代 |
|---|---|
| 声明式规则（单次校验） | Action `submission_criteria.conditions`✅ |
| **声明式批量规则（扫描全量）** | **v2 新增 P1**：轻量规则层（condition + scope + 触发的 Action，scheduler 批量评估） |
| Monitors（定期评估） | `AutomationScheduler` + `automation.py` job✅ |
| Inputs（Object Set 输入） | `Repository.read` + filter |
| Conditions（触发条件） | submission_criteria + job 内 Python 逻辑 |
| Activity（规则历史） | 未来 Action Log（§7 P0） |
| Notifications | `notification` 副作用（§9 P0 补投递） |
| Actions（规则触发 Action） | `automation.py` 直接调 `executor.execute`✅ |
| Rule Logic 表达式 | submission_criteria 操作符✅ |
| Workflow Configuration | `ValueChainProcess` + 状态机✅ |
| Workshop Rule Editor | 不需要——规则声明在 YAML |
| Proposal 审查 | 不需要——submission_criteria 是运行时校验，非 PR 流程 |
| 时间序列规则 | 🟡 部分（见 §16） |
| Legacy Taurus | ⛔ 不建议（无遗留） |

**v2 关键补齐**：轻量声明式批量规则层——让"扫描所有低于安全库存的商品并触发补货""扫描所有临期商品并预警"这类**无 LLM 在环**的确定性规则可声明、可调度、可审计。区别于 Action 内的 submission_criteria（单次提交校验）。

### §35-20 Object Monitors → agent ops 投影（对应需求 §20）— v2 新增拆解

> v1 整节⛔；v2 修订为 🔄 转换——不建 Monitor 对象，但把 condition→检测→告警→Action 模式投影为 agent ops 仪表盘。

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-OM-01 | Monitor 资源 | ⛔ 不建议 | 不建 Monitor 对象（Palantir 已 Sunset） |
| F-OM-02 | Monitor Inputs | 🔄 转换 | → 声明式批量规则的 scope（见 §35-19） |
| F-OM-03 | Monitor Conditions | 🔄 转换 | → 声明式批量规则的 condition |
| F-OM-04 | Evaluation（realtime/polling） | 🔄 转换 | → `AutomationScheduler` 间隔评估 |
| F-OM-05 | Activity | 🔄 转换 | → Action Log（§7 P0） |
| F-OM-06 | Notifications | ✅ 完全→P0 | → §9 notification 投递（人机协同底线） |
| F-OM-07 | Monitor-triggered Actions | ✅ 完全 | → `automation.py` 调 `executor.execute`✅ |
| **F-OM-08**（v2 新增） | **Agent ops 仪表盘** | ⛔ 缺→**P1** | **agent 行为监控**：异常时间改数据？批量失败？token 异常？投影为运维仪表盘 + 告警规则 |

**核心**：Monitor 对象不建；但"监控 agent 行为 + 异常告警"的**能力**以 agent ops 仪表盘形式落地（P1），与 §7 Action Metrics、§9 notification、§24 Usage/Limits 协同，构成 agent 运维闭环。

### §35-21 Map（对应需求 §21）— v2 新增拆解

> v1 整节⛔；v2 按轴 3（建模 vs 可视化分离）拆分。

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-MAP-01 | 地理数据建模 | 🟡 部分→**P2** | Store 经纬度、区域多边形、商圈 catchment；当前 `Store.address` 纯字符串是建模缺口 |
| F-MAP-02 | GeoPoint/GeoShape Property | 🟡 部分→P2 | 见 F-PR-04 Base Types 缺 GeoPoint |
| F-MAP-03 | Map Layer Editor | ⛔ 不建议 | 地图前端不建 |
| F-MAP-04 | 标注/形状 | ⛔ 不建议 | 地图前端不建 |
| F-MAP-05 | 时间线事件/轨迹 | ⛔ 不建议 | 地图前端 + timeline 不建 |
| F-MAP-06 | Search Arounds（地理） | ⛔ 不建议 | 地图交互不建；LLM 用地理 filter 查询 |
| F-MAP-07 | 模板 + Workshop widget | ⛔ 不建议 | 见 §14 |

**核心**：P2 补地理数据建模（GeoPoint Property + Store 经纬度）；地图可视化前端全部⛔。

### §35-23 Branching / Change Management（对应需求 §23）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-BR-01 | Branching Overview | ⛔ 不建议→V2 | status + review 替代 |
| F-BR-02 | Review Proposals | ⛔ 不建议→V2 | 代码 review 替代 |
| F-BR-03 | Legacy Branches | ⛔ 不建议 | 无遗留 |
| F-BR-04 | Global Branching | ⛔ 不建议→V2 | 远期 |
| F-BR-05 | Branching 资源 | ⛔ 不建议→V2 | 远期 |
| **F-BR-06**（v2 新增） | **安全变更机制**（轻量） | 🟡 部分→**P1** | 变更前校验下游引用 + 灰度发布 + 快速回滚（与 §26 edit history 同一件事） |
| F-CM-01 | Save Changes | ✅ 完全 | admin CRUD✅ |
| F-CM-02 | Review/Restore Changes | 🟡 部分→**P1** | 无历史回滚；`invalidate_workspace` 仅缓存失效；随安全变更机制补 |
| F-CM-03 | Ontology Manager Overview | 🔄 转换 | admin 控制台（`/admin`）|
| F-CM-04 | Navigation | 🔄 转换 | Objects/Links/Actions 三 tab✅ |
| F-CM-05 | Viewing Usage | ⛔ 缺→P2 | 无反向引用追踪 |
| F-CM-06 | Export/Edit/Import | 🟡 部分 | admin CRUD 运行时编辑✅；整体导出导入缺 |
| F-CM-07 | Ontology Cleanup | ⛔ 缺→P2 | 无未使用检测 |
| F-CM-08 | Migrate Project Permissions | ⛔ 不建议 | 见 F-PM-03 |

---

## §36 横切能力评估（对应需求 §33）

| 条目 | 名称 | 判定 | 现状 / 建议 |
|---|---|---|---|
| F-XC-01 | Decision Lineage | 🟡 部分→**P0**（v2 上浮） | **治理第一问**："agent 凭什么改了这条数据？"。Action Log（§7 P0）是基础；端到端谱系（哪个 LLM 版本/哪个 Skill/哪些输入/哪个用户会话触发）是企业上线 agent 的合规前提 |
| F-XC-02 | Multi-tenancy | ✅ 完全 | `workspace_name` 硬隔离 + `org_unit_id` RLS✅ |
| F-XC-03 | **AI-driven Tool Surfacing** | ✅ 完全 | **本平台核心**：ontology → system prompt → LLM 自动选 Tool |
| F-XC-04 | Scenario Staging | ⛔ 不建议 | Preview→Confirm 替代（见 §17） |
| F-XC-05 | Writeback Connectors | 🟡 部分→**P1**（v2 上浮） | `external_call` 副作用骨架✅；**ERP/WMS/POS/OMS 连接器是企业零售第一天刚需** |
| F-XC-06 | Training Data for AI | ⛔ 不建议 | 模型微调非本平台定位 |
| F-XC-07 | Agent Memory Refinement | 🟡 部分 | `MemorySaver` 短期记忆✅；长期记忆精化远期 |
| F-XC-08 | Graduated Autonomy | 🟡 部分→**P2**（v2 上浮） | **企业引入 agent 的信任构建路径**就是渐进自治：只读→受限写（Preview→Confirm）→自主写→自主多步。当前 Preview→Confirm 已是中间档，差"按角色/场景配置自治级别" |
| F-XC-09 | Auditability | 🟡 部分→P0 | auth 审计✅；**Action 审计缺**（§7 P0） |

---

## §37 优先级建议（v2 全表重排）

> 仅排序"完全/部分实现"项的落地先后，不涉实施设计。v2：P0 从 2 项扩到 5 项，P1 从 7 项扩到 13 项。

### P0 — MVP 补齐（治理/运维闭环或架构已要求但实现缺失）

| 项 | 来源 | 理由 |
|---|---|---|
| **Action Log**（F-AT-36） | §7 | 治理闭环关键——决策即数据，审计追溯基础。`auth_audit.py` 已为 auth 事件落地，Action 审计是对应缺口 |
| **Auditability 补齐**（F-XC-09） | §36 | 随 Action Log 一并闭环 |
| **Decision Lineage**（F-XC-01） | §36 | **v2 上浮**——agent 治理第一问；端到端谱系（LLM 版本/Skill/输入/会话）是企业上线 agent 的合规前提 |
| **Action Metrics**（F-AT-40/41） | §7 | **v2 上浮**——agent 运维可观测性核心；生产环境 agent 不能是黑箱 |
| **notification 投递**（F-SE-01~09） | §9 | **v2 上浮**——人机协同底线；agent 做关键操作必须通知到人，当前 no-op 是真实风险 |

**依赖**：Action Log 物化为可查询 object（类比 `[LOG]`-前缀类型），自动 link 到被编辑对象，记录 LLM 版本/Skill/输入/会话上下文（Decision Lineage）。Action Metrics 从 Action Log 聚合。notification 投递复用 Action Log 的事件触发。

### P1 — V1 增强（显著提升 agent 能力或企业零售覆盖度）

| 项 | 来源 | 理由 |
|---|---|---|
| **Object Set 聚合**（F-OT-03） | §1 | `query_entity` 加 count/sum/groupby，让 LLM 回答"多少/总量"类问题 |
| **Property Reducers**（F-PR-09） | §2 | 随 Object Set 聚合一并落地 |
| **Required Property**（F-PR-06） | §2 | 建模完整性校验 |
| **external_call 投递**（F-SE-01~09） | §9 | 真实 webhook sink 是集成前提 |
| **Action Revert**（F-AT-37） | §7 | Undo 能力，依赖 Action Log |
| **Agent 身份**（F-PM-18） | §10 | **v2 新增**——agent 作为一等主体被授权/审计/限流（服务账号） |
| **Events / 时序建模**（F-EV-01/03） | §16 | **v2 新增**——零售是时序密集业务（POS/库存/价格） |
| **批量声明式规则层**（F-FR-批量） | §19 | **v2 新增**——无 LLM 在环的确定性规则（补货点/合规扫描/临期预警） |
| **Agent ops 仪表盘**（F-OM-08） | §20 | **v2 新增**——agent 行为监控 + 异常告警（与 Action Metrics/notification 协同） |
| **安全变更机制**（F-BR-06/F-CM-02） | §23 | **v2 上浮**——生产本体演进：变更校验 + 灰度 + 回滚 |
| **Usage / Limits**（F-UL-01~） | §24 | **v2 新增**——LLM 成本治理（token 追踪/速率/配额/熔断），企业上 agent 第一道门槛 |
| **Writeback Connectors**（F-XC-05） | §36 | **v2 上浮**——ERP/WMS/POS/OMS 真实集成，企业零售第一天刚需 |
| **人用操作台**（§11/§14） | §11/§14 | **v2 新增**——店长/区经理/运营的看板/数据探索/报表/实体详情页（非 agent 对话面） |

### P2 — V2 方向（roadmap 已列 🔜）

| 项 | 来源 | 理由 |
|---|---|---|
| **Semantic Search / RAG**（F-SS-01~08） | §13 | schema 已预留 vector；场景驱动启用 |
| **Ontology Search 增强**（F-OS-01） | §12 | 多字段/范围/排序/分页 filter |
| **多跳遍历 API**（F-VE-多跳） | §15 | **v2 新增**——供应链穿透（供应商→商品→门店→库存），`traverse_relation` 扩 N 跳 |
| **Cardinality 显式声明**（F-LT-03） | §4 | 建模规范 §4.4 列 v2 |
| **Interface 元数据**（F-IF-01~06） | §5 | 架构/规范/roadmap 一致列 v2 |
| **Shared Property**（F-PR-02） | §2 | 命名约定替代 → 集中管理 |
| **Git 式 Branching**（F-BR-01~05） | §23 | 安全变更机制 → 完整分支（远期） |
| **Object Edit History**（F-OB-05） | §26 | 随 Action Log 增强 |
| **Permission 管理 UI**（F-PM-10） | §10 | admin 数据浏览器从只读 → 可编辑 |
| **Ontology Usage/Cleanup**（F-CM-05/07） | §23 | 反向引用追踪 + 未使用检测 |
| **visibility 接入 prompt**（F-MD-03） | §32 | 让 LLM 优先关注 prominent 实体 |
| **地理数据建模**（F-MAP-01/02） | §21 | **v2 新增**——门店网络/配送范围；GeoPoint Property + Store 经纬度 |
| **时间分配原语**（F-DS-时间） | §22 | **v2 新增**——排班/补货周期/促销档期窗口 |
| **Graduated Autonomy**（F-XC-08） | §36 | **v2 上浮**——按角色/场景配置自治级别 |

### P3 — 远期 / 按需

| 项 | 来源 | 触发条件 |
|---|---|---|
| Marketplace（§28） | §28 | 转为多组织 SaaS + 产品化分发 |

> **v2 对比**：P3 从 4 项收缩到 1 项（Events/Map/Scheduling 均上浮 P1/P2）。

---

## §38 与现有文档的联动建议

> 本评估产出的判定与优先级，建议回填到以下文档（具体回填动作待后续计划）。v2 新增 agent 治理/运维联动。

### 38.1 对 [`00-architecture.md`](./00-architecture.md)

- **§0 核心判断**：补充本评估的四档判定准则 + **v2 三轴方法论**（架构轴/场景轴/建模-可视化分离轴/agent 治理运维轴）作为"KEEP/DEMOTE/DROP"的形式化定义。
- **§2 概念分工表**：Function 行明确标注"转换判定——Tool+Skill+compute module 替代"，引用本评估 §35-8。
- **附录 B**：把本评估的"P0/P1"项回填为"v2 落地待办"。
- **v2 新增章节"agent 治理与运维"**：覆盖 (a) agent 身份与服务账号（§10）；(b) Decision Lineage 与审计闭环（§36）；(c) 渐进自治与 Preview→Confirm 的位置（§36 F-XC-08）；(d) agent 可观测性（Action Metrics + agent ops 仪表盘 + Usage/Limits）。

### 38.2 对 [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md)

- **§1.3 资源类型清单**：明确 Struct 标注"评估为不建议"（当前文档未提及 Struct，可补一条显式排除说明）。
- **§3.3 Shared Property**：引用本评估 §35-2 的"命名约定替代 → V2 集中管理"判定。
- **§5.4 submission_criteria**：补嵌套 AND/OR 标注为 v3（当前操作符集已 ✅）。
- **v2 新增"时序与事件建模"小节**：Event Object Type + Time Series Property 的建模规范（§16 P1）。
- **v2 新增"批量声明式规则"小节**：区别于 submission_criteria 的批量规则层规范（§19 P1）。

### 38.3 对 [`roadmap.md`](./roadmap.md)

- **§阶段总览表**：把本评估的 P0（Action Log + Auditability + Decision Lineage + Action Metrics + notification 投递）/ P1 全部 13 项回填为 V1 周期项。
- **§3 本体深化**：Cardinality / Interface / Shared Property 的 v2 标注与本评估 P2 对齐。
- **新增"Palantir 对标"小节**：引用本评估作为对标依据，让 roadmap 的优先级有外部参照。
- **v2 新增"agent 运维"小节**：覆盖 Usage/Limits + Action Metrics + agent ops 仪表盘 + Decision Lineage——这些是 agent 上生产的运维闭环，当前 roadmap 完全缺失这一轴。

---

## 附录：术语对照（v2 更新）

| Palantir 术语 | 本平台对应 | 判定 |
|---|---|---|
| Object Type | Object Type（TTL `rdfs:Class`） | ✅ 完全 |
| Property | Property（`PropertyDef`） | 🟡 部分 |
| Link Type | Link Type（TTL `rdfs:Property` + via） | 🟡 部分 |
| Interface | — | ⛔ V2 |
| Struct | — | ⛔ 不建议 |
| Action Type | Action Type（YAML） | ✅ 完全 |
| Function | Tool + Skill + compute module | 🔄 转换 |
| Object Set | Repository.read + filter | 🟡 部分 |
| Object Explorer | query tools + generative UI + **人用操作台** | 🔄 转换 |
| Object View | renderToolCalls + **人用操作台实体详情** | 🔄 转换 |
| Workshop | — | ⛔ 不建议 |
| Vertex/Graphs | traverse_relation（单跳）+ **多跳遍历 API（P2）** | ⛔图可视化 / 🟡多跳 |
| Events/Time Series | **Event Object Type + Time Series Property（P1）** | 🟡建模 / ⛔回放 |
| Map | **GeoPoint Property + Store 经纬度（P2）** | 🟡建模 / ⛔前端 |
| Dynamic Scheduling | AutomationScheduler + **时间分配原语（P2）** | 🟡 部分 |
| Foundry Rules | submission_criteria + automation.py + **批量声明式规则层（P1）** | 🔄 转换 |
| Object Monitors | **agent ops 仪表盘 + 告警规则（P1）** | 🔄 转换 |
| Ontology Branching | status + deprecation + admin CRUD + **安全变更机制（P1）** | 🟡 部分 |
| Usage/Limits | **token 追踪 + 速率/配额/熔断（P1）** | 🟡 部分 |
| Marketplace | industry pack 目录 + onboarding CLI | ⛔ 不建议 MVP |
| Ontology SDK | Tool schema（AG-UI） | 🔄 转换 |
| Multi-Ontology | multi-workspace | 🔄 转换 |
| Permissioning | PermissionEvaluator（RBAC×ABAC + RLS + 列级）+ **agent 身份（P1）** | ✅ 完全 |
| Semantic Search | schema 预留 vector | 🟡 部分 V2 |
| Writeback Connectors | external_call + **ERP/WMS/POS 连接器（P1）** | 🟡 部分 |
| Decision Lineage | **Action Log + 端到端谱系（P0）** | 🟡 部分 |
| Graduated Autonomy | Preview→Confirm + **自治级别配置（P2）** | 🟡 部分 |
