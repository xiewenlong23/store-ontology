---
name: clearance-workflow
description: 临期出清跨天流程编排
type: workflow_orchestration
allowed_tools: query_near_expiry, query_entity, query_task, execute_action, confirm_action
---

# 临期出清流程

出清是一条跨天工作流，由 Task 状态机驱动。每一步是一个 Action：先 `execute_action` 预览，再 `confirm_action(preview_id)` 执行。

## 步骤
1. **查询**：`query_near_expiry` 找临期商品。
2. **建单**：`execute_action(action_type="create_clearance_task", target_id, store_id, assignee_id, discount_percent, planned_quantity)`。
3. **提交审批**：`execute_action(action_type="submit_for_approval", task_id)`。
4. **审批**（后端回调，对话中可模拟）：`approve_clearance`。
5. **接单**：`accept_task`。
6. **打签陈列**：`print_labels`。
7. **POS 扣库存**（后端）：`deduct_stock`。
8. **售罄完成**：`complete_task`。
9. **到期未售罄**：`create_loss_report`。

## 折扣
`discount_percent` 是减扣百分比（0-100，50=五折），由 tier 决定，见 `discount_rules.json`。

## 非法迁移会被拒
状态机只允许相邻迁移（见 store-ontology SKILL）。跳步会被拒绝，请按顺序。
