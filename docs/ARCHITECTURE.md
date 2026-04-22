# 门店大脑 AI 原生应用 — 架构规划

> 来源：与谢文龙的对齐讨论（2026-04-21）
> 定位：企业级零售大脑本体论项目的系统性设计框架

---

## 一、核心挑战

| 挑战维度 | 具体问题 |
|---------|---------|
| **规模** | 单门店 1.5 万 SKU，1 万员工；全系统千万级 SKU，千万级员工关系 |
| **异构性** | 门店地域/规模/客群差异大，本体需兼顾通用+局部特化 |
| **时效性** | 临期打折/补货/排班需要分钟级推理响应 |
| **稀疏性** | 单个门店实际活跃 SKU 可能只有 30-40%，大量冷数据 |
| **层级性** | 总部→区域→门店→部门→员工，五级管理结构 |

---

## 二、本体分层架构

### 层级总览

```
┌─────────────────────────────────────────┐
│ L0: 全局核心本体 (Foundation)            │ ← 所有门店共享，如 Product/Employee/Store
├─────────────────────────────────────────┤
│ L1: 业务域本体 (Domain)                  │ ← 促销域/库存域/排班域/补货域
├─────────────────────────────────────────┤
│ L2: 区域/品类本体 (Regional/Category)    │ ← 华北区/生鲜类/家电类
├─────────────────────────────────────────┤
│ L3: 单店本体实例 (Store Instance)        │ ← 每个门店的具体数据
└─────────────────────────────────────────┘
```

### L0 核心实体（必须稳固）

```turtle
:Product a owl:Class ;
    rdfs:label "商品 SKU"@zh-CN ;
    rdfs:label "Product (SKU)"@en .

:Store a owl:Class ;
    rdfs:label "门店"@zh-CN ;
    rdfs:label "Store"@en .

:Employee a owl:Class ;
    rdfs:label "员工"@zh-CN ;
    rdfs:label "Employee"@en .

:WorkTask a owl:Class ;
    rdfs:label "工作记录"@zh-CN ;
    rdfs:label "Work Task"@en .
```

#### :Product 属性

```turtle
:skuId        a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:string .
:productName  a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:string .
:category     a owl:ObjectProperty   ; rdfs:domain :Product ; rdfs:range :Category .
:subCategory  a owl:ObjectProperty   ; rdfs:domain :Product ; rdfs:range :SubCategory .
:supplier     a owl:ObjectProperty   ; rdfs:domain :Product ; rdfs:range :Supplier .
:brand        a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:string .
:unitPrice    a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:decimal .
:costPrice    a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:decimal .
:shelfLife    a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:duration .
:minStockLevel a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:integer .
:maxStockLevel a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:integer .
:isPerishable  a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:boolean .
:isSeasonal    a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:boolean .
:temperatureRequirement a owl:DatatypeProperty ; rdfs:domain :Product ; rdfs:range xsd:string .
```

#### :Store 属性

```turtle
:storeId       a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:string .
:storeName     a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:string .
:region        a owl:ObjectProperty   ; rdfs:domain :Store ; rdfs:range :Region .
:city          a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:string .
:district      a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:string .
:storeType     a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:string .
:area          a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:decimal .
:employeeCount a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:integer .
:openDate      a owl:DatatypeProperty ; rdfs:domain :Store ; rdfs:range xsd:date .
```

#### :Employee 属性

```turtle
:employeeId      a owl:DatatypeProperty ; rdfs:domain :Employee ; rdfs:range xsd:string .
:name            a owl:DatatypeProperty ; rdfs:domain :Employee ; rdfs:range xsd:string .
:role            a owl:ObjectProperty   ; rdfs:domain :Employee ; rdfs:range :Role .
:department      a owl:ObjectProperty   ; rdfs:domain :Employee ; rdfs:range :Department .
:storeId         a owl:ObjectProperty   ; rdfs:domain :Employee ; rdfs:range :Store .
:regionId        a owl:ObjectProperty   ; rdfs:domain :Employee ; rdfs:range :Region .
:skills          a owl:ObjectProperty   ; rdfs:domain :Employee ; rdfs:range :Skill .
:certifications  a owl:ObjectProperty   ; rdfs:domain :Employee ; rdfs:range :Certification .
:shiftPattern    a owl:DatatypeProperty ; rdfs:domain :Employee ; rdfs:range xsd:string .
:employmentType  a owl:DatatypeProperty ; rdfs:domain :Employee ; rdfs:range xsd:string .
```

### L1 业务域本体（可插拔模块）

#### 促销域

```turtle
:Promotion a owl:Class ;
    rdfs:label "促销活动"@zh-CN .

:promotionId            a owl:DatatypeProperty ; rdfs:domain :Promotion ; rdfs:range xsd:string .
:promotionType          a owl:DatatypeProperty ; rdfs:domain :Promotion ; rdfs:range xsd:string .
:discountRate           a owl:DatatypeProperty ; rdfs:domain :Promotion ; rdfs:range xsd:decimal .
:startDate              a owl:DatatypeProperty ; rdfs:domain :Promotion ; rdfs:range xsd:date .
:endDate                a owl:DatatypeProperty ; rdfs:domain :Promotion ; rdfs:range xsd:date .
:applicableStores       a owl:ObjectProperty   ; rdfs:domain :Promotion ; rdfs:range :Store .
:applicableCategories   a owl:ObjectProperty   ; rdfs:domain :Promotion ; rdfs:range :Category .
:excludedProducts       a owl:ObjectProperty   ; rdfs:domain :Promotion ; rdfs:range :Product .
```

#### 库存域

```turtle
:InventoryEvent a owl:Class ;
    rdfs:label "库存事件"@zh-CN .

:eventId     a owl:DatatypeProperty ; rdfs:domain :InventoryEvent ; rdfs:range xsd:string .
:eventType   a owl:ObjectProperty   ; rdfs:domain :InventoryEvent ; rdfs:range :InventoryEventType .
:storeId     a owl:ObjectProperty   ; rdfs:domain :InventoryEvent ; rdfs:range :Store .
:skuId       a owl:ObjectProperty   ; rdfs:domain :InventoryEvent ; rdfs:range :Product .
:quantity    a owl:DatatypeProperty ; rdfs:domain :InventoryEvent ; rdfs:range xsd:integer .
:timestamp   a owl:DatatypeProperty ; rdfs:domain :InventoryEvent ; rdfs:range xsd:dateTime .
:reason      a owl:DatatypeProperty ; rdfs:domain :InventoryEvent ; rdfs:range xsd:string .
:employeeId  a owl:ObjectProperty   ; rdfs:domain :InventoryEvent ; rdfs:range :Employee .
```

#### 补货域

```turtle
:ReplenishmentTask a owl:Class ;
    rdfs:label "补货任务"@zh-CN .

:taskId             a owl:DatatypeProperty ; rdfs:domain :ReplenishmentTask ; rdfs:range xsd:string .
:storeId            a owl:ObjectProperty   ; rdfs:domain :ReplenishmentTask ; rdfs:range :Store .
:skuId              a owl:ObjectProperty   ; rdfs:domain :ReplenishmentTask ; rdfs:range :Product .
:currentStock       a owl:DatatypeProperty ; rdfs:domain :ReplenishmentTask ; rdfs:range xsd:integer .
:suggestedQuantity  a owl:DatatypeProperty ; rdfs:domain :ReplenishmentTask ; rdfs:range xsd:integer .
:urgency            a owl:ObjectProperty   ; rdfs:domain :ReplenishmentTask ; rdfs:range :UrgencyLevel .
:autoGenerate       a owl:DatatypeProperty ; rdfs:domain :ReplenishmentTask ; rdfs:range xsd:boolean .
```

### L2 区域/品类本体

```turtle
:Region a owl:Class ;
    rdfs:label "区域"@zh-CN ;
    rdfs:label "Region"@en .

:Category a owl:Class ;
    rdfs:label "品类"@zh-CN ;
    rdfs:label "Category"@en .

:SubCategory a owl:Class ;
    rdfs:label "子品类"@zh-CN ;
    rdfs:label "Sub-Category"@en .

:hasParentRegion  a owl:ObjectProperty ;
    rdfs:domain :Region ;
    rdfs:range :Region ;
    owl:inverseOf :hasSubRegion .

:hasParentCategory a owl:ObjectProperty ;
    rdfs:domain :Category ;
    rdfs:range :Category ;
    owl:inverseOf :hasSubCategory .
```

### L3 单店本体实例

```turtle
# 单店活跃 SKU 索引（解决稀疏性：只索引本店实际销售的 SKU）
:Store_001 a :Store ;
    :storeId "STORE-001" ;
    :hasActiveSKU :SKU_OatMilk_500g ;
    :hasActiveSKU :SKU_Bread_300g ;
    :hasDepartment :Dept_FreshFood ;
    :hasEmployee :Emp_001, :Emp_002 .

# 时间窗口切片（只保留近 90 天活跃数据）
:InventorySnapshot_2026-Q2 a :TimeSlicedOntology ;
    :validFrom "2026-04-01"^^xsd:date ;
    :validTo   "2026-06-30"^^xsd:date .
```

---

## 三、解决稀疏性：多视图本体

**问题**：单门店 1.5 万 SKU，但门店 A 实际卖的只有 5000 种，其他 1 万种是"理论 SKU 池"。

**解法**：用 **View-based Ontology**，区分"全局 SKU 池"和"门店活跃 SKU"：

```turtle
# 全局产品目录（亿级 triples，但高度结构化）
:GlobalProductCatalog a owl:Ontology .
:SKU_OatMilk_500g a :Product ;
    :skuId "SKU-00001" ;
    :category :Dairy ;
    :shelfLife "180days"^^xsd:duration .

# 门店活跃 SKU（每个门店只索引自己卖的产品，大幅减少查询范围）
:Store_001 :hasActiveSKU :SKU_OatMilk_500g ;
            :hasActiveSKU :SKU_Bread_300g .
```

---

## 四、规模化查询策略

### 4.1 空间分区（而非全局扫描）

```
门店实体 → 区域聚合 → 全国索引
    ↓
SPARQL 先定位到 region 切片，再在该切片内查询
```

### 4.2 三级推理引擎

| 路径 | 响应时间 | 适用场景 | 实现方式 |
|------|---------|---------|---------|
| **Fast Path** | 毫秒级 | 确定性规则：临期商品 → 查询 <3天 → 直接执行打折 | 规则引擎（Python if-then / Drools） |
| **Medium Path** | 百毫秒级 | 本体推理：查找"所有缺货且销量高的生鲜 SKU" | OWL 2 RL 推理（GraphDB） |
| **Slow Path** | 秒级 | LLM Agent：自然语言理解、多跳推理 | LLM + SPARQL + Tool Call |

### 4.3 时间窗口切片

```turtle
# 只保留近 90 天活跃数据，避免历史数据膨胀
:InventorySnapshot_2026-Q1 a :TimeSlicedOntology ;
    :validFrom "2026-01-01"^^xsd:date ;
    :validTo   "2026-03-31"^^xsd:date .
```

---

## 五、LLM Agent 多步工作流

### 业务流程

```
用户输入: "哪家门店的蒙牛酸奶临期数量最多，需要优先处理？"

┌─────────────┐
│ 理解意图    │ → 识别为「临期库存 → 排序 → 优先级」任务
└──────┬──────┘
       ▼
┌─────────────┐
│ 查询本体    │ → SPARQL: 找所有 store，临期酸奶，按数量排序
└──────┬──────┘
       ▼
┌─────────────┐
│ 执行推理    │ → 返回 Top3 门店 + 建议处理策略
└──────┬──────┘
       ▼
┌─────────────┐
│ 生成报告    │ → 按门店/品类/紧迫度组织输出
└─────────────┘
```

### 迭代 8 方向：AgentExecutor 从 One-Shot 到 Multi-Step Loop

当前 `agent_executor.py` 是单步（one-shot）工具调用，需改为循环架构：

```python
# 目标架构
steps = []
while step_count < MAX_STEPS:
    # 1. LLM 查询本体理解业务语义
    messages.append({"role": "user", "content": context})
    response = llm.chat(messages)
    
    # 2. LLM 决定调用工具
    parsed = json.loads(response)
    if not parsed.get("continue"):
        break  # 任务完成
    
    tool_name = parsed["tool"]
    args = parsed["args"]
    
    # 3. 执行工具
    tool_result = registry.dispatch(tool_name, args)
    messages.append({"role": "tool", "content": str(tool_result)})
    steps.append(tool_name)
    step_count += 1

# 4. 结果回流 → LLM 再决策 → 循环直到结束
```

---

## 六、关键架构决策

| 决策点 | 当前实现 | 建议方向 | 原因 |
|-------|---------|---------|------|
| **存储后端** | RDFLib 内存加载 | GraphDB (Ontotext/BlazeGraph) + Redis 热数据层 | 亿级 triples 需要原生图存储 |
| **查询语言** | SPARQL 1.0 | SPARQL 1.1 + 服务定义 (SERVICE) | 支持联邦查询，分片友好 |
| **推理时机** | 运行时增量推理 | 异步预推理 + 运行时增量 | 避免每次查询都触发 OWL 推理 |
| **数据更新** | 静态 JSON 文件 | 事件驱动 (Kafka/RabbitMQ) | 库存变动即时反映到本体 |
| **LLM接口** | 直接调用 | RAG + 本体 Schema 增强 | 防止 LLM 幻觉，保证业务语义准确 |
| **本体分层** | 单一 WORKTASK-MODULE | L0-L3 层级化本体 | 解决规模/异构/稀疏问题 |

---

## 七、验证思路：单门店最小验证单元

1. 选一家典型门店，建模其完整本体（L0 + L1 促销域）
2. 跑通所有核心场景（临期打折 / 补货 / 排班 / 盘点）
3. 确认后再横向扩展到区域 → 全国

**当前项目已实现（临期出清场景）：**

- ✅ TTL 本体（WorkTask / SKU / Category / DiscountTier / ExemptionRule）
- ✅ SPARQL 推理层（`sparql_service.py`）
- ✅ AgentExecutor 多步循环（`agent_executor.py`，迭代8方向）
- ✅ 豁免检查（`is_imported` / `is_organic` / `is_promoted` / `arrival_days`）
- ✅ 降级规则统一管理（`discount_constants.py`）

**待建设：**

- [ ] L0-L3 分层本体拆分
- [ ] 多视图本体（全局SKU池 vs 门店活跃SKU）
- [ ] 三级推理引擎 Fast Path（规则引擎）
- [ ] 事件驱动数据更新（Kafka/RabbitMQ）
- [ ] GraphDB 后端迁移
- [ ] 补货域 / 排班域 / 盘点域 L1 本体模块

---

## 八、项目演进路线

```
阶段 1（当前）: 临期出清单场景跑通
  └→ 单一 WORKTASK-MODULE → 单门店验证

阶段 2: 临期出清场景深化
  └→ L0 核心实体拆分 + 多视图本体
  └→ Fast Path 规则引擎
  └→ 单门店完整数据模型

阶段 3: 扩展到补货/排班/盘点域
  └→ L1 业务域本体（可插拔模块）
  └→ 区域层级（L2）

阶段 4: 全量上线
  └→ GraphDB 亿级 triples
  └→ 事件驱动实时更新
  └→ 全链路 RAG + 本体增强
```
