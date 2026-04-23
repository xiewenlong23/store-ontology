# Runtime Adapters — 运行时适配器

> 来源：昊晴整理 | 作者：谢文龙团队 | 时间：2026-04-22
> 标签：store-ontology, RDFLib, SPARQL, TTL, 推理引擎
> 描述：store-ontology 项目 TTL 本体与后端推理引擎的运行时集成适配说明

---

## 一、适配器架构

```
app/services/
├── sparql_service.py      ← TTL/SPARQL 适配器（查询 TBOX 本体）
├── ttl_llm_reasoning.py   ← TTL + LLM 混合推理引擎
├── llm_service.py          ← LLM 调用服务
├── inventory_service.py    ← ABOX 适配器（读写 JSON 实例）
└── agent_executor.py      ← Agent 执行循环
```

---

## 二、TTL/SPARQL 适配器（sparql_service.py）

### 职责
- 加载 `modules/module1-worktask/WORKTASK-MODULE.ttl` 到 RDFLib Graph
- 执行 SPARQL 查询（折扣规则、豁免规则、任务状态等）
- 返回结构化结果给上层服务

### 加载路径（已修复）

```python
from pathlib import Path
TTL_PATH = Path(__file__).parent.parent.parent / "modules" / "module1-worktask" / "WORKTASK-MODULE.ttl"

def load_ontology() -> Graph:
    g = Graph()
    g.parse(TTL_PATH, format="turtle")
    return g
```

> ⚠️ 路径曾错误指向 `app/data/`（已删除），现已修正为 `modules/`。

### 核心查询

```python
# 折扣规则查询
def query_clearance_rules(category: str) -> list[dict]:
    g = load_ontology()
    query = """
    PREFIX so: <http://store-ontology.example.org/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?rule ?tier ?minDiscount ?maxDiscount ?recommended ?urgency
    WHERE {
        ?rule rdf:type so:ClearanceRule .
        ?rule so:applicableCategory so:Category_%s .
        ?rule so:hasTier ?tier .
        ?rule so:minDiscount ?minDiscount .
        ?rule so:maxDiscount ?maxDiscount .
        ?rule so:recommendedDiscount ?recommended .
        ?tier so:tierUrgency ?urgency .
    }
    """ % category.upper()
    return list(g.query(query))
```

---

## 三、TTL + LLM 混合推理（ttl_llm_reasoning.py）

### 职责
- 接收自然语言查询
- 查询 TTL/SPARQL 获取业务规则
- 将规则注入 LLM Prompt
- 返回自然语言推理结果

### 推理链路

```
用户查询（自然语言）
  → intent_classifier（意图分类）
  → ttl_llm_reasoning
      → sparql_service（查 TTL 规则）
      → llm_service（注入规则 + 生成结论）
  → agent_executor（结构化返回）
```

### Prompt 增强结构

```
System: 你是一个零售门店运营专家...
Context: 当前临期规则如下...
  - 日配品类：T1(0-1天)→20%折扣, T2(2-3天)→40%折扣
  - 豁免商品：进口食品、有机商品不可打折
Query: 嫩豆腐还有1天到期，推荐什么折扣？
Answer: 根据规则，嫩豆腐属于日配品类，剩余1天属于T1层级，建议20%折扣。
```

---

## 四、LLM Service（llm_service.py）

### 职责
- 封装 MiniMax API 调用
- 管理对话上下文（messages 列表）
- 处理流式/非流式响应

### 调用方式

```python
def chat(messages: list[dict], stream: bool = False) -> str:
    response = client.chat.completions.create(
        model="MiniMax-M2.7-flash",
        messages=messages,
        stream=stream,
        temperature=0.7
    )
    return response.choices[0].message.content
```

---

## 五、ABOX 适配器（inventory_service.py）

### 职责
- 读写 `data/products.json`（商品实例）
- 读写 `data/tasks.json`（任务实例）
- 不走 SPARQL，直接 JSON 文件操作

### 路径

```python
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
TASKS_FILE = DATA_DIR / "tasks.json"
```

---

## 六、Agent 执行循环（agent_executor.py）

### 当前状态：单步（One-Shot）

```python
def execute(user_input: str) -> dict:
    messages = build_messages(user_input)
    response = llm_service.chat(messages)
    parsed = parse_tool_calls(response)
    results = [registry.dispatch(t, a) for t, a in parsed]
    return format_response(results)
```

### 迭代方向：多步循环（Iteration 8）

```python
async def execute_loop(user_input: str, max_steps: int = 10) -> dict:
    messages = build_messages(user_input)
    steps = []
    for _ in range(max_steps):
        response = llm_service.chat(messages)
        parsed = parse_tool_calls(response)
        if not parsed.get("continue"):
            break
        result = registry.dispatch(parsed["tool"], parsed["args"])
        messages.append({"role": "tool", "content": str(result)})
        steps.append(parsed["tool"])
    return format_response(steps)
```

---

## 七、System Prompt 约束（已生效）

`agent_executor.py` 的 SYSTEM_PROMPT 已追加数据展示原则：

```
数据展示原则：
- ASCII 图表仅展示汇总结构（如柱状图），不要在图表下方列出详细商品清单
- tool_result 中的 products/SKUs 数据仅用于组件渲染，前端 ProductList 会自动展示
- 你的 response 文本只能包含：分析结论 + 图表 + 行动建议，禁止复述具体商品数据
```

---

## 八、验证命令

```bash
# TTL 语法验证
rapper -i turtle -o ntriples file:///mnt/d/ObsidianVault/store-ontology/modules/module1-worktask/WORKTASK-MODULE.ttl

# 后端健康检查
curl http://localhost:8000/api/health

# 前端健康检查
curl http://localhost:3000

# 前端 API 代理验证
curl http://localhost:3000/api/reasoning/products
```
