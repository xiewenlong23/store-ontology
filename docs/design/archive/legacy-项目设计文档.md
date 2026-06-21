> **🗄 归档说明**：本文档为「AI 门店大脑-临期商品管理」原始设计，**已被取代**。
> - 架构/平台部分 → [`00-architecture.md`](../00-architecture.md)
> - 零售临期行业包 as-built → [`industry-packs/retail-clearance.md`](../industry-packs/retail-clearance.md)
>
> 保留作历史追溯。**请勿据此文档实施**（路径与术语均已过时）。

---

# AI门店大脑 - 临期商品管理

## 1. 项目概述

### 1.1 项目背景

零售门店面临临期商品管理难题：商品过期造成损耗、临期折扣策略执行不到位、人工管理效率低。通过AI助手赋能门店，实现临期商品的智能查询、自动出清任务创建与执行，降低损耗、提升运营效率。

### 1.2 项目目标

搭建基于CopilotKit + Deep Agents的AI门店大脑，为店员、店长、总部管理者提供临期商品管理的智能助手。

### 1.3 项目范围

**本期实现：**
- AI助手对话能力（查询临期商品、创建/执行出清任务）
- 临期商品本体建模与数据存储
- 多店数据隔离
- 基于 MiniMax-M2.7-highspeed 模型的 AI 对话
- CopilotKit v1.57.4 五大功能：Chat UI / Generative UI / Shared State / Backend Tool Rendering / HITL
- Deep Agents agent 工具调用 + SkillsMiddleware（Skill 驱动业务规则）
- **Deep Agents Skills**：Progressive Disclosure 本体知识与工作流规范

**后续扩展：**
- 外部系统对接（ERP、POS）
- 移动端支持
- 数据库持久化
- CopilotKit v2 正式版升级

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  AI助手对话  │  │  任务管理    │  │  数据看板   │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         │                │                │                         │
│  ┌──────┴────────────────┴────────────────┴──────┐                │
│  │  @copilotkit/react-core v1.57.4              │                │
│  │  CopilotKit runtimeUrl="/api/copilotkit"     │                │
│  │  renderToolCalls={[...]} (Generative UI)     │                │
│  └─────────────────────┬───────────────────────┘                │
└────────────────────────┼────────────────────────────────────────────┘
                         │ POST /api/copilotkit
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend API Route (Next.js)                      │
│              app/api/copilotkit/route.ts                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  CopilotRuntime + LangGraphHttpAgent                          │  │
│  │  - 代理请求到 Deep Agent 服务                                 │  │
│  │  - url: http://localhost:8123/api/copilotkit                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP (AG-UI 协议)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Deep Agent 服务 (FastAPI)                        │
│                    端口: 8123                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Deep Agents: create_deep_agent() + LangGraphAgent            │  │
│  │  - 模型: MiniMax-M2.7-highspeed (OpenAI兼容API)              │  │
│  │  - Tools: 通用工具 (execute_action / query_task 等)           │  │
│  │  - Skills: clearance-workflow / ontology-knowledge             │  │
│  │  - SkillsMiddleware: Progressive Disclosure 自动加载           │  │
│  │  - AG-UI: add_langgraph_fastapi_endpoint 暴露 SSE 端点        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Next.js 15 (App Router) | React 19, TypeScript |
| AI前端组件 | @copilotkit/react-core @copilotkit/react-ui **v1.57.4** | 对话UI、Generative UI、Shared State、HITL |
| 前端API代理 | @copilotkit/runtime (LangGraphHttpAgent) | 前端与Deep Agent的桥梁 |
| 后端框架 | FastAPI | Python异步框架 |
| Agent 框架 | **Deep Agents** (`create_deep_agent`) + **LangGraphAgent** | 工具调用 + SkillsMiddleware |
| 本体驱动 | **OntologyParser** (TTL) + **Generic Tools** | 6 Object Types / 7 Link Types / 3 Action Types |
| AI模型 | **MiniMax-M2.7-highspeed** (OpenAI兼容API) | `https://api.minimaxi.com/v1` |
| Skills | **FilesystemBackend** + **SKILL.md** | 业务规则与工作流规范 |
| 数据存储 | JSON 文件 | 后续扩展数据库 |

**官方参考文档：**
- [CopilotKit 文档](https://docs.copilotkit.ai/)
- [Deep Agents 文档](https://docs.langchain.com/oss/python/deep_agents/)

**重要说明：**
- Deep Agents 的 **SkillsMiddleware** 从 `backend/skills/` 加载 SKILL.md，实现 Progressive Disclosure
- Skill 是**给 LLM 读的指令文档**，不是可执行工具
- 业务规则（折扣算法、工作流）在 Skill 中描述，通用工具负责执行

### 2.3 端口规划

| 服务 | 端口/地址 | 说明 |
|------|------|------|
| Frontend (Next.js) | localhost:3000 | 前端开发服务器 |
| Frontend API Route | localhost:3000/api/copilotkit | 前端API代理 |
| Deep Agent (FastAPI) | localhost:8123 | Deep Agent服务 |
| MiniMax API | api.minimaxi.com/v1 | MiniMax 云端 API |

### 2.4 本体驱动架构（v0.4.0）

```
backend/skills/store-ontology/        ← Skill 文件（业务规则 + 工作流）
       ├── store-ontology/SKILL.md
       └── clearance-workflow/SKILL.md

ontology/store.ttl          ← 本体语义定义（标准 TTL 格式）
       ↓                            Object Types / Link Types / Action Types
ontology/parser.py          ← 解析 TTL → EntityRegistry（单例）
       ↓                            6 对象类型 + 7 关系类型 + 3 动作类型
ontology/tools.py           ← 通用工具：
       ├── execute_action()    ← Preview → Confirm 入口
       ├── confirm_action()    ← 用户确认后执行
       ├── query_task()        ← 查询任务记录
       ├── update_task()       ← 修改任务
       ├── query_entity()      ← 查任意实体
       ├── create_entity()     ← 创建任意实体
       ├── update_entity()     ← 修改任意实体
       ├── traverse_relation()  ← 遍历关系链
       └── query_near_expiry() ← 查询临期商品
       ↓
main.py                     ← 挂载工具 + SkillsMiddleware
       ↓                           动态生成系统提示 (build_ontology_prompt)
create_deep_agent()          ← Deep Agents 自动处理工具调用循环
       ↓                           SkillsMiddleware 自动加载 SKILL.md
LangGraphAgent               ← ag_ui_langgraph，暴露 AG-UI SSE 端点
```

**核心原则：**
- **Object Types** 定义静态实体（Store/Employee/Product/NearExpiryProduct/Task/Region）
- **Action Types** 定义可执行操作（clearance/transfer/restock），在代码中通过 `ActionType` 枚举校验
- **Task Object** 是 Action 的执行记录（通用 `Task`，`type` 字段区分操作类型）
- **Skill** 描述业务规则（折扣算法、工作流步骤），LLM 按需读取
- **Tool** 是通用执行接口，Skill 告诉 LLM 何时用什么 Tool

---

## 3. 本体建模

### 3.1 本体论概述

本体论(Ontology)是对现实世界概念的形式化表示。参考 Palantir Foundry Ontology 标准，采用 TTL（Turtle）格式存储语义定义，JSON 文件存储实例数据。

**语义层次：**

| 层次 | 格式 | 内容 |
|------|------|------|
| TBox（术语层） | `ontology/store.ttl` | Object Types / Link Types / Action Types 的定义 |
| ABox（实例层） | `data/*.json` | 具体的门店、员工、商品等实例数据 |
| AI 理解层 | `build_ontology_prompt()` | 从 TTL 自动生成系统提示 |

**类型说明：**

| 类型 | 说明 |
|------|------|
| **Object Types** | 对象类型，实体定义（如 Store, Product, Employee） |
| **Link Types** | 链接类型，对象之间的关系 |
| **Action Types** | 动作类型，对对象的操作集合（含参数定义） |
| **Skill** | 业务规则与工作流规范，LLM 按需读取 |

**核心概念：**
- **Object Type Definition**：类型级别的定义（如"所有员工"）
- **Object Instance**：具体的实例（如"张三"）
- **Action Type**：操作的定义（如"出清"），描述参数和行为
- **Task (= Action Instance)**：Action Type 的具体执行记录

### 3.2 本体结构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Ontology: 门店临期商品本体                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Object Types                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Region  │  │  Store   │  │ Product  │  │ Employee │  │NearExpiry│  │
│  │  区域    │◄─┤  门店    │  │  商品    │  │  员工    │  │ Product  │  │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│                      │             │             │             │           │
│  Link Types          │             │             │             │           │
│  ──────────          │             │             │             │           │
│  located_in ─────────┘             │             │             │           │
│  has_employee ─────────────────────┘             │             │           │
│  belongs_to ─────────────────────────────────────┘             │           │
│  has_near_expiry_product ───────────────────────────────────────┘           │
│  has_task ───────────────────────────────────────────────────────────────┐  │
│                                                                             │  │
│  Action Types        Target              Link from Object                   │  │
│  ───────────                                                                │  │
│  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  clearance (出清)      NearExpiryProduct                            │──┘  │
│  │  transfer (调拨)       Product                                       │────┘  │
│  │  restock (补货)        Product                                       │────┘  │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Task Object = Action Instance                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Task { id, type, target_id, store_id, status, params_json, ... } │    │
│  │  type ∈ { clearance, transfer, restock }                            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Object Types 定义

#### 3.3.1 Region (区域)

| 属性 | 类型 | 说明 |
|------|------|------|
| id | string | 区域唯一标识 |
| name | string | 区域名称 |
| code | string | 区域编码 |

#### 3.3.2 Store (门店)

| 属性 | 类型 | 说明 |
|------|------|------|
| id | string | 门店唯一标识 |
| name | string | 门店名称 |
| region_id | string | 所属区域 |
| address | string | 门店地址 |
| manager_id | string | 店长ID |
| created_at | datetime | 创建时间 |

#### 3.3.3 Employee (员工)

| 属性 | 类型 | 说明 |
|------|------|------|
| id | string | 员工唯一标识 |
| name | string | 员工姓名 |
| store_id | string | 所属门店 |
| role | enum | 角色：clerk/manager/admin |
| phone | string | 联系电话 |

#### 3.3.4 Product (商品)

| 属性 | 类型 | 说明 |
|------|------|------|
| id | string | 商品唯一标识 |
| name | string | 商品名称 |
| category | string | 商品类别 |
| brand | string | 品牌 |
| unit | string | 单位 |
| cost_price | number | 成本价 |
| retail_price | number | 零售价 |

#### 3.3.5 NearExpiryProduct (临期商品)

| 属性 | 类型 | 说明 |
|------|------|------|
| id | string | 临期商品实例ID |
| product_id | string | 关联商品 |
| store_id | string | 所属门店 |
| batch_no | string | 批次号 |
| production_date | date | 生产日期 |
| expiry_date | date | 过期日期 |
| stock_quantity | number | 库存数量 |
| days_left | number | 剩余天数 |
| discount_tier | enum | 折扣层级：T1/T2/T3 |
| status | enum | 状态：normal/low_stock/expiring/expired |

#### 3.3.6 Task (通用任务)

Action Type 的执行记录。`type` 字段标识操作类型。

| 属性 | 类型 | 说明 |
|------|------|------|
| id | string | 任务ID |
| type | enum | 操作类型：clearance/transfer/restock（ActionType 枚举） |
| target_id | string | 操作目标ID（如 NearExpiryProduct.id） |
| store_id | string | 所属门店 |
| assignee_id | string | 负责人 |
| status | enum | 状态：pending/executing/completed/failed/cancelled |
| params_json | object | 操作参数字典（JSON） |
| result_json | object | 执行结果字典（JSON） |
| priority | enum | 优先级：low/medium/high |
| notes | string | 备注 |
| created_at | datetime | 创建时间 |
| started_at | datetime | 开始时间 |
| completed_at | datetime | 完成时间 |

### 3.4 Link Types 定义

| Link Type ID | 源 Object | 目标 Object | 说明 |
|--------------|-----------|-------------|------|
| located_in | Store | Region | 门店位于区域 |
| has_employee | Store | Employee | 门店拥有员工 |
| has_near_expiry | Store | NearExpiryProduct | 门店拥有临期商品 |
| is_instance_of | NearExpiryProduct | Product | 临期商品是商品实例 |
| manages | Employee | Store | 店长管理门店 |
| has_task | Store | Task | 门店有任务 |
| created_for | Task | NearExpiryProduct | 任务针对临期商品 |

### 3.5 Action Types 定义

#### 3.5.1 clearance (出清)

对临期商品进行出清处理，创建 Task 记录。

| 字段 | 值 |
|------|-----|
| ID | clearance |
| Display Name | 出清 |
| Target | NearExpiryProduct |
| Requires Approval | true |

**Parameters（参数）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| discount | integer | 是 | 折扣百分比(0-100) |
| quantity | integer | 是 | 出清数量 |
| notes | string | 否 | 备注 |

**Submission Criteria（提交条件）：**

| 条件 | 失败消息 |
|------|----------|
| discount ∈ [0, 100] | 折扣必须在 0-100 之间 |
| target.status != 'expired' | 已过期商品不能出清 |
| target 存在 | 操作目标不存在 |

---

#### 3.5.2 transfer (调拨)

门店间调拨商品。

| 字段 | 值 |
|------|-----|
| ID | transfer |
| Target | Product |

**Parameters（参数）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| from_store | string | 是 | 源门店ID |
| to_store | string | 是 | 目标门店ID |
| quantity | integer | 是 | 调拨数量 |
| notes | string | 否 | 备注 |

---

#### 3.5.3 restock (补货)

补充商品库存。

| 字段 | 值 |
|------|-----|
| ID | restock |
| Target | Product |

**Parameters（参数）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| quantity | integer | 是 | 补货数量 |
| supplier_id | string | 是 | 供应商ID |
| notes | string | 否 | 备注 |

---

### 3.6 折扣规则（Discount Rules）

折扣规则由 **Skill** 描述，不作为独立的 Object Type。

| 层级 | 剩余天数 | 折扣率 | 建议折扣 |
|------|---------|--------|---------|
| T1 | ≤3 天 | 70% off | 70% |
| T2 | 4-7 天 | 50% off | 50% |
| T3 | 8-14 天 | 30% off | 30% |

折扣由 `NearExpiryProduct.discount_tier` 字段决定。Skill 中的 `clearance-workflow` 描述完整计算规则，LLM 读取后自动推荐合适折扣。

---

## 4. 数据模型

### 4.1 数据目录结构

```
data/
├── stores.json              # 门店数据
├── regions.json             # 区域数据
├── employees.json           # 员工数据
├── products.json            # 商品数据
├── near_expiry_products.json  # 临期商品数据
└── tasks.json               # 通用任务数据（Action Instance 记录）
```

> 注意：`clearance_tasks.json` 已合并为通用的 `tasks.json`，通过 `type` 字段区分操作类型。

### 4.2 JSON Schema

#### 4.2.1 stores.json

```json
[
  {
    "id": "store_001",
    "name": "北京朝阳店",
    "region_id": "region_002",
    "address": "北京市朝阳区建国路88号",
    "manager_id": "emp_001",
    "created_at": "2024-01-15T08:00:00"
  }
]
```

#### 4.2.2 regions.json

```json
[
  { "id": "region_001", "name": "华东区", "code": "HD" },
  { "id": "region_002", "name": "华北区", "code": "HB" }
]
```

#### 4.2.3 employees.json

```json
[
  {
    "id": "emp_001",
    "name": "张三",
    "store_id": "store_001",
    "role": "manager",
    "phone": "13800138000"
  }
]
```

#### 4.2.4 products.json

```json
[
  {
    "id": "prod_001",
    "name": "蒙牛纯牛奶",
    "category": "乳制品",
    "brand": "蒙牛",
    "unit": "盒",
    "cost_price": 3.5,
    "retail_price": 5.0
  }
]
```

#### 4.2.5 near_expiry_products.json

```json
[
  {
    "id": "nep_001",
    "product_id": "prod_001",
    "store_id": "store_001",
    "batch_no": "B20260501",
    "production_date": "2026-04-25",
    "expiry_date": "2026-05-27",
    "stock_quantity": 50,
    "days_left": 5,
    "discount_tier": "T2",
    "status": "expiring"
  }
]
```

#### 4.2.6 tasks.json（通用 Task）

```json
[
  {
    "id": "task_001",
    "type": "clearance",
    "target_id": "nep_001",
    "store_id": "store_001",
    "assignee_id": "emp_001",
    "status": "pending",
    "params_json": { "discount": 50, "quantity": 30 },
    "result_json": {},
    "priority": "high",
    "notes": "优先处理",
    "created_at": "2026-05-21T08:00:00",
    "started_at": null,
    "completed_at": null
  }
]
```

---

## 5. Skills 系统

### 5.1 Skill 架构

Deep Agents 的 **SkillsMiddleware** 从 `backend/skills/` 目录加载 SKILL.md 文件，实现 Progressive Disclosure（渐进式披露）：

- **首次加载**：system prompt 只注入 skill 的 `name` + `description`（几行）
- **按需读取**：LLM 遇到相关场景时，主动 `read_file` 读取完整 SKILL.md
- **token 节省**：多轮对话中 schema 不重复发送

### 5.2 Skill 文件结构

```
backend/skills/store-ontology/
├── store-ontology/              ← 本体知识 Skill
│   └── SKILL.md
└── clearance-workflow/          ← 出清工作流 Skill
    └── SKILL.md
```

### 5.3 store-ontology Skill

本体领域知识，包含 Object Types、Link Types 和工具使用策略。

**allowed_tools：** 所有通用工具

### 5.4 clearance-workflow Skill

出清工作流规范，包含折扣规则、Preview→Confirm 流程和禁止事项。

**allowed_tools：** `query_near_expiry`, `execute_action`, `confirm_action`, `query_task`, `update_task`, `query_entity`, `update_entity`

**折扣规则：**

| 层级 | 剩余天数 | 折扣率 | 建议折扣 |
|------|---------|--------|---------|
| T1 | ≤3 天 | 70% off | 70% |
| T2 | 4-7 天 | 50% off | 50% |
| T3 | 8-14 天 | 30% off | 30% |

---

## 6. 功能模块

### 6.1 AI助手模块

#### 6.1.1 功能描述

通过自然语言对话，为用户提供临期商品管理服务。Agent 通过 Skills 理解业务规则，通过通用工具执行操作，在关键操作前请求用户确认。

#### 6.1.2 工具清单

| 工具 | 类型 | 用途 |
|------|------|------|
| `execute_action` | 通用 | Preview 模式：验证参数，返回操作预览 |
| `confirm_action` | 通用 | 用户确认后实际执行，创建 Task 记录 |
| `query_task` | 通用 | 按 type/store_id/status 过滤查询任务 |
| `update_task` | 通用 | 修改任务状态/备注 |
| `query_entity` | 通用 | 查询任意实体 |
| `create_entity` | 通用 | 创建实体 |
| `update_entity` | 通用 | 修改实体 |
| `traverse_relation` | 通用 | 遍历关系链 |
| `query_near_expiry` | 业务 | 查询临期商品列表 |

**工具设计原则：**
- **通用工具**：基于 TTL 本体注册表，通过 `entity_type` 参数动态路由到对应 JSON 文件
- **Action 工具**：`execute_action` + `confirm_action` 成对使用，遵循 Preview → Confirm 模式
- **Skill 驱动**：业务规则（折扣算法、工作流步骤）在 Skill 中描述，Tool 只负责执行

#### 6.1.3 对话能力

| 能力 | 示例对话 | 触发工具 |
|------|----------|----------|
| 查询任意实体 | "store_001 有哪些员工" | `query_entity(type="employee", store_id="store_001")` |
| 遍历关系 | "张三属于哪个门店" | `traverse_relation(Employee, emp_001, manages)` |
| 查询临期商品 | "查看门店的临期商品" | `query_near_expiry(store_id="store_001")` |
| 创建出清任务 | "帮我出清这些临期商品" | `execute_action(type="clearance", ...)` → HITL → `confirm_action(...)` |
| 查询任务 | "有哪些出清任务" | `query_task(type="clearance")` |
| 修改任务 | "把这个任务标记完成" | `update_task(task_id="...", status="completed")` |

#### 6.1.4 CopilotKit 五大功能实现

##### Generative UI

**实现方式：** `<CopilotKit renderToolCalls={[...]}>` prop。

```tsx
// app/layout.tsx
function TaskCard({ text }: { text: string }) {
  return (
    <div style={{padding:12,background:'#f0fdf4',borderRadius:8}}>
      <pre>{text}</pre>
    </div>
  )
}

export default function RootLayout({ children }) {
  const renderToolCalls = useMemo(() => [
    {
      name: 'execute_action',
      render: ({ status, result }) => {
        if (status === 'executing') return <div>🔍 执行中...</div>
        if (status === 'complete' && result) return <TaskCard text={result} />
        return <></>
      },
    },
    {
      name: 'query_near_expiry',
      render: ({ status, result }) => {
        if (status === 'complete' && result) return <TaskCard text={result} />
        return <></>
      },
    },
  ], [])

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="default" renderToolCalls={renderToolCalls}>
      {children}
      <CopilotPopup />
    </CopilotKit>
  )
}
```

##### Shared State

**实现方式：** `useCoAgent({ name, initialState })`。

```tsx
// app/home-page.tsx
const { state: agentState, setState: setAgentState } = useCoAgent<{
  selected_store: string
}>({
  name: 'default',
  initialState: { selected_store: 'store_001' },
})
```

##### Human-in-the-Loop

**实现方式：** `execute_action` 返回预览，LLM 询问用户确认，用户回复后调用 `confirm_action`。

```
用户: "帮我出清 nep_001"
  → execute_action → 返回预览
  → LLM 询问: "是否确认执行？"
用户: "确认"
  → confirm_action → 实际创建任务
```

##### Backend Tool Rendering

**实现方式：** `ag_ui_langgraph` 原生支持。`@tool` 函数通过 LangGraph 执行后，结果通过 AG-UI 协议流式传输到前端，CopilotKit 自动匹配 `renderToolCalls` 中注册的渲染器。

##### Chat UI

**实现方式：** `CopilotPopup` + MiniMax 流式对话。

```tsx
<CopilotKit runtimeUrl="/api/copilotkit" agent="default">
  <CopilotPopup labels={{ title: 'AI 门店助手' }} />
</CopilotKit>
```

---

## 7. 项目文件结构

```
store-ontology/
├── backend/
│   ├── __init__.py
│   ├── main.py                      # FastAPI 入口 + Deep Agent Graph
│   ├── models/
│   │   └── schemas.py              # Pydantic models: ActionType枚举 + Task
│   ├── ontology/
│   │   ├── store.ttl               # 本体定义（Object/Link/Action Types）
│   │   ├── parser.py               # TTL 解析器 + 单例 get_ontology_parser()
│   │   └── tools.py                # 通用工具（execute/query/update）
│   └── skills/
│       └── store-ontology/
│           ├── store-ontology/
│           │   └── SKILL.md        # 本体知识
│           └── clearance-workflow/
│               └── SKILL.md        # 出清工作流（含折扣规则）
├── frontend/                         # Next.js 15 + CopilotKit
├── data/                            # JSON 实例数据
│   ├── stores.json
│   ├── regions.json
│   ├── employees.json
│   ├── products.json
│   ├── near_expiry_products.json
│   └── tasks.json
├── docs/
│   └── 项目设计文档.md
└── .env
```

---

## 8. 启动方式

### 后端

```bash
cd backend
conda run -n store-ontology python main.py
# 端口: 8123
```

### 前端

```bash
cd frontend
NODE_ENV=development npm run dev
# 端口: 3000
```
