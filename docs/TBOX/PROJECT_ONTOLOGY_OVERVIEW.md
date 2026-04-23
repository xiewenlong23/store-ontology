# 门店本体模块总览（PROJECT_ONTOLOGY_OVERVIEW）

> 来源：昊晴整理 | 作者：谢文龙团队 | 时间：2026-04-22
> 标签：store-ontology, TBOX, 本体论, TTL, OWL2
> 描述：store-ontology 项目 TTL 本体模块的架构说明、与后端推理引擎的集成方式

---

## 一、模块定位

`modules/` 目录是 store-ontology 项目的 **TBOX（语义模式层）**，存放 RDF/OWL2 格式的本体定义文件（`.ttl`），包含：
- **类（Class）** 定义：门店业务对象的类型体系
- **属性（Property）** 声明：类之间的关系和数据特征
- **OWL 声明**：推理规则、约束条件（cardinality, domain, range）
- **SPARQL 查询规则**：可复用的查询模板

---

## 二、当前本体模块

### module1-worktask（临期打折工作流）

| 文件 | 说明 |
|---|---|
| `WORKTASK-MODULE.ttl` | 临期打折场景完整本体（1256 triples，已验证） |
| `WORKTASK-MODULE.ttl.bak-20260419a` | 备份（已废弃，可删除） |
| `WORKTASK-MODULE.ttl.bak-20260419b` | 备份（已废弃，可删除） |

**WORKTASK-MODULE 覆盖的业务概念：**

```
WorkTask（工作任务）
├── TaskID / TaskName / TaskStatus（待办/进行中/完成）
├── TaskType（DiscountTask 打折任务）
├── associatedProduct → Product（关联商品）
├── definedBy → DiscountRule（打折规则）
├── priority → Priority（优先级）
├── deadline → xsd:dateTime
└── performedBy → StoreStaff（执行人）

Product（商品）
├── productID / productName
├── category → Category（生鲜/日配/烘焙/标品）
├── stockQuantity / expiryDate
├── status → ProductStatus（正常/临期/过期）
└── isNearExpiry → xsd:boolean（计算属性）

DiscountRule（打折规则）
├── ruleID / ruleName
├── discountStrategy → DiscountStrategy（阶梯/固定/清仓）
├── applicableCategories → Category[]
├── nearExpiryDays → xsd:integer（临期天数阈值）
└── discountRate → xsd:decimal（折扣率）

StoreStaff（店员）
├── staffID / staffName
├── role → StaffRole（店长/店员）
└── assignedTasks → WorkTask[]

Category（枚举）：daily_fresh | bakery | daily_products | packaged_goods
Priority（枚举）：high | medium | low
```

---

## 三、与后端推理引擎的集成

### 集成链路

```
后端 SPARQL Service
    ↓ 查询
modules/module1-worktask/WORKTASK-MODULE.ttl  ← 加载到 RDFLib Graph
    ↓ 推理
ttl_llm_reasoning.py（TTL + LLM 混合推理）
    ↓
Agent Executor → 返回结构化结果
```

### 加载方式（sparql_service.py）

```python
from rdflib import Graph

TTL_PATH = Path(__file__).parent.parent.parent / "modules" / "module1-worktask" / "WORKTASK-MODULE.ttl"

def load_ontology() -> Graph:
    g = Graph()
    g.parse(TTL_PATH, format="turtle")
    return g
```

### 本体查询示例（SPARQL）

```sparql
# 查询所有临期商品
PREFIX store: <http://store-ontology.example.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?product ?name ?category ?stock ?expiry
WHERE {
  ?product a store:Product .
  ?product store:productName ?name .
  ?product store:category ?category .
  ?product store:stockQuantity ?stock .
  ?product store:expiryDate ?expiry .
  FILTER (?expiry <= "2026-04-25"^^xsd:date)
}
```

---

## 四、验证工具

```bash
# 语法验证
rapper -i turtle -o ntriples file://modules/module1-worktask/WORKTASK-MODULE.ttl

# WebVOWL 可视化（浏览器打开）
# http://visualdataweb.de/webvowl/#iri=<file://modules/module1-worktask/WORKTASK-MODULE.ttl>

# Protege（桌面工具）
# File → Open → modules/module1-worktask/WORKTASK-MODULE.ttl
```

---

## 五、本体迭代方向

**目标**：从当前的单步（one-shot）工具调用，演进为 **LLM Agent 多步循环推理**：

```
LLM 查询本体（理解业务语义）
  → 决策：调用哪个工具/规则
  → 执行：SPARQL 查询 / 业务操作
  → 结果回流： SparqlResult / ActionResult
  → LLM 再决策：是否需要继续查询/执行
  → 循环直到任务完成
```

涉及文件：
- `app/services/agent_executor.py` — Agent 执行循环
- `app/services/ttl_llm_reasoning.py` — TTL+LLM 混合推理
- `app/services/sparql_service.py` — SPARQL 查询服务

---

## 六、扩展新本体模块

新增模块时，在 `modules/` 下创建新目录：

```
modules/
├── module1-worktask/          # 临期打折（已完成）
└── module2-inventory/         # 新模块：库存管理（规划中）
    └── INVENTORY-MODULE.ttl
```

新增后需更新：
1. `sparql_service.py` 中的 `load_ontology()` 合并加载
2. `docs/TBOX/PROJECT_ONTOLOGY_OVERVIEW.md` 本文档
3. `docs/ABOX/MANAGEMENT.md`（如新模块有实例数据）
