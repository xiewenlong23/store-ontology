# Worked Example：门店设备维修工单（第二个工作目录端到端）

> **状态**：✅ 当前。本文对照真实代码 `workspace/customerA/` 写成（非臆造）。
> **目的**：证明多工作目录并存 + 零改内核 + 无折扣概念也能跑。可作为新工作目录接入的完整对照。

---

## 1. 建模决策（Phase A 设计）

设备维修场景的核心实体：
- **Equipment**（设备）：被维修的对象
- **RepairTicket**（维修工单）：工作流主对象，状态机载体
- **Technician**（技师）：执行维修的人
- **Vendor**（供应商）：设备供应商

无折扣概念（区别于 retail），无调拨/补货。验证内核不依赖任何 retail 符号。

---

## 2. 目录结构（接入产物）

```
workspace/customerA/
├── workspace.py                                     # 工作目录（WorkspaceDef） 声明（register_workspace_dir）
├── ontology/
│   └── domains/
│       └── maintenance/                        # 1 能力域：维修域
│           ├── domain.ttl                      # 4 Object + 4 Link
│           └── actions/                        # 全部 6 个 Action（含状态迁移类）
├── data/                                       # 种子数据（equipment/repair_tickets/...）
└── skills/
    └── repair_workflow/                        # 价值链流程：repair
        ├── SKILL.md                            # 流程编排 Skill
        ├── tools.py                            # 专属工具（query_repair_tickets）
        └── state_machine.py                    # REPAIR_TICKET_TRANSITIONS + TERMINAL_STATES
```

> 注：customerA 把所有 Action 放在能力域 `maintenance/actions/`（`workspace.py` 的 `REPAIR.actions_dir` 指向此处）。流程专属 Action 也可放 `skills/<process>/actions/`（由 `ValueChainProcess.actions_dir` 决定）——两种位置都合法，看是否需要把 Action 与 Skill 场景单元打包。retail 的 clearance 流程用的是后者。

---

## 3. workspace.py 实际结构（对照 `workspace/customerA/workspace.py`）

```python
from engine.pack import 工作目录（WorkspaceDef）, CapabilityDomain, ValueChainProcess, register_workspace_dir
from workspace.customerA.skills.repair_workflow.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_BASE = os.path.dirname(os.path.abspath(__file__))

MAINTENANCE = CapabilityDomain(
    name="maintenance", display_name="维修域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "maintenance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "maintenance", "actions"))

REPAIR = ValueChainProcess(
    name="repair", display_name="设备维修",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.customerA.skills.repair_workflow.tools",
    actions_dir=os.path.join(_BASE, "ontology", "domains", "maintenance", "actions"),
    system_prompt_intro="你是门店设备维修管理助手。")

EQUIPMENT_REPAIR_PACK = 工作目录（WorkspaceDef）(
    name="customerA", display_name="设备维修工作目录",
    domains=[MAINTENANCE],
    processes=[REPAIR],
    data_dir=os.path.join(_BASE, "data"))
```

---

## 4. 关键设计点

### 4.1 `locator_field: ticket_id`（数据驱动定位）

每个流程专属 Action（`diagnose_ticket`/`assign_technician`/`start_repair`/`complete_repair`/`cancel_ticket`）在 YAML 里声明 `locator_field: ticket_id`。executor 据此定位 RepairTicket 记录，取代旧的 `target_type == "Task"` 硬编码。

### 4.2 ValueChainProcess 的工作流字段

- `workflow_object_type="RepairTicket"` —— 状态机载体
- `workflow_object_id_field="ticket_id"` —— Action 参数里的定位键
- `state_transitions=REPAIR_TICKET_TRANSITIONS` —— 从 `state_machine.py` import

### 4.3 submission_criteria 的条件根

```yaml
submission_criteria:
  conditions:
    - { field: repair_ticket.status, operator: is, value: reported, fail_msg: "仅 reported 状态可诊断" }
```

executor 把 `repair_ticket.status` 解析为"当前 process 的工作流对象的状态"，通用化（不硬编码 `task.status`）。

### 4.4 状态机

`workspace/customerA/skills/repair_workflow/state_machine.py`：
```
reported → diagnosed → assigned → repairing → resolved
                                         任何非终态 → cancelled（旁路）
```
终态：`resolved` / `cancelled`。per-process，与 clearance 的 Task 状态机互不干扰。

---

## 5. 端到端验证

启动后端，`bootstrap()` 发现 `workspace/customerA/workspace.py` → 注册进 pack 注册表。

### 5.1 多工作目录并存的工具与 Skill 聚合

- `main._aggregate_pack_tools()` 聚合 retail + customerA 的专属工具 → `query_near_expiry` + `query_repair_tickets`
- `_aggregate_skill_paths()` 收录两工作目录的 Skill
- `_build_combined_prompt()` 合并两工作目录的本体知识

### 5.2 可验证的操作

```bash
# 查设备
query_entity(entity_type="Equipment", workspace_name="jjy")

# 建维修工单 → 诊断 → 分配 → 维修 → 完成
execute_action(action_type="create_repair_ticket", params={...}, workspace_name="jjy")
# → confirm_action(preview_id)
execute_action(action_type="diagnose_ticket", params={"ticket_id": "...", "diagnosis": "..."})
# → confirm
# ... assign_technician → start_repair → complete_repair
```

测试见 `agent/tests/test_customerA.py`。

---

## 6. 这个例子刻意压测的耦合点

| 压测点 | 结果 |
|--------|------|
| 内核是否 import retail 符号 | ❌ 不 import（`engine/` 零 retail 依赖） |
| 折扣计算是否必需 | ❌ customerA 无折扣，证明内核不依赖 |
| 状态机是否通用 | ✅ per-process 表，RepairTicket 与 Task 互不干扰 |
| locator_field 是否数据驱动 | ✅ `ticket_id` 不需 executor 改代码 |
| 多工作目录工具是否自动聚合 | ✅ `query_repair_tickets` 自动进 agent |

---

## 7. 复现步骤

1. 按 [`01-onboarding.md`](./01-onboarding.md) Phase A-F 建 `workspace/<新包>/`。
2. 重启后端，看启动日志确认 `bootstrap` 发现新 pack。
3. 用 `query_entity` / `execute_action` / `confirm_action` 端到端验证。
4. 对照本例的压测点表，确认零内核耦合。

---

## 8. 结论

新增工作目录是**纯增量**：建 `workspace/<pack>/`（workspace.py + 能力域本体 + 可选 state_machine/tools/skills）+ `data/` 种子。重启即生效，零改内核。详见 [`01-onboarding.md`](./01-onboarding.md)。
