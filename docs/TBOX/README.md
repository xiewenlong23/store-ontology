# 门店本体论 (Store Ontology) — 设计文档

> 来源：昊晴整理 | 作者：谢文龙团队 | 时间：2026-04-22（更新）
> 标签：store-ontology, TTL, OWL2, 本体论, 零售
> 描述：门店大脑 AI 原生应用的本体设计文档，基于 Palantir Foundry Ontology 框架

---

## 1. 项目概述

门店本体论以 [Palantir Foundry Ontology](https://www.palantir.com/docs/foundry/ontology/overview) 为蓝本，采用四层架构建模零售门店业务实体与流程。

**顶层目录：**

```
store-ontology/
├── modules/                    # TBOX — 本体模块（TTL/OWL 格式）
│   └── module1-worktask/
│       └── WORKTASK-MODULE.ttl
├── data/                       # ABOX — 实例数据（JSON 格式）
│   ├── products.json           # 商品实例
│   └── tasks.json              # 任务实例
└── docs/
    ├── TBOX/                  # TBOX — 本体设计文档
    ├── ABOX/                  # ABOX — 实例数据文档
    ├── OPERATIONS/            # 运维文档
    ├── AGENT/                 # Agent 系统文档
    └── INFRASTRUCTURE/        # 工程基础设施
```

---

## 2. 四层架构映射

| Foundry 层 | 说明 | 本项目对应 |
|-----------|------|-----------|
| **ObjectType** | 业务实体（人/事/物） | WorkTask, Product, StoreStaff, DiscountRule... |
| **ObjectProperty** | 实体间关系 | associatedProduct, definedBy, performedBy... |
| **ActionType** | 可执行的操作语义 | ConfirmDiscount, ExecuteTask, SubmitResult... |
| **LinkType / WriteType** | 写入语义（增删改） | WriteLink, WriteProp |

---

## 3. 核心 ObjectType

### WorkTask（工作任务）
> 商品临期打折任务。完整闭环：创建 → 确认 → 执行 → 提交 → 复核 → 闭环。

| 属性 | 类型 | 说明 |
|------|------|------|
| taskName | xsd:string | 任务名称 |
| triggerReason | xsd:string | 触发原因（保质期/库存/...） |
| status | TaskStatus (enum) | 任务状态 |
| hasResult | WorkTaskResult | 执行结果 |
| hasReview | WorkTaskReview | 复核结果 |
| checklistOfTask | WorkTaskCheckItem | 检查项清单 |

### Product（商品）

| 属性 | 类型 | 说明 |
|------|------|------|
| productID | xsd:string | 商品唯一标识 |
| productName | xsd:string | 商品名称 |
| category | Category (enum) | 品类 |
| stockQuantity | xsd:integer | 当前库存 |
| expiryDate | xsd:date | 到期日期 |
| isNearExpiry | xsd:boolean | 是否临期（计算属性）|

### DiscountRule（打折规则）

| 属性 | 类型 | 说明 |
|------|------|------|
| discountStrategy | DiscountStrategy (enum) | 阶梯/固定/清仓 |
| applicableCategories | Category[] | 适用品类 |
| nearExpiryDays | xsd:integer | 临期天数阈值 |
| discountRate | xsd:decimal | 折扣率 |

---

## 4. ActionType 语义

ActionType 是连接语义层（Ontology）和执行层（Transformation/Pipeline）的关键。

### ConfirmDiscount（确认打折幅度）
```
触发条件：系统建议 3 折，店长确认为 5 折
Action 逻辑：
  writesProperty: confirmedDiscountRate  ← 5折（5折为最终执行折扣）
  writesProperty: recommendedReason     ← 保质期 3 天 + 库存 120（双推理）
  paramSource: recommendedDiscountRate   ← 从 ParamConfirmDiscountRate 拿值
  paramRequired: true
  submissionCriteria: confirmedDiscountRate 必须有值
```

### ExecuteTask（执行任务）
```
Action 逻辑：
  targetObjectType: WorkTaskCheckItem   ← 操作检查项对象
  writesProperty: checkStatus           ← 更新检查状态
  writesLink: performedBy              ← 关联执行员工
  paramSource: checkItemType            ← 检查项类型参数
```

### SubmitResult（提交结果）
```
Action 逻辑：
  targetObjectType: WorkTaskResult
  writesProperty: executedDiscountRate, soldQty, clearanceRate
  paramSource: POS出清数据              ← 自动回填 POS 数据
  autoPopulateProperties: originalInventoryQty, soldQty, clearanceRate
```

---

## 5. 验证方法

### 方法 A：命令行 RDF 验证（最快）
```bash
# 验证 Schema 语法
rapper -i turtle -o ntriples \
  file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl \
  2>/dev/null | wc -l
# 预期输出：1256（1256 triples，无语法错误）
```

### 方法 B：WebVOWL 可视化（最直观）
```
打开 https://webvowl.tib.eu/
输入 IRI: file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl
```

### 方法 C：导入 Protege 查看（最专业）
```
https://protege.stanford.edu/
File → Open → modules/module1-worktask/WORKTASK-MODULE.ttl
支持：类层次、属性层次、推理验证
```

---

## 6. 如何扩展新场景

### 扩展步骤：
1. **在 WORKTASK-MODULE.ttl 中新增 ObjectType**
2. **定义 ObjectProperty**（standard 属性 + inverseOf 配对）
3. **注册 NamedIndividual**（枚举值）
4. **定义 ActionType**（元属性完整声明）
5. **更新 `docs/TBOX/PROJECT_ONTOLOGY_OVERVIEW.md`**
6. **运行 `rapper` 验证 TTL 语法**

### 命名规范：
- ObjectType：`PascalCase`（如 `WorkTask`, `WorkTaskResult`）
- ObjectProperty：`camelCase`（如 `hasResult`, `assignedTo`）
- DatatypeProperty：`camelCase`
- NamedIndividual：`UPPER_SNAKE_CASE`（如 `STATUS_PENDING`）
- ActionType：`PascalCase`（如 `ConfirmDiscount`）

---

## 7. 品类出清促销规则

### 品类分类体系（9大类）

| 品类 | 说明 | 出清紧迫度 | 标准保质期 |
|------|------|-----------|-----------|
| 日配 | 豆腐/豆制品/卤味 | 🔴 紧急 | 1天 |
| 烘焙 | 面包/蛋糕/西点 | 🔴 紧急 | 2天 |
| 生鲜 | 蔬菜/水果 | 🔴 高 | 3天 |
| 肉禽 | 鲜肉/冷鲜肉/冷冻肉 | 🔴 高 | 5天 |
| 水产 | 活鲜/冰鲜/冷冻海鲜 | 🔴 高 | 3天 |
| 乳品 | 牛奶/酸奶/乳饮料 | 🟡 中 | 7天 |
| 冷冻食品 | 速冻米面/冰淇淋 | 🟢 低 | 30天 |
| 饮品 | 饮料/瓶装水/果汁 | 🟢 低 | 60天 |
| 休闲食品 | 饼干/糖果/坚果 | 🟢 低 | 90天 |

### 折扣层级（T1-T5）

| 层级 | 保质期剩余 | 折扣区间 | 推荐折扣 |
|------|-----------|---------|---------|
| T1（临期1天） | 0-1天 | 10%-50% | 20% |
| T2（临期2-3天） | 2-3天 | 30%-60% | 40% |
| T3（临期4-7天） | 4-7天 | 50%-80% | 70% |
| T4（临期8-14天） | 8-14天 | 70%-90% | 85% |
| T5（临期15-30天） | 15-30天 | 90%-100% | 95% |

### 豁免规则

| 豁免类型 | 说明 | 能否覆盖 |
|---------|------|---------|
| 进口商品 | 追溯要求和品质标准 | ❌ 不可 |
| 有机/绿色食品 | 品牌保护 | ⚠️ 可覆盖 |
| 促销中商品 | 不叠加折扣 | ❌ 不可 |
| 新上架商品（7天内）| 维护价格形象 | ❌ 不可 |
| 总部强制禁止 | 总部指定 | ❌ 不可 |
| 门店本地豁免 | 门店申请+总部审批 | ✅ 可覆盖 |

---

## 8. 文件清单

| 文件 | 说明 |
|------|------|
| `modules/module1-worktask/WORKTASK-MODULE.ttl` | 本体 Schema（1256 triples）|
| `data/products.json` | 商品实例数据 |
| `data/tasks.json` | 任务实例数据 |

---

*文档更新时间：2026-04-22*
*项目负责人：谢文龙*
