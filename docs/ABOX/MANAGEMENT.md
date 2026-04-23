# ABOX 实例数据管理指南

> 来源：昊晴整理 | 作者：谢文龙团队 | 时间：2026-04-22
> 标签：store-ontology, ABOX, 实例数据, JSON, 数据管理
> 描述：store-ontology 项目 ABOX 实例数据的存储结构、运行时操作、备份与恢复

---

## 一、ABOX 定位

ABOX（Assertion Box）是 store-ontology 项目的 **实例数据层**，存放具体业务对象（商品、任务、库存、员工）的实例数据，与 TBOX 的类/属性定义（`modules/`）相对应。

---

## 二、存储结构

```
store-ontology/
├── data/                        # ABOX 实例数据根目录
│   ├── products.json            # 商品实例
│   └── tasks.json               # 工作任务实例
```

> ⚠️ 注意：`app/data/` 已在 2026-04-22 清理中删除，所有实例数据统一在 `data/` 目录。

---

## 三、数据文件说明

### products.json（商品实例）

```json
{
  "products": [
    {
      "product_id": "P001",
      "name": "嫩豆腐",
      "category": "daily_fresh",
      "stock": 50,
      "expiry_date": "2026-04-23",
      "price": 3.5,
      "cost": 1.8
    },
    ...
  ]
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `product_id` | string | 商品唯一标识 |
| `name` | string | 商品名称 |
| `category` | string | 品类（见 Category 枚举） |
| `stock` | integer | 当前库存数量 |
| `expiry_date` | string (ISO date) | 到期日期 |
| `price` | decimal | 售价 |
| `cost` | decimal | 成本价 |

**Category 枚举值：**

| 值 | 说明 |
|---|---|
| `daily_fresh` | 生鲜 |
| `daily_products` | 日配（牛奶/酸奶） |
| `bakery` | 烘焙 |
| `packaged_goods` | 包装食品/标品 |

### tasks.json（工作任务实例）

```json
{
  "tasks": [
    {
      "task_id": "T001",
      "name": "嫩豆腐临期打折",
      "task_type": "discount",
      "status": "pending",
      "priority": "high",
      "product_id": "P001",
      "deadline": "2026-04-22T18:00:00",
      "assigned_to": "STAFF_001"
    }
  ]
}
```

---

## 四、运行时操作

### 读取数据（后端）

```python
# app/routers/reasoning.py
DATA_DIR = Path(__file__).parent.parent.parent / "data"

def load_products():
    with open(DATA_DIR / "products.json") as f:
        return json.load(f)["products"]

def load_tasks():
    with open(DATA_DIR / "tasks.json") as f:
        return json.load(f)["tasks"]
```

### API 端点

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/reasoning/products` | GET | 获取所有商品列表 |
| `/api/tasks` | GET | 获取所有任务 |
| `/api/tasks` | POST | 创建新任务 |
| `/api/tasks/{task_id}` | PATCH | 更新任务状态 |

### 更新商品（库存扣减示例）

```python
def reduce_stock(product_id: str, quantity: int):
    data = load_products()
    for p in data:
        if p["product_id"] == product_id:
            p["stock"] -= quantity
    with open(DATA_DIR / "products.json", "w") as f:
        json.dump({"products": data}, f, indent=2, ensure_ascii=False)
```

---

## 五、备份与恢复

```bash
# 手动备份
cp data/products.json data/products.json.bak-$(date +%Y%m%d)
cp data/tasks.json data/tasks.json.bak-$(date +%Y%m%d)

# 恢复
cp data/products.json.bak-20260422 data/products.json
```

---

## 六、TBOX / ABOX 边界原则

| 层级 | 存放内容 | 修改频率 |
|---|---|---|
| **TBOX**（`modules/`） | 类/属性/推理规则/OWL 声明 | 低（业务稳定时几乎不变） |
| **ABOX**（`data/`） | 具体商品/任务实例 | 高（每日运营频繁变化） |

---

## 七、扩展实例数据

新增实例文件（如 `inventory.json`）时：
1. 在 `data/` 下创建新文件
2. 在 `app/routers/reasoning.py` 中补充加载逻辑
3. 更新本文档
4. 在 `docs/TBOX/PROJECT_ONTOLOGY_OVERVIEW.md` 的 SPARQL 查询中补充新实体的查询规则
