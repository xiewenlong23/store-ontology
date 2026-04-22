# ABox/TBox 数据分层架构设计

> 更新：2026-04-21
> 背景：单门店临期出清场景验证，修复 ABox/TBox 边界混淆问题

---

## 一、核心原则

**TBox（业务语义层）** — 存"规则是什么"
- 类定义、属性声明、约束规则
- 变化频率低，版本管理严格
- 格式：TTL/OWL 文件，只读

**ABox（业务实例层）** — 存"具体有哪些"
- 商品、任务、库存事件、员员工等实例数据
- 变化频率高，按业务需要读写
- 格式：JSON 文件或 GraphDB，按规模和访问模式选型

**禁止事项：不要用 SPARQL 查 ABox 数据（JSON 文件）。**

---

## 二、存储布局

```
store-ontology/
├── modules/
│   └── module1-worktask/
│       └── WORKTASK-MODULE.ttl    ← TBox（只读）
│           ├── owl:Class 定义
│           ├── owl:ObjectProperty / DatatypeProperty 声明
│           ├── rdfs:subClassOf 层级
│           └── 约束规则（SHACL 或注释说明的 min/max 范围）
│
├── examples/                        ← ABox 示例数据（仅演示）
│   ├── DEMO-CLEARANCE-RULES.ttl   ← TTL 格式的清仓规则示例
│   └── DEMO-STORE-INVENTORY.ttl   ← TTL 格式的门店示例
│
└── data/                           ← ABox 运行时数据
    ├── products.json               ← 商品实例（5,000条）
    ├── tasks.json                  ← 工作任务实例（API 增删改）
    └── inventory_events.json       ← 库存事件（append 追加）
```

---

## 三、TBox/SPARQL 负责什么

| 查询 | 走 TTL/SPARQL | 说明 |
|------|:-------------:|------|
| 折扣规则（按品类/剩余天数匹配 tier）| ✅ | 规则定义在 TTL |
| 折扣范围（minDiscount / maxDiscount / recommendedDiscount）| ✅ | 规则定义在 TTL |
| 豁免规则类型列表 | ✅ | ExemptionRule 类在 TTL |
| 折扣 tier 优先级（Critical > High > Medium）| ✅ | tierUrgency 在 TTL |
| ActionType 工作流步骤定义 | ✅ | 步骤定义在 TTL |
| 类/属性 schema 信息 | ✅ | 本身就是元数据 |

---

## 四、JSON/Python 负责什么

| 查询 | 走 JSON/Python | 说明 |
|------|:--------------:|------|
| 临期货商品列表（scan 入口）| ✅ | 商品实例在 JSON |
| 具体商品属性（is_imported / is_organic / is_promoted / arrival_days）| ✅ | 实例属性在 JSON |
| 豁免检查（具体商品是否豁免）| ✅ | Python fallback，属性来自 JSON |
| 任务 CRUD | ✅ | tasks.json 文件读写 |
| 库存事件追加 | ✅ | inventory_events.json append |

---

## 五、查询路径设计

### 临期出清流程的查询路径

```
/agent/scan（扫描临期货）
    │
    ├── TTL/SPARQL ──→ query_clearance_rules(category_uri)
    │                    返回：该品类适用的折扣规则（min/max/rec/tier/urgency）
    │
    └── JSON/Python ──→ 遍历 products.json
                           过滤：days_left ≤ 2 AND NOT in_reduction
                           返回：临期货列表（product_id / name / stock / expiry_date）
```

### 折扣推荐流程的查询路径

```
POST /discount（推荐折扣率）
    │
    ├── TTL/SPARQL ──→ query_clearance_rules(category_uri)
    │                    匹配：tierMin ≤ days_left ≤ tierMax
    │                    返回：tier 名称、minDiscount、maxDiscount、recommendedDiscount
    │
    ├── JSON/Python ──→ 从 products.json 查商品属性
    │                    is_imported / is_organic / is_promoted / arrival_days
    │
    └── Python ───────→ 豁免检查（fallback）
                           规则来自 TTL（ExemptionRule 类型）
                           商品属性来自 JSON
```

### 豁免检查的完整路径

```
check_product_exemption(product_id, is_imported, is_organic, is_promoted, arrival_days)
    │
    ├── Step 1: SPARQL query_exemption_rules() [TTL]
    │            查所有豁免规则类型（目前broken，Python fallback兜底）
    │
    └── Step 2: Python fallback [JSON]
                 if is_imported → ExemptionTypeImported
                 if is_organic → ExemptionTypeOrganic
                 if is_promoted → ExemptionTypeAlreadyPromoted
                 if arrival_days ≤ 7 → ExemptionTypeNewArrival
```

---

## 六、重构方案：query_pending_clearance_skus

### 问题

原实现尝试用 SPARQL 从 TTL 图中查询临期货 SKU 实例，但 TTL 只包含类定义，不包含 ABox 实例数据。products.json 中的 5,000 条商品实例从未加载到 RDFLib 图中，导致查询永远返回 0。

### 修复后的实现

将 `query_pending_clearance_skus()` 改为直接读取 `products.json`，在 Python 层做业务过滤。

**修改位置：** `app/services/sparql_service.py` 或在 `app/services/inventory_service.py`（新建）

**新逻辑：**
```python
def query_pending_clearance_skus(days_threshold: int = 2) -> list[dict]:
    """
    从 products.json 查询临期货商品。
    days_threshold: 剩余天数阈值（默认 ≤ 2 天）
    返回：[{"sku": ..., "name": ..., "qty": ..., "expiry": ..., "days_left": ...}, ...]
    """
    with open(PRODUCTS_FILE) as f:
        products = json.load(f)
    today = date.today()
    result = []
    for p in products:
        expiry = date.fromisoformat(p["expiry_date"])
        days_left = (expiry - today).days
        if days_left <= days_threshold and not p.get("in_reduction"):
            result.append({
                "sku": p["product_id"],
                "name": p["name"],
                "qty": p["stock"],
                "expiry": p["expiry_date"],
                "days_left": days_left,
                "category": p["category"],
            })
    return result
```

---

## 七、重构方案：豁免检查 SPARQL

### 问题

`query_exemption_rules()` 的 SPARQL 查询期望 ExemptionRule 类本身是 `rdfs:subClassOf so:ExemptionType`，但 TTL 中 ExemptionRule 是 `owl:Class`，用 `so:exemptionType` 属性指向 NamedIndividual。结构不匹配导致永远返回 0。

### 修复后的实现

修改 SPARQL 查询，通过属性路径查找豁免规则。

**修改位置：** `app/services/sparql_service.py` → `query_exemption_rules()`

**修复后的 SPARQL：**
```sparql
PREFIX so: <https://store-ontology.example.com/retail#>

SELECT ?rule ?exemptionType ?reason
WHERE {
    ?rule a owl:Class ;
          so:exemptionType ?exemptionType ;
          so:exemptionReason ?reason .
    FILTER(STRSTARTS(STR(?exemptionType), STR(so:)))
}
```

这样无论 ExemptionRule 是不是 ExemptionType 的 subclass，只要它用 `so:exemptionType` 属性指向了豁免类型，就能查到。

---

## 八、状态机统一

### 问题

TTL 状态机（TaskPending / TaskConfirmed / TaskInProgress / TaskCompleted）与 Python 模型（PENDING / CONFIRMED / EXECUTED / REVIEWED / COMPLETED）不一致。

### 修复方案

统一以 Python 模型为准（更符合实际工作流），TTL 中移除冗余的状态定义，或添加缺少的状态 NamedIndividual。

**TTL 侧修改：** 在 WORKTASK-MODULE.ttl 中添加：
```turtle
so:TaskExecuted a owl:NamedIndividual ;
    rdfs:subClassOf so:TaskStatus ;
    rdfs:label "已执行"@zh-CN .

so:TaskReviewed a owl:NamedIndividual ;
    rdfs:subClassOf so:TaskStatus ;
    rdfs:label "已复盘"@zh-CN .
```

---

## 九、文件归属总结

| 文件 | 职责 | ABox/TBox |
|------|------|:---------:|
| modules/module1-worktask/WORKTASK-MODULE.ttl | 类/属性/规则定义 | TBox |
| examples/DEMO-*.ttl | 演示用示例实例 | ABox（仅演示）|
| data/products.json | 商品实例 | ABox |
| data/tasks.json | 任务实例 | ABox |
| data/inventory_events.json | 库存事件 | ABox |
| app/services/sparql_service.py | TBox 查询（SPARQL）| TBox |
| app/services/inventory_service.py | ABox 查询（JSON）| ABox（新建）|
| app/routers/reasoning.py | 折扣推荐（规则来自TTL + 商品来自JSON）| 混合 |

---

## 十、测试验证

修复后验证清单：

- [ ] `query_pending_clearance_skus()` 能从 JSON 返回临期货（524条 days_left ≤ 2）
- [ ] `/agent/scan` 接口能正确触发折扣推荐流程
- [ ] `query_exemption_rules()` 能查到豁免规则（修复 SPARQL 后）
- [ ] 豁免检查能正确识别进口/有机/已促销商品
- [ ] TTL 测试全部通过（50/50）
- [ ] 新增 `inventory_service.py` 的单元测试
