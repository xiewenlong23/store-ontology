# ABox/TBox 数据分层架构设计

> 更新时间：2026-04-22
> 背景：store-ontology 项目 TBOX/ABOX 分离架构，适配门店大脑 AI 原生应用

---

## 一、核心原则

**TBox（业务语义层）** — 存"规则是什么"
- 类定义、属性声明、约束规则
- 变化频率低，版本管理严格
- 格式：TTL/OWL 文件，只读
- 工具：Protege、WebVOWL、rapper

**ABox（业务实例层）** — 存"具体有哪些"
- 商品、任务、库存事件、员工等实例数据
- 变化频率高，按业务需要读写
- 格式：JSON 文件（`data/` 目录）

**禁止事项：不要用 SPARQL 查 ABox 数据（JSON 文件）。**

---

## 二、存储布局

```
store-ontology/
├── modules/                           # TBOX — 本体定义（只读）
│   └── module1-worktask/
│       └── WORKTASK-MODULE.ttl        # 临期打折本体（1256 triples）

├── data/                              # ABOX — 实例数据（运行时读写）
│   ├── products.json                  # 商品实例
│   └── tasks.json                     # 任务实例

└── docs/
    ├── TBOX/                        # TBOX — 本体设计文档
    ├── ABOX/                        # ABOX — 实例数据文档
    │   └── MANAGEMENT.md            # ABOX 管理指南（新建）
    ├── OPERATIONS/                  # 运维文档
    ├── AGENT/                       # Agent 系统文档
    └── INFRASTRUCTURE/               # 工程基础设施
```

---

## 三、TBox / SPARQL 负责什么

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
| 临期货商品列表（scan 入口）| ✅ | 商品实例在 `data/products.json` |
| 具体商品属性（category / stock / expiry_date）| ✅ | 实例属性在 JSON |
| 豁免检查（is_imported / is_organic / is_promoted）| ✅ | Python fallback，属性来自 JSON |
| 任务 CRUD | ✅ | `data/tasks.json` 文件读写 |
| Dashboard 左侧数据 | ✅ | `/api/reasoning/products` |

---

## 五、查询路径设计

### 临期出清流程的查询路径

```
/agent/scan（扫描临期货）
    │
    ├── TTL/SPARQL ──→ query_clearance_rules(category_uri)
    │                    返回：该品类适用的折扣规则（min/max/rec/tier/urgency）
    │
    └── JSON/Python ──→ 遍历 data/products.json
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
    ├── JSON/Python ──→ 从 data/products.json 查商品属性
    │                    category / stock / expiry_date
    │
    └── Python ───────→ 豁免检查
                           规则来自 TTL（ExemptionRule 类型）
                           商品属性来自 JSON
```

---

## 六、文件归属总结

| 文件 | 职责 | TBox/ABox |
|------|------|:---------:|
| `modules/module1-worktask/WORKTASK-MODULE.ttl` | 类/属性/规则定义 | **TBox** |
| `data/products.json` | 商品实例 | **ABox** |
| `data/tasks.json` | 任务实例 | **ABox** |
| `app/services/sparql_service.py` | TBox 查询（SPARQL）| TBox |
| `app/services/inventory_service.py` | ABox 查询（JSON）| ABox |
| `app/routers/reasoning.py` | 折扣推荐（规则来自TTL + 商品来自JSON）| 混合 |

---

## 七、验证清单

- [x] `query_pending_clearance_skus()` 能从 `data/products.json` 返回临期货
- [x] `/api/reasoning/products` 接口能正确返回商品列表
- [x] `query_exemption_rules()` 能查到豁免规则
- [x] TTL 测试全部通过（1256 triples）
- [x] Dashboard 左侧显示正确数据

---

## 八、扩展说明

新增本体模块（如 `module2-inventory/`）：
1. 在 `modules/` 下创建新目录
2. 在 `sparql_service.py` 中合并加载
3. 新增 `docs/TBOX/PROJECT_ONTOLOGY_OVERVIEW.md` 中的模块说明
4. 新增 `docs/ABOX/MANAGEMENT.md` 中的实例数据说明
