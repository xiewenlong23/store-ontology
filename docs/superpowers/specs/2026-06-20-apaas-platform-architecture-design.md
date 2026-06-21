# OntologyAgent APaaS 平台总体架构设计

> **状态**：已与用户逐节确认，待 review
> **日期**：2026-06-20（2026-06-21 修订：引入 Workspace-First 设计）
> **性质**：从"单 vertical demo + 多 vertical 内核"升级为"Workspace-First 多客户 APaaS + Agent 平台 + 行业/客户 Workspace"的**总体架构骨架**。只定架构与 phase 拆分，不含详细实体清单（各 phase 独立 spec 细化）。
> **前置文档**：
> - `docs/superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md`（单 vertical 目标架构，内核多 vertical 改造已完成）
> - `docs/业务本体建模规范.md`（建模规范）
> - `docs/manual/`（接入手册）
> **参考开源项目**（吸收 Agent 设计模式）：
> - [OpenClaw](https://github.com/openclaw/openclaw)：per-agent workspace 隔离、Skill 分级加载、multi-agent binding 路由
> - [Hermes](https://github.com/NousResearch/hermes-agent)：Tool 自注册机制、声明式/实现分层、profile 隔离

---

## 0. 定位与目标

**OntologyAgent 是一个本体驱动的多客户 APaaS（Application Platform as a Service）Agent 平台。** 平台提供 Agent 内核 + 系统 Tool；行业知识与客户实例统一为 **Workspace**；每个客户（企业）从行业基础包 Copy 一个自己的 Workspace，按自身业务调整本体语义，灌入数据，启动专属 Agent 实例，即可用对话 + 自动化 + 看板进行业务运营。

**为什么是 APaaS 而非 SaaS**：SaaS 是"平台提供一套标准应用，客户配置参数使用"；APaaS 是"平台提供建模与运行能力，客户**构建自己的应用**（自定义本体/流程/规则）"。本平台的核心特征——客户 Copy 行业包后**任意调整本体语义**（加/删/改 Object/Action/Skill）、灌自己的数据、跑专属 Agent——正是 APaaS。行业包是**起点模板**而非标准应用，客户是本体的 owner。

**一句话**：Agent 平台（内核 + 系统 Tool）+ Workspace（行业模板 + 客户实例）+ 运营入口 = 每个客户一个专属 AI 业务运营平台。

### Workspace-First 设计哲学

本平台的核心抽象是 **Workspace**：

- **Agent 平台**只管"怎么跑"——引擎、系统 Tool、路由、bootstrap
- **Workspace** 只管"跑什么"——本体语义、数据、场景技能
- **行业包和客户实例本质都是 Workspace**，只是一个是只读模板（`workspace/retail/`），一个是客户拥有的实例（`workspace/jjy/`）

这种统一使得"行业包"和"客户"不再是两个割裂的概念层，而是同一种抽象的两种形态。

### 核心诉求

1. **多客户 APaaS**：一个平台服务多个企业客户，客户间全栈隔离。
2. **业务模型因客户而异**：同一行业（零售）的客户，其本体（实体/关系/规则）不同——平台不强制一套标准模型，而是提供行业包作起点，客户 copy 后按实际调整。
3. **零售领域分层**：业务按价值链组织（营销/供应链/组织/财务能力域），工作流跨域编排。
4. **Agent 驱动运营**：不止查询助手，还要主动自动化 + 运营看板。

---

## 1. 平台分层架构（3 层 + 1 横切层）

```
┌─────────────────────────────────────────────────────────────────┐
│ 运营层（Operations）—— 横切 Agent 平台 + Workspace               │
│ 对话入口（CopilotKit + X-Workspace Header）                     │
│ 定时自动化（Scheduler per-workspace）                             │
│ 运营看板（query_dashboard，业务 tool，归 workspace/skills/）      │
│ 本体管理界面（admin，读 workspace 的 OntologyRegistry）          │
├─────────────────────────────────────────────────────────────────┤
│ Agent 平台层（agent/）—— 平台通用能力                            │
│ engine/（核心引擎）+ tools/（系统原子Tool）+ skills/（系统Skill）  │
│ Workspace 路由 + 运行时上下文管理 + bootstrap                     │
├─────────────────────────────────────────────────────────────────┤
│ Workspace 层（workspace/）—— 业务知识与数据                       │
│ 行业基础包（workspace/retail/，只读模板）                         │
│ 客户实例（workspace/jjy/，Copy & Own）                           │
│ 每个 Workspace：ontology/（声明式语义）+ data/ + skills/（场景）    │
└─────────────────────────────────────────────────────────────────┘
```

### 与原 4 层架构的映射

| 原层级 | 新归属 | 变化 |
|---|---|---|
| 内核层（Kernel） | → **Agent 平台层**的 engine/ | 保留核心能力，命名更聚焦 |
| 行业包层（Industry Pack） | → **Workspace 层**的 workspace/retail/ | 从独立层降为 workspace 的一种形态（只读模板） |
| 客户配置层（Customer Config） | → **Workspace 层**的 workspace/jjy/ | 从独立层降为 workspace 的另一种形态（Copy & Own） |
| 运营层 | → **运营层**（不变，加 X-Workspace 路由） | 基本不变 |

**重构的核心思想**：原 Kernel/IndustryPack/Customer 三层混合了"平台能力"和"业务知识"两个维度。重构后，**Agent 平台层**只管"怎么跑"（引擎、路由、系统工具），**Workspace 层**只管"跑什么"（本体、数据、业务技能）。

### 关键概念重定义（现有→目标）

| 现有概念 | 目标概念 | 变化 |
|---|---|---|
| backend/ | **agent/**（Agent 平台层） | 重命名 + 重组：engine/ + tools/ + skills/ |
| packs/ + customers/ | **workspace/**（统一） | 行业包和客户统一为 Workspace 的两种形态 |
| processes/ 目录 | **skills/**（自包含场景单元） | 废弃 processes/，状态机/Tool/自动化归入 skills/ |
| vertical（clearance） | **CapabilityDomain**（能力域）+ **ValueChainProcess**（价值链流程） | 拆双轴：域提供原子，流程跨域编排 |
| VerticalConfig | **Workspace ontology**（domains/）+ **skills**（场景单元） | 升级为本体声明 + 场景技能双解耦 |
| tenant_id（字符串软隔离） | **Workspace + OrgUnit**（权限范围） | Workspace 是隔离边界，OrgUnit 是权限范围 |
| 单 Agent 实例 | **per-workspace 运行时上下文** | 按 workspace 构建，全栈隔离 |

---

## 2. 新项目目录结构

```
store-ontology/                       # 项目根
├── workspace/                        # Workspace 层（行业包 + 客户实例）
│   ├── retail/                       # 行业基础包（只读模板）
│   │   ├── config.yaml               # 包定义：行业名、能力域/场景清单
│   │   ├── ontology/                 # 纯声明式本体语义（无 Python 实现）
│   │   │   └── domains/              #   能力域（CapabilityDomain）
│   │   │       ├── marketing/        #     domain.ttl + actions/*.yaml
│   │   │       ├── supply_chain/
│   │   │       ├── organization/
│   │   │       └── finance/
│   │   ├── data/                     # 种子/示例数据
│   │   └── skills/                   # 自包含场景单元
│   │       ├── clearance-workflow/   #   工作流场景
│   │       │   ├── SKILL.md          #     场景/工作流定义
│   │       │   ├── state_machine.py  #     状态机（created→approved→completed）
│   │       │   ├── tools.py          #     该场景的业务 Tool（复杂逻辑）
│   │       │   └── automation.py     #     定时任务
│   │       └── store-ontology/       #   知识型 Skill（纯文档）
│   │           └── SKILL.md
│   │
│   └── jjy/                          # 客户实例（从 retail Copy & Own）
│       ├── config.yaml               # 客户配置：来源包 + 启用域 + DB + OrgUnit
│       ├── ontology/                 # 客户本体（独立副本，可任意修改）
│       │   └── domains/*/
│       ├── data/                     # 客户实例数据（硬隔离）
│       └── skills/                   # 客户 Skill（可覆盖/新增，与 retail 并行独立）
│           └── clearance-workflow/
│               ├── SKILL.md
│               ├── state_machine.py
│               └── tools.py
│
├── agent/                            # Agent 平台层（通用能力）
│   ├── engine/                       # 核心引擎
│   │   ├── parser.py                 # TTL 本体解析器
│   │   ├── registry.py               # OntologyRegistry（加载 workspace ontology）
│   │   ├── executor.py               # 声明式 Action 执行器（基于 YAML 执行）
│   │   ├── repository.py             # 多租户数据 Repository
│   │   ├── scheduler.py              # 调度器
│   │   ├── bootstrap.py              # 平台级 bootstrap
│   │   ├── workspace_bootstrap.py    # 按 workspace 构建运行时上下文
│   │   ├── onboarding.py             # workspace copy（ontocopy）
│   │   ├── action_loader.py          # Action YAML 加载器
│   │   ├── schemas.py                # Pydantic schemas
│   │   ├── state_machine.py          # 状态机基础设施
│   │   ├── tenant.py                 # 租户模型（workspace + org_unit）
│   │   └── errors.py                 # 错误定义
│   ├── tools/                        # 系统原子 Tool（与业务无关）
│   │   ├── crud_tools.py             # 通用 CRUD（任意 ontology 实体的增删改查）
│   │   ├── query_tools.py            # 通用查询（按 schema 过滤、聚合）
│   │   ├── ontology_browser.py       # 本体浏览（查看 Object/Action Type 定义）
│   │   └── system_tools.py           # 系统运维（workspace 信息、健康检查）
│   ├── skills/                       # 系统 Skill（平台通用）
│   │   └── system_skills/
│   ├── main.py                       # FastAPI 入口（port 8123）
│   ├── cli.py                        # CLI（ontocopy/ontoseed/ontostart）
│   ├── pyproject.toml
│   └── tests/
│
├── frontend/                         # 前端（Next.js 15 + CopilotKit）
│   ├── package.json
│   └── ...
│
└── docs/                             # 文档
```

### Workspace 三个子目录的职责

| 子目录 | 职责 | 形态 |
|---|---|---|
| **ontology/** | **语义层**——定义"有什么"：Object/Link（domain.ttl）+ Action Type（actions/*.yaml）。纯声明式，**不放任何 Python 实现代码** | TTL + YAML |
| **data/** | **数据层**——存储"具体数据"（JSON 文件，v2 可换 PostgreSQL） | JSON |
| **skills/** | **能力层**——定义"怎么用"：自包含的场景单元，每个 skill 目录可含 SKILL.md + 可选 tools.py + 可选 state_machine.py + 可选 automation.py | MD + Python |

### Skill 作为自包含场景单元

每个 skill 目录是一个**自包含的业务场景**：

```
skills/
  clearance-workflow/              # 能力型 Skill（含实现）
    SKILL.md                       #   场景/工作流定义（必选）
    state_machine.py               #   状态机（可选，有流程编排时）
    tools.py                       #   业务 Tool（可选，复杂逻辑时）
    automation.py                  #   定时任务（可选，需自动化时）
  store-ontology/                  # 知识型 Skill（纯文档）
    SKILL.md
```

- **知识型 Skill**：只有 SKILL.md，提供领域知识或操作指引
- **能力型 Skill**：SKILL.md + 实现（tools/state_machine/automation），提供可执行的业务场景

---

## 3. Agent 设计模式（吸收 OpenClaw / Hermes）

### 3.1 声明式执行 + Tool 发现机制

**设计原则**：ontology/ 中的 Action Type YAML 由 Engine 声明式 Executor 自动执行（主力路径），只有复杂逻辑才写 Python 业务 Tool 放到 skills/ 中。

**三级发现机制**：

| 类型 | 来源 | 发现方式 | 时机 |
|---|---|---|---|
| **系统原子 Tool** | `agent/tools/` | 模块导入时 `registry.register()` 自注册 | 平台启动 |
| **Action Type** | `workspace/*/ontology/domains/*/actions/*.yaml` | `action_loader.py` 解析 YAML → Executor 声明式执行 | `workspace_bootstrap()` 时扫描 |
| **业务 Tool** | `workspace/*/skills/*/tools.py` | Python 模块自注册（同系统 Tool 模式） | `workspace_bootstrap()` 时扫描 |

**声明式 Executor 工作原理**：
- Action YAML 中声明步骤（step）：读/写 Repository、调用规则、转换状态
- Executor 按 YAML 定义自动执行，不需要写 Python
- 仅当逻辑无法声明式表达（如复杂计算、外部 API 调用）时，才在 skills/*/tools.py 写 Python

**灵感来源**：Hermes 的 `registry.register()` 自注册 + AST 自动发现机制。

### 3.2 Skill 分级加载（2 级）

**关键澄清**：由于行业包和客户实例是 **Copy & Own**（客户 copy 时已获得所有行业包 Skill 的副本），两者是**并行独立**的 workspace，无运行时继承关系。因此 Skill 只有 **2 级**：

| 优先级 | 来源 | 说明 |
|---|---|---|
| 1（高） | `workspace/{name}/skills/` | 该 workspace 自己的 Skill（不论是 retail 模板还是 jjy 实例） |
| 2（低） | `agent/skills/` | 平台系统 Skill（所有 workspace 共享） |

**加载机制**：`workspace_bootstrap()` 时扫描两级目录，组装该 workspace 的 Skill 集合。workspace 内同名 skill 由其自身定义（客户 copy 后可任意改），系统 Skill 作为通用补充。

**灵感来源**：OpenClaw 的 Skill 优先级链（简化为 2 级，因 Copy & Own 去掉了行业包-客户继承层）。

### 3.3 Workspace 隔离与运行时上下文

每个 workspace 构建一个**独立的运行时上下文**，实现全栈隔离：

```
workspace_bootstrap(workspace_name) 构建的运行时上下文：
  WorkspaceContext = {
    workspace_name:   "jjy",
    registry:         独立 OntologyRegistry（加载 workspace/jjy/ontology/）
    repository:       独立 Repository（绑定 workspace/jjy/data/）
    executor:         独立 Executor（声明式执行该 workspace 的 Action Type）
    scheduler:        独立调度器（该 workspace 的定时任务集）
    business_tools:   独立（workspace/jjy/skills/*/tools.py 中的业务 Tool）
    skills:           独立（该 workspace 的 Skill 集合）
    system_tools:     共享（agent/tools/，所有 workspace 复用同一份）
    prompt:           独立（该 workspace 本体注入的 system prompt）
  }
  → 按 workspace_name 缓存，三入口（对话/自动化/看板）共享
```

**隔离层次**：
- **本体语义隔离**：每 workspace 专属 OntologyRegistry 实例。workspace A 的 `Product{id,name,shelf_life}` 与 workspace B 的 `Product{id,name,cost,supplier_id}` 属性不同——因为 registry 实例不同。
- **实例数据隔离**：`workspace_name` 硬隔离（APaaS 底线）+ `org_unit_id` 权限范围。
- **运行时上下文隔离**：按 workspace 构建（独立 tools/prompt/skills/registry/repository），系统 Tool 共享。

**灵感来源**：OpenClaw 的 per-agent workspace（每 agent 独立 workspace 路径 + Skill 隔离）+ Hermes 的 profile 隔离（每 profile 独立 HERMES_HOME）。

### 3.4 前端-后端 Workspace 路由

前端通过 **HTTP Header `X-Workspace`** 传递 workspace 标识，后端 FastAPI 中间件解析并路由：

```
前端请求 → HTTP Header: X-Workspace: jjy
  → FastAPI 中间件解析 workspace_name
  → get_workspace_context("jjy") 取缓存（未命中则 workspace_bootstrap 构建）
  → 路由到该 workspace 的运行时上下文处理
  → 返回结果
```

**中间件伪代码**：

```python
@app.middleware("http")
async def workspace_routing(request: Request, call_next):
    workspace_name = request.headers.get("X-Workspace")
    if not workspace_name:
        return JSONResponse(
            status_code=400,
            content={"error": "X-Workspace header required"}
        )

    ctx = get_workspace_context(workspace_name)  # 缓存查/构建
    if not ctx:
        return JSONResponse(
            status_code=404,
            content={"error": f"Workspace '{workspace_name}' not found"}
        )

    request.state.workspace_context = ctx
    request.state.workspace_name = workspace_name
    return await call_next(request)
```

**与 CopilotKit 兼容**：HTTP Header 方式同时适用于 REST API 和 WebSocket 连接，CopilotKit 前端在 runtime 配置中统一添加 header 即可。

**灵感来源**：OpenClaw 的 multi-agent binding（按 channel/account 路由到不同 agent）。

---

## 4. 双轴模型：能力域 + 价值链流程

### 4.1 为什么用价值链而非职能域

企业的大量业务流程是**跨域**的（出清涉及营销定价 + 供应链库存 + 组织执行 + 财务损耗）。按职能域切会把跨域流程强行归到某域，不符合现实。

**双轴**：
- **能力域（Capability Domain）**：提供可复用的原子 Object/Link/Action/规则。是被流程调用的"能力池"。定义在 `ontology/domains/` 中。
- **价值链流程（Value Chain Process）**：端到端跨域编排，调用多个域的 Action。有自己的状态机和 Skill。状态机定义在 `skills/` 中（作为场景单元的一部分）。

### 4.2 零售行业包的标准结构（workspace/retail/）

基于业界零售运营模型（NRF ARTS / SAP IS-Retail / Gartner 共识）+ Michael Porter 价值链：

```
workspace/retail/（行业基础包 = 只读模板）
├── ontology/
│   └── domains/（能力域，提供原子 Object/Action/规则）
│       ├── 营销域 Marketing
│       │   ├── Object: Product, PriceRule, Promotion, Member...
│       │   ├── Action: calculate_discount, apply_promotion, award_points...
│       │   └── 规则源: data/discount_rules.json（域内单一事实源）
│       ├── 供应链域 Supply Chain
│       │   ├── Object: Inventory, PurchaseOrder, Shipment...
│       │   └── Action: deduct_stock, receive_goods, transfer_stock...
│       ├── 组织域 Organization
│       │   └── Object: Employee, OrgUnit(Brand>Region>Store)...
│       └── 财务域 Finance
│           └── Object: LedgerEntry, CostRecord, LossReport...
│
├── data/（种子数据）
│
└── skills/（价值链流程作为自包含场景单元）
    ├── clearance-workflow（出清）
    │   ├── SKILL.md:    编排 marketing.定价 → supply_chain.库存 → organization.执行 → finance.损耗
    │   ├── state_machine.py: created→approved→in_progress→completed/scrapped
    │   ├── tools.py:    query_near_expiry 等
    │   └── automation.py: 定时检测临期商品
    ├── procurement-workflow（采购）
    │   └── SKILL.md:    编排 supply_chain.下单 → organization.审批 → finance.付款 → supply_chain.收货
    └── member-ops（会员运营）
        └── SKILL.md:    编排 marketing.积分 → marketing.券 → finance.核销
```

### 4.3 业务分层与原子 Action 分化

业务是分层的（域→子域→业务流程）。同一概念在不同叶子节点的**原子定义不同**：

| 概念 | 零售销售叶子 | 批发销售叶子 | 会员忠诚度叶子 |
|---|---|---|---|
| "折扣" | T1/T2/T3 减扣百分比 | 阶梯批量价 | 积分倍率 |

**设计原则**：单一事实源在**域内**成立，不跨域/跨叶子强行统一。每个叶子域有自己的规则数据源，Action Type 在 `ontology/domains/*/actions/` 中声明，由 Engine 声明式执行。

### 4.4 数据结构

| 结构 | 职责 | 位置 |
|---|---|---|
| **Workspace** | 顶层抽象，包含 ontology + data + skills 三部分 | `workspace/{name}/` |
| **CapabilityDomain** | 提供原子 Object/Link/Action Type + 域内规则源；**不含工作流/状态机** | `ontology/domains/{domain}/` |
| **Skill（场景单元）** | 跨域编排：SKILL.md（编排定义）+ 可选 state_machine.py + 可选 tools.py | `skills/{scene}/` |

**关键解耦**：ontology 只声明"有什么"（Object/Action Type），skills 定义"怎么用"（工作流/状态机/Tool）。能力域可被多场景复用（营销域的折扣能力既被 clearance-workflow 调用，也被促销场景调用）。

### 4.5 clearance 迁移示例（旧→新）

```
现有（backend/packs/retail/）:                   目标（workspace/retail/）:
  domains/                                          ontology/domains/
    marketing/                                        marketing/      (Product, PriceRule, 折扣Action)
      domain.ttl                                      supply_chain/   (Inventory, 扣库存Action)
      actions/*.yaml                                  organization/   (Employee, Store)
      discount.py  ← 实现代码（移走）                   finance/        (LossReport, 损耗Action)
    supply_chain/
    organization/                                   skills/
    finance/                                         clearance-workflow/
  processes/                                           SKILL.md        (编排定义)
    clearance/                                         state_machine.py (状态机)
      state_machine.py                                 tools.py         (query_near_expiry 等)
      tools.py (query_near_expiry)
      automation.py                                    automation.py    (定时任务)
```

**迁移要点**：
- `discount.py` 等实现代码：简单逻辑迁移为 Action YAML（声明式），复杂逻辑移到 `skills/clearance-workflow/tools.py`
- clearance 的 Action 按归属域拆分：`create_clearance_task` 的定价→marketing，`deduct_stock`→supply_chain，`create_loss_report`→finance
- Task 状态机归 `skills/clearance-workflow/state_machine.py`
- `processes/` 目录废弃，职责归入 `skills/`

---

## 5. Workspace 层：全栈隔离 + Onboarding

### 5.1 三档客户能力

| 档 | 客户做什么 | 隔离需求 |
|---|---|---|
| **L1 配置** | 启用行业包的域/场景 + 调参数（折扣表/角色/阈值） | 数据隔离 |
| **L2 扩展** | copy 行业包后，加自定义 Object/Action/Skill（不改标准的） | + 本体语义隔离 |
| **L3 自建** | copy 后任意改（加/删/改标准定义），甚至从零建模 | + 本体语义隔离 + 运行时上下文隔离 |

**核心机制**：客户 **copy 行业包到自己的 workspace 目录，成为本体 owner，可任意调整**。行业包是模板起点，copy 后断开依赖（Copy & Own）。

### 5.2 全栈隔离的三层

```
                    Agent 平台（共享，所有 workspace 复用）
                    ─────────────────────────────────
workspace A (jjy)                │            workspace B (另一客户)
┌─────────────────────────────┐│┌─────────────────────────────┐
│ 运行时上下文 A（独立）       │││ 运行时上下文 B（独立）       │
│  └ skills/tools/prompt 独立  │││  └ skills/tools/prompt 独立  │
├─────────────────────────────┤│├─────────────────────────────┤
│ 本体语义 A（独立 registry）   │││ 本体语义 B（独立 registry）   │
│  └ Object/Link/Action 定义   │││  └ Object/Link/Action 定义   │
│  └ = 行业包copy + 客户自定义  │││  └ = 行业包copy + 客户自定义  │
│  └ Product{A的属性} ≠ B的    │││  └ Product{B的属性} ≠ A的    │
├─────────────────────────────┤│├─────────────────────────────┤
│ 实例数据 A（硬隔离）         │││ 实例数据 B（硬隔离）         │
│  └ workspace=A 的存储        │││  └ workspace=B 的存储        │
└─────────────────────────────┘│└─────────────────────────────┘
```

- **本体语义隔离**：每 workspace 专属 OntologyRegistry 实例。
- **实例数据隔离**：`workspace_name` 硬隔离（APaaS 底线）+ `org_unit_id` 权限范围。
- **运行时上下文隔离**：按 workspace 构建（独立 skills/tools/prompt/registry/repository），系统 Tool 共享。

### 5.3 客户 Onboarding 工作流（五步）

```
① Copy 行业基础包
   workspace/retail/  ──copy──▶  workspace/jjy/

② 调整本体语义（按客户实际业务建模）
   编辑 ontology/domains/*/domain.ttl, actions/*.yaml
   编辑 skills/*/SKILL.md, tools.py, state_machine.py

③ 数据清洗 + 按本体初始化
   源数据(ERP/POS/Excel) ──按本体 schema 清洗/映射──▶ data/*.json

④ 配置数据库连接
   config.yaml: storage.type = json_files | postgres

⑤ 启动 workspace 运行时上下文
   workspace_bootstrap(jjy) → 加载本体 → 接 Repository → 构建 Context → 注册调度器
```

**对应 CLI**：`ontocopy` → 手动编辑 → `ontoseed` → 配 config → `ontostart`。

### 5.4 Workspace 目录结构（模板与实例对比）

```
workspace/retail/                      # 行业基础包（只读模板）
  config.yaml                          # 包定义
  ontology/domains/                    # 能力域（声明式 Object/Action）
    marketing/
    supply_chain/
    organization/
    finance/
  data/                                # 种子数据
  skills/                              # 场景单元（含状态机/Tool/自动化）

workspace/jjy/                         # 客户实例（Copy & Own，与 retail 独立）
  config.yaml                          # 客户配置
  ontology/domains/                    # 客户本体（copy 自 retail，可任意改）
    marketing/
    supply_chain/
    organization/
  data/                                # 客户实例数据（硬隔离）
    *.json
  skills/                              # 客户 Skill（可覆盖/新增，与 retail 并行）
    clearance-workflow/
      SKILL.md
      tools.py
```

### 5.5 两层权限

```
Platform（平台运营方）
  └── Workspace（客户公司 = 隔离边界，即原 Customer）
        └── OrgUnit（组织单元树：Brand > Region > Store）
              └── 权限下放：店长只能看/操作本 Store 数据
```

| 字段 | 层级 | 作用 |
|---|---|---|
| `workspace_name` | workspace 级 | **硬隔离**：不同 workspace 数据绝不交叉 |
| `org_unit_id` | 组织单元级 | **权限范围**：同 workspace 内按门店/区域限制 |

Repository 过滤：`WHERE workspace_name = ? AND org_unit_id IN (用户有权的单元)`。

### 5.6 参数覆盖链

解决"同一概念不同客户/不同区域有不同值"：
```
行业包默认规则（workspace/retail/data/discount_rules.json）  ← copy 时带入
  ↓ 客户 copy 后可修改
客户规则（workspace/jjy/data/discount_rules.json）
  ↓ 可被 OrgUnit 进一步覆盖（某区域特殊折扣）
组织单元规则（workspace/jjy/data/region_north_discount_rules.json）
```

按 `workspace_name + org_unit_id` 从最具体到最通用查找。单一事实源原则在**每层**成立，层间是覆盖不是重复。

### 5.7 WorkspaceConfig 数据结构

```yaml
workspace_name: jjy
name: JJY 连锁超市
source_pack: retail                    # copy 来源（溯源记录）
storage:
  type: json_files                     # MVP；v2: postgres
  data_dir: workspace/jjy/data
  # v2: connection: postgres://...
enabled_domains: [marketing, supply_chain, organization]
enabled_skills: [clearance-workflow, procurement-workflow]
parameters:
  marketing:
    discount_rules: discount_rules.json
org_tree:
  - { id: brand_hq, parent: null }
  - { id: region_north, parent: brand_hq }
  - { id: store_001, parent: region_north }
```

---

## 6. 运营层

运营层横切 Agent 平台与 Workspace，三入口共享同一 workspace 的运行时上下文。

### 6.1 三入口架构

```
                    workspace 运行时上下文（按 workspace_name 隔离）
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ① 对话入口        ② 自动化入口      ③ 运营看板
   （人驱动）        （定时/事件驱动）  （总览+推送）
   CopilotKit        Scheduler         query_dashboard
   + X-Workspace     per-workspace     （业务 tool，归 workspace/skills/）
```

### 6.2 对话入口（升级 workspace 路由）

CopilotKit 对话，Agent 跨域操作。**请求必须带 `X-Workspace` Header**，后端中间件解析并路由到对应 workspace 的运行时上下文。同一 workspace 的对话共享本体、权限、数据。

### 6.3 自动化入口（per-workspace 隔离）

定时作业 + 事件回调。Scheduler 按 `workspace_name` 隔离（每 workspace 自己的 job 集，定义在 `workspace/{name}/skills/*/automation.py`）。

### 6.4 运营看板（业务 tool）

| 层 | 内容 | 数据来源 |
|---|---|---|
| **指标卡** | 跨域 KPI：在办任务数、临期金额、报损率、库存周转 | 聚合查询 Repository |
| **待办流** | 待人介入事项：待审批、到期预警、库存不足 | 查各场景 pending 状态 |
| **异常告警** | Agent 主动推送：临期激增、报损超阈、流程卡死 | Scheduler 检测 + Agent 推理 |

看板查询工具（`query_dashboard` 等）归类为**业务 tool**，定义在 `workspace/{name}/skills/` 中，保证走同一治理链路（权限过滤、workspace 隔离）。Agent 主动推送：Scheduler 检测异常 → headless 唤醒 Agent → 生成告警 → 推送看板。

### 6.5 本体管理界面（admin）

客户管理员 Web 界面查看已定义的本体模型语义：

```
/admin/workspaces/{workspace_name}/ontology
├── Object Type 浏览器（按域分组，属性/类型/枚举/关系图）
├── Action Type 浏览器（按场景分组，参数/约束/副作用）
├── 场景 Skill 浏览器（工作流定义、状态机、Tool）
└── 数据源/DB 配置
```

内核提供只读 API（`GET /api/admin/workspaces/{ws}/ontology/...`）读该 workspace 的 OntologyRegistry 合并视图。MVP 只读浏览；Web 在线编辑列 v2。

---

## 7. 运行时上下文构建

三入口共享的 workspace 运行时上下文，onboarding 后 bootstrap 一次构建：

```
workspace_bootstrap(workspace_name) 一次构建：
  WorkspaceContext = {
    workspace_name:  该 workspace 标识
    registry:        该 workspace 本体视图（加载 ontology/domains/）
    repository:      该 workspace 的 Repository（按 config.storage 接 JSON 或 PG）
    executor:        该 workspace 的 Executor（绑该 registry + repository，声明式执行）
    scheduler:       该 workspace 的 job 集（定时/事件）
    system_tools:    平台系统 Tool（共享，agent/tools/）
    business_tools:  该 workspace 业务 Tool（skills/*/tools.py）
    skills:          该 workspace Skill 集合（2 级加载）
    prompt:          该 workspace 本体注入的 system prompt
  }
  → 按 workspace_name 缓存，三入口共享
```

构建流程：
1. 加载系统 Tool（agent/tools/，启动时已注册）
2. 扫描 `workspace/{name}/ontology/` → 解析 Action Type YAML → 注册到 registry
3. 扫描 `workspace/{name}/skills/` → 注册业务 Tool + 加载 SKILL.md + 状态机
4. 合并组装为该 workspace 的运行时上下文

对话/自动化/看板都通过 `get_workspace_context(workspace_name)` 取同一上下文——保证一致性（同一本体、同一权限、同一份数据）。

---

## 8. 企业规模部署策略

### 8.1 现状瓶颈

| 维度 | 现状（demo） | 企业级要求 |
|---|---|---|
| 存储 | 单 JSON 文件 | 高并发、大数据量、事务 |
| 运行时上下文 | 单进程单实例 | 多 workspace、高可用 |
| 调度 | 进程内 APScheduler | 分布式、可扩展 |
| LLM | 同步阻塞 | 高并发、限流、成本控制 |

### 8.2 分层部署架构（目标）

```
                    ┌─────────────────────┐
                    │  负载均衡 / API 网关  │
                    └──────────┬──────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │ Agent Worker │   │ Agent Worker │   │ Agent Worker │  ← 无状态，水平扩展
    │ （FastAPI）  │   │              │   │              │    按 workspace_name 路由
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           └──────────────────┼──────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │     共享状态层（Redis/PG）      │
              │  运行时上下文缓存 / 会话 / 本体  │
              │  业务数据(PG per-workspace)     │
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
- **Agent Worker**：无状态，按 `workspace_name` 从共享层加载 registry/repository 配置构建临时 Executor，水平扩展。
- **存储**：业务数据 → PostgreSQL per-workspace schema（Repository 接口不变，换实现）；本体定义 → PG/Git；运行时状态 → Redis。
- **调度**：APScheduler → Celery Beat + Worker（或 APScheduler + Redis 分布式锁）。
- **LLM**：LLM 网关（统一限流/缓存/多 provider）。

### 8.3 渐进式部署

| 阶段 | 部署 | 适用 |
|---|---|---|
| **现状** | 单进程，JSON，MemorySaver | demo/POC |
| **P5a** | + PostgreSQL（per-workspace schema）+ 多 worker | <50 客户 |
| **P5b** | + Redis + Celery + LLM 网关 | <500 客户 |
| **P5c** | + K8s 弹性 + 大客户独占 + 多 region | 大规模 APaaS |

**关键原则**：Repository 抽象使存储可换，运行时上下文按 workspace 构建使水平扩展自然——**Agent 平台架构不阻塞部署升级**。

---

## 9. 演进路线（phase 拆分）

每 phase = 独立 spec → plan → 实现，依赖递进。

| Phase | 目标 | 依赖 | 验证 |
|---|---|---|---|
| **P1 多 workspace 隔离地基** | tenant_id → workspace_name + org_unit_id 双层；Repository 双层过滤；WorkspaceConfig + workspace_bootstrap(workspace) 按工作空间构建上下文；per-workspace 上下文缓存 | 现有内核 | 两 workspace 数据隔离；OrgUnit 权限过滤；按 workspace 构建上下文 |
| **P2 行业包 + 双轴 + 目录重构** | vertical → Workspace(ontology domains + skills) 双轴；backend/ → agent/，packs/+customers/ → workspace/；clearance 迁移为 retail workspace 的场景；Action 按域拆分 | P1 | clearance 跨域编排跑通；新目录结构就位 |
| **P3 客户自定义 + onboarding** | copy→改→灌→接DB→启 五步；客户自定义本体合并；ontocopy/ontoseed/ontostart CLI | P2 | 客户 copy retail workspace → 改 → 灌 → 启 → 可用 |
| **P4 运营看板 + 本体管理界面** | 跨域指标卡 + 待办流 + 异常告警；query_dashboard；Agent 推送；admin 本体浏览器 | P3 | 看板呈现跨域指标；admin 浏览本体 |
| **P5a 数据库存储** | JSON → PostgreSQL per-workspace schema；PostgresRepository | P1 | 换 DB 不改上层 |
| **P5b 分布式部署** | Redis + Celery + LLM 网关 + 多 worker | P5a | 多 workspace 高并发 |

**建议从 P1 开始**——多 workspace 隔离地基是 APaaS 底线。

---

## 10. 与现有架构的关系

| 现有（已完成） | 本设计中的位置 |
|---|---|
| 内核（Repository/Executor/Scheduler/bootstrap） | **保留升级**：迁入 agent/engine/，加 workspace 维度 |
| 多 vertical 机制（VerticalConfig/注册表） | **重构为** Workspace(ontology domains + skills) 双轴 |
| clearance vertical | **迁移为** workspace/retail/skills/clearance-workflow 场景单元 |
| equipment_repair vertical | **迁移为** 另一个 workspace 或独立行业包的场景 |
| tenant_id 软隔离 | **升级为** workspace_name + org_unit_id 双层 |
| backend/ 目录 | **重命名 + 重组为** agent/（engine/ + tools/ + skills/） |
| backend/packs/ + customers/ | **统一为** workspace/（retail/ + jjy/） |
| 接入手册/模板（docs/manual/） | **保留**：客户自定义本体的流程仍适用 |
| 业务本体建模规范 | **保留**：建模原则不变，适用 workspace 层 |

---

## 附录 A：关键设计决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 平台分层 | 3 层（Agent 平台 + Workspace + 运营横切） | 简化原 4 层，平台能力与业务知识分离 |
| 行业包和客户归属 | 统一为 Workspace 的两种形态（模板/实例） | 概念统一，结构简洁 |
| 客户 copy 模式 | **Copy & Own**（copy 后断开依赖） | 每客户业务模型确实不同，独立演进 |
| ontology/ 是否放实现 | 纯声明式，不放 Python | 声明与实现解耦，Engine 声明式执行为主 |
| processes/ 目录 | 废弃，归入 skills/ | Skill 作为自包含场景单元 |
| 状态机位置 | skills/ 目录中（与工作流同目录） | 场景自包含 |
| Skill 级别 | 2 级（workspace > 系统） | Copy & Own 无运行时继承，不需行业包-客户继承层 |
| 领域组织方式 | 双轴（能力域提供原子 + 价值链流程跨域编排） | 跨域流程是常态 |
| 运营形态 | 对话+自动化+看板 | 主动运营，非被动查询 |
| 权限层级 | Platform>Workspace>OrgUnit | 权限可下放到门店 |
| 客户隔离 | 全栈（本体语义+数据+运行时上下文） | APaaS 多客户底线 |
| Workspace 路由 | HTTP Header `X-Workspace` | 与 CopilotKit WebSocket 兼容 |
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

---

## 附录 C：Agent 设计模式来源（开源参考）

本设计的 Agent 部分吸收了以下开源项目的核心模式：

### OpenClaw（[github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)）

| 借鉴的模式 | 在本平台的应用 |
|---|---|
| per-agent workspace（每 agent 独立 workspace 路径） | 每 workspace 独立运行时上下文 |
| Skill 优先级链（6 级） | 简化为 2 级（workspace > 系统），因 Copy & Own 去掉继承层 |
| multi-agent binding（按 channel 路由） | X-Workspace Header 路由 |

### Hermes（[github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)）

| 借鉴的模式 | 在本平台的应用 |
|---|---|
| Tool 自注册（`registry.register()` + AST 发现） | 系统 Tool 自注册 + 业务 Tool 模块发现 |
| profile 隔离（每 profile 独立 HERMES_HOME） | workspace 隔离（每 workspace 独立 ontology/data/skills） |
| 声明式/实现分层 | ontology 纯声明 + Engine 声明式执行 + skills 实现 |
