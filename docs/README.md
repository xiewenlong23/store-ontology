# 门店本体论 (Store Ontology) — 设计文档

## 1. 项目概述

门店本体论以 [Palantir Foundry Ontology](https://www.palantir.com/docs/foundry/ontology/overview) 为蓝本，采用四层架构建模零售门店业务实体与流程。

**顶层目录：**
```
store-ontology/
├── modules/          # 本体模块（OWL/Turtle 格式）
│   └── module1-worktask/WORKTASK-MODULE.ttl
├── examples/         # 业务场景实例数据
│   ├── DEMO-DISCOUNT-001.ttl     # 临期打折完整流程示例
│   └── DEMO-CLEARANCE-RULES.ttl  # 品类出清规则示例
├── validation/       # 验证框架
│   └── validate_ontology.py
└── docs/             # 本文档
```

## 2. 四层架构映射

| Foundry 层 | 说明 | 本项目对应 |
|-----------|------|-----------|
| **ObjectType** | 业务实体（人/事/物） | WorkTask, SKU, Store, Employee, InventoryEvent... |
| **ObjectProperty** | 实体间关系 | hasResult, hasReview, assignedTo, triggeredBy... |
| **ActionType** | 可执行的操作语义 | ConfirmDiscount, AssignTask, ExecuteTask... |
| **LinkType / WriteType** | 写入语义（增删改） | WriteLink, WriteProp |

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

### WorkTaskResult（执行结果）
| 属性 | 类型 | 说明 |
|------|------|------|
| executedDiscountRate | xsd:decimal | 实际执行折扣率 |
| soldQty | xsd:integer | 实际销售数量 |
| originalInventoryQty | xsd:integer | 原库存量 |
| clearanceRate | xsd:decimal | 出清率（= soldQty/originalInventoryQty） |

### WorkTaskCheckItem（检查项）
> IF枪扫描 + 价格标签打印，是打折执行的完整闭环。

| 属性 | 类型 | 说明 |
|------|------|------|
| checkItemType | CheckItemType (enum) | 检查项类型 |
| checkStatus | CheckStatus (enum) | 执行状态 |
| performedBy | Employee | 执行人 |

### WorkTaskReview（复核）
| 属性 | 类型 | 说明 |
|------|------|------|
| reviewDecision | ReviewDecision (enum) | 复核结论 |
| reviewer | Employee | 复核人 |

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
  populatesProperty: clearanceRate      ← 计算出清率
  dataMapping: POS机销售数据 → WorkTaskResult 字段映射
```

## 5. 验证方法

### 方法 A：命令行 RDF 验证（最快）
```bash
# 验证 Schema 语法
rapper -i turtle -o ntriples file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl 2>/dev/null | wc -l
# 预期输出：1256（1256 triples，无语法错误）

# 验证示例数据语法
rapper -i turtle -o ntriples file:///mnt/d/ObsidianVault/store-ontology/examples/DEMO-DISCOUNT-001.ttl 2>/dev/null | wc -l
# 预期输出：108
```

### 方法 B：自动化验证脚本（最全）
```bash
cd /mnt/d/ObsidianVault/store-ontology
python3 validation/validate_ontology.py
```
验证项目：
1. RDF 语法正确性（rapper 解析）
2. 标签完整性（rdfs:label）
3. 逆属性（inverseOf）配对
4. ActionType 元属性声明
5. 实例数据业务完整性

### 方法 C：图形化可视化（最直观）
```bash
# 上传 TTL 文件到 WebVOWL
open https://webvowl.tib.eu/
# 或 http://visualdataweb.de/webvowl/
```

### 方法 D：导入 Protege 查看（最专业）
```bash
# 用 Protege 打开 TTL 文件（需要 Java）
# https://protege.stanford.edu/
# 支持：类层次、属性层次、推理验证
```

## 6. 如何扩展新场景

### 扩展步骤：
1. **在 WORKTASK-MODULE.ttl 中新增 ObjectType**（第六部分或新模块）
2. **定义 ObjectProperty**（standard 属性 + inverseOf 配对）
3. **注册 NamedIndividual**（枚举值）
4. **定义 ActionType**（元属性完整声明）
5. **在 examples/ 中添加场景实例**
6. **运行验证脚本确认**

### 命名规范：
- ObjectType：`PascalCase`（如 `WorkTask`, `WorkTaskResult`）
- ObjectProperty：`camelCase`（如 `hasResult`, `assignedTo`）
- DatatypeProperty：`camelCase`
- NamedIndividual：`UPPER_SNAKE_CASE`（如 `STATUS_PENDING`）
- ActionType：`PascalCase`（如 `ConfirmDiscount`）

## 7. 与 Palantir Foundry Ontology 的对照

| Foundry 概念 | 本项目实现 |
|-------------|-----------|
| ObjectType | `owl:Class` + `rdfs:label` |
| ObjectProperty | `owl:ObjectProperty` + `rdfs:domain` + `rdfs:range` |
| DatatypeProperty | `owl:DatatypeProperty` |
| ActionType | 自定义元属性结构（hasParameter, writesProperty, targetObjectType...） |
| LinkType | `WriteLink` 类（描述写入关联） |
| WriteType | `WriteProp` 类（描述写入属性） |
| Function | `Derivation` 类（派生属性逻辑） |

## 8. 文件清单

| 文件 | 行数 | triples | 说明 |
|------|------|---------|------|
| WORKTASK-MODULE.ttl | ~1850 | 1679 | 本体 Schema（含 WorkTask + 品类出清规则）|
| DEMO-DISCOUNT-001.ttl | ~230 | 108 | 商品临期打折完整业务流程示例 |
| DEMO-CLEARANCE-RULES.ttl | ~430 | 262 | 品类出清规则示例（6个SKU × AI推理）|
| validate_ontology.py | 317 | — | 自动化验证脚本 |

## 9. 品类出清促销规则

### 9.1 品类分类体系（9大类）

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
| 米面粮油 | 大米/面粉/食用油 | 🟢 低 | 180天 |

### 9.2 折扣层级（T1-T5）

| 层级 | 保质期剩余 | 折扣区间 | 推荐折扣 |
|------|-----------|---------|---------|
| T1（临期1天） | 0-1天 | 10%-50% | 20% |
| T2（临期2-3天） | 2-3天 | 30%-60% | 40% |
| T3（临期4-7天） | 4-7天 | 50%-80% | 70% |
| T4（临期8-14天） | 8-14天 | 70%-90% | 85% |
| T5（临期15-30天） | 15-30天 | 90%-100% | 95% |

### 9.3 出清规则（按品类）

每个品类有一条 `ClearanceRule`，指定适用的折扣层级。例如：

- **生鲜规则**：`T1 + T2 + T3 + T4`
- **乳品规则**：`T1 + T2 + T3 + T4 + T5`（保质期较长）
- **日配规则**：`T1 + T2`（保质期极短）
- **烘焙规则**：`T1 + T2 + T3`（保质期短）
- **饮品规则**：`T1 + T2 + T3 + T4 + T5`（保质期长）

### 9.4 豁免规则

| 豁免类型 | 说明 | 能否覆盖 |
|---------|------|---------|
| 进口商品 | 追溯要求和品质标准 | ❌ 不可 |
| 有机/绿色食品 | 品牌保护 | ⚠️ 可覆盖 |
| 促销中商品 | 不叠加折扣 | ❌ 不可 |
| 新上架商品（7天内） | 维护价格形象 | ❌ 不可 |
| 总部强制禁止 | 总部指定 | ❌ 不可 |
| 门店本地豁免 | 门店申请+总部审批 | ✅ 可覆盖 |

### 9.5 AI 推理流程

```
输入：SKU + 当前保质期剩余天数 + 库存量
  ↓
Step 1：查品类归属 → 确定品类出清规则
Step 2：查保质期 → 确定折扣层级（T1-T5）
Step 3：查折扣层级 → 确定折扣区间 + 推荐折扣
Step 4：查豁免规则 → 判断是否能打折
Step 5：输出推荐 → recommendedDiscountRate + 理由
```

### 9.6 示例数据

| SKU | 品类 | 剩余天数 | 推荐折扣 | 推荐理由 |
|-----|------|---------|---------|---------|
| 蒙牛特仑苏 | 乳品 | 2天 | 40% | T2层级，有机商品部分豁免 |
| 红富士苹果 | 生鲜 | 1天 | 20% | T1层级，生鲜高紧迫度 |
| 现烤法式面包 | 烘焙 | 0天 | 10% | T1层级，当日强制出清 |
| 嫩豆腐 | 日配 | 1天 | 20% | T1层级，日配当日出清 |
| 农夫山泉 | 饮品 | 5天 | 70% | T3层级，饮品低紧迫度 |
| 奥利奥饼干 | 休闲食品 | 10天 | 90% | T4层级，休闲低紧迫度 |

---
*文档生成时间：2026-04-19*
*项目负责人：谢文龙*
