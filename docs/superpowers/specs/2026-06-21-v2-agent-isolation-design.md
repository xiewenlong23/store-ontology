# v2-agent 隔离：per-workspace agent 实例设计

> **状态**：设计待确认
> **日期**：2026-06-21
> **性质**：架构级改造——agent 从全局单例 → per-workspace 实例。让工具/skill/本体 prompt 按 workspace 隔离。
> **关联**：[`roadmap.md`](../design/roadmap.md) §9、[`00-architecture.md`](../design/00-architecture.md) §3.3

---

## 0. 问题陈述

v2-tenant 动态（数据层）完成后发现更深的 gap：`main.py` 构建 agent 时，工具/skill/本体 prompt **全局聚合所有 pack**：
- `_aggregate_pack_tools()`：`for pack in all_packs()` → 所有行业包工具都注入 agent
- `_aggregate_skill_paths()`：所有行业包 skill 都挂载
- `_build_combined_prompt()`：所有行业包实体/关系/Action 合并进系统提示

实测：agent 同时含 `query_near_expiry`(retail) + `query_repair_tickets`(equipment_repair)，本体 prompt 同时含 `NearExpiryProduct` + `RepairTicket`。`bootstrap_workspace()` 返回的 per-workspace `WorkspaceAgentInstance` 只被 dashboard API 消费，**agent 本身没消费**。

**影响**：不同 workspace 的请求共用同一个 agent，LLM 看到所有 pack 的工具/skill/本体。多 workspace 共存时互相干扰（LLM 可调到不属于当前 workspace pack 的工具）。

---

## 1. 方案：per-workspace agent 实例 + 网关路由

### 决策（用户确认）
- **隔离粒度**：per-workspace（每个 workspace 一个独立 agent 实例）
- **跨 pack**：不支持（一个 workspace 一个 source_pack）
- **jjy workspace**：真实存在的第二个 workspace（当前待创建）

### 架构
```
浏览器（X-Workspace header）
    → AG-UI 网关 endpoint（POST /api/copilotkit）
        → 解析 workspace_name（从 header）
        → get_or_build_workspace_agent(workspace_name)  ← per-workspace 缓存
            → 按 workspace 的 source_pack 构建 graph：
                - 只含该 pack 的工具（_aggregate_pack_tools 改为按指定 pack）
                - 只含该 pack 的 skill
                - 只含该 pack 的本体 prompt
            → 缓存到 _workspace_agents[workspace_name]
        → agent.clone()（per-request 状态隔离）
        → agent.run(input_data) → SSE 流式响应
```

### 为什么不用 add_langgraph_fastapi_endpoint
它内部 `agent.clone()` 每请求 clone，但 **graph 固定**（`self.graph = graph` 构造时绑定）。要 per-workspace 不同 graph，需自己写 endpoint，per-request 按 workspace 选 agent（复用 EventEncoder + LangGraphAgent.run）。

---

## 2. 实现要点

### 2.1 per-workspace graph 构建

新增 `build_workspace_graph(workspace_name) -> CompiledStateGraph`：
- 从 `bootstrap_workspace(workspace_name)` 取 `WorkspaceAgentInstance`（已有 registry/repository/executor）
- 取该 workspace 的 `source_pack`
- **工具**：只聚合该 pack 的工具（内核 8 个 + 该 pack 的 `process.tools_module`）
- **skill**：只挂载该 pack 的 skill 路径
- **prompt**：只构建该 pack 的本体提示
- `create_deep_agent(model, tools=..., system_prompt=..., skills=..., ...)`

现有 `_aggregate_pack_tools`/`_build_combined_prompt`/`_aggregate_skill_paths` 从"遍历 all_packs()"改为"接受指定 pack 参数"。

### 2.2 per-workspace agent 缓存

```python
_workspace_agents: Dict[str, LangGraphAgent] = {}

def get_or_build_workspace_agent(workspace_name: str) -> LangGraphAgent:
    if workspace_name not in _workspace_agents:
        graph = build_workspace_graph(workspace_name)
        _workspace_agents[workspace_name] = LangGraphAgent(
            name=workspace_name, graph=graph)
    return _workspace_agents[workspace_name]
```

graph 按 workspace 缓存（不每请求重建，高效）。workspace 数稳定（当前 2 个），内存可控。

### 2.3 替换 endpoint

```python
from ag_ui_langgraph import LangGraphAgent
from ag_ui.core import EventEncoder  # 复用 SSE 编码

@app.post("/api/copilotkit")
async def copilotkit_endpoint(input_data: RunAgentInput, request: Request):
    workspace = _resolve_workspace_name(request)  # 从 X-Workspace header
    agent = get_or_build_workspace_agent(workspace)
    request_agent = agent.clone()  # per-request 状态隔离
    accept = request.headers.get("accept")
    encoder = EventEncoder(accept=accept)

    async def event_generator():
        async for event in request_agent.run(input_data):
            yield encoder.encode(event)
    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())
```

> 注：需确认 `EventEncoder` 的 import 路径（ag_ui_langgraph 或 ag_ui.core）。实现时核实。

### 2.4 创建 jjy workspace（验证用）

建 `workspace/jjy/config.yaml`：
```yaml
workspace_name: jjy
name: JJY 客户
source_pack: equipment_repair   # 待用户确认；用 equipment_repair 验证工具/本体与 retail 完全不同
storage:
  type: json_files
  data_dir: workspace/equipment_repair/data
enabled_domains: [maintenance]
enabled_processes: [repair]
org_tree:
  - { id: brand_jjy, parent: null }
```

> **待用户确认**：jjy 的 source_pack。默认设 equipment_repair（验证最有力：customer_default→retail 工具，jjy→equipment_repair 工具，完全不同）。若 jjy 应是 retail 客户，改为 retail（验证数据隔离 + 独立实例）。

---

## 3. 目标 / 范围 / 成功标准

### 3.1 目标
不同 workspace 的请求路由到不同 agent 实例，工具/skill/本体 prompt 完全按 workspace 的 source_pack 隔离。

### 3.2 范围 — In
1. `build_workspace_graph`：按 workspace 的 source_pack 构建 graph（工具/skill/prompt 隔离）
2. per-workspace agent 缓存
3. 替换 endpoint（网关路由）
4. 创建 jjy workspace（验证）
5. 现有 `_aggregate_*` 函数改为接受指定 pack

### 3.3 范围 — Out
- ❌ 不支持跨 pack workspace（单 source_pack）
- ❌ 不改 pack 本身（retail/equipment_repair 定义不动）
- ❌ 不改数据层（Repository 隔离已实现）
- ❌ 不做 workspace 动态创建 UI（config.yaml 手动建）

### 3.4 成功标准
1. customer_default 请求 → agent 只含 retail 工具/本体（无 equipment_repair）
2. jjy 请求 → agent 只含 equipment_repair 工具/本体（无 retail）
3. 两个 workspace 的 LLM schema/prompt 互不干扰
4. 现有对话流程（查询/出清/确认）在 customer_default 不回归
5. pytest 全套通过
6. endpoint SSE 流式响应正常（浏览器对话不崩）

---

## 4. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 替换 endpoint 的 SSE 编码不对（EventEncoder 用法） | 参考 `add_langgraph_fastapi_endpoint` 源码逐行复刻；用 playwright 验证流式响应 |
| per-workspace graph 构建慢（首次请求延迟） | 缓存（`_workspace_agents`）；可在 startup 预热已知 workspace |
| workspace graph 缓存失效（config 改后不更新） | 提供 invalidate 接口；MVP 重启生效（config 变更低频） |
| 现有测试依赖全局 `deep_agent_graph` | 改为用 `get_or_build_workspace_agent("customer_default")` |
| deepagents create_deep_agent 多次调用的副作用（MemorySaver 共享？） | 每个 workspace graph 独立 MemorySaver（会话隔离） |

---

## 5. 验证

1. **单元测试**：`build_workspace_graph("customer_default")` 的 tools 只含 retail 工具；`build_workspace_graph("jjy")` 只含 equipment_repair 工具
2. **端到端（playwright）**：
   - customer_default 对话 → AI 只知 retail 实体/工具
   - jjy 对话 → AI 只知 equipment_repair 实体/工具
3. **回归**：现有 pytest 全套通过；customer_default 对话流程正常

---

## 附录：待用户确认

1. **jjy 的 source_pack**：equipment_repair（默认，验证工具隔离）还是 retail（验证数据+实例隔离）？
2. **jjy 是否需要独立数据**：用 equipment_repair 的现有数据（共享）还是独立数据目录？
