# API 与数据契约规范

> **版本**：0.1.0（MVP）
> **最后更新**：2026-06-20

---

## 1. 端点定义

### 1.1 AG-UI 端点

| 属性 | 值 |
|------|------|
| **路径** | `POST /api/copilotkit` |
| **协议** | AG-UI Protocol（CopilotKit 标准，基于 SSE） |
| **Content-Type** | `application/json`（请求） |
| **响应** | `text/event-stream`（SSE） |

**请求体**：由 CopilotKit 客户端自动构造，包含对话消息和 shared state。后端通过 `ag_ui_langgraph` 的 `add_langgraph_fastapi_endpoint` 自动处理。

**Header 约定（MVP 新增）**：

| Header | 方向 | 说明 |
|--------|------|------|
| `X-Tenant-ID` | 前端 → 后端 | 租户标识，由 route.ts 从 CopilotKit shared state 提取注入 |

> 当前 MVP 路由 `route.ts` 使用 `ExperimentalEmptyAdapter` 直接代理，无 hook 修改 header 的能力。MVP 需改为自定义 fetch wrapper 或 CopilotKit 中间件来注入 `X-Tenant-ID`。

### 1.2 Health Check 端点

| 属性 | 值 |
|------|------|
| **路径** | `GET /health` |
| **响应** | `{"status": "ok"}` |

---

## 2. Tool Schema 规范

### 2.1 通用返回值格式

所有 Tool 返回 **字符串**（`langchain_core.tools.tool` 约定）。结构化数据嵌入在 HTML 注释标记中：

```
{人类可读的摘要文本}
<!--COPILOTKIT_DATA-->
{"type": "{json_type}", "data": {...}}
<!--/COPILOTKIT_DATA-->
```

- **type**：前端 `renderToolCalls` 据此选择渲染组件
- **data**：对应渲染组件所需的结构化数据

### 2.2 查询类 Tool

#### `query_entity` — 通用实体查询

```python
@tool
def query_entity(
    entity_type: str,          # Object Type 名称，如 "Store"、"Employee"
    entity_id: str = None,     # 精确查询（按 id）
    store_id: str = None,      # 按门店过滤
    filter_field: str = None,  # 自定义过滤字段名
    filter_value: str = None,  # 自定义过滤字段值
) -> str
```

**JSON type**：

查询单个实体（传入 entity_id）：
```json
{"type": "entity_detail", "data": {"id": "store_001", "name": "北京朝阳店", "region_id": "region_001", ...}}
```

查询列表（无 entity_id）：
```json
{"type": "entity_list", "data": [{"id": "store_001", "name": "北京朝阳店"}, {"id": "store_002", "name": "上海浦东店"}]}
```

#### `query_task` — 任务查询

```python
@tool
def query_task(
    action_type: str = None,    # 按 Action Type 过滤
    store_id: str = None,       # 按门店过滤
    status: str = None,         # 按状态过滤
) -> str
```

**JSON type**：
```json
{"type": "task_list", "data": [
  {
    "task_id": "task_xxx",
    "action_type": "clearance",
    "status": "pending",
    "target_name": "有机牛奶",
    "store_name": "北京朝阳店",
    "discount": 50,
    "assignee": "张经理",
    "created_at": "2026-05-22T12:00:00"
  }
]}
```

#### `query_near_expiry` — 临期商品查询

```python
@tool
def query_near_expiry(
    store_id: str = None,       # 按门店过滤
) -> str
```

**JSON type**：
```json
{"type": "near_expiry_list", "data": [
  {
    "id": "nep_001",
    "product_name": "有机牛奶",
    "brand": "蒙牛",
    "batch_no": "B20260510",
    "stock_quantity": 20,
    "expiry_date": "2026-05-25",
    "days_left": 3,
    "discount_tier": "T1",
    "discounted_price": 8.5,
    "urgency_color": "#ef4444"
  }
]}
```

#### `traverse_relation` — 关系遍历

```python
@tool
def traverse_relation(
    source_type: str,   # 起点 Object Type
    source_id: str,     # 起点 entity id
    relation: str,      # Link Type 名称
) -> str
```

**JSON type**：
```json
{"type": "relation_result", "data": {
  "source": {"type": "Store", "id": "store_001", "name": "北京朝阳店"},
  "relation": "has_employee",
  "targets": [
    {"type": "Employee", "id": "emp_001", "name": "张三", "role": "店长"},
    {"type": "Employee", "id": "emp_002", "name": "李四", "role": "店员"}
  ]
}}
```

### 2.3 CRUD 类 Tool

> **注意**：MVP 中 `create_entity`/`update_entity` 被 `edits_only_via_actions` 降级。对 NearExpiryProduct、Task 等核心实体的写操作会被 Repository 拦截。

#### `create_entity` — 通用创建

```python
@tool
def create_entity(
    entity_type: str,    # Object Type 名称
    name: str = None,     # 实体名称（便捷参数）
    **kwargs,             # 其他字段
) -> str
```

**JSON type**：
```json
{"type": "create_result", "data": {"entity_type": "Region", "id": "region_xxx", "name": "华南区", "success": true}}
```

#### `update_entity` — 通用更新

```python
@tool
def update_entity(
    entity_type: str,    # Object Type 名称
    entity_id: str,      # 目标实体 id
    **kwargs,             # 要更新的字段
) -> str
```

**JSON type**：
```json
{"type": "update_result", "data": {"entity_type": "Employee", "id": "emp_001", "updated_fields": ["phone"], "success": true}}
```

### 2.4 Action 执行类 Tool

#### `execute_action` — 操作预览（不写数据）

```python
@tool
def execute_action(
    action_type: str,         # Action Type 名称：clearance / transfer / restock
    target_id: str,            # 目标实体 id
    store_id: str,             # 门店 id
    discount: int = None,      # 折扣（clearance 专用，0-100）
    quantity: int = None,       # 数量
    from_store: str = None,     # 调出门店（transfer 专用）
    to_store: str = None,       # 调入门店（transfer 专用）
    supplier_id: str = None,    # 供应商 id（restock 专用）
    notes: str = None,          # 备注
) -> str
```

**JSON type**：
```json
{
  "type": "action_preview",
  "data": {
    "action_type": "clearance",
    "target": {"id": "nep_001", "product_name": "有机牛奶", "stock_quantity": 20},
    "store": {"id": "store_001", "name": "北京朝阳店"},
    "assignee": {"id": "emp_001", "name": "张经理", "role": "店长"},
    "params": {"discount": 50, "quantity": 10, "notes": "周末促销"},
    "preview_id": "clr_nep001_20260620_abc123"
  }
}
```

#### `confirm_action` — 确认执行（写数据）

```python
@tool
def confirm_action(
    action_type: str,
    target_id: str,
    store_id: str,
    preview_id: str,            # preview 返回的 id，用于治理闭环校验
    discount: int = None,
    quantity: int = None,
    from_store: str = None,
    to_store: str = None,
    supplier_id: str = None,
    notes: str = None,
) -> str
```

**JSON type**：
```json
{
  "type": "action_result",
  "data": {
    "action_type": "clearance",
    "task_id": "task_xxx",
    "target_name": "有机牛奶",
    "status": "pending",
    "success": true,
    "message": "出清任务已创建，等待执行人确认"
  }
}
```

### 2.5 任务操作类 Tool

#### `update_task` — 任务更新

```python
@tool
def update_task(
    task_id: str,         # 任务 id
    **kwargs,             # 要更新的字段（status, notes, assignee_id 等）
) -> str
```

**JSON type**：
```json
{"type": "update_task_result", "data": {"task_id": "task_xxx", "updated_fields": ["status"], "new_status": "completed", "success": true}}
```

### 2.6 Tool JSON Type 速查表

| JSON type | 对应 Tool | 渲染组件 |
|-----------|----------|---------|
| `entity_detail` | query_entity | 键值网格卡片 |
| `entity_list` | query_entity | 实体卡片列表 |
| `task_list` | query_task | 任务列表（状态 badge） |
| `near_expiry_list` | query_near_expiry | 商品卡片列表（进度条、折扣价） |
| `relation_result` | traverse_relation | 箭头关系展示 |
| `action_preview` | execute_action | 黄色边框预览卡 |
| `action_result` | confirm_action | 成功/失败卡 |
| `create_result` | create_entity | 成功消息 |
| `update_result` | update_entity | 成功消息 |
| `update_task_result` | update_task | 成功消息 |

---

## 3. Action Type 契约规范

### 3.1 YAML 格式定义

Action Type 定义存储为 YAML 文件（`backend/ontology/actions/*.yaml`），由 OntologyParser 加载。

```yaml
# 必填字段
api_name: string                   # 编程引用名（snake_case，唯一）
display_name: string               # UI 显示名（中文）
description: string                # 业务含义描述
status: "active" | "experimental" | "deprecated"
target_object_type: string          # 目标 Object Type api_name
edits_object_types: [string]       # 本 Action 会修改的 Object Type 列表

# 参数定义
parameters:
  - name: string                   # 参数名
    type: string                   # 类型：string / integer / float / boolean
    required: boolean
    constraint: string             # 约束表达式（MVP 仅 "0..100" 等简单范围）
    description: string             # 参数说明

# 权限门控
submission_criteria:
  roles: [string]                  # 允许提交的角色白名单
  conditions:                     # 参数级条件（MVP 简化版）
    - field: string                # 目标实体字段路径（如 "target.status"）
      operator: string             # 操作符：is / is_not / gt / lt / gte / lte
      value: any                  # 比较值
      fail_msg: string             # 校验失败时的错误信息

# 副作用声明
side_effects:
  - type: "notification"          # 副作用类型
    template: string               # 通知模板名
    recipients: [string]           # 接收人字段引用
  - type: "state_change"           # 状态变更
    target_field: string           # 目标实体字段
    new_value: string               # 新值
```

### 3.2 现有 3 个 Action Type 完整定义

#### clearance（出清）

```yaml
api_name: clearance
display_name: 出清
description: 对临期商品进行出清处理，创建出清 Task 记录
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]
parameters:
  - { name: discount, type: integer, required: true, constraint: "0..100", description: "折扣百分比（0=无折扣，100=免费）" }
  - { name: quantity, type: integer, required: true, description: "出清数量" }
  - { name: notes, type: string, required: false, description: "备注" }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is_not, value: expired, fail_msg: "已过期商品不能出清" }
    - { field: target.status, operator: is, value: normal, fail_msg: "仅 normal/expiring/low_stock 状态可出清" }
side_effects:
  - { type: state_change, target_field: "status", new_value: "expiring" }
  - { type: notification, template: clearance_created, recipients: [assignee_id, manager_id] }
```

#### transfer（调拨）

```yaml
api_name: transfer
display_name: 调拨
description: 将商品从一家门店调拨到另一家门店
status: active
target_object_type: Product
edits_object_types: [Product, Task]
parameters:
  - { name: from_store, type: string, required: true, description: "调出门店 ID" }
  - { name: to_store, type: string, required: true, description: "调入门店 ID" }
  - { name: quantity, type: integer, required: true, description: "调拨数量" }
  - { name: notes, type: string, required: false, description: "备注" }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: param.quantity, operator: gt, value: 0, fail_msg: "调拨数量必须大于 0" }
side_effects:
  - { type: notification, template: transfer_created, recipients: [from_store_manager_id, to_store_manager_id] }
```

#### restock（补货）

```yaml
api_name: restock
display_name: 补货
description: 向门店补充商品库存
status: active
target_object_type: Product
edits_object_types: [Product, Task]
parameters:
  - { name: quantity, type: integer, required: true, description: "补货数量" }
  - { name: supplier_id, type: string, required: true, description: "供应商 ID" }
  - { name: notes, type: string, required: false, description: "备注" }
submission_criteria:
  roles: [store_manager]
  conditions:
    - { field: param.quantity, operator: gt, value: 0, fail_msg: "补货数量必须大于 0" }
side_effects:
  - { type: notification, template: restock_created, recipients: [manager_id] }
```

---

## 4. 数据模型

### 4.1 Object Type 定义

#### Region（区域）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 主键，如 `region_001` |
| `name` | string | ✅ | 区域名称，如 "华东区" |
| `code` | string | ✅ | 区域编码，如 "HD" |

#### Store（门店）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 主键，如 `store_001` |
| `name` | string | ✅ | 门店名称，如 "北京朝阳店" |
| `region_id` | string | ✅ | 所属区域 ID（→ Region） |
| `address` | string | ❌ | 门店地址 |
| `manager_id` | string | ❌ | 店长 ID（→ Employee） |
| `created_at` | datetime (ISO 8601) | ✅ | 创建时间 |

#### Employee（员工）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 主键，如 `emp_001` |
| `name` | string | ✅ | 员工姓名 |
| `store_id` | string | ✅ | 所属门店 ID（→ Store） |
| `role` | enum | ✅ | 角色：`clerk`（店员）/ `manager`（店长）/ `admin`（管理员） |
| `phone` | string | ❌ | 联系电话 |

#### Product（商品）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 主键，如 `prod_001` |
| `name` | string | ✅ | 商品名称 |
| `category` | string | ✅ | 品类（扁平字符串，v2 扩展为 5 级树） |
| `brand` | string | ❌ | 品牌 |
| `unit` | string | ❌ | 计量单位，如 "盒"、"瓶" |
| `cost_price` | float | ❌ | 成本价（元） |
| `retail_price` | float | ❌ | 零售价（元） |

#### NearExpiryProduct（临期商品）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 主键，如 `nep_001` |
| `product_id` | string | ✅ | 关联商品 ID（→ Product） |
| `store_id` | string | ✅ | 所属门店 ID（→ Store） |
| `batch_no` | string | ✅ | 批次号 |
| `production_date` | date (YYYY-MM-DD) | ✅ | 生产日期 |
| `expiry_date` | date (YYYY-MM-DD) | ✅ | 过期日期 |
| `stock_quantity` | integer | ✅ | 库存数量 |
| `days_left` | integer | ✅ | 剩余天数（自动计算） |
| `discount_tier` | enum | ✅ | 折扣层级：`T1`（≤3天）/ `T2`（4-7天）/ `T3`（8-14天） |
| `status` | enum | ✅ | 状态：`normal` / `low_stock` / `expiring` / `expired` |

#### Task（任务）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 主键，如 `task_001` |
| `type` | enum | ✅ | Action Type：`clearance` / `transfer` / `restock` |
| `target_id` | string | ✅ | 目标实体 ID（NearExpiryProduct 或 Product） |
| `store_id` | string | ✅ | 所属门店 ID |
| `assignee_id` | string | ❌ | 执行人 ID（→ Employee） |
| `status` | enum | ✅ | 状态：`pending` / `executing` / `completed` / `failed` / `cancelled` |
| `params_json` | dict | ✅ | 操作参数 JSON（如 `{"discount": 50, "quantity": 10}`） |
| `result_json` | dict | ❌ | 执行结果 JSON |
| `priority` | enum | ❌ | 优先级：`low` / `medium` / `high` |
| `notes` | string | ❌ | 备注 |
| `created_at` | datetime (ISO 8601) | ✅ | 创建时间 |
| `started_at` | datetime (ISO 8601) | ❌ | 开始时间 |
| `completed_at` | datetime (ISO 8601) | ❌ | 完成时间 |

### 4.2 Link Type 定义

| Link Type | Domain → Range | Via 字段 | 说明 |
|-----------|----------------|----------|------|
| `located_in` | Store → Region | `region_id` | 门店位于区域 |
| `has_employee` | Store → Employee | `store_id` | 门店拥有员工 |
| `has_near_expiry` | Store → NearExpiryProduct | `store_id` | 门店有临期商品 |
| `is_instance_of` | NearExpiryProduct → Product | `product_id` | 临期商品是商品的实例 |
| `manages` | Employee → Store | `manager_id` | 店长管理门店 |
| `has_task` | Store → Task | `store_id` | 门店有任务 |
| `created_for` | Task → NearExpiryProduct | `target_id` | 任务针对临期商品 |

> **注意**：`manages` 的 `via` 字段 `manager_id` 实际是 Store 的属性（不是 Employee 的）。遍历时通过 `stores where manager_id == employee.id` 实现。这是已知的设计缺陷，MVP 将修正方向。

### 4.3 折扣规则数据格式（统一后）

**语义约定**：全系统统一使用**减扣百分比（0-100 整数）**。

```json
[
  {
    "id": "rule_T1",
    "tier": "T1",
    "days_min": 0,
    "days_max": 3,
    "discount_percent": 50,
    "description": "即将过期，5折（减50%）"
  },
  {
    "id": "rule_T2",
    "tier": "T2",
    "days_min": 4,
    "days_max": 7,
    "discount_percent": 30,
    "description": "中期临期，7折（减30%）"
  },
  {
    "id": "rule_T3",
    "tier": "T3",
    "days_min": 8,
    "days_max": 14,
    "discount_percent": 10,
    "description": "初期临期，9折（减10%）"
  }
]
```

- `discount_percent`：减扣百分比，50 表示五折（原价减 50%）
- 单一事实源：`discount_rules.json`
- 单一计算函数：`business/discount.py` → `calculate_discount(tier) → int`

### 4.4 审计日志格式

每条审计记录追加到 `data/tenant/{tenant_id}/audit/{date}.jsonl`（append-only）。

```json
{
  "audit_id": "AUD-20260620-0001",
  "timestamp": "2026-06-20T14:30:00.000Z",
  "tenant_id": "store_001",
  "actor": {"user_id": "emp_001", "role": "store_manager"},
  "action": {
    "tool_name": "confirm_action",
    "params": {"action_type": "clearance", "target_id": "nep_001", "discount": 50}
  },
  "rule_matched": {"rule_id": "PR-001"} | null,
  "outcome": "SUCCESS | REJECTED"
}
```

---

## 5. Skill 格式规范

### 5.1 SKILL.md 结构

```markdown
---
name: skill-name                  # Skill 唯一标识（kebab-case）
description: 简短描述              # 一句话说明用途
type: workflow | domain_knowledge  # Skill 类型
allowed_tools: tool1, tool2, ...   # 本 Skill 可使用的 Tool 白名单
license: MIT
---

# Skill 标题

## 何时使用
描述触发条件。

## [内容区域]
根据 type 不同，内容结构不同（见 5.2）。
```

### 5.2 Skill 类型

| 类型 | type 值 | 内容结构 |
|------|---------|---------|
| **流程编排类** | `workflow` | 步骤列表（Step 1 / Step 2 / ...）、工具调用示例、禁止事项 |
| **领域知识类** | `domain_knowledge` | 实体/关系/属性列表、工具使用策略、关键约束 |

### 5.3 现有 Skill

| Skill | type | 文件 |
|-------|------|------|
| `store-ontology` | `domain_knowledge` | `backend/skills/store-ontology/SKILL.md` |
| `clearance-workflow` | `workflow` | `backend/skills/store-ontology/clearance-workflow/SKILL.md` |

---

## 6. 多租户传递链路

```
┌─────────────────────────────────────────────────────────────────┐
│ 前端 (CopilotKit)                                                │
│                                                                  │
│  useCoAgent().setAgentState({ selected_store: "store_001" })     │
│       │                                                          │
│       ▼                                                          │
│  POST /api/copilotkit                                           │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│ route.ts (Next.js API Route)                                     │
│                                                                  │
│  从 CopilotKit shared state 提取 selected_store                  │
│  → 写入 HTTP header: X-Tenant-ID: store_001                    │
│  → 转发到 http://localhost:8123/api/copilotkit                   │
└──────────┬──────────────────────────────────────────────────────┘
           │  Header: X-Tenant-ID: store_001
           ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Middleware                                               │
│                                                                  │
│  读取 X-Tenant-ID header                                         │
│  → 校验：存在 + 在合法租户列表中                                  │
│  → 存入 RequestContext(tenant_id="store_001")                   │
│  → 缺失 → 401 | 非法 → 403                                       │
└──────────┬──────────────────────────────────────────────────────┘
           │  RequestContext
           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Agent 系统提示 (Layer 3)                                         │
│                                                                  │
│  "当前用户选择的门店ID是: store_001"                              │
└──────────┬──────────────────────────────────────────────────────┘
           │  Agent context
           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Tool 执行                                                        │
│                                                                  │
│  repository.read(entity_type, tenant_id, ...)                   │
│  repository.write(entity_type, entity_id, data, tenant_id, ...)  │
│                                                                  │
│  Repository 所有查询自动带 tenant_id 过滤                          │
└─────────────────────────────────────────────────────────────────┘
```

### 租户 ID 传递规范

| 层 | 如何获取 tenant_id |
|----|-------------------|
| 前端 UI | `useCoAgent()` 的 `agentState.selected_store` |
| route.ts | 从 CopilotKit shared state 提取，写入 `X-Tenant-ID` header |
| FastAPI Middleware | 读取 `X-Tenant-ID` header，存入 `RequestContext` |
| Agent system prompt | 从 `RequestContext.tenant_id` 读取，注入 Layer 3 |
| Tool 执行 | 从 `RequestContext.tenant_id` 读取，传给 Repository |
| Repository | `read()`/`write()` 强制参数，用于过滤查询和隔离写入 |
| 后端自动化（定时器） | 由定时器任务直接指定 `tenant_id`（headless 调用无前端） |
