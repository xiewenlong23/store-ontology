---
name: repair-workflow
description: 设备维修工单跨步骤工作流编排
type: workflow_orchestration
allowed_tools: query_repair_tickets, query_entity, execute_action, confirm_action
---

# 设备维修工单流程

维修是一条工作流，由 RepairTicket 状态机驱动。
每一步是一个 Action：先 `execute_action` 预览，再 `confirm_action(preview_id)` 执行。

## 步骤
1. **查询设备**：`query_entity(entity_type="Equipment", store_id=...)`。
2. **报修建单**：`execute_action(action_type="create_repair_ticket", equipment_id, store_id, reporter_id, fault_description)` → 工单 reported，设备 in_repair。
3. **诊断**：`execute_action(action_type="diagnose_ticket", ticket_id, diagnosis)` → diagnosed。
4. **指派技师**：`execute_action(action_type="assign_technician", ticket_id, technician_id)` → assigned。
5. **开始维修**：`execute_action(action_type="start_repair", ticket_id)` → repairing。
6. **完成维修**：`execute_action(action_type="complete_repair", ticket_id, equipment_id, parts_cost, labor_cost)` → resolved，设备 normal。
7. **取消**（任意非终态）：`execute_action(action_type="cancel_ticket", ticket_id, equipment_id)` → cancelled，设备 normal。

## 非法迁移会被拒
状态机只允许相邻迁移（reported→diagnosed→assigned→repairing→resolved；任意非终态→cancelled）。
跳步会被拒绝，请按顺序。
