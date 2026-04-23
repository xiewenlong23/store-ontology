# Agent System Improvements — 门店大脑 Agent

> 更新时间：2026-04-22
> 背景：store-ontology Agent 执行器的实际改进记录，与项目当前状态同步

---

## 一、当前 Agent 架构

### 执行链路

```
用户输入（自然语言）
  → ChatAssistant.jsx（前端）
  → POST /api/agent/chat（后端路由）
  → agent_executor.py（Agent 执行器）
  → intent_classifier（意图分类）
  → ttl_llm_reasoning.py（TTL + LLM 混合推理）
  → sparql_service.py（SPARQL 查询）
  → llm_service.py（MiniMax API 调用）
  → 前端渲染（Chart / ProductList）
```

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| Agent 执行器 | `app/services/agent_executor.py` | 对话循环、工具调用、响应格式化 |
| 意图分类 | `app/services/intent_classifier.py` | 分类用户意图（查临期/打折/任务等）|
| TTL+LLM 推理 | `app/services/ttl_llm_reasoning.py` | 查询 TTL 规则 + 注入 LLM Prompt |
| SPARQL 服务 | `app/services/sparql_service.py` | 本体图查询 |
| LLM 服务 | `app/services/llm_service.py` | MiniMax API 封装 |

---

## 二、已应用的改进

### 1. System Prompt 数据展示约束（2026-04-22）

**问题**：LLM 在 response 文本中嵌入完整产品数据，导致前端柱状图下方出现重复产品行（与 `<ProductList>` 组件双重渲染）。

**修复**：在 `agent_executor.py` 的 SYSTEM_PROMPT 中追加：

```
数据展示原则：
- ASCII 图表仅展示汇总结构（如柱状图），不要在图表下方列出详细商品清单
- tool_result 中的 products/SKUs 数据仅用于组件渲染，前端 ProductList 会自动展示
- 你的 response 文本只能包含：分析结论 + 图表 + 行动建议，禁止复述具体商品数据
```

**效果**：柱状图场景下，response 文本只输出图表结构，产品详情由前端 `<ProductList>` 组件独立渲染。

---

### 2. 前端双重渲染兜底过滤（2026-04-22）

**位置**：`frontend/src/components/ChatAssistant.jsx` 第 140-160 行

**逻辑**：当 `tool_result.products` 存在时，用正则过滤掉 `品类:`/`库存:`/`到期:` 格式的产品行，避免与 `<ProductList>` 重复渲染。

```javascript
// 产品行过滤正则
const productLinePattern = /^[^\n]*\n品类:[^\n]+\n库存:[^\n]+\n到期:[^\n]+$/gm;
if (products && products.length > 0) {
  response = response.replace(productLinePattern, '');
}
```

---

### 3. Dashboard 数据路径修复（2026-04-22）

**问题**：`app/routers/reasoning.py` 中 `DATA_DIR` 指向已删除的 `app/data/`，导致 Dashboard 左侧无数据。

**修复**：`DATA_DIR = parent.parent.parent / "data"`（指向根目录 `data/`）

**影响的文件**（同步修复）：
- `app/routers/reasoning.py`
- `app/routers/tasks.py`
- `app/services/pos_simulator.py`

---

## 三、Agent 执行模式演进

### 当前：One-Shot（单步）

```python
def execute(user_input: str) -> dict:
    messages = build_messages(user_input)
    response = llm_service.chat(messages)
    parsed = parse_tool_calls(response)
    results = [registry.dispatch(t, a) for t, a in parsed]
    return format_response(results)
```

### 目标：Multi-Step Loop（多步循环，Iteration 8）

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

## 四、迭代路线图

| 迭代 | 方向 | 状态 |
|------|------|------|
| 0 | 基础框架 | ✅ |
| 1 | 数据层（TTL/SPARQL + JSON）| ✅ |
| 2 | 因子层（本体建模）| ✅ |
| 3 | 策略优化（折扣规则）| ✅ |
| 4 | 回测增强 | ✅ |
| 5 | 交易层 | 进行中 |
| 6 | Agent 单步执行 | ✅ |
| 7 | System Prompt 约束 | ✅ |
| 8 | **Agent 多步循环** | 待实现 |

---

## 五、已知限制与改进方向

| 限制 | 当前状态 | 改进方向 |
|------|---------|---------|
| One-Shot 执行 | 单步工具调用 | 多步循环推理 |
| MiniMax API 依赖 | 直接调用 | RAG + 本体 Schema 增强 |
| 静态 JSON 数据 | 文件轮询 | 事件驱动实时更新 |
| RDFLib 内存加载 | 全量加载 | GraphDB 分片 |
| 豁免规则查询 | Python fallback | SPARQL 直接查询 |
