---
name: platform-help
description: OntologyAgent 平台操作指引（如何用 execute_action/confirm_action 完成受治理操作、如何查本体）
---

# OntologyAgent 平台操作指引

本 Skill 是**系统级 Skill**（所有 workspace 共享），提供平台通用操作指引。
具体业务 Skill（如 clearance-workflow）在各 workspace 的 skills/ 目录中，优先级更高。

## 受治理操作的标准流程（Preview → Confirm）

平台所有受治理的写操作都走两步流程，避免直接写数据绕过校验：

1. **预览**：调用 `execute_action(action_type, params, ...)` 生成预览
   - 返回 `preview_id` + 校验后的参数
   - 参数错误（缺必填、约束不满足）在预览阶段就报错，不进缓存
2. **确认**：用户确认后调用 `confirm_action(preview_id)` 真正执行
   - preview 有 TTL（默认 300 秒），过期需重新预览

## 查询数据的系统工具

- `query_entity(entity_type, ...)`：通用实体查询（Store/Product/Task 等）
- `traverse_relation(source_type, source_id, relation)`：遍历实体关系
- `query_task(status, store_id)`：查询任务

业务专用查询（如 `query_near_expiry`）在各 workspace 的 skills/ 中。

## 通用 CRUD（仅非业务数据）

- `create_entity` / `update_entity`：仅限非治理实体
- 受治理实体（edits_only_via_actions）会被 Repository 拒绝，必须走 execute_action

## 本体浏览

管理界面（admin）提供只读本体浏览：Object Type / Action Type / Link Type 定义。
对话中可通过 query_entity 探索数据，通过 execute_action（错误返回）查看可用 Action。
