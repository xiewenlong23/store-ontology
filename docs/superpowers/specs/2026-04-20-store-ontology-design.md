# Store-Ontology 应用设计文档

**日期：** 2026-04-20
**项目：** AI 原生门店任务制应用
**第一阶段：** 门店商品出清（Reduced to Clear）

---

## 1. 项目概述

以门店任务制为基础的 AI 原生应用，第一个探索场景是 **门店商品出清（Reduced to Clear）**。

### 核心目标

- 帮助店长高效管理门店商品健康度
- 通过 Agent 自动化识别 + 推理，减少商品损耗
- 用自然语言交互提升操作效率

### 参考资料

- 本体建模方法论：基于 Palantir Foundry Ontology 四层架构
- 现有工作：[store-ontology](https://github.com/xiewenlong23/store-ontology) 仓库

---

## 2. UI 布局

### 页面结构

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI 原生门店任务应用                          │
├───────────────────────────────┬─────────────────────────────────┤
│                               │                                  │
│   商品健康度仪表盘            │      对话式助手                    │
│   (左侧 - 店长总览)          │   (右侧 - 任务操作)               │
│                              │                                  │
│   60% width                  │   40% width                      │
│                              │                                  │
└───────────────────────────────┴─────────────────────────────────┘
```

### 左侧：商品健康度仪表盘

**按品类分组，每类显示：**
- 商品列表（名称、保质期剩余天数）
- 紧迫度标签（🔴紧急 / 🟡预警 / 🟢正常）
- 当前折扣状态
- 该品类下待执行/进行中/已完成任务数

### 右侧：对话式助手

**支持的能力：**
1. **创建任务** - "帮我创建今天的日配出清任务"
2. **查询状态** - "今天有哪些商品需要出清？"
3. **AI 推理** - "这家门店库存大，帮我推理合适的折扣"
4. **结果追踪** - "昨天的出清任务售罄率是多少？"

---

## 3. 本体架构

### 核心 Object Types

| 对象类型 | 说明 | 父类型/接口 |
|---------|------|------------|
| **WorkTask** | 通用工作任务抽象 | Interface |
| **ReductionTask** | 商品出清任务 | implements WorkTask |
| **Store** | 门店 | - |
| **Employee** | 门店员工（含 Agent） | - |
| **Product** | 商品 | - |
| **DiscountStrategy** | 折扣策略配置 | - |

### 核心 Link Types

| 链接 | 说明 |
|------|------|
| Store → WorkTask | 门店创建/执行的任务 |
| Employee → WorkTask | 员工接收/执行任务 |
| WorkTask → Product | 任务关联的商品 |
| DiscountStrategy → WorkTask | 任务采用的折扣策略 |

### 核心 Action Types

| Action | 说明 |
|--------|------|
| CreateWorkTask | 创建任务（店长手动或 Agent 自动） |
| AssignEmployee | 分配员工执行任务 |
| ExecuteDiscount | 执行打折（打印价格签） |
| ReportSellThrough | 记录售罄率结果 |
| AgentReasoning | Agent 推理折扣策略 |

---

## 4. ReductionTask 详细设计

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| task_id | xsd:string | 任务唯一标识 |
| store_id | xsd:string | 门店ID |
| product_id | xsd:string | 商品ID |
| expiry_date | xsd:date | 商品到期日期 |
| original_stock | xsd:integer | 原始库存 |
| discount_rate | xsd:decimal | 折扣率（Agent 推理或总部配置） |
| sell_through_rate | xsd:decimal | 售罄率（结果反馈） |
| status | TaskStatus (enum) | 任务状态（pending/in_progress/completed） |
| created_by | Employee | 创建者（店长或 Agent） |
| created_at | xsd:datetime | 创建时间 |

### 枚举值

| TaskStatus | 说明 |
|------------|------|
| STATUS_PENDING | 待执行 |
| STATUS_IN_PROGRESS | 进行中 |
| STATUS_COMPLETED | 已完成 |

---

## 5. Agent 角色

### 全程参与的环节

| 环节 | Agent 行为 |
|------|-----------|
| **识别** | 监控商品保质期 + 库存，推理是否需要创建任务 |
| **推荐** | 根据品类规则 + 库存量推理折扣率 |
| **创建** | 自动创建 ReductionTask |
| **追踪** | 售罄率计算 → 反馈优化策略 |

### AI 推理流程

```
输入：SKU + 当前保质期剩余天数 + 库存量
  ↓
Step 1：查品类归属 → 确定品类出清规则
Step 2：查保质期 → 确定折扣层级（T1-T5）
Step 3：查折扣层级 → 确定折扣区间 + 推荐折扣
Step 4：查豁免规则 → 判断是否能打折
Step 5：输出推荐 → recommendedDiscountRate + 理由
```

---

## 6. 折扣层级体系（参考现有文档）

| 层级 | 保质期剩余 | 折扣区间 | 推荐折扣 |
|------|-----------|---------|---------|
| T1 | 0-1天 | 10%-50% | 20% |
| T2 | 2-3天 | 30%-60% | 40% |
| T3 | 4-7天 | 50%-80% | 70% |
| T4 | 8-14天 | 70%-90% | 85% |
| T5 | 15-30天 | 90%-100% | 95% |

### 品类紧迫度

| 品类 | 出清紧迫度 | 标准保质期 |
|------|-----------|-----------|
| 日配 | 🔴 紧急 | 1天 |
| 烘焙 | 🔴 紧急 | 2天 |
| 生鲜 | 🔴 高 | 3天 |
| 肉禽 | 🔴 高 | 5天 |
| 水产 | 🔴 高 | 3天 |
| 乳品 | 🟡 中 | 7天 |
| 冷冻食品 | 🟢 低 | 30天 |
| 饮品 | 🟢 低 | 60天 |
| 休闲食品 | 🟢 低 | 90天 |
| 米面粮油 | 🟢 低 | 180天 |

---

## 7. 验证方法

### 方法 A：命令行 RDF 验证

```bash
rapper -i turtle -o ntriples modules/module1-worktask/WORKTASK-MODULE.ttl
```

### 方法 B：自动化验证脚本

```bash
python3 validation/validate_ontology.py
```

---

## 8. 下一步

1. 实现对话助手的 UI 原型
2. 设计对话交互流程（意图识别 → 参数提取 → 执行 → 反馈）
3. 实现 Agent 推理模块

---

*文档生成时间：2026-04-20*
