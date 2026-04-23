# 门店大脑 AI 原生应用 — 架构规划

> 更新时间：2026-04-22
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

### 三级推理引擎

| 路径 | 响应时间 | 适用场景 | 实现方式 |
|------|---------|---------|---------|
| **Fast Path** | 毫秒级 | 确定性规则：临期商品 → 查询 <3天 → 直接执行打折 | 规则引擎（Python if-then） |
| **Medium Path** | 百毫秒级 | 本体推理：查找"所有缺货且销量高的生鲜 SKU" | OWL 2 RL 推理（GraphDB） |
| **Slow Path** | 秒级 | LLM Agent：自然语言理解、多跳推理 | LLM + SPARQL + Tool Call |

---

## 五、LLM Agent 多步工作流（当前状态）

### 当前：`agent_executor.py` 是单步（One-Shot）

```python
def execute(user_input: str) -> dict:
    messages = build_messages(user_input)
    response = llm_service.chat(messages)
    parsed = parse_tool_calls(response)
    results = [registry.dispatch(t, a) for t, a in parsed]
    return format_response(results)
```

### 迭代方向：多步循环推理（Iteration 8）

```
LLM 查询本体（理解业务语义）
  → 决策：调用哪个工具/规则
  → 执行：SPARQL 查询 / 业务操作
  → 结果回流：SparqlResult / ActionResult
  → LLM 再决策：是否需要继续查询/执行
  → 循环直到任务完成
```

### System Prompt 约束（已生效）

`agent_executor.py` 的 SYSTEM_PROMPT 已追加数据展示原则：

```
数据展示原则：
- ASCII 图表仅展示汇总结构（如柱状图），不要在图表下方列出详细商品清单
- tool_result 中的 products/SKUs 数据仅用于组件渲染，前端 ProductList 会自动展示
- 你的 response 文本只能包含：分析结论 + 图表 + 行动建议，禁止复述具体商品数据
```

**目的**：解决柱状图场景下 LLM 在 response 文本中嵌入完整产品数据，导致前端双重渲染问题。

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

## 七、当前项目已实现

- ✅ TTL 本体（WorkTask / Product / Category / DiscountTier / ExemptionRule）
- ✅ SPARQL 推理层（`sparql_service.py`）
- ✅ AgentExecutor 单步执行（`agent_executor.py`）
- ✅ System Prompt 数据展示约束（双重渲染修复）
- ✅ ABOX 实例数据（`data/products.json` / `data/tasks.json`）
- ✅ Dashboard 数据 API（`/api/reasoning/products`）
- ✅ TBOX/ABOX 文档分离（`docs/TBOX/` / `docs/ABOX/`）

**待建设：**

- [ ] AgentExecutor 多步循环（Iteration 8）
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
