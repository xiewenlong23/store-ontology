# 零售临期行业包（retail）

> **状态**：✅ 当前（已实现）。本包是第一个行业包，作为内核能力的验证场景与首个落地 demo。
> **单一事实源**：本文件的字段/Action 列表是**速览**；权威定义以 TTL/YAML 为准（路径见下）。

---

## 1. 行业包声明

声明文件：`workspace/retail/pack.py`。`bootstrap()` 自动发现 `workspace/*/pack.py`。

```python
RETAIL_PACK = IndustryPack(
    name="retail", display_name="零售行业包",
    domains=[MARKETING, ORGANIZATION, FINANCE],   # 3 能力域
    processes=[CLEARANCE],                         # 1 价值链流程
    data_dir=.../"workspace/retail/data")
```

- **能力域**（CapabilityDomain）：`marketing`（营销）、`organization`（组织）、`finance`（财务）。各域有 `domain.ttl`（Object/Link）+ `actions/`（域内 Action）+ 可选 `rules/`（如 `marketing/rules/discount_rules.json`）。
- **价值链流程**（ValueChainProcess）：`clearance`（出清）。跨域编排，有自己的状态机 + Skill + 专属工具 + 流程 Action。

---

## 2. Object Types（7 个）

> 权威定义：`workspace/retail/ontology/domains/<域>/domain.ttl`。字段详见 [`20-api-data-contract.md`](./20-api-data-contract.md) §4.1 与建模规范。

| Object Type | 所属域 | 受治理（edits-only） | 说明 |
|-------------|--------|---------------------|------|
| Region | organization | — | 销售运营区域 |
| Store | organization | — | 门店 |
| Employee | organization | — | 员工（role: clerk/manager/admin） |
| Product | marketing | — | 商品（扁平 category 字符串；5 级品类树留 v2） |
| NearExpiryProduct | marketing | ✅ | 临期商品（含 batch_no/production_date/expiry_date/stock_quantity/days_left/discount_tier/status） |
| Task | finance | ✅ | 出清工作流主对象（状态机载体） |
| LossReport | finance | ✅ | 报损记录 |

## 3. Link Types

以 TTL 为准（`manages` 方向已修正为 Store→Employee）。建模规范 §4.3 的 via 归属原则是关键约束。

## 4. Action Types（8 个，clearance 价值链流程）

> 权威定义：`workspace/retail/skills/clearance_workflow/actions/*.yaml`。每个 Action 含完整 YAML 契约（parameters + submission_criteria + side_effects + locator_field），详见 [`20-api-data-contract.md`](./20-api-data-contract.md) §3。

clearance 单体已拆为 8 个细粒度 Action，对应 Task 状态机的每一步迁移：

| Action | 触发的状态迁移 | locator_field |
|--------|---------------|---------------|
| `create_clearance_task` | → created | target_id |
| `submit_for_approval` | created → pending_approval | task_id |
| `approve_clearance` | pending_approval → approved | task_id |
| `accept_task` | approved → accepted | task_id |
| `print_labels` | （打印折扣签，副作用） | task_id |
| `deduct_stock` | （POS 扫码扣库存） | task_id |
| `complete_task` | in_progress → completed | task_id |
| `create_loss_report` | （到期报损，计算式） | task_id |

> 🔜 `transfer`/`restock` 两个 Action 的契约补全留后续。

### Task 状态机（`agent/engine/state_machine.py` 的 `TASK_TRANSITIONS`）

```
created → pending_approval | scrapped
pending_approval → approved | rejected | scrapped
approved → accepted | scrapped
accepted → in_progress | scrapped
in_progress → completed | scrapped
```

终态：`completed` / `rejected` / `scrapped`。

---

## 5. 折扣单一事实源

全系统折扣统一为**减扣百分比（0-100 int）**。

- **数据**：`workspace/retail/ontology/domains/marketing/rules/discount_rules.json`（T1=50/T2=30/T3=10）
- **计算**：`calculate_discount(tier) → int`（读上述 JSON）

| tier | days_left | discount_percent | 含义 |
|------|-----------|------------------|------|
| T1 | 0-3 | 50 | 即将过期，5折 |
| T2 | 4-7 | 30 | 中期临期，7折 |
| T3 | 8-14 | 10 | 初期临期，9折 |

SKILL.md 引用此 JSON，不在文档里重复写数值。

---

## 6. Skill（2 个，workspace 级）

| Skill | type | 位置 |
|-------|------|------|
| `store-ontology` | domain_knowledge | `workspace/retail/skills/store_ontology/SKILL.md` |
| `clearance-workflow` | workflow | `workspace/retail/skills/clearance_workflow/SKILL.md` |

---

## 7. 专属工具

`workspace/retail/skills/clearance_workflow/tools.py` 导出 `TOOLS = [query_near_expiry]`（临期商品查询，关联 Product + 计算折扣价）。被 `main._aggregate_pack_tools()` 自动聚合进 agent。

---

## 8. 后端自动化

`workspace/retail/skills/clearance_workflow/automation.py`：
- `expiry_check_job`：查 in_progress + 关联 NEP 已过期 → `create_loss_report`（计算式 loss_value）
- `inventory_check_job`：查 in_progress + sold≥planned → `complete_task`
- `handle_approval` / `handle_pos_scan`：webhook 回调（`/api/webhooks/approval`、`/api/webhooks/pos`）
- `register_clearance_automation`：把两 job 注册进 `AutomationScheduler`

---

## 9. CopilotKit 接入要点

- 9 个手写 `renderToolCalls`（clearance 专用，已验证可用）
- workspace 选择器从列表加载，写入 co-agent state
- route.ts 注入 `X-Workspace` header（现状静态默认；🔜 v2 动态）
