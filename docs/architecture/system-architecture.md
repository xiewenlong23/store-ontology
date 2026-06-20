# 系统架构文档

> **版本**：0.1.0（MVP）
> **最后更新**：2026-06-20

---

## 1. 平台定位

**OntologyAgent 是一个本体驱动的通用 AI Agent 平台。**

通用内核提供：本体元数据 + CRUD + 多租户抽象 + 权限/审计/观测 + Agent harness + Tool/Skill 体系。

各行业 vertical（零售、物流、制造……）在本体之上构建领域实体与工作流。**临期商品零售是第一个 vertical，作为内核能力的验证场景与首个落地 demo。**

> 详细的设计决策、三文档 reconcile、MVP/v2 边界，见[目标架构设计文档](../superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md)。

---

## 2. 五层架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│  第5层：用户交互入口                                                      │
│  CopilotKit v1.57 · Chat UI · Generative UI (9 renderToolCalls)        │
│  tenant/门店选择器 · AG-UI 协议代理 (route.ts)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  第4层：Agent 层                                                          │
│  Deep Agents (cauchyturing/deepagents)                                  │
│  create_deep_agent · 工具循环 · SummarizationMiddleware                   │
│  SkillsMiddleware · 4 层系统提示组装                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  第3层：Tools / Action Types / Skills / 计算逻辑                          │
│  Tool（4 类）：查询 / CRUD / Action 执行 / 业务查询                        │
│  Action Type：声明式变更契约（YAML · parameters + submission_criteria）   │
│  Skill（SKILL.md）：流程编排类 · 领域知识类                                │
│  计算逻辑：普通 Python 模块（calculate_discount 等）                       │
├─────────────────────────────────────────────────────────────────────────┤
│  第2层：Ontology 层                                                       │
│  OntologyParser（TTL + YAML）→ EntityRegistry（内存注册表）                │
│  Repository 抽象层（JSONFileRepository · tenant_id 过滤）                 │
│  Object Type × 6 · Link Type × 7 · Action Type × 3                      │
├─────────────────────────────────────────────────────────────────────────┤
│  第1层：LLM + 存储                                                        │
│  LLM：MiniMax-M2.7-highspeed（OpenAI 兼容，未来多 provider）              │
│  存储：JSON 文件（data/*.json）→ Repository → PostgreSQL+JSONB（v2）       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 各层职责

| 层 | 职责 | 关键组件 | MVP 状态 |
|----|------|---------|---------|
| **第1层** | LLM 推理能力 + 数据持久化 | MiniMax-M2.7 · JSON 文件 · fcntl 文件锁 | ✅ 已实现 |
| **第2层** | 描述世界——实体、关系、行为契约的定义与存储 | OntologyParser · EntityRegistry · Repository | ⚠️ 部分实现（缺 Repository 抽象和 YAML Action Type） |
| **第3层** | 操作世界——LLM 的手和眼睛 | 9 个 Tool · 3 个 Action Type · 2 个 Skill · 计算逻辑 | ⚠️ 部分实现（缺计算逻辑抽取、Action 契约补全） |
| **第4层** | 编排——串联 LLM + Tool + Skill 完成任务 | Deep Agent · SkillsMiddleware · 系统提示 | ✅ 已实现 |
| **第5层** | 人机交互——Chat UI + Generative UI + tenant 选择 | CopilotKit · 9 个 renderToolCalls · route.ts | ⚠️ 部分实现（tenant 传递链路未通） |

---

## 3. 核心概念模型

### 3.1 六概念分工

OntologyAgent 的地基。混淆大多来自没区分清楚这些概念。

```
                    ┌─────────────────────────┐
                    │     LLM（消费者）         │
                    └────┬──────────┬──────────┘
                         │          │
              ┌──────────▼──┐  ┌────▼──────────┐
              │   Skill     │  │    Tool        │
              │ (读指令文档)  │  │ (调用函数)      │
              └──────┬──────┘  └────┬──────────┘
                     │               │
         ┌───────────▼──────┐  ┌────▼──────────┐
         │    计算逻辑       │  │  Action Type   │
         │ (普通 Python)     │  │ (声明式变更契约) │
         └───────┬──────────┘  └────┬──────────┘
                 │                   │
                 └───────┬───────────┘
                         │
              ┌──────────▼──────────┐
              │  Object / Link Type  │
              │   (本体定义)          │
              └─────────────────────┘
```

| 概念 | 性质 | LLM 关系 | 何时用 |
|------|------|---------|-------|
| **Object / Link Type** | 本体定义·实体与关系 | 经 `build_ontology_prompt` 让 LLM 理解世界结构 | 建模领域实体与关系 |
| **Action Type** | 本体定义·声明式变更契约 | LLM 不直接执行，经 `execute_action` Tool 调用；后端自动化也调同一套 | 描述受治理的业务事务 |
| **Tool** | 执行机制·LLM 直接调用的函数 | LLM 直接 invoke（schema 注入 prompt） | LLM 读数据、调 Action、与外部交互 |
| **Skill** | 执行机制·给 LLM 读的指令文档 | LLM 按需 `read_file` | 流程编排、领域知识、策略指南 |
| **计算逻辑** | 普通代码·命名 Python 模块 | LLM 不可见（除非包成 Tool） | 跨工具复用的纯计算 |
| **Interface Type** | 本体定义·抽象类型 | v2，MVP 不实现 | 跨 Object 共享形状 |

### 3.2 Action Type 与 Tool 的关系

这是最容易混淆的一对。**不在同一层级。**

```
Action Type 层（业务维度）          Tool 层（技术维度）
┌─────────────────────┐          ┌──────────────────────┐
│ clearance            │──1:N────►│ execute_action       │
│ transfer             │          │ confirm_action       │
│ restock              │          │ query_entity         │
│ (未来: submit,       │          │ create_entity        │
│  accept, deduct...)  │          │ update_entity        │
└─────────────────────┘          │ traverse_relation    │
                                  │ query_task           │
  双消费者：                        │ update_task          │
  ┌── LLM（经 execute_action）      │ query_near_expiry    │
  └── 后端自动化（直接调执行器）      └──────────────────────┘
```

核心规则：
1. **层级不同**：Action Type 是业务事务维度，Tool 是技术接口维度
2. **1:N 映射**：一个 `execute_action` Tool 执行多个 Action Type
3. **双消费者**：Action Type 被 LLM 和后端自动化共用，走同一套校验/权限/审计
4. **边界**：Action Type 只管写操作（受治理的变更）；读操作（query_*）是纯 Tool
5. **治理强制**：核心实体的写操作锁为 edits-only-via-actions，通用 CRUD 被降级
6. **execute_action 是瘦路由器**：读定义 → 校验 → 执行声明的变更 → 触发副作用 → 写审计 → 返回

### 3.3 本体 Vertical 分层

```
┌─────────────────────────────────────┐
│  零售 Vertical（MVP）                │
│  Region / Store / Employee           │
│  Product / NearExpiryProduct / Task  │
│  clearance / transfer / restock      │
│  clearance-workflow Skill             │
└──────────────┬──────────────────────┘
               │ 继承
┌──────────────▼──────────────────────┐
│  通用内核                             │
│  Object/Link/Action Type 元数据      │
│  Repository · PermissionEvaluator     │
│  Agent Harness · Tool/Skill 体系      │
│  审计 · 观测                           │
└─────────────────────────────────────┘
```

通用内核不包含任何行业特定逻辑，可复用到任意行业 vertical。

---

## 4. 模块设计

### 4.1 第2层：Ontology 层

```
backend/ontology/
├── store.ttl              ← Object Type / Link Type 定义（声明式 schema）
├── actions/                ← Action Type 定义（YAML，MVP 新增）
│   ├── clearance.yaml
│   ├── transfer.yaml
│   └── restock.yaml
├── parser.py               ← OntologyParser：TTL + YAML → EntityRegistry
└── tools.py                ← 9 个 @tool 函数（第3层，但依赖本层的 EntityRegistry）
```

#### OntologyParser

```
store.ttl + actions/*.yaml
        │
        ▼
OntologyParser._parse()
        │ 正则解析 TTL（Object/Link Type）
        │ YAML 加载 actions/（Action Type）
        ▼
EntityRegistry（内存注册表，单例）
├── object_types: Dict[str, ObjectType]     # 6 个
├── link_types: Dict[str, LinkType]         # 7 个
└── action_types: Dict[str, ActionType]     # 3 个
```

- **单例模式**：`get_ontology_parser()` 返回模块级 `_parser_instance`
- **默认路径**：TTL = `backend/ontology/store.ttl`，data = `data/`
- **build_system_prompt()**：从 EntityRegistry 生成中文本体描述，注入 Agent 系统提示

#### EntityRegistry 数据结构

```python
@dataclass
class PropertyDef:
    name: str           # "store_id"
    type: str           # "string" / "integer" / "float" / "datetime" / enum

@dataclass
class ObjectType:
    id: str             # "NearExpiryProduct"
    label: str          # "Near Expiry Product"
    comment: str         # 描述
    properties: List[PropertyDef]
    storage_file: str    # "near_expiry_products.json"
    label_zh: str       # "临期商品"

@dataclass
class LinkType:
    id: str             # "has_near_expiry"
    label: str          # "has near expiry"
    domain: str         # "Store"（起点）
    range: str          # "NearExpiryProduct"（终点）
    via: str            # "store_id"（关联字段）
    label_zh: str       # "拥有临期商品"

@dataclass
class ActionType:
    id: str             # "clearance"
    label: str          # "Clearance"
    description: str    # 描述
    input_fields: List[PropertyDef]
    output_type: str
    requires_approval: bool    # 当前硬编码 True，未实际检查
    label_zh: str       # "出清"
    # MVP 新增字段（从 YAML 加载）:
    submission_criteria: dict  # {roles, conditions}
    side_effects: list
    edits_object_types: list
```

#### Repository 抽象层（MVP 新增）

```
Repository 接口（抽象基类）
├── read(entity_type, tenant_id, filters?) → List[dict]
├── read_one(entity_type, entity_id, tenant_id) → dict | None
├── write(entity_type, entity_id, data, tenant_id, bypass_action_check=False)
├── create(entity_type, data, tenant_id, bypass_action_check=False)
└── list_entity_types() → List[str]

实现：
├── JSONFileRepository（MVP）
│     data/*.json
│     fcntl.flock 文件锁
│     原子写入（临时文件 + os.rename）
│     tenant_id 过滤（list comprehension）
└── PostgresRepository（v2，PostgreSQL + JSONB）
```

Repository 是所有数据访问的唯一入口。Tool 不直接 `_load_json`/`_save_json`，改调 `repository.read()`/`repository.write()`。

### 4.2 第3层：Tool / Action / Skill

#### Tool 分类

```
Tool（9 个，分 4 类）
├── 查询类（OS 原子 + 业务原子）
│   ├── query_entity          → 通用实体查询（按 type/id/store_id/字段过滤）
│   ├── query_task            → 任务查询（按 action_type/store_id/status）
│   ├── query_near_expiry     → 临期商品查询（关联 product 计算折扣价）
│   └── traverse_relation     → 关系遍历（按 LinkType 的 domain/range/via）
├── CRUD 类（降级，仅限非业务数据）
│   ├── create_entity         → 通用创建（生成 UUID，追加 JSON）
│   └── update_entity         → 通用更新（按 id 合并字段）
├── Action 执行类
│   ├── execute_action         → Preview（不写数据，生成预览）
│   └── confirm_action        → Confirm（实际执行，创建 Task）
└── 任务操作类
    └── update_task           → 任务状态/备注更新
```

> **安全设计**：`create_entity`/`update_entity` 在 MVP 中被 `edits_only_via_actions` 拦截——对 NearExpiryProduct、Task 等核心实体的写操作会被 Repository 拒绝。这两个工具降级为仅用于非业务数据或管理场景。

#### Tool 返回值格式

所有 Tool 返回 **字符串**，结构化数据嵌入在 `<!--COPILOTKIT_DATA-->` 标记中：

```
{人类可读的摘要文本}
<!--COPILOTKIT_DATA-->
{"type": "near_expiry_list", "data": [...]}
<!--/COPILOTKIT_DATA-->
```

前端 `renderToolCalls` 通过正则提取此 JSON block，根据 `type` 渲染对应的 Generative UI 组件。

#### Action Type 契约

```yaml
# ontology/actions/clearance.yaml
api_name: clearance
display_name: 出清
description: 对临期商品进行出清处理，创建 Task 记录
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]
parameters:
  - { name: discount, type: integer, required: true, constraint: "0..100" }
  - { name: quantity, type: integer, required: true }
  - { name: notes, type: string, required: false }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is_not, value: expired, fail_msg: "已过期商品不能出清" }
side_effects:
  - { type: notification, template: clearance_created, recipients: [assignee_id, manager_id] }
```

> 完整的 Tool Schema 和数据模型定义见 [API 与数据契约规范](./api-and-data-spec.md)。

#### Skill 加载机制

```
backend/skills/
├── store-ontology/
│   ├── SKILL.md              ← 领域知识类（本体实体、关系、工具使用策略）
│   └── clearance-workflow/
│       └── SKILL.md          ← 流程编排类（出清 7 步工作流）
```

- Deep Agents 的 `FilesystemBackend` 以 `virtual_mode=True` 加载 Skill
- `SkillsMiddleware` 在 Agent 循环中按需注入 SKILL.md 内容（Progressive Disclosure）
- 每个 SKILL.md 有 YAML frontmatter（name, description, allowed_tools）
- Skill 按 `type` 字段分为：**流程编排类**（workflow）和**领域知识类**（domain_knowledge）

### 4.3 第4层：Agent 层

```
main.py
│
├── ChatOpenAI（LLM 客户端）
│     base_url → QWEN_BASE_URL（默认 MiniMax）
│     model → QWEN_MODEL（默认 MiniMax-M2.7-highspeed）
│
├── create_deep_agent()
│     ├── model（LLM）
│     ├── tools（9 个 @tool）
│     ├── system_prompt（4 层组装，见下）
│     ├── MemorySaver（checkpoint，内存持久化）
│     ├── FilesystemBackend(skills_root, virtual_mode=True)
│     └── skill_filter=["/store-ontology/"]
│
└── FastAPI
      ├── CORS middleware（localhost:3000）
      ├── GET /health
      └── POST /api/copilotkit（AG-UI 端点）
```

#### 系统提示 4 层组装

```
Layer 1: Agent 身份与核心原则（固定）
  "你是 AI 门店大脑助手..."

Layer 2: 本体知识（build_ontology_prompt 动态生成）
  "系统中有以下实体类型：Store（门店）... 可用关系：has_employee..."

Layer 3: 当前 tenant 上下文（动态注入）
  "当前用户选择的门店ID是: {tenant_id}"   ← 从 RequestContext 读取

Layer 4: 可用工具清单（Deep Agents 自动注入）
  Tool schema 由 @tool 装饰器自动提取，注入 prompt
```

#### Deep Agents 中间件

| 中间件 | 作用 |
|--------|------|
| **SummarizationMiddleware** | 长对话自动压缩上下文，避免 token 溢出 |
| **SkillsMiddleware** | 按需加载 SKILL.md 内容，Progressive Disclosure |
| **DeltaChannel** | 高效 checkpoint 流式传输，减少 SSE 数据量 |

### 4.4 第5层：前端层

```
frontend/app/
├── layout.tsx              ← 根布局：CopilotKit Provider + 9 个 renderToolCalls
├── page.tsx                ← 入口页（force-dynamic）
├── home-page.tsx           ← 主内容：门店概览 + AI 能力列表 + tenant 选择器
├── api/copilotkit/
│   └── route.ts            ← AG-UI 代理：CopilotRuntime → LangGraphHttpAgent → 后端
└── globals.css             ← 样式
```

#### Generative UI 渲染

每个 Tool 对应一个 `renderToolCalls` 条目，根据 `status`（`executing`/`complete`）渲染不同 UI：

| Tool | executing | complete |
|------|-----------|----------|
| `query_near_expiry` | 蓝色 spinner | 商品卡片列表（名称、品牌、层级 badge、库存、过期进度条、折扣价） |
| `query_task` | 蓝色 spinner | 任务列表（类型标签、状态 badge、目标、门店） |
| `execute_action` | 蓝色 spinner | 黄色边框预览卡（操作类型、目标详情、折扣、执行人） |
| `confirm_action` | 绿色 spinner | 成功/失败卡（task_id、操作类型） |
| `query_entity` | 蓝色 spinner | 实体详情（键值网格）或实体列表（卡片） |
| `traverse_relation` | 蓝色 spinner | 箭头样式关系列表 |
| 其他（create/update） | 彩色 spinner | 成功/失败消息 |

---

## 5. 数据流

### 5.1 完整请求链路

```
用户输入 "帮我处理临期商品"
        │
        ▼
[第5层] CopilotKit React Client
        │ useCoAgent() 共享状态 { selected_store: "store_001" }
        │ POST /api/copilotkit（SSE 流）
        ▼
[第5层] route.ts（AG-UI 代理）
        │ CopilotRuntime + ExperimentalEmptyAdapter
        │ → LangGraphHttpAgent(http://localhost:8123/api/copilotkit)
        ▼
[第4层] FastAPI + ag_ui_langgraph
        │ LangGraphAgent → deep_agent_graph
        ▼
[第4层] Deep Agent（工具循环）
        │
        │  1. SkillsMiddleware 加载 clearance-workflow/SKILL.md
        │  2. LLM 判断需要查询临期商品
        │  3. LLM 调用 query_near_expiry(store_id="store_001")
        ▼
[第3层] Tool: query_near_expiry()
        │  1. _get_registry() → EntityRegistry（查 NearExpiryProduct 定义）
        │  2. repository.read("NearExpiryProduct", tenant_id, store_id="store_001")
        │  3. 关联 Product（计算原价）
        │  4. calculate_discount(tier)（计算逻辑）
        │  5. 返回字符串 + <!--COPILOTKIT_DATA--> JSON
        ▼
[第4层] Deep Agent（继续循环）
        │  4. LLM 展示结果，等待用户选择商品
        │  5. 用户选择后，LLM 调用 execute_action(action_type="clearance", ...)
        ▼
[第3层] Tool: execute_action()
        │  1. 校验 action_type 存在、目标存在、约束满足
        │  2. 生成 preview 数据（不写存储）
        │  3. 存入 preview 缓存，返回 preview_id
        │  4. 返回预览字符串 + <!--COPILOTKIT_DATA--> JSON
        ▼
[第4层] Deep Agent
        │  6. LLM 展示预览，询问确认
        │  7. 用户确认后，LLM 调用 confirm_action(preview_id=..., ...)
        ▼
[第3层] Tool: confirm_action()
        │  1. 校验 preview_id 有效且未过期
        │  2. permission_gate.check("confirm_action", context)
        │  3. repository.write("Task", data, bypass_action_check=True)
        │  4. 写审计日志
        │  5. 返回成功信息
        ▼
[第4层] Deep Agent → LangGraph → AG-UI SSE 流
        ▼
[第5层] renderToolCalls 提取 <!--COPILOTKIT_DATA-->
        │ 渲染 Generative UI（预览卡 → 成功卡）
        ▼
用户看到：商品列表 → 预览 → 确认 → 成功
```

### 5.2 Preview→Confirm 治理链路

```
execute_action(...)              confirm_action(preview_id=...)
       │                                    │
       ▼                                    ▼
  校验 Action Type                     校验 preview_id
  校验目标存在                         查缓存是否存在
  校验参数约束                         检查未过期（5min TTL）
       │                                    │
       ▼                                    ▼
  生成 preview 数据                   提取缓存的 preview
  生成 preview_id                     二次校验（action/target/params）
       │                                    │
       ▼                                    ▼
  存入内存缓存                         permission_gate.check()
  key = {action}:{target}:{hash}      repository.write(..., bypass=True)
  TTL = 5 分钟                         写审计日志
       │                                    │
       ▼                                    ▼
  返回 preview_id + 预览数据           删除缓存 → 返回结果
```

---

## 6. 技术选型

| 层 | 技术 | 版本 | 选型理由 |
|----|------|------|---------|
| **前端框架** | Next.js | 15 | App Router + Server Components，与 CopilotKit 集成成熟 |
| **Agent UI** | CopilotKit | 1.57.4 | Chat UI + Generative UI + Shared State + HITL，一站式前端 Agent 框架 |
| **UI 协议** | AG-UI | — | CopilotKit 定义的标准 Agent-UI 通信协议，SSE 流式 |
| **后端框架** | FastAPI | 0.115+ | 异步、自动 OpenAPI、与 LangGraph 集成简单 |
| **Agent 框架** | Deep Agents (cauchyturing) | latest | LangGraph Agent，工具循环 + SkillsMiddleware + SummarizationMiddleware |
| **LLM 接入** | langchain-openai ChatOpenAI | — | OpenAI 兼容协议，可切 MiniMax/Qwen/其他 provider |
| **LLM 模型** | MiniMax-M2.7-highspeed | — | 中文能力强，高性价比，OpenAI 兼容 |
| **本体格式** | Turtle (TTL) | — | W3C 标准 RDF 格式，声明式 schema 定义 |
| **Action 格式** | YAML | — | 嵌套结构友好（parameters/submission_criteria/side_effects），比 TTL 扩展更轻量 |
| **数据存储** | JSON 文件 | — | MVP 零依赖，未来通过 Repository 抽象迁移到 PostgreSQL+JSONB |
| **前端语言** | TypeScript | 5.8 | 类型安全，CopilotKit 生态标准 |
| **后端语言** | Python | 3.11+ | LangChain/LangGraph 生态标准 |

---

## 7. 目录结构

```
store-ontology/
├── .env.example                    # 环境变量模板
├── README.md                       # 项目说明
│
├── backend/
│   ├── main.py                     # FastAPI 入口 · Agent 创建 · AG-UI 端点
│   ├── pyproject.toml              # Python 依赖
│   ├── models/
│   │   └── schemas.py              # Pydantic 模型 · Enums · LinkTypes 常量
│   ├── ontology/
│   │   ├── store.ttl               # 本体定义（Object/Link Type）
│   │   ├── actions/                # Action Type 定义（YAML）[MVP 新增]
│   │   │   ├── clearance.yaml
│   │   │   ├── transfer.yaml
│   │   │   └── restock.yaml
│   │   ├── parser.py               # OntologyParser · EntityRegistry 单例
│   │   └── tools.py                # 9 个 @tool 函数 · build_ontology_prompt
│   ├── business/                    # 计算逻辑模块 [MVP 新增]
│   │   └── discount.py              # calculate_discount() · 单一事实源
│   ├── repository/                  # Repository 抽象层 [MVP 新增]
│   │   ├── base.py                  # Repository 抽象基类
│   │   └── json_repository.py       # JSONFileRepository 实现
│   ├── permissions/                 # 权限模块 [MVP 新增]
│   │   ├── evaluator.py             # PermissionEvaluator 接口
│   │   └── rbac.py                  # MVPRbacEvaluator 实现
│   └── skills/
│       └── store-ontology/
│           ├── SKILL.md             # 领域知识 Skill
│           └── clearance-workflow/
│               └── SKILL.md         # 出清流程 Skill
│
├── data/                            # JSON 数据文件
│   ├── regions.json
│   ├── stores.json
│   ├── employees.json
│   ├── products.json
│   ├── near_expiry_products.json
│   ├── tasks.json
│   └── discount_rules.json
│
├── frontend/
│   ├── package.json
│   └── app/
│       ├── layout.tsx               # CopilotKit Provider + 9 renderToolCalls
│       ├── page.tsx                 # 入口页
│       ├── home-page.tsx            # 主内容 · tenant 选择器
│       └── api/copilotkit/
│           └── route.ts             # AG-UI 代理
│
└── docs/
    ├── architecture/                # 📋 本目录：架构与规范文档
    ├── superpowers/specs/           # 设计决策文档
    ├── palantir-ontology-docs/     # Palantir 参考
    ├── 项目设计文档.md                # 现有 demo 设计
    ├── Harness-Design.md            # 零售深度特化愿景
    ├── ontologyagent-design-CN.md   # 通用平台想法
    └── 业务本体建模规范.md            # 本体建模规范
```

> `[MVP 新增]` 标记的文件/目录是本轮 MVP 需要新建的。其余是已有文件。

---

## 8. 部署架构

### 8.1 本地开发

```
┌──────────────────┐         ┌──────────────────┐
│  前端 (Next.js)   │         │  后端 (FastAPI)   │
│  localhost:3000   │──SSE──→│  localhost:8123   │
│                   │         │                   │
│  CopilotKit UI    │         │  Deep Agent       │
│  Generative UI    │         │  9 Tools          │
│                   │         │  data/*.json      │
└──────────────────┘         └──────────────────┘
                                      │
                                 MiniMax API
                                (外部 LLM)
```

启动命令：

```bash
# 后端
cd backend && pip install -e ".[dev]" && python main.py

# 前端
cd frontend && npm install && npm run dev
```

### 8.2 MVP 生产部署

```
┌──────────────────┐
│   Nginx          │
│   (反向代理)      │
│   :80/:443       │
└────┬────────┬────┘
     │        │
     ▼        ▼
┌─────────┐  ┌──────────────────┐
│ 前端    │  │ 后端 (FastAPI)    │
│ (静态)  │  │ (uvicorn workers) │
│         │  │                   │
│         │  │ Deep Agent         │
│         │  │ Repository         │
│         │  │ data/*.json       │
└─────────┘  └────────┬─────────┘
                      │
                 MiniMax API
```

- 前端 `next build` → `next start` 或 Nginx 托管静态文件
- 后端 `uvicorn main:app --workers 2 --host 0.0.0.0 --port 8123`
- Nginx 反向代理 `/api/copilotkit` → 后端
- `.env` 配置 LLM API key

### 8.3 v2 部署（架构预留）

```
┌──────────────────┐
│   Nginx / LB      │
└────┬────────┬────┘
     │        │
     ▼        ▼
┌─────────┐  ┌──────────────────┐
│ 前端    │  │ 后端 (FastAPI)    │  ← 多实例
│         │  │ × N               │
└─────────┘  └────────┬─────────┘
                      │
              ┌───────┴────────┐
              │  PostgreSQL    │  ← 替换 JSON 文件
              │  + JSONB       │
              └────────────────┘
                      │
                 多 Provider LLM
```

- 数据存储从 JSON 迁移到 PostgreSQL+JSONB（换 Repository 实现，上层接口不变）
- 后端可水平扩展（多 uvicorn worker/实例）
- 前端可 CDN 分发
