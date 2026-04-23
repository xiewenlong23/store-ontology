# 门店大脑 AI 原生应用 — 整合架构规划

> 项目：store-ontology（门店大脑 AI 原生应用）
> 版本：v2.0（整合版）
> 日期：2026-04-23
> 状态：规划中
> 来源：ARCHITECTURE.md + ENTERPRISE_AGENT_ARCHITECTURE.md

---

## 一、背景与核心挑战

### 1.1 为什么需要企业级语义 Agent

当前 `agent_executor.py` 是单步（one-shot）工具调用循环，存在五大局限：

| 局限 | 说明 |
|-----|------|
| 无持久记忆 | 每次对话都是全新上下文，无法积累店铺运营知识 |
| 无多轮推理 | 复杂业务问题需要多轮查询、验证、确认，当前无法支持 |
| 工具扩展性差 | 10个固定工具函数，无法按需加载新技能 |
| 无权限隔离 | 所有用户看到相同数据，无法按门店/角色隔离 |
| 无上下文管理 | 长对话会超出 context window，无压缩机制 |

### 1.2 核心挑战

| 挑战维度 | 具体问题 |
|---------|---------|
| **规模** | 单门店 1.5 万 SKU，1 万员工；全系统千万级 SKU，千万级员工关系 |
| **异构性** | 门店地域/规模/客群差异大，本体需兼顾通用+局部特化 |
| **时效性** | 临期打折/补货/排班需要分钟级推理响应 |
| **稀疏性** | 单个门店实际活跃 SKU 可能只有 30-40%，大量冷数据 |
| **层级性** | 总部→区域→门店→部门→员工，五级管理结构 |

### 1.3 Hermes Agent 的价值

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

---

## 二、设计目标

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
│  ⑦ 规模可扩展    — L0-L3 分层本体解决规模/稀疏/异构问题     │
│  ⑧ 分层推理      — Fast/Medium/Slow 三级推理路径           │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、系统架构总览

### 3.1 四层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: 企业增强层                                        │
│  ├── RBAC 权限本体（三层租户隔离）                          │
│  ├── Skill 注册中心（组织级技能治理）                       │
│  └── 审计与回滚（技能版本管理）                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 领域推理引擎                                     │
│  ├── Fast Path（规则引擎，毫秒级）                          │
│  ├── Medium Path（OWL RL 推理，百毫秒级）                   │
│  └── Slow Path（LLM Agent 多步循环，秒级）                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 本体语义注入                                      │
│  ├── TBOX（L0-L3 分层本体）                                │
│  ├── ABOX（多视图本体：全局 SKU 池 vs 门店活跃 SKU）        │
│  └── SPARQL 语义查询                                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Hermes Agent 运行时                              │
│  ├── AIAgent.run_conversation()（核心对话循环）            │
│  ├── 工具注册与编排（registry.py）                         │
│  ├── 记忆系统（MEMORY.md / USER.md / SQLite）              │
│  ├── Skill 系统（按需加载 Markdown 知识）                  │
│  └── 上下文压缩（ContextCompressor）                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 整体数据流

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
│  Layer 1: Hermes CLI / Gateway                              │
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
│  Layer 2: 本体语义层                                        │
│  ├── TBOX（modules/module1-worktask/）                      │
│  │     ├── WORKTASK-MODULE.ttl（临期打折本体，1256 triples）│
│  │     ├── RBAC-MODULE.ttl（权限本体）                      │
│  │     └── REPLENISHMENT-MODULE.ttl（补货本体，待扩展）    │
│  └── ABOX（data/）                                          │
│        ├── products.json（商品实例）                        │
│        ├── tasks.json（任务实例）                          │
│        └── permissions.ttl（权限实例）                      │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 三级推理引擎                                      │
│  ├── Fast Path（规则引擎）  ← 毫秒级确定性规则              │
│  ├── Medium Path（OWL RL）  ← 百毫秒级本体推理              │
│  └── Slow Path（LLM Agent） ← 秒级多步循环推理              │
└─────────────────────────────────────────────────────────────┘
    ↓
返回结果（已按权限过滤）
```

### 3.3 组件职责矩阵

| 组件 | 层级 | 职责 | 位置 |
|-----|------|------|------|
| Hermes CLI | Layer 1 | 交互入口，多渠道接入 | `hermes-agent run` |
| AIAgent | Layer 1 | 核心对话循环，LLM 调用，工具分发 | `run_agent.py` |
| Tools | Layer 1 | 执行 SPARQL / 文件操作 / HTTP 调用 | `tools/store_ontology_tools.py` |
| Skills | Layer 4 | 业务知识按需加载 | `~/.hermes/skills/` |
| Memory | Layer 1 | 长期记忆，用户偏好 | `~/.hermes/memories/` |
| TBOX | Layer 2 | 本体类/属性/规则声明（L0-L3 分层） | `modules/module1-worktask/` |
| ABOX | Layer 2 | 业务实例数据（多视图本体） | `data/` |
| SPARQL Service | Layer 2/3 | 语义查询服务 + 推理 | `app/services/sparql_service.py` |
| 三级推理引擎 | Layer 3 | Fast/Medium/Slow 路径分发 | `app/services/reasoning_engine.py` |
| Permission Layer | Layer 4 | 权限过滤中间件 | `app/services/permission_aware_sparql.py` |

---

## 四、本体分层架构（L0-L3）

### 4.1 层级总览

```
┌─────────────────────────────────────────┐
│ L0: 全局核心本体 (Foundation)            │ ← 所有门店共享，如 Product/Employee/Store
├─────────────────────────────────────────┤
│ L1: 业务域本体 (Domain)                  │ ← 促销域/库存域/排班域/补货域
├─────────────────────────────────────────┤
│ L2: 区域/品类本体 (Regional/Category)    │ ← 华北区/生鲜类/家电类
├─────────────────────────────────────────┤
│ L3: 单店本体实例 (Store Instance)        │ ← 每个门店的具体数据
└─────────────────────────────────────────┘
```

### 4.2 解决稀疏性：多视图本体

**问题**：单门店 1.5 万 SKU，但门店 A 实际卖的只有 5000 种，其他 1 万种是"理论 SKU 池"。

**解法**：用 **View-based Ontology**，区分"全局 SKU 池"和"门店活跃 SKU"：

```turtle
# 全局产品目录（亿级 triples，但高度结构化）
:GlobalProductCatalog a owl:Ontology .
:SKU_OatMilk_500g a :Product ;
    :skuId "SKU-00001" ;
    :category :Dairy ;
    :shelfLife "180days"^^xsd:duration .

# 门店活跃 SKU（每个门店只索引自己卖的产品，大幅减少查询范围）
:Store_001 :hasActiveSKU :SKU_OatMilk_500g ;
            :hasActiveSKU :SKU_Bread_300g .
```

### 4.3 TBOX 核心类

**业务实体**：

```turtle
store:Product         # 商品
store:WorkTask        # 工作任务
store:DiscountRule   # 折扣规则
store:InventoryEvent # 库存事件
store:Store          # 门店
store:Role           # 角色
store:Permission     # 权限
store:UserAssignment  # 用户分配
```

**核心属性**：

```turtle
store:productName     # 商品名称
store:expiryDate      # 到期日期
store:daysUntilExpiry # 临期天数
store:discountRate    # 折扣率
store:taskStatus      # 任务状态
store:storeId         # 门店编号
store:skuId           # SKU 编号
```

**推理规则**：

```turtle
store:isNearExpiry    # 临期待处理（到期前X天）
store:needsDiscount   # 需要打折（无豁免 + 临期）
store:hasPermission   # 角色拥有某权限
```

---

## 五、三级推理引擎

### 5.1 路径总览

| 路径 | 响应时间 | 适用场景 | 实现方式 |
|------|---------|---------|---------|
| **Fast Path** | 毫秒级 | 确定性规则：临期商品 → 查询 <3天 → 直接执行打折 | 规则引擎（Python if-then） |
| **Medium Path** | 百毫秒级 | 本体推理：查找"所有缺货且销量高的生鲜 SKU" | OWL 2 RL 推理（GraphDB） |
| **Slow Path** | 秒级 | LLM Agent：自然语言理解、多跳推理 | LLM + SPARQL + Tool Call |

### 5.2 Fast Path（规则引擎）

适用于确定性业务规则，毫秒级响应：

```python
def fast_path_check_expiry(product) -> dict:
    """Fast Path：临期商品规则引擎"""
    if product.days_until_expiry <= 3 and product.category not in EXEMPTION_LIST:
        return {
            "action": "APPLY_DISCOUNT",
            "discount_rate": get_discount_rate(product.days_until_expiry),
            "reasoning_path": "Fast Path (规则引擎)"
        }
    return {"action": "NO_ACTION", "reasoning_path": "Fast Path (规则引擎)"}
```

### 5.3 Medium Path（OWL RL 推理）

适用于需要本体推理的复杂查询：

```python
def medium_path_query(user_id: str, query: str) -> list:
    """Medium Path：结合 OWL 推理的语义查询"""
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
    implicit_results = owl_reasoner.query(implicit_query)

    return merge_results(explicit_results, implicit_results)
```

### 5.4 Slow Path（LLM Agent 多步循环）

适用于复杂业务问题，需要多轮查询验证确认：

```python
def slow_path_agent(user_input: str, user_id: str) -> str:
    """Slow Path：LLM Agent 多步循环推理"""
    messages = build_messages(user_input, user_id)

    while api_call_count < max_iterations:
        response = llm_service.chat(messages)

        if response.tool_calls:
            results = execute_tool_calls(response.tool_calls, user_id)
            messages.append(assistant_msg)
            messages.extend(results)
            continue
        else:
            return response.content

    return "已达到最大迭代次数，请简化您的问题"
```

### 5.5 推理路径选择策略

```python
def select_reasoning_path(query: str) -> str:
    """自动选择推理路径"""
    query_lower = query.lower()

    # Fast Path：确定性关键词
    if any(kw in query_lower for kw in ["临期", "打折", "折扣", "到期"]):
        if "豁免" not in query_lower and "缺货" not in query_lower:
            return "Fast Path"

    # Medium Path：推理关键词
    if any(kw in query_lower for kw in ["缺货", "销量", "生鲜", "品类", "所有"]):
        return "Medium Path"

    # Slow Path：复杂推理
    if any(kw in query_lower for kw in ["为什么", "分析", "建议", "比较", "预测"]):
        return "Slow Path"

    return "Medium Path"  # 默认
```

---

## 六、权限与数据隔离

### 6.1 三层隔离模型

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

### 6.2 权限本体建模（TBOX）

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

### 6.3 权限实例数据（ABOX）

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

### 6.4 权限检查实现

#### 方案 A：工具层过滤（推荐）

对 Agent 隐藏 tenant_id，工具内部自动附加权限过滤：

```python
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

#### 方案 B：权限检查装饰器

```python
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

### 6.5 方案对比

| | 方案 A 工具层过滤 | 方案 B SPARQL 重写 | 方案 C 图级隔离 |
|---|---|---|---|
| 实现复杂度 | ⭐ 低 | ⭐⭐ 中 | ⭐⭐⭐ 高 |
| 隔离强度 | 强（应用层保证）| 中（查询层可绕过）| 强（存储层天然隔离）|
| 跨店查询 | 支持（需 canViewOtherStore）| 支持 | 需要 union 多个图 |
| 审计追溯 | 好 | 好 | 最好 |
| **推荐场景** | **日常场景首选** | 中等复杂度 | 多租户强隔离 |

**最终推荐**：日常场景用**方案 A**，需要极高隔离强度时引入**方案 C**。

---

## 七、Memory 与数据机制

### 7.1 多层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│  长期记忆（Long-term Memory）                                │
│  ├── MEMORY.md — Agent 持久记忆                             │
│  │     ├── 项目信息（store-ontology 上下文）                │
│  │     ├── 跨会话积累的店铺知识                            │
│  │     └── 常见问题处理记录                                │
│  └── USER.md — 用户画像                                    │
│        ├── 用户偏好（对话风格/响应格式）                    │
│        └── 用户角色和权限（快照）                           │
├─────────────────────────────────────────────────────────────┤
│  工作记忆（Working Memory）                                 │
│  ├── 对话历史（messages[]）                                │
│  └── 当前推理上下文（SPARQL 结果缓存）                     │
├─────────────────────────────────────────────────────────────┤
│  ABOX 快照（ABOX Snapshot）                                 │
│  └── 每日自动快照（cron job）                              │
│        ├── 当前库存状态                                    │
│        ├── 待处理任务数量                                  │
│        └── 临期商品概览                                    │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 每日 ABOX 快照脚本

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

### 7.3 上下文注入流程

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

## 八、Skill 系统设计

### 8.1 Skill 与 Tool 的区别

| | Tool（工具）| Skill（技能）|
|---|---|---|
| 用途 | 执行操作（读文件/执行命令/查询）| 知识/流程/操作手册 |
| 格式 | Python 函数 + JSON schema | Markdown + YAML frontmatter |
| 加载 | 始终在 System Prompt 中 | 按需加载（Agent 判断）|
| 调用 | LLM 决定自动调用 | Agent 读取后自行理解执行 |
| 持久化 | 不持久 | 可通过 `skill_manage` 创建/修改 |

### 8.2 三级渐进式加载

```
Level 0:  skill_view(name)           → {name, description, category}  (~3k tokens)
              ↓ 发现需要
Level 1:  skill_view(name, path=None) → 完整 SKILL.md 内容 + metadata
              ↓ 需要具体文件
Level 2:  skill_view(name, path)     → 指定 reference/template/script 文件
```

### 8.3 门店大脑 Skill 体系

```
~/.hermes/skills/
├── store-brain-skill.md       ← 本体使用说明（触发：涉及门店业务）
├── expiry-sop.md              ← 临期商品处理 SOP
├── discount-rules.md          ← 促销规则说明（折扣区间/豁免名单）
├── replenishment-sop.md       ← 补货决策 SOP
├── permission-guide.md        ← 权限系统说明
└── audit-guide.md            ← 审计日志说明
```

### 8.4 store-brain-skill.md 示例

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

## 九、SPARQL 与推理集成

### 9.1 权限感知的 SPARQL 服务

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

### 9.2 缓存策略

```python
# 推理结果缓存（避免重复 SPARQL 查询）
from functools import lru_cache

@lru_cache(maxsize=500)
def cached_query(query_hash: str, user_id: str) -> list:
    """基于 (query_hash, user_id) 缓存 SPARQL 结果"""
    ...
```

---

## 十、LLM Agent 多步工作流

### 10.1 当前：`agent_executor.py` 是单步（One-Shot）

```python
def execute(user_input: str) -> dict:
    messages = build_messages(user_input)
    response = llm_service.chat(messages)
    parsed = parse_tool_calls(response)
    results = [registry.dispatch(t, a) for t, a in parsed]
    return format_response(results)
```

### 10.2 迭代方向：多步循环推理（Iteration 8）

```
LLM 查询本体（理解业务语义）
  → 决策：调用哪个工具/规则
  → 执行：SPARQL 查询 / 业务操作
  → 结果回流：SparqlResult / ActionResult
  → LLM 再决策：是否需要继续查询/执行
  → 循环直到任务完成
```

### 10.3 System Prompt 约束（已生效）

`agent_executor.py` 的 SYSTEM_PROMPT 已追加数据展示原则：

```
数据展示原则：
- ASCII 图表仅展示汇总结构（如柱状图），不要在图表下方列出详细商品清单
- tool_result 中的 products/SKUs 数据仅用于组件渲染，前端 ProductList 会自动展示
- 你的 response 文本只能包含：分析结论 + 图表 + 行动建议，禁止复述具体商品数据
```

**目的**：解决柱状图场景下 LLM 在 response 文本中嵌入完整产品数据，导致前端双重渲染问题。

---

## 十一、关键架构决策

| 决策点 | 当前实现 | 建议方向 | 原因 |
|-------|---------|---------|------|
| **存储后端** | RDFLib 内存加载 | GraphDB (Ontotext/BlazeGraph) + Redis 热数据层 | 亿级 triples 需要原生图存储 |
| **查询语言** | SPARQL 1.0 | SPARQL 1.1 + 服务定义 (SERVICE) | 支持联邦查询，分片友好 |
| **推理时机** | 运行时增量推理 | 异步预推理 + 运行时增量 | 避免每次查询都触发 OWL 推理 |
| **数据更新** | 静态 JSON 文件 | 事件驱动 (Kafka/RabbitMQ) | 库存变动即时反映到本体 |
| **LLM接口** | 直接调用 | RAG + 本体 Schema 增强 | 防止 LLM 幻觉，保证业务语义准确 |
| **本体分层** | 单一 WORKTASK-MODULE | L0-L3 层级化本体 | 解决规模/异构/稀疏问题 |
| **Agent 框架** | 自研 agent_executor.py | Hermes AIAgent | 完整多轮对话 + 记忆 + Skill 系统 |
| **权限隔离** | 无 | 三层隔离（租户/角色/操作）| 多租户数据安全 |

---

## 十二、当前项目已实现

- ✅ TTL 本体（WorkTask / Product / Category / DiscountTier / ExemptionRule）
- ✅ SPARQL 推理层（`sparql_service.py`）
- ✅ AgentExecutor 单步执行（`agent_executor.py`）
- ✅ System Prompt 数据展示约束（双重渲染修复）
- ✅ ABOX 实例数据（`data/products.json` / `data/tasks.json`）
- ✅ Dashboard 数据 API（`/api/reasoning/products`）
- ✅ TBOX/ABOX 文档分离（`docs/TBOX/` / `docs/ABOX/`）

---

## 十三、项目演进路线

```
阶段 1（当前）: 临期出清单场景跑通
  └→ 单一 WORKTASK-MODULE → 单门店验证

阶段 2: 临期出清场景深化
  └→ L0 核心实体拆分 + 多视图本体
  └→ Fast Path 规则引擎
  └→ 单门店完整数据模型

阶段 3: 扩展到补货/排班/盘点域
  └→ L1 业务域本体（可插拔模块）
  └→ 区域层级（L2）
  └→ Hermes Agent 集成
  └→ RBAC 权限本体

阶段 4: 全量上线
  └→ GraphDB 亿级 triples
  └→ 事件驱动实时更新
  └→ 全链路 RAG + 本体增强
  └→ 三级推理引擎完整实现
```

---

## 十四、实施路径

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

Step 10: L0-L3 分层本体
  - 全局核心本体拆分
  - 多视图本体实现
  - 三级推理引擎 Fast Path
```

---

## 十五、附录

### A. 文件结构

```
store-ontology/
├── CLAUDE.md
├── modules/                          # TBOX（L0-L3 分层）
│   └── module1-worktask/
│       ├── WORKTASK-MODULE.ttl     # 临期打折本体
│       └── RBAC-MODULE.ttl         # 权限本体
├── data/                            # ABOX
│   ├── products.json
│   ├── tasks.json
│   └── permissions.ttl             # 权限实例
├── docs/
│   └── TBOX/
│       ├── ARCHITECTURE.md         # 原项目架构（参考）
│       ├── ENTERPRISE_AGENT_ARCHITECTURE.md  # 原企业级架构（参考）
│       └── INTEGRATED_ARCHITECTURE.md  # 本文档（整合版）★
├── app/
│   └── services/
│       ├── sparql_service.py
│       ├── permission_aware_sparql.py
│       └── reasoning_engine.py     # 三级推理引擎
├── tools/
│   └── store_ontology_tools.py
├── scripts/
│   └── snapshot_abox_to_memory.py
└── ~/.hermes/                       # Hermes 配置
    ├── memories/
    │   ├── MEMORY.md
    │   └── USER.md
    └── skills/
        └── store-brain-skill.md
```

### B. 参考资料

- [Hermes Agent GitHub](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com)
- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/)
- [store-ontology 项目文档](docs/TBOX/)
