---
name: clearance-workflow
description: 临期商品出清标准工作流 — Preview → Confirm 模式，折扣规则与执行规范
license: MIT
allowed_tools: query_near_expiry, execute_action, confirm_action, query_task, update_task, query_entity, update_entity
---

# 出清工作流 Skill

## 何时使用
用户说"处理临期商品"、"出清"、"打折"、"清库存"、"临期货怎么处理"时，使用本工作流。

## 折扣规则（Discount Rules）

折扣由临期商品的 `discount_tier` 决定：

| 层级 | 剩余天数 | 折扣率 | 建议折扣 |
|------|---------|--------|---------|
| T1 | ≤3 天 | 70% off | 70% |
| T2 | 4-7 天 | 50% off | 50% |
| T3 | 8-14 天 | 30% off | 30% |

**计算规则：**
- `折扣 = 折扣层级对应的折扣率`（由 `discount_tier` 字段决定）
- 用户可覆盖折扣，但必须在 0-100 之间
- 已过期商品（status == "expired"）**不能**出清

## 工具清单

| 工具 | 用途 |
|------|------|
| `query_near_expiry(store_id)` | 查询门店所有临期商品 |
| `execute_action(action_type="clearance", target_id, store_id, discount, quantity)` | 创建出清预览（不实际执行） |
| `confirm_action(action_type="clearance", target_id, store_id, discount, quantity)` | 用户确认后实际执行并创建任务 |
| `query_task(action_type="clearance", store_id)` | 查询出清任务记录 |
| `update_task(task_id, status="completed", ...)` | 修改任务状态/备注 |
| `query_entity(entity_type="NearExpiryProduct", store_id)` | 通用实体查询 |
| `update_entity(entity_type="NearExpiryProduct", entity_id, ...)` | 修改临期商品状态 |

## 标准工作流（Preview → Confirm）

### Step 1：确认门店
- 如果用户未指定门店，询问用户要操作哪个门店
- 门店ID格式：`store_001`, `store_002` 等

### Step 2：查询临期商品
调用 `query_near_expiry(store_id=store_id)` 获取列表

### Step 3：展示并让用户选择
展示临期商品列表（名称、库存、过期日、剩余天数、折扣层级），询问用户要对哪个商品出清。

获取：
- `target_id` = NearExpiryProduct.id
- `discount` = 用户指定折扣（未指定则用折扣规则的建议值）
- `quantity` = 用户指定数量（未指定则用全部库存）

### Step 4：创建预览
调用 `execute_action(action_type="clearance", target_id=near_expiry_product_id, store_id=store_id, discount=discount, quantity=quantity)` 返回预览信息

### Step 5：询问确认
向用户展示预览结果，询问"是否确认执行？"。用户必须明确回复"确认"/"好的"/"可以"才能继续。

### Step 6：确认执行
用户确认后，立即调用 `confirm_action(action_type="clearance", target_id=near_expiry_product_id, store_id=store_id, discount=discount, quantity=quantity)` 完成执行。

### Step 7：展示结果
展示创建成功的任务ID和关键信息。

## 禁止事项

- **禁止**跳过 Step 4 直接调用 `confirm_action`
- **禁止**为已过期商品（status == "expired"）创建出清任务
- **禁止**在用户未回复确认时自动执行
