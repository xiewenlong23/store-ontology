# API 与数据契约规范

> **状态**：✅ 当前（已实现）。本文档是 AG-UI 端点、Tool Schema、Action Type 契约、数据模型的规范。
> **配套**：架构总览见 [`00-architecture.md`](./00-architecture.md)；建模硬规范见 [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md)。

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

**Header 约定（workspace 传递）**：

| Header | 方向 | 说明 |
|--------|------|------|
| `X-Workspace` | 前端 → 后端 | workspace 标识（优先） |
| `X-Customer-ID` | 前端 → 后端 | 旧前端兼容（回退） |
| `X-Org-Unit-ID` | 前端 → 后端 | workspace 内组织单元（权限范围，默认 `*`=全可见） |

`agent/engine/tenant.py` 的 `TenantContext.from_headers` 按 `X-Workspace` 优先、回退 `X-Customer-ID` 解析；未传默认 `customer_default`。

### 1.2 Health Check 端点

| 属性 | 值 |
|------|------|
| **路径** | `GET /health` |
| **响应** | `{"status": "healthy"}` |

### 1.3 Webhook 端点（模拟，真实集成留 v2）

| 路径 | 用途 | 执行的 Action |
|------|------|--------------|
| `POST /api/webhooks/approval` | 审批回调 | `approve_clearance`（经 `handle_approval`） |
| `POST /api/webhooks/pos` | POS 扫码 | `deduct_stock`（经 `handle_pos_scan`） |

webhook 取 executor 用 `_get_executor(process_name="clearance")`（精确选价值链流程，workspace 由 contextvar 解析）。

---

## 2. Tool Schema 规范

### 2.1 通用返回值格式

所有 Tool 返回 **字符串**（`langchain_core.tools.tool` 约定）。结构化数据嵌入在 HTML 注释标记中：

```
{人类可读的摘要文本}
<!--COPILOTKIT_DATA-->
{"type": "{json_type}", ...}
<!--/COPILOTKIT_DATA-->
```

前端 `renderToolCalls` 通过正则提取此 JSON block，根据 `type` 渲染对应 Generative UI 组件。

### 2.2 内核工具（固定 8 个）

所有工具都接受 `workspace_name: str = "customer_default"` + `org_unit_id: str = "*"` 参数，经 `shared._tc()` 构造 `TenantContext` 决定可见范围。

#### `query_entity` — 通用实体查询
```python
@tool
def query_entity(entity_type: str, entity_id: Optional[str] = None,
                 filter_field: Optional[str] = None, filter_value: Optional[str] = None,
                 workspace_name: str = "customer_default", org_unit_id: str = "*") -> str
```
JSON type：`entity_list`（列表）/ `entity_detail`（单条，按 entity_id）。

#### `traverse_relation` — 关系遍历
```python
@tool
def traverse_relation(source_type: str, source_id: str, relation: str,
                      workspace_name: str = "customer_default", org_unit_id: str = "*") -> str
```
JSON type：`relation_result`。按 LinkType 的 domain/range/via 遍历。

#### `query_task` — 任务查询
```python
@tool
def query_task(status: Optional[str] = None, store_id: Optional[str] = None,
               workspace_name: str = "customer_default", org_unit_id: str = "*") -> str
```
JSON type：`task_list`。

#### `create_entity` / `update_entity` — 降级 CRUD
> **安全设计**：被 `edits_only_via_actions` 拦截——对 NearExpiryProduct、Task、LossReport 等核心实体的写操作会被 Repository 拒绝（抛 `ActionRequiredError`）。仅限非业务数据。详见架构 §2.3。

#### `execute_action` — 操作预览（不写数据）
```python
@tool
def execute_action(action_type: str, params: dict,
                   actor_role: str = "store_manager",
                   workspace_name: str = "customer_default", org_unit_id: str = "*") -> str
```
**params** 是该 Action 的参数字典（参数名见系统提示中的 Action 清单）。预览阶段就校验参数；生成 preview 存入 `PreviewCache`，返回 `preview_id`。JSON type：`action_preview`。

#### `confirm_action` — 确认执行（写数据）
```python
@tool
def confirm_action(preview_id: str) -> str
```
凭 `preview_id` 查 `PreviewCache`（存在 + 未过期 + 一次性），执行已预览的 Action。JSON type：`action_result`。

#### `update_task` — 任务更新（受治理白名单）
```python
@tool
def update_task(task_id: str, notes: str = None, priority: str = None,
                workspace_name: str = "customer_default", org_unit_id: str = "*") -> str
```
Task 是 edits-only-via-actions 实体。本工具仅放行白名单字段（`notes`/`priority`），经 `update_task_notes` Action 执行；其余业务字段（discount_percent/status 等）必须走各自 Action。

### 2.3 行业包工具（聚合）

由各价值链流程的 `tools_module` 导出的 `TOOLS` 列表聚合（`main._aggregate_pack_tools()`）。例：
- retail/clearance：`query_near_expiry`（临期商品查询，关联 Product + 计算折扣价）
- equipment_repair/repair：`query_repair_tickets`

### 2.4 Tool JSON Type 速查表

| JSON type | 对应 Tool | 渲染组件 |
|-----------|----------|---------|
| `entity_list` / `entity_detail` | query_entity | 实体卡片列表 / 键值网格 |
| `task_list` | query_task | 任务列表（状态 badge） |
| `near_expiry_list` | query_near_expiry | 商品卡片列表（进度条、折扣价） |
| `relation_result` | traverse_relation | 箭头关系展示 |
| `action_preview` | execute_action | 黄色边框预览卡 |
| `action_result` | confirm_action | 成功/失败卡 |
| `create_result` / `update_result` | create/update_entity | 成功消息 |
| `update_task_result` | update_task | 成功消息 |

---

## 3. Action Type 契约规范

### 3.1 YAML 格式定义

Action Type 定义为 YAML（放 `workspace/<pack>/ontology/domains/<域>/actions/*.yaml` 或价值链流程的 `actions_dir`），由 `action_loader` 加载。

```yaml
# 必填
api_name: string                   # 编程引用名（snake_case，唯一）
display_name: string               # UI 显示名
description: string
status: "active" | "experimental" | "deprecated"
target_object_type: string          # 目标 Object Type
edits_object_types: [string]       # 本 Action 会修改的 Object Type 列表（provenance）
locator_field: string              # 定位 target 的参数名（数据驱动，如 task_id/target_id）

# 参数
parameters:
  - name: string
    type: string                   # string / integer / float / boolean
    required: boolean
    constraint: string             # 约束表达式（如 "0..100"、">0"）

# 细粒度门控（独立于粗粒度 RBAC）
submission_criteria:
  roles: [string]                  # 允许提交的角色白名单
  conditions:
    - field: string                # 如 "target.status"、"task.status"
      operator: string             # is / is_not（MVP）；🔜 v2 加 gte/matches/includes/value_ref
      value: any
      fail_msg: string

# 副作用声明
side_effects:
  - type: "create_object" | "update_object" | "state_transition" | "notification" | "external_call"
    # ... 各 type 自己的字段
```

### 3.2 现有 Action Type

**clearance 价值链流程（retail 行业包，8 个流程 Action + 1 个内核辅助 Action）**：`create_clearance_task` / `submit_for_approval` / `approve_clearance` / `accept_task` / `print_labels` / `deduct_stock` / `complete_task` / `create_loss_report`（流程 Action）；外加 `update_task_notes`（支撑 `update_task` 内核工具的白名单字段写入）。详见 [`industry-packs/retail-clearance.md`](./industry-packs/retail-clearance.md)。

**repair 价值链流程（equipment_repair 行业包，6 个）**：`create_repair_ticket` / `diagnose_ticket` / `assign_technician` / `start_repair` / `complete_repair` / `cancel_ticket`。详见 [`manual/03-worked-example-equipment-repair.md`](./manual/03-worked-example-equipment-repair.md)。

> 🔜 `transfer`/`restock` 契约补全留后续（当前行业包聚焦 clearance + equipment_repair）。

---

## 4. 数据模型

> 完整的 Object Type / Link Type 定义以 TTL 为单一事实源（`workspace/<pack>/ontology/domains/<域>/domain.ttl`）。下表是 retail 行业包的速览。

### 4.1 Object Type（retail 行业包）

| Object Type | 主键 | 关键字段 | 受治理 |
|-------------|------|---------|--------|
| Region | id | name, code | — |
| Store | id | name, region_id, address, manager_id, created_at | — |
| Employee | id | name, store_id, role, phone | — |
| Product | id | name, category, brand, unit, cost_price, retail_price | — |
| NearExpiryProduct | id | product_id, store_id, batch_no, production_date, expiry_date, stock_quantity, days_left, discount_tier, status | ✅ edits-only |
| Task | id | task_type, target_id, store_id, assignee_id, status, params_json, result_json, priority, notes, created_at | ✅ edits-only |
| LossReport | id | task_id, loss_quantity, loss_value, ... | ✅ edits-only |

字段类型规范、必填规则详见建模规范 [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md) §6。

### 4.2 Link Type（retail 行业包）

以 TTL 为准（`manages` 方向已修正为 Store→Employee）。建模规范 §4.3 的 via 归属原则是关键约束。

### 4.3 折扣规则数据格式

全系统统一使用**减扣百分比（0-100 整数）**。单一事实源 = `workspace/retail/ontology/domains/marketing/rules/discount_rules.json` + `calculate_discount()`。

```json
[
  {"id": "rule_T1", "tier": "T1", "days_min": 0, "days_max": 3,
   "discount_percent": 50, "description": "即将过期，5折（减50%）"},
  {"id": "rule_T2", "tier": "T2", "days_min": 4, "days_max": 7,
   "discount_percent": 30, "description": "中期临期，7折（减30%）"},
  {"id": "rule_T3", "tier": "T3", "days_min": 8, "days_max": 14,
   "discount_percent": 10, "description": "初期临期，9折（减10%）"}
]
```

### 4.4 审计日志格式（🔜 v2 未实现）

目标格式（当前未落地，见 [`roadmap.md`](./roadmap.md)）：
```json
{
  "audit_id": "AUD-20260620-0001",
  "timestamp": "2026-06-20T14:30:00Z",
  "workspace_name": "customer_default",
  "actor": {"user_id": "emp_001", "role": "store_manager"},
  "action": {"tool_name": "confirm_action", "params": {...}},
  "rule_matched": {"rule_id": "PR-001"} | null,
  "outcome": "SUCCESS | REJECTED"
}
```

---

## 5. Skill 格式规范

### 5.1 SKILL.md 结构

```markdown
---
name: skill-name                  # kebab-case 唯一标识
description: 简短描述
type: workflow | domain_knowledge # Skill 类型
allowed_tools: tool1, tool2, ...   # 本 Skill 可使用的 Tool 白名单
license: MIT
---

# Skill 标题
## 何时使用
## 步骤（workflow 类）或 实体/关系/策略（domain_knowledge 类）
## 禁止事项
```

### 5.2 Skill 类型

| 类型 | type 值 | 内容结构 |
|------|---------|---------|
| **流程编排类** | `workflow` | 步骤列表、工具调用示例、禁止事项 |
| **领域知识类** | `domain_knowledge` | 实体/关系/属性、工具使用策略、关键约束 |

### 5.3 现有 Skill（2 级加载）

| 层级 | Skill | type | 位置 |
|------|-------|------|------|
| workspace（高优先级） | `store-ontology` | domain_knowledge | `workspace/retail/skills/store-ontology/` |
| workspace（高优先级） | `clearance-workflow` | workflow | `workspace/retail/skills/clearance_workflow/` |
| workspace（高优先级） | `repair-workflow` | workflow | `workspace/equipment_repair/skills/repair_workflow/` |
| 系统（低优先级，所有 workspace 共享） | `platform-help` | domain_knowledge | `agent/skills/platform-help/` |

CompositeBackend：系统 skills 经 `/system/<name>/` 路由，workspace skills 在根路径。

---

## 6. 多 workspace 传递链路

```
前端 CopilotKit co-agent state (selected_store)
    → route.ts 注入 HTTP header (X-Workspace)              [现状: 静态默认 header]
    → 后端 middleware 读取 → contextvar (tenant_ctx)         [✅ 已实现]
    → shared._tc() / _workspace_name_from_ctx()              [✅ 已实现]
    → bootstrap_workspace(name) → WorkspaceAgentInstance     [✅ 已实现]
    → Repository 所有读写强制带 workspace_name + org_unit_id 过滤  [✅ 已实现]
```

### workspace 传递规范

| 层 | 如何解析 workspace |
|----|-------------------|
| 前端 UI | `useCoAgent()` 的 `agentState.selected_store` |
| route.ts | 从 shared state 提取，写入 `X-Workspace` header |
| FastAPI middleware | 读取 `X-Workspace`（回退 `X-Customer-ID`）→ `TenantContext.from_headers` → contextvar `tenant_ctx` |
| Tool 执行 | 工具参数 `workspace_name`/`org_unit_id` → `shared._tc()`；或 shared helper 从 `tenant_ctx` contextvar 解析 |
| Repository | `read()`/`write()` 强制带 `TenantContext`，按 `workspace_name` + `org_unit_id` 过滤 |
| 后端自动化（定时器） | 注册时直接绑定 workspace/executor（headless，无前端） |
