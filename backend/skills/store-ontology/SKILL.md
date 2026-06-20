---
name: store-ontology
description: 门店临期商品管理本体知识与工具使用策略
type: domain_knowledge
---

# 门店临期商品管理

## 本体（7 Object / 10 Link）
- **Object**: Region、Store、Employee、Product、NearExpiryProduct、Task、LossReport
- 读实体用 `query_entity`，遍历关系用 `traverse_relation`。

## 折扣（单一事实源）
折扣由临期商品的 `discount_tier`（T1/T2/T3）决定，具体数值见本体数据 `data/discount_rules.json`（减扣百分比，0-100）。
**不要在本对话中重复定义折扣数值**；如需数值，调 `query_near_expiry` 查看。

## 状态
- NearExpiryProduct.status：expiring / clearance / sold_out / expired / scrapped
- Task.status：created / pending_approval / approved / accepted / in_progress / completed / rejected / scrapped

状态迁移只能经 Action，不可直接改写。
