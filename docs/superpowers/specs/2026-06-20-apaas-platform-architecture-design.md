# OntologyAgent APaaS 平台总体架构设计

> **状态**：已与用户逐节确认，待 review
> **日期**：2026-06-20
> **性质**：从"单 vertical demo + 多 vertical 内核"升级为"多客户 APaaS + 行业包 + 客户自定义"的**总体架构骨架**。只定架构与 phase 拆分，不含详细实体清单（各 phase 独立 spec 细化）。
> **前置文档**：
> - `docs/superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md`（单 vertical 目标架构，内核多 vertical 改造已完成）
> - `docs/业务本体建模规范.md`（建模规范）
> - `docs/manual/`（接入手册）

---

## 0. 定位与目标

**OntologyAgent 是一个本体驱动的多客户 APaaS（Application Platform as a Service）Agent 平台。** 平台提供通用内核 + 可插拔行业包；每个客户（企业）copy 行业包作为起点，按自身业务调整本体语义，灌入数据，启动专属 Agent 实例，即可用对话 + 自动化 + 看板进行业务运营。

**为什么是 APaaS 而非 SaaS**：SaaS 是"平台提供一套标准应用，客户配置参数使用"；APaaS 是"平台提供建模与运行能力，客户**构建自己的应用**（自定义本体/流程/规则）"。本平台的核心特征——客户 copy 行业包后**任意调整本体语义**（加/删/改 Object/Action/Skill）、灌自己的数据、跑专属 Agent——正是 APaaS。行业包是**起点模板**而非标准应用，客户是本体的 owner。

**一句话**：内核（建模引擎）+ 行业包（领域模板）+ 客户配置（copy→改→灌→接DB→启）= 每个客户一个专属 AI 业务运营平台。

### 核心诉求

1. **多客户 APaaS**：一个平台服务多个企业客户，客户间全栈隔离。
2. **业务模型因客户而异**：同一行业（零售）的客户，其本体（实体/关系/规则）不同——平台不强制一套标准模型，而是提供行业包作起点，客户 copy 后按实际调整。
3. **零售领域分层**：业务按价值链组织（营销/供应链/组织/财务能力域），工作流跨域编排。
4. **Agent 驱动运营**：不止查询助手，还要主动自动化 + 运营看板。

---

## 1. 平台分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 客户配置层（Customer Config）                                    │
│ 每客户：copy 行业包 → 调整本体语义 → 灌数据 → 接DB → 启 agent    │
│ 客户成为自己本体的 owner（标准包是模板，copy 后断开依赖）          │
├─────────────────────────────────────────────────────────────────┤
│ 行业包层（Industry Pack）—— 可插拔模板                           │
│ retail-pack：按价值链组织的能力域 + 跨域价值链流程                │
│ 未来：logistics-pack / manufacturing-pack                        │
├─────────────────────────────────────────────────────────────────┤
│ 内核层（Kernel）—— 已验证（85 测试），升级 customer/tenant 维度   │
│ 多租户 Repository / 声明式 Executor / Scheduler / Agent harness    │
│ Tool/Skill 体系 / bootstrap 注册 / OntologyRegistry               │
├─────────────────────────────────────────────────────────────────┤
│ 运营层（Operations）—— 横切，跨三层                              │
│ 对话入口（CopilotKit）+ 定时自动化（Scheduler）+ 运营看板          │
│ + 本体管理界面（admin）                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 关键概念重定义（现有→目标）

| 现有概念 | 目标概念 | 变化 |
|---|---|---|
| vertical（clearance） | **CapabilityDomain**（能力域）+ **ValueChainProcess**（价值链流程） | 拆双轴：域提供原子，流程跨域编排 |
| VerticalConfig | **IndustryPack** 含多个 CapabilityDomain + ValueChainProcess | 升一级：行业包聚合 |
| tenant_id（字符串软隔离） | **Customer（租户硬隔离）+ OrgUnit（权限范围）** | 升为分层权限主体 |
| 单 Agent 实例 | **per-customer Agent 实例** | 按客户构建，全栈隔离 |
| 无行业包概念 | **IndustryPack**（可插拔模板，客户 copy 起点） | 新增 |

---

## 2. 双轴模型：能力域 + 价值链流程

### 2.1 为什么用价值链而非职能域

企业的大量业务流程是**跨域**的（出清涉及营销定价 + 供应链库存 + 组织执行 + 财务损耗）。按职能域切会把跨域流程强行归到某域，不符合现实。

**双轴**：
- **能力域（Capability Domain）**：提供可复用的原子 Object/Link/Action/规则。是被流程调用的"能力池"。
- **价值链流程（Value Chain Process）**：端到端跨域编排，调用多个域的 Action。有自己的状态机和 Skill。

### 2.2 零售行业包的标准结构（retail-pack）

基于业界零售运营模型（NRF ARTS / SAP IS-Retail / Gartner 共识）+ Michael Porter 价值链：

```
retail-pack（行业包 = 模板）
├── 能力域（Capabilities，提供原子 Object/Action/规则）
│   ├── 营销域 Marketing
│   │   ├── Object: Product, PriceRule, Promotion, Member...
│   │   ├── Action: calculate_discount, apply_promotion, award_points...
│   │   └── 规则源: discount_rules.json（域内单一事实源）
│   ├── 供应链域 Supply Chain
│   │   ├── Object: Inventory, PurchaseOrder, Shipment...
│   │   └── Action: deduct_stock, receive_goods, transfer_stock...
│   ├── 组织域 Organization
│   │   └── Object: Employee, OrgUnit(Brand>Region>Store)...
│   └── 财务域 Finance
│       └── Object: LedgerEntry, CostRecord, LossReport...
│
└── 价值链流程（Value Chain Processes，跨域编排）
    ├── 出清 clearance
    │   ├── 编排: marketing.定价 → supply_chain.库存 → organization.执行 → finance.损耗
    │   ├── 状态机: created→approved→in_progress→completed/scrapped
    │   └── Skill: clearance-workflow
    ├── 采购 procurement
    │   └── 编排: supply_chain.下单 → organization.审批 → finance.付款 → supply_chain.收货
    └── 会员运营 member_ops
        └── 编排: marketing.积分 → marketing.券 → finance.核销
```

### 2.3 业务分层与原子 Action 分化

业务是分层的（域→子域→业务流程）。同一概念在不同叶子节点的**原子定义不同**：

| 概念 | 零售销售叶子 | 批发销售叶子 | 会员忠诚度叶子 |
|---|---|---|---|
| "折扣" | T1/T2/T3 减扣百分比 | 阶梯批量价 | 积分倍率 |

**设计原则**：单一事实源在**域内**成立，不跨域/跨叶子强行统一。每个叶子域有自己的规则数据源（如 `retail_sales/discount_rules.json` vs `wholesale/tier_pricing.json`），计算逻辑各属其域。

### 2.4 数据结构

| 结构 | 职责 | 复用现有 |
|---|---|---|
| **IndustryPack** | 聚合多个 CapabilityDomain + 多个 ValueChainProcess；声明本行业能力域/流程清单 | 类似现有 verticals/ 目录，升级为 packs/ |
| **CapabilityDomain** | 提供原子 Object/Link/Action + 域内规则源；**不含工作流/状态机** | 拆自现有 VerticalConfig 的 ontology/actions 部分 |
| **ValueChainProcess** | 跨域编排：声明调用的 Action + 状态机 + Skill | 拆自现有 VerticalConfig 的 state_machine + workflow 部分 |

**关键解耦**：现有 VerticalConfig 把"本体定义 + 工作流 + 状态机"揉在一起；拆开后域可被多流程复用（营销域的折扣能力既被出清调用，也被促销调用）。

### 2.5 clearance 迁移示例

```
现有:                              目标:
verticals/clearance/               packs/retail/
  config.py (揉在一起)               ├── domains/
  ontology/store.ttl                  │   ├── marketing/  (Product, PriceRule, 折扣Action)
  ontology/actions/*.yaml             │   ├── supply_chain/ (Inventory, 扣库存Action)
  state_machine.py                    │   ├── organization/ (Employee, Store)
  tools.py (query_near_expiry)        │   └── finance/ (LossReport, 损耗Action)
  skills/                           └── processes/
                                       └── clearance/  (状态机 + 编排Skill + query工具)
```

clearance 的 Action 按归属域拆分：create_clearance_task 的定价→marketing，deduct_stock→supply_chain，create_loss_report→finance。Task 状态机归 clearance 流程。

---

## 3. 客户配置层：全栈隔离 + Onboarding

### 3.1 三档客户能力

| 档 | 客户做什么 | 隔离需求 |
|---|---|---|
| **L1 配置** | 启用行业包的域/流程 + 调参数（折扣表/角色/阈值） | 数据隔离 |
| **L2 扩展** | copy 行业包后，加自定义 Object/Action/Skill（不改标准的） | + 本体语义隔离 |
| **L3 自建** | copy 后任意改（加/删/改标准定义），甚至从零建模 | + 本体语义隔离 + Agent 实例隔离 |

**核心机制**：客户 **copy 行业包到自己的目录，成为本体 owner，可任意调整**。行业包是模板起点，copy 后断开依赖。

### 3.2 全栈隔离的三层

```
                    Platform 内核（共享，所有客户复用）
                    ─────────────────────────────────
客户A                          │            客户B
┌─────────────────────────────┐│┌─────────────────────────────┐
│ Agent 实例A（独立）          │││ Agent 实例B（独立）          │
│  └ tools/prompt/skills 独立  │││  └ tools/prompt/skills 独立  │
├─────────────────────────────┤│├─────────────────────────────┤
│ 本体语义A（独立 registry）    │││ 本体语义B（独立 registry）    │
│  └ Object/Link/Action 定义   │││  └ Object/Link/Action 定义   │
│  └ = 行业包copy + 客户自定义  │││  └ = 行业包copy + 客户自定义  │
│  └ Product{A的属性} ≠ B的    │││  └ Product{B的属性} ≠ A的    │
├─────────────────────────────┤│├─────────────────────────────┤
│ 实例数据A（硬隔离）          │││ 实例数据B（硬隔离）          │
│  └ customer_id=A 的存储      │││  └ customer_id=B 的存储      │
└─────────────────────────────┘│└─────────────────────────────┘
```

- **本体语义隔离**：每客户专属 OntologyRegistry 实例。客户 A 的 `Product{id,name,shelf_life,organic_cert}` 与客户 B 的 `Product{id,name,cost,supplier_id}` 属性不同——因为 registry 实例不同。
- **实例数据隔离**：`customer_id` 硬隔离（APaaS 底线）+ `org_unit_id` 权限范围。
- **Agent 实例隔离**：按 customer 构建（独立 tools/prompt/skills/registry/repository）。

### 3.3 客户 Onboarding 工作流（五步）

```
① Copy 行业标准语义包
   packs/retail/  ──copy──▶  customers/customer_001/ontology/

② 调整本体语义（按客户实际业务建模）
   编辑 ontology/store.ttl, actions/*.yaml, skills/*.md

③ 数据清洗 + 按本体初始化
   源数据(ERP/POS/Excel) ──按本体 schema 清洗/映射──▶ data/*.json

④ 配置数据库连接
   config.yaml: storage.type = json_files | postgres

⑤ 启动客户 agent 实例
   bootstrap(customer_001) → 合并本体 → 接 Repository → 构建 Agent → 注册调度器
```

**对应 CLI（将来）**：`ontocopy` → 手动编辑 → `ontoseed` → 配 config → `ontostart`。

### 3.4 客户目录结构

```
packs/retail/                          # 行业包标准（模板，只读）
  pack.py                              # 声明 IndustryPack
  domains/                             # 能力域
    marketing/                         #   Object/Action/规则
    supply_chain/
    organization/
    finance/
  processes/                           # 价值链流程
    clearance/
    procurement/

customers/                             # 客户层
  customer_001/
    config.yaml                        # 启用范围 + 参数 + DB配置 + OrgUnit树
    ontology/                          # copy 自行业包，客户可任意改
      store.ttl
      actions/*.yaml
    skills/                            # 自定义 Skill
    data/                              # 实例数据（硬隔离）
      *.json
```

### 3.5 三层租户权限

```
Platform（平台运营方）
  └── Customer（客户公司 = 租户隔离边界）
        └── OrgUnit（组织单元树：Brand > Region > Store）
              └── 权限下放：店长只能看/操作本 Store 数据
```

| 字段 | 层级 | 作用 |
|---|---|---|
| `customer_id` | 客户级 | **硬隔离**：不同客户数据绝不交叉 |
| `org_unit_id` | 组织单元级 | **权限范围**：同客户内按门店/区域限制 |

Repository 过滤升级：`WHERE customer_id = ? AND org_unit_id IN (用户有权的单元)`。

### 3.6 参数覆盖链

解决"同一概念不同客户/不同区域有不同值"：
```
行业包默认规则（packs/retail/domains/marketing/discount_rules.json）
  ↓ 被客户配置覆盖
客户规则（customers/customer_001/discount_rules.json）
  ↓ 可被 OrgUnit 进一步覆盖（某区域特殊折扣）
组织单元规则（customers/customer_001/region_north_discount_rules.json）
```
按 `customer_id + org_unit_id` 从最具体到最通用查找。单一事实源原则在**每层**成立，层间是覆盖不是重复。

### 3.7 CustomerConfig 数据结构

```yaml
customer_id: customer_001
name: 某连锁超市
source_pack: retail                    # copy 来源（溯源记录）
storage:
  type: json_files                     # MVP；v2: postgres
  data_dir: customers/customer_001/data
  # v2: connection: postgres://...
enabled_domains: [marketing, supply_chain, organization]
enabled_processes: [clearance, procurement]
parameters:
  marketing:
    discount_rules: discount_rules.json
org_tree:
  - { id: brand_hq, parent: null }
  - { id: region_north, parent: brand_hq }
  - { id: store_001, parent: region_north }
```

---

## 4. 运营层

运营层横切三层，三入口共享同一客户的 Agent 实例。

### 4.1 三入口架构

```
                    客户 Agent 实例（按 customer_id 隔离）
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ① 对话入口        ② 自动化入口      ③ 运营看板
   （人驱动）        （定时/事件驱动）  （总览+推送）
```

### 4.2 对话入口（已有雏形，升级 customer 路由）

CopilotKit 对话，Agent 跨域操作。升级：请求带 `customer_id` + `org_unit_id`，路由到对应客户 Agent 实例。

### 4.3 自动化入口（已有雏形，升级 per-customer）

定时作业 + 事件回调。升级：Scheduler 按 `customer_id` 隔离（每客户自己的 job 集）。

### 4.4 运营看板（新建）

| 层 | 内容 | 数据来源 |
|---|---|---|
| **指标卡** | 跨域 KPI：在办任务数、临期金额、报损率、库存周转 | 聚合查询 Repository |
| **待办流** | 待人介入事项：待审批、到期预警、库存不足 | 查各流程 pending 状态 |
| **异常告警** | Agent 主动推送：临期激增、报损超阈、流程卡死 | Scheduler 检测 + Agent 推理 |

看板经只读聚合工具（`query_dashboard`）跨域读 Repository，保证走同一治理链路（权限过滤、租户隔离）。Agent 主动推送：Scheduler 检测异常 → headless 唤醒 Agent → 生成告警 → 推送看板。

### 4.5 本体管理界面（admin，新建）

客户管理员 Web 界面查看已定义的本体模型语义：

```
/admin/customers/{customer_id}/ontology
├── Object Type 浏览器（按域分组，属性/类型/枚举/关系图）
├── Action Type 浏览器（按流程分组，参数/约束/副作用/状态机）
├── 价值链流程图（跨域编排可视化）
├── Skill 浏览器
└── 数据源/DB 配置
```

内核提供只读 API（`GET /api/admin/customers/{cid}/ontology/...`）读该客户的 OntologyRegistry 合并视图。MVP 只读浏览；Web 在线编辑列 v2。

---

## 5. Agent 实例构建

三入口共享的客户 Agent 实例，onboarding 时 bootstrap 一次构建：

```
bootstrap(customer_id) 一次构建：
  Agent = {
    registry:    该客户本体合并视图（行业包copy + 客户自定义）
    repository:  该客户的 Repository（按 config.storage 接 JSON 或 PG）
    executor:    该客户的 ActionExecutor（绑该 registry + repository）
    scheduler:   该客户的 job 集（定时/事件）
    tools:       内核通用 + 该客户域/流程工具
    prompt:      该客户本体注入的 system prompt
  }
  → 按 customer_id 缓存，三入口共享
```

对话/自动化/看板都通过 `get_customer_agent(customer_id)` 取同一实例——保证一致性（同一本体、同一权限、同一份数据）。

---

## 6. 企业规模部署策略

### 6.1 现状瓶颈

| 维度 | 现状（demo） | 企业级要求 |
|---|---|---|
| 存储 | 单 JSON 文件 | 高并发、大数据量、事务 |
| Agent | 单进程单实例 | 多客户、高可用 |
| 调度 | 进程内 APScheduler | 分布式、可扩展 |
| LLM | 同步阻塞 | 高并发、限流、成本控制 |

### 6.2 分层部署架构（目标）

```
                    ┌─────────────────────┐
                    │  负载均衡 / API 网关  │
                    └──────────┬──────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │ Agent Worker │   │ Agent Worker │   │ Agent Worker │  ← 无状态，水平扩展
    │ （FastAPI）  │   │              │   │              │    按 customer 路由
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           └──────────────────┼──────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │     共享状态层（Redis/PG）      │
              │  Agent 实例缓存 / 会话 / 本体   │
              │  业务数据(PG per-customer)      │
              │  预览缓存(Redis TTL)            │
              └───────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │Scheduler │   │Scheduler │   │Scheduler │  ← 分布式调度
        │ Worker   │   │ Worker   │   │ Worker   │
        └──────────┘   └──────────┘   └──────────┘
```

**各层方案**：
- **Agent Worker**：无状态，按 `customer_id` 从共享层加载 registry/repository 配置构建临时 Executor，水平扩展。
- **存储**：业务数据 → PostgreSQL per-customer schema（Repository 接口不变，换实现）；本体定义 → PG/Git；运行时状态 → Redis。
- **调度**：APScheduler → Celery Beat + Worker（或 APScheduler + Redis 分布式锁）。
- **LLM**：LLM 网关（统一限流/缓存/多 provider）。

### 6.3 渐进式部署

| 阶段 | 部署 | 适用 |
|---|---|---|
| **现状** | 单进程，JSON，MemorySaver | demo/POC |
| **P5a** | + PostgreSQL（per-customer schema）+ 多 worker | <50 客户 |
| **P5b** | + Redis + Celery + LLM 网关 | <500 客户 |
| **P5c** | + K8s 弹性 + 大客户独占 + 多 region | 大规模 APaaS |

**关键原则**：Repository 抽象使存储可换，Agent 按 customer 构建使水平扩展自然——**内核架构不阻塞部署升级**。

---

## 7. 演进路线（phase 拆分）

每 phase = 独立 spec → plan → 实现，依赖递进。

| Phase | 目标 | 依赖 | 验证 |
|---|---|---|---|
| **P1 多客户租户地基** | tenant_id → customer_id + org_unit_id 双层；Repository 双层过滤；CustomerConfig + bootstrap(customer) 按客户构建 Agent 实例；per-customer Agent 实例缓存 | 现有内核 | 两客户数据隔离；OrgUnit 权限过滤；按 customer 构建 Agent |
| **P2 行业包 + 双轴** | vertical → IndustryPack/CapabilityDomain/ValueChainProcess 三级；clearance 迁移为 retail-pack 跨域流程；Action 按域拆分；域可被多流程复用 | P1 | clearance 跨域编排跑通 |
| **P3 客户自定义 + onboarding** | copy→改→灌→接DB→启 五步；客户自定义本体合并；ontocopy/ontoseed/ontostart CLI | P2 | 客户 copy retail 包→改→灌→启→可用 |
| **P4 运营看板 + 本体管理界面** | 跨域指标卡 + 待办流 + 异常告警；query_dashboard；Agent 推送；admin 本体浏览器 | P3 | 看板呈现跨域指标；admin 浏览本体 |
| **P5a 数据库存储** | JSON → PostgreSQL per-customer schema；PostgresRepository | P1 | 换 DB 不改上层 |
| **P5b 分布式部署** | Redis + Celery + LLM 网关 + 多 worker | P5a | 多客户高并发 |

**建议从 P1 开始**——多客户租户地基是 APaaS 底线。

---

## 8. 与现有架构的关系

| 现有（已完成） | 本设计中的位置 |
|---|---|
| 内核（Repository/Executor/Scheduler/bootstrap） | **保留升级**：内核不变，加 customer 维度 |
| 多 vertical 机制（VerticalConfig/注册表） | **重构为** IndustryPack/Domain/Process 三级 |
| clearance vertical | **迁移为** retail-pack 的 clearance 价值链流程 |
| equipment_repair vertical | **迁移为** 另一个流程（或独立行业包的流程） |
| tenant_id 软隔离 | **升级为** customer_id + org_unit_id 双层 |
| 接入手册/模板（docs/manual/） | **保留**：客户自定义本体的流程仍适用 |
| 业务本体建模规范 | **保留**：建模原则不变，适用行业包+客户层 |

---

## 附录 A：关键设计决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 平台与客户的本体边界 | 三层（内核+行业包+客户配置） | 分层最清晰，行业包可插拔 |
| 行业包定位 | 模板（copy 后断开依赖，客户可任意改） | 每客户业务模型确实不同 |
| 领域组织方式 | 双轴（能力域提供原子 + 价值链流程跨域编排） | 跨域流程是常态 |
| 运营形态 | 对话+自动化+看板 | 主动运营，非被动查询 |
| 租户层级 | Platform>Customer>OrgUnit | 权限可下放到门店 |
| 客户隔离 | 全栈（本体语义+数据+Agent 实例） | APaaS 多客户底线 |
| 本体管理 | Web 只读浏览（MVP），在线编辑（v2） | 编辑需校验/迁移/版本 |
| 部署 | 渐进式（单进程→PG→Redis+Celery→K8s） | 内核不阻塞部署升级 |

---

## 附录 B：不在本 spec 范围（各 phase 独立 spec 细化）

- 零售四域的详细 Object/Link/Action 清单（P2 spec）
- 客户自定义本体的冲突检测/校验规则（P3 spec）
- 看板的具体指标定义/告警阈值（P4 spec）
- PostgreSQL schema 设计/迁移（P5a spec）
- 计费/客户生命周期管理（独立 spec）
- 多 region 部署的容灾（P5c）
