---
name: store-ontology
description: 门店大脑本体知识 — Store/Employee/Product/NearExpiryProduct/ClearanceTask 语义与关系
license: MIT
---

# 门店大脑本体 Skill

## 何时使用
当用户询问门店、商品、员工、临期商品、出清任务时使用。

## 实体类型（Object Types）

| 实体 | 说明 | 关键字段 |
|------|------|---------|
| Store | 门店 | id, name, region_id, manager_id, address |
| Employee | 员工 | id, name, store_id, role |
| Product | 商品 | id, name, category |
| NearExpiryProduct | 临期商品 | id, store_id, product_id, batch_no, stock_quantity, expiry_date, discount_tier |
| DiscountRule | 折扣规则 | id, tier, min_days_left, max_days_left, discount_rate |
| ClearanceTask | 出清任务 | id, store_id, near_expiry_product_id, assignee_id, status, actual_discount |

## 关系类型（Link Types）

| 关系 | 遍历方式 | 说明 |
|------|---------|------|
| has_employee | Store → Employee |门店拥有员工，通过 store_id |
| belongs_to | Employee → Store | 员工属于门店，通过 store_id |
| located_in | Store → Region | 门店位于区域，通过 region_id |
| is_instance_of | NearExpiryProduct → Product | 临期商品是商品的实例，通过 product_id |
| manages | Employee → Store | 店长管理门店，通过 manager_id |
| has_near_expiry | Store → NearExpiryProduct | 门店有临期商品，通过 store_id |
| has_task | Store → ClearanceTask | 门店有出清任务，通过 store_id |

## 折扣层级规则（Discount Tiers）

| 层级 | 剩余天数 | 折扣率 |
|------|---------|--------|
| T1 | ≤3 天 | 70% off |
| T2 | 4-7 天 | 50% off |
| T3 | 8-14 天 | 30% off |

## 工具使用策略

- **查门店/员工/商品**：用 `query_entity(entity_type="...", store_id="...")`
- **查临期商品**：用 `get_near_expiry_products(store_id=store_id)`
- **创建出清任务**：
  1. 先用 `create_clearance_task(store_id, product_id, discount)` 获取预览
  2. 用户确认后调用 `confirm_clearance_task(store_id, product_id, discount)`
- **修改任务**：用 `update_entity(entity_type="ClearanceTask", entity_id=task_id, ...)`
- **遍历关系**：用 `traverse_relation(source_type, source_id, relation)`

## 关键约束
- 已过期的商品（status == "expired"）不能创建出清任务
- 出清任务必须先预览再创建（HITL 模式）
- 折扣范围 0-100
