# 企业级语义 Agent 架构文档

> 项目：store-ontology（门店大脑 AI 原生应用）
> 版本：v1.0
> 日期：2026-04-23
> 状态：规划中

---

## 一、背景与目标

### 1.1 为什么需要企业级语义 Agent

当前 store-ontology 项目的 Agent 实现（`agent_executor.py`）是一个简单的 one-shot 工具调用循环，存在以下局限：

| 局限 | 说明 |
|---|---|
| 无持久记忆 | 每次对话都是全新上下文，无法积累店铺运营知识 |
| 无多轮推理 | 复杂业务问题需要多轮查询、验证、确认，当前无法支持 |
| 工具扩展性差 | 10个固定工具函数，无法按需加载新技能 |
| 无权限隔离 | 所有用户看到相同数据，无法按门店/角色隔离 |
| 无上下文管理 | 长对话会超出 context window，无压缩机制 |

### 1.2 Hermes Agent 的价值

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 是一个无领域知识的通用 Agent 运行时，提供：

- 完整多轮对话循环（`AIAgent.run_conversation()`，12011行）
- 工具注册与编排（`model_tools.py` + `registry.py`）
- 记忆系统（MEMORY.md / USER.md / SQLite 会话存储）
- Skill 系统（按需加载的 Markdown 知识文档）
- 上下文压缩（`ContextCompressor`）
- Slash 命令体系（`/skill`, `/fad`, `/plan` 等）

**store-ontology 的价值是为 Hermes 注入领域语义**：

```
Hermes Agent（通用运行时引擎）
    ├── LLM 推理（通用能力）
    ├── 工具系统（操作能力）
    ├── 记忆系统（长期记忆）
    ├── Skill 系统（知识技能）
    └── 上下文管理（短期记忆）
         ↓ + 本体语义层（store-ontology 注入）
    ├── TBOX（业务概念语义 → LLM 理解"临期/折扣/豁免"语义）
    ├── ABOX（业务实例数据 → 真实库存/产品/任务）
    ├── SPARQL（语义查询 → 结构化推理）
    └── 权限本体（RBAC → 租户/角色/操作三层隔离）
```

### 1.3 设计目标

```
┌─────────────────────────────────────────────────────────────┐
│                    设计目标                                  │
├─────────────────────────────────────────────────────────────┤
│  ① 多租户隔离    — A店店长只能看A店数据，B店同理           │
│  ② 多轮推理      — 复杂业务问题支持多轮查询验证确认          │
│  ③ 持久记忆      — 店铺运营知识跨会话积累                  │
│  ④ 权限感知      — 店长可审批折扣，店员只能查               │
│  ⑤ 语义理解      — LLM 原生理解 TBOX 业务概念              │
│  ⑥ 技能可扩展    — 通过 Skill 系统按需加载业务 SOP           │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、系统架构总览

### 2.1 整体数据流

```
用户（飞书 / Web / CLI）
    ↓
┌─────────────────────────────────────────────────────────────┐
│  身份认证层（飞书 Bot / SSO）                                │
│  → 提取 user_id → 查询权限本体 ABOX                        │
│  → 获取：tenant_id（门店ID）+ roles（角色）+ permissions    │
└─────────────────────────────────────────────────────────────┘
    ↓ 权限上下文
┌─────────────────────────────────────────────────────────────┐
│  Hermes CLI / Gateway                                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  AIAgent.run_conversation()  ← 核心对话循环            ││
│  │  run_agent.py（12011行）                               ││
│  └─────────────────────────────────────────────────────────┘│
│  ├── System Prompt                                          │
│  │     ├── SOUL.md（Agent 身份：门店大脑）                 │
│  │     ├── 店铺业务上下文（从 ABOX 注入当前状态）          │
│  │     └── 用户权限上下文（tenant_id + roles + permissions）│
│  ├── Tools（Hermes 工具注册表）                            │
│  │     ├── 原有工具：terminal / read_file / browser / ... │
│  │     └── ★ 本体工具：                                    │
│  │           ├── sparql_query()         ← SPARQL 查询      │
│  │           ├── ttl_reasoning()       ← OWL 推理          │
│  │           ├── check_expiry()        ← 临期商品查询      │
│  │           ├── verify_discount()     ← 折扣合规校验      │
│  │           ├── create_task()         ← 任务创建          │
│  │           └── approve_action()      ← 审批操作          │
│  ├── Skills                                                │
│  │     ├── store-brain-skill.md    ← 本体使用说明          │
│  │     ├── expiry-sop.md           ← 临期处理 SOP          │
│  │     ├── discount-rules.md       ← 促销规则说明          │
│  │     └── replenishment-sop.md    ← 补货决策 SOP          │
│  └── Memory                                                │
│        ├── MEMORY.md（Agent 记忆：店铺偏好/常见问题）       │
│        ├── USER.md（用户画像：店长/店员/总部）             │
│        └── ABOX 快照（每日自动更新）                       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  本体语义层                                                 │
│  ├── TBOX（modules/module1-worktask/）                      │
│  │     ├── WORKTASK-MODULE.ttl（临期打折本体，1256 triples）│
│  │     └── RBAC-MODULE.ttl（权限本体，待新增）              │
│  └── ABOX（data/）                                          │
│        ├── products.json（商品实例）                        │
│        ├── tasks.json（任务实例）                          │
│        └── permissions.ttl（权限实例，待新增）              │
└─────────────────────────────────────────────────────────────┘
    ↓
返回结果（已按权限过滤）
```

### 2.2 组件职责矩阵

| 组件 | 职责 | 位置 |
|---|---|---|
| Hermes CLI | 交互入口，多渠道接入 | `hermes-agent run` |
| AIAgent | 核心对话循环，LLM 调用，工具分发 | `run_agent.py` |
| Tools | 执行 SPARQL / 文件操作 / HTTP 调用 | `tools/store_ontology_tools.py` |
| Skills | 业务知识按需加载 | `~/.hermes/skills/` |
| Memory | 长期记忆，用户偏好 | `~/.hermes/memories/` |
| TBOX | 本体类/属性/规则声明 | `modules/module1-worktask/` |
| ABOX | 业务实例数据 | `data/` |
| SPARQL Service | 语义查询服务 | `app/services/sparql_service.py` |
| Permission Layer | 权限过滤中间件 | `app/services/permission_aware_sparql.py` |

---

## 三、核心组件设计

### 3.1 Hermes Agent 运行时

**核心循环**（`run_agent.py`）：

```python
while api_call_count < max_iterations:
    # ① 构建消息（含 System Prompt + 上下文 + Skills）
    api_messages = build_api_messages(messages, system_prompt)
    
    # ② 调用 LLM
    response = client.chat.completions.create(
        model=model, messages=api_messages, tools=tool_schemas
    )
    
    # ③ 判断返回类型
    if response.tool_calls:
        # 有工具调用 → 分发执行 → 返回结果 → 继续循环
        results = execute_tool_calls(response.tool_calls)
        messages.append(assistant_msg)
        messages.extend(tool_results)
        continue
    else:
        # 纯文本 → 返回用户
        return response.content
```

**关键设计原则**：

| 原则 | 说明 |
|---|---|
| 同步循环 | 完全同步，不丢上下文，支持最大迭代控制 |
| 消息格式 | OpenAI Chat Completions 格式 |
| 工具并行 | `_should_parallelize_tool_batch()` 判断是否并行执行 |
| Prompt 缓存 | Snapshot 模式——System Prompt 会话内不改变 |

### 3.2 本体语义层（TBOX/ABOX）

**TBOX 职责**：

```
modules/module1-worktask/
├── WORKTASK-MODULE.ttl      ← 临期打折业务本体（已存在，1256 triples）
├── RBAC-MODULE.ttl          ← 权限本体（待新增）
└── REPLENISHMENT-MODULE.ttl ← 补货本体（待扩展）
```

**TBOX 核心类**（WORKTASK-MODULE）：

```turtle
# 业务实体
store:Product         # 商品
store:WorkTask        # 工作任务
store:DiscountRule   # 折扣规则
store:InventoryEvent # 库存事件

# 核心属性
store:productName     # 商品名称
store:expiryDate      # 到期日期
store:daysUntilExpiry # 临期天数
store:discountRate    # 折扣率
store:taskStatus      # 任务状态

# 推理规则
store:isNearExpiry    # 临期待处理（到期前X天）
store:needsDiscount    # 需要打折（无豁免 + 临期）
```

**ABOX 职责**：

```
data/
├── products.json      ← 商品实例（含 storeId 标记）
├── tasks.json        ← 任务实例（含 storeId 标记）
├── permissions.ttl   ← 权限实例（待新增）
└── daily_snapshot/   ← ABOX 每日快照（供 Memory 使用）
```

### 3.3 权限感知层

权限感知是连接用户身份与数据访问的桥梁：

```
用户身份（飞书 user_id）
    ↓
查询权限 ABOX（SPARQL）
    ↓
获取：tenant_id + roles + permissions
    ↓
注入 System Prompt（用户权限上下文）
    ↓
工具调用时自动附加 tenant_id 过滤
    ↓
返回结果（已过滤）
```

---

## 四、权限与数据隔离

### 4.1 三层隔离模型

```
┌─────────────────────────────────────────────────────────────┐
│  第一层：租户隔离（Tenant Isolation）                        │
│  A店店长只能看A店库存，B店店长只能看B店库存                 │
│  核心机制：SPARQL 自动附加 FILTER(?storeId = "STORE_001")   │
├─────────────────────────────────────────────────────────────┤
│  第二层：角色隔离（Role-based Access）                       │
│  店长可审批折扣，店员只能查看                               │
│  核心机制：@require_permission 装饰器                       │
├─────────────────────────────────────────────────────────────┤
│  第三层：操作隔离（Operation-based Access）                  │
│  读取/写入/审批是不同的权限点                               │
│  核心机制：Permission 枚举 + 工具权限检查                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 权限本体建模（TBOX）

```turtle
@prefix store: <http://store-ontology.example.org/> .
@prefix rbac:  <http://store-ontology.example.org/rbac/> .
@prefix owl:   <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .

# ── 租户（门店）────────────────────────────────────────────
store:Store a rdfs:Class ; rdfs:label "门店" .
store:storeId a owl:DatatypeProperty ; rdfs:domain store:Store ; rdfs:range xsd:string ; rdfs:label "门店编号" .
store:storeName a owl:DatatypeProperty ; rdfs:domain store:Store ; rdfs:range xsd:string .

# ── 角色────────────────────────────────────────────────────
store:Role a rdfs:Class ; rdfs:label "角色" .

store:StoreManager   a store:Role ; rdfs:label "店长" .
store:StoreClerk     a store:Role ; rdfs:label "店员" .
store:DistrictManager a store:Role ; rdfs:label "区域经理" .
store:Headquarters   a store:Role ; rdfs:label "总部人员" .

# ── 权限────────────────────────────────────────────────────
store:Permission a rdfs:Class ; rdfs:label "权限" .

store:canRead         a store:Permission ; rdfs:label "读取" .
store:canWrite        a store:Permission ; rdfs:label "写入" .
store:canApprove      a store:Permission ; rdfs:label "审批折扣" .
store:canViewOtherStore a store:Permission ; rdfs:label "查看其他门店" .
store:canManageStaff  a store:Permission ; rdfs:label "管理店员" .

# ── 角色-权限关联────────────────────────────────────────────
store:hasPermission a owl:ObjectProperty ; rdfs:domain store:Role ; rdfs:range store:Permission .

# 店长：读取 + 写入 + 审批折扣
store:StoreManager store:hasPermission store:canRead .
store:StoreManager store:hasPermission store:canWrite .
store:StoreManager store:hasPermission store:canApprove .

# 店员：读取 + 写入（不能审批）
store:StoreClerk store:hasPermission store:canRead .
store:StoreClerk store:hasPermission store:canWrite .

# 区域经理：读取管辖区域内所有门店
store:DistrictManager store:hasPermission store:canRead .
store:DistrictManager store:hasPermission store:canViewOtherStore .

# 总部：所有权限
store:Headquarters store:hasPermission store:canRead .
store:Headquarters store:hasPermission store:canWrite .
store:Headquarters store:hasPermission store:canApprove .
store:Headquarters store:hasPermission store:canViewOtherStore .

# ── 用户分配（UserAssignment）───────────────────────────────
store:UserAssignment a rdfs:Class ; rdfs:label "用户分配" .

store:userId a owl:DatatypeProperty ; rdfs:domain store:UserAssignment ; rdfs:range xsd:string ; rdfs:label "飞书用户ID" .
store:assignedStore a owl:ObjectProperty ; rdfs:domain store:UserAssignment ; rdfs:range store:Store ; rdfs:label "所属门店" .
store:assignedRole a owl:ObjectProperty ; rdfs:domain store:UserAssignment ; rdfs:range store:Role ; rdfs:label "分配角色" .
store:assignedAt a owl:DatatypeProperty ; rdfs:domain store:UserAssignment ; rdfs:range xsd:date .
```

### 4.3 权限实例数据（ABOX）

```turtle
# ── 门店实例 ────────────────────────────────────────────────
store:StoreA a store:Store ; store:storeId "STORE_001" ; store:storeName "A 店（欢乐港）" .
store:StoreB a store:Store ; store:storeId "STORE_002" ; store:storeName "B 店（万达广场）" .

# ── 用户分配实例 ────────────────────────────────────────────
# 张三 - A店店长
store:ZhangSan_Assign a store:UserAssignment ;
    store:userId "feishu_user_001" ;
    store:assignedStore store:StoreA ;
    store:assignedRole store:StoreManager ;
    store:assignedAt "2026-01-01"^^xsd:date .

# 李四 - A店店员
store:LiSi_Assign a store:UserAssignment ;
    store:userId "feishu_user_002" ;
    store:assignedStore store:StoreA ;
    store:assignedRole store:StoreClerk ;
    store:assignedAt "2026-01-15"^^xsd:date .

# 王五 - B店店长
store:WangWu_Assign a store:UserAssignment ;
    store:userId "feishu_user_003" ;
    store:assignedStore store:StoreB ;
    store:assignedRole store:StoreManager ;
    store:assignedAt "2026-02-01"^^xsd:date .

# 赵六 - 总部人员
store:ZhaoLiu_Assign a store:UserAssignment ;
    store:userId "feishu_user_004" ;
    store:assignedRole store:Headquarters ;
    store:assignedAt "2026-03-01"^^xsd:date .
```

### 4.4 三种权限隔离实现方案

#### 方案 A：工具层过滤（推荐 ⭐⭐）

**思路：** 对 Agent 隐藏 tenant_id，工具内部自动附加权限过滤。

```python
# tools/store_ontology_tools.py
from functools import lru_cache

@lru_cache(maxsize=100)
def get_user_permissions(user_id: str) -> dict:
    """从 ABOX 查询用户权限"""
    query = f"""
    PREFIX store: <http://store-ontology.example.org/>
    SELECT ?storeId ?role ?permission
    WHERE {{
      ?assignment a store:UserAssignment ;
                   store:userId "{user_id}" ;
                   store:assignedRole ?role ;
                   store:assignedStore ?store .
      OPTIONAL {{ ?role store:hasPermission ?permission . }}
      BIND(REPLACE(STR(?store), ".*STORE_", "") AS ?storeId)
    }}
    """
    return sparql_query_internal(query)

def check_expiry_products(task_id: str = None) -> str:
    """
    查询当前用户有权限查看的临期商品。
    tenant_id 从会话上下文自动获取，Agent 无需知道。
    """
    user_id = get_current_user_id(task_id)
    perms = get_user_permissions(user_id)
    tenant_id = perms["tenant_id"]
    can_view_all = "canViewOtherStore" in perms["permissions"]

    if can_view_all:
        filter_clause = ""
    else:
        filter_clause = f'FILTER(?storeId = "{tenant_id}")'

    query = f"""
    PREFIX store: <http://store-ontology.example.org/>
    SELECT ?product ?name ?expiryDate ?daysUntil
    WHERE {{
      ?product a store:Product ;
               store:name ?name ;
               store:expiryDate ?expiryDate ;
               store:daysUntilExpiry ?daysUntil ;
               store:storeId ?storeId .
      FILTER(?daysUntil <= 3)
      {filter_clause}
    }}
    """
    return sparql_query_internal(query)
```

**优势**：Agent 完全无需感知权限逻辑，工具层自动处理，改动最小。

#### 方案 B：SPARQL 重写中间件

**思路：** 在 SPARQL 服务层加查询重写中间件，自动注入权限过滤。

```python
# app/services/permission_aware_sparql.py

class PermissionAwareSPARQLService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.permissions = self._load_permissions()

    def query(self, raw_query: str) -> list:
        perms = self.permissions
        needs_filter = any(p in raw_query for p in ["?product", "?task", "?inventory"])

        if not needs_filter or "canViewOtherStore" in perms["permissions"]:
            return self._execute(raw_query)

        # 重写：向 SPARQL 注入 tenant 过滤
        rewritten = self._inject_tenant_filter(raw_query, perms["tenant_id"])
        return self._execute(rewritten)

    def _inject_tenant_filter(self, query: str, tenant_id: str) -> str:
        return query + f'\nFILTER(?storeId = "{tenant_id}")'
```

#### 方案 C：图级隔离（Graph Partition）

**思路：** 不同门店的数据存在不同的 Named Graph 中，查询时指定 Graph 即天然隔离。

```turtle
GRAPH store:StoreA_Products {
    store:Product001 store:name "嫩豆腐" ; store:storeId "STORE_001" .
}

GRAPH store:StoreB_Products {
    store:Product101 store:name "日式味噌" ; store:storeId "STORE_002" .
}
```

```python
def query_with_graph(query: str, task_id: str) -> str:
    perms = get_user_permissions(get_current_user_id(task_id))

    if "canViewOtherStore" in perms["permissions"]:
        graph = "http://store-ontology.example.org/all"
    else:
        graph = f"http://store-ontology.example.org/Store{perms['tenant_id']}_Products"

    return sparql_query_internal(f"FROM <{graph}> {{ {query} }}")
```

### 4.5 方案对比

| | 方案 A 工具层过滤 | 方案 B SPARQL 重写 | 方案 C 图级隔离 |
|---|---|---|---|
| 实现复杂度 | ⭐ 低 | ⭐⭐ 中 | ⭐⭐⭐ 高 |
| 隔离强度 | 强（应用层保证）| 中（查询层可绕过）| 强（存储层天然隔离）|
| 跨店查询 | 支持（需 canViewOtherStore）| 支持 | 需要 union 多个图 |
| 审计追溯 | 好 | 好 | 最好 |
| **推荐场景** | **日常场景首选** | 中等复杂度 | 多租户强隔离 |

**最终推荐**：日常场景用**方案 A**，需要极高隔离强度时引入**方案 C**。

### 4.6 权限检查装饰器

```python
# tools/permissions.py

def require_permission(*required_permissions):
    """工具权限检查装饰器"""
    def decorator(func):
        def wrapper(*args, task_id=None, **kwargs):
            user_id = get_current_user_id(task_id)
            perms = get_user_permissions(user_id)

            for perm in required_permissions:
                if perm not in perms["permissions"]:
                    return json.dumps({
                        "error": "权限不足",
                        "required": perm,
                        "message": f"您没有 {perm} 权限，请联系店长或系统管理员"
                    })
            return func(*args, task_id=task_id, **kwargs)
        return wrapper
    return decorator

# 使用示例
@require_permission("canApprove")
def approve_discount(product_name: str, discount_rate: float, task_id: str = None) -> str:
    """审批折扣（需 canApprove 权限）"""
    ...
```

---

## 五、Memory 与数据机制

### 5.1 多层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│  长期记忆（Long-term Memory）                               │
│  ├── MEMORY.md — Agent 持久记忆（~2200 chars）              │
│  │     ├── 项目信息（store-ontology 上下文）                │
│  │     ├── 跨会话积累的店铺知识                            │
│  │     └── 常见问题处理记录                                │
│  └── USER.md — 用户画像（~1375 chars）                      │
│        ├── 用户偏好（对话风格/响应格式）                    │
│        └── 用户角色和权限（快照）                           │
├─────────────────────────────────────────────────────────────┤
│  工作记忆（Working Memory）                                 │
│  ├── 对话历史（messages[]）                                │
│  └── 当前推理上下文（SPARQL 结果缓存）                     │
├─────────────────────────────────────────────────────────────┤
│  ABOX 快照（ABOX Snapshot）                                 │
│  └── 每日自动快照（cron job）                               │
│        ├── 当前库存状态                                    │
│        ├── 待处理任务数量                                  │
│        └── 临期商品概览                                    │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 每日 ABOX 快照脚本

```python
# scripts/snapshot_abox_to_memory.py（每日 cron job）

def snapshot():
    products = json.load(open("data/products.json"))
    tasks = json.load(open("data/tasks.json"))

    near_expiry = [p["name"] for p in products if p.get("days_until_expiry", 999) <= 3]
    pending_tasks = len([t for t in tasks if t.get("status") != "done"])

    lines = [
        "## 门店数据快照\n",
        f"临期商品（3天内）: {near_expiry}",
        f"待处理任务数: {pending_tasks}",
        f"更新于: {datetime.now().isoformat()}\n"
    ]

    memory_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
    with open(memory_path, "a") as f:
        f.write("\n".join(lines))
```

### 5.3 上下文注入流程

```
Hermes 启动会话
    ↓
prompt_builder.build_system_prompt()
    ↓
① 读取 SOUL.md（Agent 身份）
② 读取 store-ontology 上下文文件
③ 读取 MEMORY.md（长期记忆快照）
④ 读取 USER.md（用户画像 + 权限快照）
⑤ 组装为最终 System Prompt
    ↓
冻结（Snapshot 模式）—— 本会话内不改变
    ↓
LLM 调用
```

---

## 六、Skill 系统设计

### 6.1 Skill 与 Tool 的区别

| | Tool（工具）| Skill（技能）|
|---|---|---|
| 用途 | 执行操作（读文件/执行命令/查询）| 知识/流程/操作手册 |
| 格式 | Python 函数 + JSON schema | Markdown + YAML frontmatter |
| 加载 | 始终在 System Prompt 中 | 按需加载（Agent 判断）|
| 调用 | LLM 决定自动调用 | Agent 读取后自行理解执行 |
| 持久化 | 不持久 | 可通过 `skill_manage` 创建/修改 |

### 6.2 三级渐进式加载

```
Level 0:  skill_view(name)           → {name, description, category}  (~3k tokens)
              ↓ 发现需要
Level 1:  skill_view(name, path=None) → 完整 SKILL.md 内容 + metadata
              ↓ 需要具体文件
Level 2:  skill_view(name, path)     → 指定 reference/template/script 文件
```

### 6.3 门店大脑 Skill 体系

```
~/.hermes/skills/
├── store-brain-skill.md       ← 本体使用说明（触发：涉及门店业务）
├── expiry-sop.md              ← 临期商品处理 SOP
├── discount-rules.md          ← 促销规则说明（折扣区间/豁免名单）
├── replenishment-sop.md       ← 补货决策 SOP
├── permission-guide.md        ← 权限系统说明
└── audit-guide.md            ← 审计日志说明
```

### 6.4 store-brain-skill.md 示例

```yaml
---
name: store-brain-skill
description: 门店大脑 AI 助手技能库 — 本体使用说明
category: knowledge
tags: [store-ontology, 本体, SPARQL, 临期, 折扣]
trigger: ["临期", "打折", "库存", "任务", "促销", "审批"]
---

# 门店大脑技能库

## 触发条件
当用户提到以下关键词时，加载本 Skill：
- 临期商品、临期天数、到期日期
- 打折、折扣率、促销
- 库存查询、库存事件
- 任务创建、任务审批
- 补货建议、盘点

## 本体查询方法

### SPARQL 端点
```python
from app.services.sparql_service import SPARQLService
service = SPARQLService()
results = service.query("""
PREFIX store: <http://store-ontology.example.org/>
SELECT ?product ?name ?daysUntil
WHERE {
  ?product a store:Product ;
           store:name ?name ;
           store:daysUntilExpiry ?daysUntil .
  FILTER(?daysUntil <= 3)
}
""")
```

### 常用查询模板
1. **临期商品查询**：到期天数 <= threshold
2. **折扣合规校验**：检查折扣是否在 10%-50% 区间
3. **豁免名单查询**：SKIP 产品是否在豁免名单

## 数据位置
- 本体定义：`modules/module1-worktask/WORKTASK-MODULE.ttl`
- 商品实例：`data/products.json`
- 任务实例：`data/tasks.json`
- 权限实例：`data/permissions.ttl`

## 业务规则
- 临期定义：到期前 3 天内
- 折扣区间：10% - 50%（超出需审批）
- 豁免名单：生鲜、熟食、进口食品
```

---

## 七、SPARQL 与推理集成

### 7.1 权限感知的 SPARQL 服务

```python
# app/services/permission_aware_sparql.py

class PermissionAwareSPARQLService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.permissions = self._load_permissions()
        self._store = Graph()
        self._store.parse("modules/module1-worktask/WORKTASK-MODULE.ttl")
        self._store.parse("data/permissions.ttl")

    def _load_permissions(self) -> dict:
        query = f"""
        PREFIX store: <http://store-ontology.example.org/>
        SELECT ?storeId ?role ?permission
        WHERE {{
          ?assignment a store:UserAssignment ;
                       store:userId "{self.user_id}" ;
                       store:assignedRole ?role ;
                       store:assignedStore ?store .
          OPTIONAL {{ ?role store:hasPermission ?permission . }}
          BIND(REPLACE(STR(?store), ".*STORE_", "") AS ?storeId)
        }}
        """
        results = self._query_internal(query)
        return self._parse_permissions(results)

    def query(self, raw_query: str) -> list:
        """执行查询，自动注入权限过滤"""
        needs_filter = any(p in raw_query for p in ["?product", "?task", "?inventory"])
        if needs_filter and "canViewOtherStore" not in self.permissions["permissions"]:
            tenant_id = self.permissions["tenant_id"]
            rewritten = self._inject_tenant_filter(raw_query, tenant_id)
            return self._query_internal(rewritten)
        return self._query_internal(raw_query)

    def _inject_tenant_filter(self, query: str, tenant_id: str) -> str:
        return query + f'\nFILTER(?storeId = "{tenant_id}")'
```

### 7.2 OWL 推理集成

```python
# app/services/ttl_llm_reasoning.py（已有逻辑增强）

def reason_with_ontology(query: str, user_id: str) -> dict:
    """
    结合 OWL 推理的语义查询。
    1. 执行 SPARQL 查询（显式知识）
    2. 通过 HermiT/Pellet 推理机获取隐含知识
    3. 合并结果返回
    """
    sparql_service = PermissionAwareSPARQLService(user_id)
    explicit_results = sparql_service.query(query)

    # OWL 推理：获取隐含的类成员关系
    implicit_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    SELECT ?entity ?class
    WHERE {{
      ?entity a ?class .
      ?class a owl:Class .
    }}
    """
    # 合并显式 + 隐式结果
    return merge_results(explicit_results, implicit_results)
```

### 7.3 缓存策略

```python
# 推理结果缓存（避免重复 SPARQL 查询）
from functools import lru_cache

@lru_cache(maxsize=500)
def cached_query(query_hash: str, user_id: str) -> list:
    """基于 (query_hash, user_id) 缓存 SPARQL 结果"""
    ...
```

---

## 八、实施路径与路线图

### 立即可做（1-2天）

```
Step 1: 部署 Hermes Agent
  - 安装 hermes-agent 到 store-ontology 目录
  - 配置 MiniMax API Key
  - 配置工作目录为 store-ontology

Step 2: 创建 SOUL.md
  - Agent 身份：门店大脑 AI 助手
  - 权限感知身份定义
  - 当前门店状态注入

Step 3: 创建 store-brain-skill.md
  - 本体使用说明
  - SPARQL 查询模板
  - 业务规则说明
```

### 短期（1周）

```
Step 4: 注册本体工具集
  - tools/store_ontology_tools.py
  - sparql_query / check_expiry / verify_discount / create_task

Step 5: 实现权限层
  - RBAC-MODULE.ttl（权限本体）
  - permissions.ttl（权限实例）
  - PermissionAwareSPARQLService

Step 6: 实现每日 ABOX 快照
  - scripts/snapshot_abox_to_memory.py
  - cron job 每日执行
```

### 中期（2-4周）

```
Step 7: 深度集成 OWL 推理
  - HermiT/Pellet 推理机
  - 推理触发工具
  - 隐含知识查询

Step 8: Skill 系统扩展
  - expiry-sop.md（临期处理 SOP）
  - discount-rules.md（促销规则）
  - replenishment-sop.md（补货决策）

Step 9: 多Agent协作
  - 店长 Agent（前端用户）
  - 总部 Agent（管理视角）
  - Agent 间 SPARQL 共享

Step 10: 审计日志完善
  - 每次数据访问的审计记录
  - 权限变更追踪
  - 合规报告生成
```

---

## 九、附录

### A. 文件结构

```
store-ontology/
├── CLAUDE.md
├── modules/                          # TBOX
│   └── module1-worktask/
│       ├── WORKTASK-MODULE.ttl     # 临期打折本体
│       └── RBAC-MODULE.ttl         # 权限本体（待新增）
├── data/                            # ABOX
│   ├── products.json
│   ├── tasks.json
│   └── permissions.ttl             # 权限实例（待新增）
├── docs/
│   └── TBOX/
│       ├── ARCHITECTURE.md
│       ├── ABOX_TBOX_ARCHITECTURE.md
│       └── ENTERPRISE_AGENT_ARCHITECTURE.md  ← 本文档
├── app/
│   └── services/
│       ├── sparql_service.py
│       └── permission_aware_sparql.py  # 新增
├── tools/
│   └── store_ontology_tools.py     # 新增/增强
├── scripts/
│   └── snapshot_abox_to_memory.py  # 新增
└── ~/.hermes/                       # Hermes 配置
    ├── memories/
    │   ├── MEMORY.md
    │   └── USER.md
    └── skills/
        └── store-brain-skill.md    # 新增
```

### B. 参考资料

- [Hermes Agent GitHub](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com)
- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/)
- [store-ontology 项目文档](docs/TBOX/)
