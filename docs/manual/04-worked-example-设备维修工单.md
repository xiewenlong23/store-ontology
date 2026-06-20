# Worked Example：门店设备维修工单（第二 vertical 端到端）

> **目的**：完整走通第二个 vertical，证明三件事：
> 1. **多 vertical 并存** —— clearance 与 equipment_repair 同时注册、互不干扰
> 2. **零改内核接入** —— 全程只新增 `backend/verticals/equipment_repair/` + `data/equipment_repair/`，未改任何 `ontology/*` 内核文件
> 3. **无折扣概念也能跑** —— 证明内核改造后不依赖 `business/discount`
>
> **场景**：门店设备（冷柜、微波炉、收银机…）报修 → 诊断 → 指派技师 → 维修 → 完成/取消。

---

## 1. 建模决策（Phase A 设计）

| 决策 | 选择 | 理由 |
|---|---|---|
| 工作流主对象 | `RepairTicket`（非 Task） | 故意与 clearance 的 Task 不同，压测 executor 的 `locator_field` 数据驱动 |
| 状态机 | `reported→diagnosed→assigned→repairing→resolved` + 旁路 `cancelled` | 5 步主路径 + 取消旁路 |
| 折扣 | **无** | 证明内核不依赖 discount；费用（parts_cost/labor_cost）按实际填 |
| Object 数 | 4（Equipment/RepairTicket/Technician/Vendor） | 够演示又不臃肿 |
| 受治理实体 | Equipment + RepairTicket | 都标 `edits_only_via_actions` |

---

## 2. 目录结构（接入产物）

```
backend/verticals/equipment_repair/
├── __init__.py
├── config.py                              # Phase F：VerticalConfig 注册
├── state_machine.py                       # Phase C：REPAIR_TICKET_TRANSITIONS
├── tools.py                               # Phase E.1：query_repair_tickets
├── ontology/
│   ├── equipment_repair.ttl               # Phase A：4 Object + 4 Link
│   └── actions/                           # Phase B：6 个 Action YAML
│       ├── create_repair_ticket.yaml
│       ├── diagnose_ticket.yaml
│       ├── assign_technician.yaml
│       ├── start_repair.yaml
│       ├── complete_repair.yaml
│       └── cancel_ticket.yaml
└── skills/
    ├── equipment-repair-knowledge/SKILL.md   # Phase E.2：领域知识
    └── repair-workflow/SKILL.md              # Phase E.2：工作流编排

data/equipment_repair/                     # Phase D：种子数据
├── equipments.json
├── repair_tickets.json
├── technicians.json
└── vendors.json
```

**全程未触碰的内核文件**：`ontology/parser.py`、`executor.py`、`repository.py`、`tools.py`、`main.py`、`state_machine.py`、`action_loader.py`、`bootstrap.py`。这是"零改内核"的直接证据。

---

## 3. 关键设计点

### 3.1 `locator_field: ticket_id`（数据驱动定位）

6 个 Action 里，target 是 RepairTicket 的 5 个（diagnose/assign/start/complete/cancel）都声明 `locator_field: ticket_id`；create_repair_ticket 的 target 是 Equipment，声明 `locator_field: equipment_id`。

这与 clearance 的 `task_id` 完全平行，但用的是不同的参数名 —— 证明 executor 定位键不再硬编码 `"Task"`。

### 3.2 config.py 的工作流字段

```python
EQUIPMENT_REPAIR_CONFIG = VerticalConfig(
    ...
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",   # submission_criteria 里写 "repair_ticket.status" 时用这个查
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    ...
)
```

executor 的 state_transition 副作用自动用这张表校验合法迁移。

### 3.3 submission_criteria 的条件根

diagnose_ticket 的条件写 `target.status is reported`（target 是 RepairTicket，locator_field=ticket_id，executor 用 ticket_id 查 RepairTicket 作为 target）。
若一个 Action 同时涉及工作流对象和标的物（如 complete_repair 改 RepairTicket + Equipment），target 是工作流对象，标的物在 side_effects 里用 `equipment_id` 单独定位。

---

## 4. 端到端验证（实测输出）

```
=== 1. both verticals registered ===
  clearance: workflow=Task has_flow=True
  equipment_repair: workflow=RepairTicket has_flow=True

=== 2. equipment_repair TTL/actions parse ===
  prefix=repair: objects=['Equipment', 'RepairTicket', 'Technician', 'Vendor'] links=4
  actions=['assign_technician', 'cancel_ticket', 'complete_repair',
           'create_repair_ticket', 'diagnose_ticket', 'start_repair']

=== 3. full repair workflow end-to-end ===
  create -> ticket repairticket_5a95e95e, equip status now in_repair
  final: ticket=resolved parts_cost=200 labor_cost=100 | equip=normal

=== 4. illegal transition rejected ===
  correctly rejected: 仅 assigned 态可开始维修

=== 5. kernel not coupled to clearance ===
  kernel scenario-agnostic confirmed

所有验证通过 ✓
```

主路径 6 步全部跑通；非法迁移（reported→repairing 跳步）被拒；内核源码 grep 确认无 `business.discount` import、无 `门店临期商品管理助手` 硬编码。

### 4.1 多 vertical 并存的工具与 Skill 聚合

```
verticals: ['clearance', 'equipment_repair']
tools: [query_entity, create_entity, update_entity, traverse_relation,
        execute_action, confirm_action, query_task, update_task,
        query_near_expiry, query_repair_tickets]   # 8 内核 + 2 vertical 专属
skills: ['/store-ontology/', '/equipment-repair-knowledge/', '/repair-workflow/']
```

同一个 LLM agent 同时知道出清和维修两套本体、两套工作流。

---

## 5. 复现步骤

若你想自己跑一遍：

```bash
cd backend
/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/ -q   # 53 passed
# 端到端验证脚本见本仓库（可写成 test_equipment_repair.py）
```

---

## 6. 这个例子刻意压测的耦合点

| 耦合点（改造前） | 本例如何验证已修复 |
|---|---|
| L2 TTL prefix 硬编码 `store:` | 用 `repair:` prefix，parser 动态读取成功 |
| L4 executor `target_type == "Task"` | 工作流对象是 `RepairTicket`，靠 `locator_field: ticket_id` 定位成功 |
| L5 状态机全局唯一 | equipment_repair 自带 `REPAIR_TICKET_TRANSITIONS`，与 clearance 的 TASK_TRANSITIONS 并存 |
| L6 内核 import business.discount | 本 vertical 无折扣，内核正常工作 |
| L7 tools/skills 硬编码 | `query_repair_tickets` 自动聚合进 main.tools，repair skill 自动收录 |

---

## 7. 结论

接入 equipment_repair = 新建 1 个 vertical 目录（含 8 个文件）+ 1 个种子目录（4 个 JSON）。
**内核零改动，重启即生效，clearance 全流程不受影响。** 这正是内核多 vertical 改造（`01`）的目标。

第三个、第四个 vertical 重复本流程即可。
