# v2-agent 隔离 + workspace 自洽设计

> **状态**：设计待确认
> **日期**：2026-06-21
> **性质**：架构级改造。① agent 从全局单例 → per-workspace 实例隔离；② workspace 目录自洽化（每个工作目录独立定义本体/数据/skill，平级隔离）。
> **关联**：[`roadmap.md`](../design/roadmap.md) §9、[`00-architecture.md`](../design/00-architecture.md) §3.3

---

## 0. 问题陈述

两个相互关联的 gap：

### gap 1：agent 全局聚合（v2-agent 隔离）
`main.py` 构建 agent 时，`_aggregate_pack_tools()`/`_aggregate_skill_paths()`/`_build_combined_prompt()` 用 `all_packs()` 聚合**所有**工作目录的工具/skill/本体。实测 agent 同时含 `query_near_expiry`(retail) + `query_repair_tickets`(equipment_repair)，本体 prompt 同时含两套实体。不同 workspace 的请求共用一个 agent，工具/skill/本体未隔离。

### gap 2：workspace 目录角色混乱
当前结构：
- `workspace/retail/`、`workspace/equipment_repair/` = 自洽工作目录（有 pack.py + ontology + data + skills）
- `workspace/customer_default/` = **薄壳**（只有 config.yaml，`source_pack: retail` + `data_dir: workspace/retail/data`，无自己的本体/数据/skill）

**正确的架构**：workspace 下是 **N 个平级、独立、自洽的工作目录**。每个工作目录完整定义自己的本体语义/数据/skill，互不引用。工作目录分两类：
- **行业工作目录**（公司开发，如 retail）：定义某行业的本体/工具/skill，可作客户初始化的拷贝源
- **客户工作目录**（如 jjy、customerA）：某客户的定制实例，从行业目录拷贝修改或从 0 自定义

当前 customer_default 这个薄壳违背了"自洽"原则——它复用 retail 的数据和本体，没有真正隔离。

### 用户的明确要求
- `customer_default` → 改名 `jjy`（客户 jjy 的独立工作目录）
- `equipment_repair` → 改名 `customerA`（客户A 的独立工作目录）
- jjy/customerA 本体定义**后续做**，本次只确保**架构隔离**（jjy 暂从 retail 拷贝本体/数据让它自洽能跑）
- 工作目录初始化支持"从行业目录拷贝修改"或"从 0 自定义"

---

## 1. 目标状态

```
workspace/
├── retail/          # 零售行业工作目录（公司开发，自洽：pack.py + ontology/ + data/ + skills/）
├── jjy/             # 客户 jjy 工作目录（原 customer_default 改名 + 自洽化）
│                     #   本次：从 retail 拷贝 pack.py/ontology/data/skills，改 pack.name=jjy
│                     #   后续：客户定义自己的本体语义
└── customerA/       # 客户A 工作目录（原 equipment_repair 改名，内容不变，自洽）
```

每个工作目录经 `bootstrap()` 发现 `pack.py` 注册为独立 pack。**agent 按 pack（=工作目录）隔离**：不同 workspace 的请求路由到只含该工作目录工具/skill/本体的 agent 实例。

---

## 2. 方案：per-workspace agent 实例 + 工作目录自洽化

### 2.1 工作目录自洽化（gap 2）

**改名 + 自洽化 jjy**：
- `workspace/customer_default/` → `workspace/jjy/`
- 从 `workspace/retail/` 拷贝 `pack.py`/`ontology/`/`data/`/`skills/` 到 `jjy/`
- 改 `jjy/pack.py` 的 pack name 为 `jjy`、display_name 为"客户 jjy"
- 删除原 config.yaml 的 source_pack 依赖（jjy 自洽，不再指向 retail）
- 数据文件的 `workspace_name` 字段值改 `customer_default` → `jjy`

**改名 customerA**：
- `workspace/equipment_repair/` → `workspace/customerA/`
- 改 `customerA/pack.py` 的 pack name 为 `customerA`
- 内容（本体/数据/skill）不变

**bootstrap 机制不变**：`bootstrap()` 扫描 `workspace/*/pack.py`，jjy/customerA/retail 各自被注册为独立 pack。

### 2.2 per-workspace agent 实例（gap 1）

新增 `build_workspace_graph(pack_name) -> CompiledStateGraph`：
- 只构建**指定 pack** 的工具/skill/本体 prompt（不再 `all_packs()` 聚合）
- 现有 `_aggregate_pack_tools`/`_build_combined_prompt`/`_aggregate_skill_paths` 改为接受单个 pack 参数

per-pack agent 缓存：
```python
_pack_agents: Dict[str, LangGraphAgent] = {}
def get_or_build_pack_agent(pack_name: str) -> LangGraphAgent:
    if pack_name not in _pack_agents:
        graph = build_workspace_graph(pack_name)
        _pack_agents[pack_name] = LangGraphAgent(name=pack_name, graph=graph)
    return _pack_agents[pack_name]
```

### 2.3 替换 endpoint（网关路由）

不用 `add_langgraph_fastapi_endpoint`（它 graph 固定）。自写 endpoint：
```python
@app.post("/api/copilotkit")
async def copilotkit_endpoint(input_data: RunAgentInput, request: Request):
    # 从 X-Workspace header 解析 workspace → 取对应 pack → 路由到该 pack 的 agent
    workspace_name = _resolve_workspace_name(request)
    cfg = get_workspace(workspace_name)
    pack_name = cfg.source_pack if cfg else "retail"  # 或 workspace 本身就是 pack
    agent = get_or_build_pack_agent(pack_name)
    request_agent = agent.clone()
    encoder = EventEncoder(accept=request.headers.get("accept"))
    async def gen():
        async for ev in request_agent.run(input_data): yield encoder.encode(ev)
    return StreamingResponse(gen(), media_type=encoder.get_content_type())
```

### 2.4 workspace → pack 映射

工作目录自洽后，workspace 名 = pack 名（jjy 工作目录的 pack name=jjy）。endpoint 从 `X-Workspace` header 取 workspace_name，直接作为 pack_name 查 agent。

> **兜底**：无 X-Workspace 或未知 workspace → 路由到默认 pack（jjy 或首个 pack）。

---

## 3. customer_default 引用处理（101 处）

`customer_default` 在代码里有两种用途：
1. **兜底常量**：`TenantContext.default()`、`shared._workspace_name_from_ctx()` 的 `or "customer_default"`、config 默认值——表示"未知请求的默认 workspace"。
2. **测试 fixture**：测试里硬编码 `workspace_name="customer_default"`。

**处理**：
- 兜底常量改为 `jjy`（默认 workspace 现在是 jjy）
- 测试 fixture 改 `customer_default` → `jjy`
- 数据文件 `workspace_name` 字段 → `jjy`

---

## 4. 目标 / 范围 / 成功标准

### 4.1 目标
① 工作目录自洽化（customer_default→jjy 自洽、equipment_repair→customerA 改名）；② agent per-workspace 实例隔离。

### 4.2 范围 — In
1. workspace 改名 + jjy 自洽化（拷贝 retail 内容）
2. `_aggregate_*` 改为按指定 pack 构建
3. per-pack agent 缓存 + 自写 endpoint 网关路由
4. customer_default 101 处引用 → jjy
5. 数据文件 workspace_name → jjy

### 4.3 范围 — Out
- ❌ 不定义 jjy/customerA 的业务本体（后续做；jjy 暂用 retail 拷贝）
- ❌ 不改 pack 内部定义（retail 本体/工具不动，只是被 jjy 拷贝）
- ❌ 不改数据层隔离机制（Repository 已实现）
- ❌ 不做 workspace 初始化 UI（手动建/拷贝）

### 4.4 成功标准
1. `workspace/` 下是 retail / jjy / customerA 三个自洽工作目录
2. jjy 请求 → agent 只含 jjy(retail 拷贝)的工具/本体；customerA 请求 → 只含 customerA(equipment_repair)工具/本体
3. 工作目录互相隔离（jjy 看不到 customerA 的工具/本体/skill）
4. 代码无 `customer_default` 残留（除非历史兼容注释）
5. pytest 全套通过
6. endpoint SSE 流式正常，浏览器对话不崩

---

## 5. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 自写 endpoint 的 SSE 编码错误 | 逐行复刻 add_langgraph_fastapi_endpoint 源码；playwright 验证流式 |
| jjy 从 retail 拷贝后，pack name/路径冲突 | 拷贝后改 pack.name=jjy、data_dir 指向 jjy/data |
| 101 处 customer_default 改名漏改 | grep 兜底；pytest 全套验证 |
| per-pack agent 首次构建延迟 | startup 预热已知 pack；或首次请求懒加载（可接受） |
| MemorySaver 会话隔离 | 每个 pack graph 独立 MemorySaver |
| retail 同时是"行业模板"又是 pack——jjy 拷贝后 retail 还该被注册吗 | retail 保留注册（它是有效行业目录，也能独立跑）；jjy 是它的拷贝实例 |

---

## 6. 验证

1. **单元**：`build_workspace_graph("jjy")` 的 tools 只含 retail 工具集（因 jjy 拷贝自 retail）；`build_workspace_graph("customerA")` 只含 equipment_repair 工具集
2. **端到端（playwright）**：
   - jjy 对话 → AI 只知 jjy 的实体（retail 拷贝来的）
   - customerA 对话 → AI 只知 customerA 的实体（维修）
   - 切换 workspace（X-Workspace header）→ agent 实例切换
3. **回归**：pytest 全套通过；jjy 对话流程正常（查询/出清/确认）

---

## 附录：决策记录

- **隔离粒度**：per-workspace（用户确认）。工作目录 = pack，workspace 名 = pack 名。
- **跨 pack**：不支持（一个工作目录一个 pack）。
- **jjy 本体**：后续定义（本次从 retail 拷贝占位）。
- **兜底 workspace**：jjy（原 customer_default 角色）。
