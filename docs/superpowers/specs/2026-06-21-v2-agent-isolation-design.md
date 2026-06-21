# workspace 自洽 + agent 隔离设计（去 IndustryPack）

> **状态**：设计待确认
> **日期**：2026-06-21
> **性质**：架构重构。去 IndustryPack 中间层；工作目录自洽化 + 改名；agent per-workspace 实例隔离；重写 manual。
> **关联**：[`roadmap.md`](../design/roadmap.md) §9、[`00-architecture.md`](../design/00-architecture.md) §3

---

## 0. 核心架构决策

**去掉 `IndustryPack` 这一层。** 每个工作目录直接就是一组 `CapabilityDomain` + `ValueChainProcess` 的扁平集合，无需被 IndustryPack 包装。retail 不是"行业包"，只是"一个示例工作目录"。

### 新模型
```
workspace/<工作目录>/  ← 工作目录 = 能力域 + 价值链流程的扁平集合（无 pack 包装）
├── workspace.py       ← 声明本目录的 domains[] + processes[]（取代 pack.py）
├── ontology/domains/  ← 能力域本体
├── data/              ← 数据
└── skills/            ← skill
```

工作目录三类角色（结构相同，用途不同）：
- **行业示例目录**（公司开发，如 retail）：可作客户初始化的拷贝源
- **客户目录**（如 jjy、customerA）：客户定制实例，从行业目录拷贝修改或从 0 自定义

### 四个工作包（一个 spec，递进实施）
1. **WP1 去 IndustryPack**：代码重构，pack.py → workspace.py，去 IndustryPack 类
2. **WP2 工作目录改名 + 自洽化**：customer_default→jjy、equipment_repair→customerA
3. **WP3 agent per-workspace 隔离**：每个工作目录独立 agent 实例
4. **WP4 重写 manual**：去掉 pack 模型，对齐新结构

---

## WP1：去 IndustryPack（代码重构）

### 目标
移除 `IndustryPack` 类及其注册表，工作目录直接声明 domains + processes。

### 改动

**`agent/engine/pack.py` 重构**：
- 删除 `IndustryPack` 类、`_packs` 注册表、`register_pack`/`get_pack`/`all_packs`/`clear_packs`
- 保留 `CapabilityDomain`、`ValueChainProcess`（这俩仍需要）
- `pack_to_registry(pack, ...)` 改为 `domains_to_registry(domains, processes, data_dir)`（入参从 pack 变成显式的 domains+processes 列表）
- 新增工作目录注册表：`_workspaces: Dict[str, WorkspaceDef]`，`WorkspaceDef = {name, display_name, domains, processes, data_dir}`（取代 IndustryPack 的容器职责）

**`agent/engine/bootstrap.py`**：
- 扫描 `workspace/*/workspace.py`（文件名 pack.py → workspace.py）
- import 时触发工作目录自注册

**`workspace/<目录>/workspace.py`（取代 pack.py）**：
```python
# workspace/retail/workspace.py
from engine.pack import CapabilityDomain, ValueChainProcess, register_workspace_dir

MARKETING = CapabilityDomain(...)
CLEARANCE = ValueChainProcess(...)

register_workspace_dir(
    name="retail", display_name="零售（示例）",
    domains=[MARKETING, ORGANIZATION, FINANCE],
    processes=[CLEARANCE],
    data_dir=os.path.join(_BASE, "data"))
```

**`main.py` 的 `_aggregate_pack_tools`/`_aggregate_skill_paths`/`_build_combined_prompt`**：
- 从 `all_packs()` 改为 `all_workspace_dirs()`（或保留函数名但内部改）
- WP3 会进一步改为按指定工作目录构建（per-workspace agent）

**`workspace_bootstrap.py`**：
- `get_pack(cfg.source_pack)` + `pack_to_registry` → `get_workspace_dir(name)` + `domains_to_registry`
- source_pack 概念随 WP2 自洽化消失（工作目录名即标识）

### 验证
- pytest 全套通过（测试改 import + 调用点）
- `grep -rn 'IndustryPack\|all_packs\|register_pack\|get_pack' agent --include='*.py'` 零残留

---

## WP2：工作目录改名 + 自洽化

### 目标
- `workspace/customer_default/` → `workspace/jjy/`（客户 jjy 独立工作目录，自洽化）
- `workspace/equipment_repair/` → `workspace/customerA/`（客户A 工作目录）

### 改动

**jjy 自洽化**（原 customer_default 是薄壳，只有 config.yaml）：
- 从 `workspace/retail/` 拷贝 `ontology/`、`data/`、`skills/` 到 `workspace/jjy/`
- 建 `workspace/jjy/workspace.py`（声明 domains+processes，name="jjy"）
- 数据文件 `workspace_name` 字段 `customer_default` → `jjy`
- 删除原 config.yaml 的 source_pack 依赖（jjy 自洽）

**customerA 改名**：
- `workspace/equipment_repair/` → `workspace/customerA/`
- `workspace/customerA/workspace.py` 的 name 改 `customerA`
- 内容（本体/数据/skill）不变
- 代码 import 路径 `workspace.equipment_repair.*` → `workspace.customerA.*`

**customer_default 引用处理（101 处）**：
- 兜底常量（tenant.py/shared.py/main.py 的 `or "customer_default"`）→ `"jjy"`
- `TenantContext.default()` → 返回 `workspace_name="jjy"`
- 测试 fixture → `customer_default` 改 `jjy`
- 数据文件 workspace_name → `jjy`

### 验证
- `grep -rn 'customer_default' agent workspace --include='*.py' --include='*.yaml' --include='*.json'` 零残留（除历史注释）
- pytest 全套通过

---

## WP3：agent per-workspace 隔离

### 目标
不同工作目录的请求路由到不同 agent 实例，工具/skill/本体只含该工作目录的内容。

### 改动

**新增 `build_workspace_graph(ws_name) -> CompiledStateGraph`**：
- 从 `get_workspace_dir(ws_name)` 取 domains+processes
- 工具：内核 8 个 + 该工作目录的 processes 的 tools_module
- skill：只该工作目录的 skills_dir
- prompt：只该工作目录的本体（`domains_to_registry` → `build_system_prompt`）
- `create_deep_agent(...)`

**per-workspace agent 缓存**：
```python
_ws_agents: Dict[str, LangGraphAgent] = {}
def get_or_build_ws_agent(ws_name) -> LangGraphAgent:
    if ws_name not in _ws_agents:
        _ws_agents[ws_name] = LangGraphAgent(name=ws_name, graph=build_workspace_graph(ws_name))
    return _ws_agents[ws_name]
```

**替换 endpoint（网关路由）**：
- 不用 `add_langgraph_fastapi_endpoint`（graph 固定）
- 自写 endpoint：per-request 从 X-Workspace 取 ws_name → `get_or_build_ws_agent` → clone → run
- 复用 EventEncoder（逐行参考 add_langgraph_fastapi_endpoint 源码）

**删全局 `deep_agent_graph` 单例**（main.py:223）+ `add_langgraph_fastapi_endpoint` 绑定。

### 验证
- 单元：`build_workspace_graph("jjy")` 只含 jjy(retail拷贝)工具；`build_workspace_graph("customerA")` 只含 customerA(维修)工具
- 端到端（playwright）：jjy 对话只见零售实体；customerA 对话只见维修实体
- pytest 全套通过；SSE 流式正常

---

## WP4：重写 manual

### 目标
当前 manual（4 文档 + 8 模板）全基于 IndustryPack 模型，过时。重写为 workspace 自洽模型。

### 改动
- `manual/00-overview.md`：kernel/工作目录边界表（去 IndustryPack）
- `manual/01-onboarding.md`：新建工作目录流程（建 workspace.py + domains + processes，不再建 pack.py）
- `manual/02-templates.md`：占位符填法（workspace.py 模板）
- `manual/03-worked-example-*.md`：用 customerA（原 equipment_repair）作 worked example
- `templates/`：`pack.py.template` → `workspace.py.template`；`pack-tools.py.template` 改名；其余对齐

### 验证
- manual 描述的结构与代码一致（workspace.py、去 IndustryPack）
- `grep -rn 'IndustryPack\|pack\.py' docs/design/manual/` 零残留

---

## 成功标准（全局）

1. `agent/engine/pack.py` 无 `IndustryPack` 类；工作目录经 workspace.py 注册
2. `workspace/` 下是 retail / jjy / customerA 三个自洽工作目录（各有 workspace.py + ontology + data + skills）
3. 代码无 `customer_default` 残留（兜底常量改 jjy）；无 `equipment_repair` 残留（改 customerA）
4. agent per-workspace 隔离：jjy 请求只见 jjy 工具/本体，customerA 请求只见 customerA 工具/本体
5. pytest 全套通过
6. endpoint SSE 流式正常，浏览器对话不崩
7. manual 无 IndustryPack/pack.py 残留，结构对齐代码

---

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 去 IndustryPack 涉及 57 处非测试代码 + 测试 | 🔴 高 | WP1 独立完成 + pytest 全绿为门槛，才进 WP2 |
| customer_default 101 处改名漏改 | 🟡 中 | grep 兜底 + pytest |
| 自写 endpoint SSE 编码错误 | 🟡 中 | 逐行复刻 add_langgraph_fastapi_endpoint；playwright 验证 |
| jjy 拷贝 retail 后工具模块路径冲突 | 🟡 中 | 拷贝后改 tools_module 路径为 workspace.jjy.* |
| import 路径 workspace.equipment_repair → workspace.customerA 漏改 | 🟡 中 | grep + pytest |
| 范围大，单 spec 工期长 | 🟡 中 | 4 个 WP 递进，每 WP 独立 commit + 验证 |

---

## 执行顺序（强制）

WP1（去 IndustryPack，pytest 全绿）→ WP2（改名自洽，pytest 全绿）→ WP3（agent 隔离，pytest + playwright）→ WP4（重写 manual）。

每 WP 独立 commit，前一个 WP 不绿不进下一个。
