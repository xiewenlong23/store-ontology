# 门店本体企业 Agent — 日志与审计架构设计

> 项目：store-ontology（门店大脑 AI 原生应用）
> 版本：v1.0
> 日期：2026-04-23
> 状态：规划中

---

## 一、背景与设计目标

### 1.1 为什么需要审计

门店大脑是一个多租户、多角色的企业级 AI 应用，涉及到：

- **折扣审批**：店长审批 45% 折扣（超出正常区间）
- **权限变更**：总部调整某门店店员的角色
- **本体修改**：TTL 本体的类/属性/规则变更
- **数据导出**：门店经营数据被导出

这些操作都需要完整的审计日志，满足：
- 合规要求（零售行业数据监管）
- 问题溯源（出了事能查到谁在什么时候做了什么）
- 成本分析（Token 消耗、API 调用统计）

### 1.2 设计目标

```
┌─────────────────────────────────────────────────────────────┐
│  ① 全链路可追溯  — 每个操作都能找到对应的用户、时间、结果 │
│  ② 三层审计覆盖  — 技术层 + 业务层 + 合规层              │
│  ③ 本体化存储    — 审计事件存入 ABOX，支持 SPARQL 查询   │
│  ④ Hermes 原生  — 基于 Hermes Event Hooks 实现          │
│  ⑤ 低侵入扩展    — 不改变 Hermes 核心代码                │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、三层审计架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 技术审计层（Hermes 内置 + 增强）                │
│  ─────────────────────────────────────────────────────────  │
│  Session Storage (SQLite ~/.hermes/state.db)               │
│  + Gateway Event Hooks (agent:start/end/step)             │
│  记录：Token 消耗、API 延迟、工具调用、消息历史           │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 业务事件层（本体感知 Hooks）                   │
│  ─────────────────────────────────────────────────────────  │
│  自定义 Event Hooks 拦截业务操作                         │
│  记录：折扣审批、任务创建、本体查询、权限变更            │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 合规审计层（RBAC 审计本体）                    │
│  ─────────────────────────────────────────────────────────  │
│  ABOX 记录权限变更、合规操作、敏感数据访问               │
│  记录：谁在什么时间做了什么操作，结果如何               │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、Layer 1 — 技术审计层

### 3.1 Hermes Session Storage

Hermes 使用 SQLite 数据库（`~/.hermes/state.db`）持久化会话数据：

```
~/.hermes/state.db (SQLite, WAL mode)
├── sessions        — Session 元数据、Token 计数、计费
├── messages       — 每个 Session 的完整消息历史
├── messages_fts   — FTS5 虚拟表，用于全文搜索
└── schema_version — 单行表，跟踪迁移状态
```

**Sessions 表核心字段：**

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,           -- cli / telegram / discord / feishu
    user_id TEXT,
    model TEXT,
    model_config TEXT,
    system_prompt TEXT,
    parent_session_id TEXT,          -- 压缩触发的会话分裂链
    started_at REAL NOT NULL,
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    billing_provider TEXT,
    billing_base_url TEXT,
    billing_mode TEXT,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    cost_status TEXT,
    cost_source TEXT,
    pricing_version TEXT,
    title TEXT,
    tenant_id TEXT,                  -- 【新增】门店ID
    store_region TEXT,              -- 【新增】区域
    session_type TEXT,              -- 【新增】dialog / task / cron
    action_type TEXT                -- 【新增】expiry_check / discount_approve / ...
);
```

**Messages 表核心字段：**

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,             -- user / assistant / system / tool
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,                -- JSON 序列化的工具调用列表
    tool_name TEXT,
    timestamp REAL NOT NULL,        -- Unix epoch
    token_count INTEGER,
    finish_reason TEXT,
    reasoning TEXT,
    reasoning_details TEXT,         -- JSON
    codex_reasoning_items TEXT     -- JSON
);
```

### 3.2 Hermes Gateway Hook 配置

**目录结构：**

```
~/.hermes/hooks/
└── store-ontology-audit/
    ├── HOOK.yaml
    └── handler.py
```

**HOOK.yaml：**

```yaml
name: store-ontology-audit
description: 门店大脑技术审计日志
events:
  - agent:start
  - agent:end
  - agent:step
  - tool:call
  - tool:result
  - error:*
```

**handler.py：**

```python
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_DIR = Path.home() / ".hermes" / "hooks" / "store-ontology-audit"
LOG_FILE = LOG_DIR / "technical_audit.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)


async def handle(event_type: str, context: dict):
    """记录所有 Agent 技术活动"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": "INFO",
        "event": event_type,
        "session_id": context.get("session_id"),
        "user_id": context.get("user_id"),
        "message": context.get("message", ""),
    }

    # 工具调用时记录完整上下文
    if event_type == "tool:call":
        entry.update({
            "tool_name": context.get("tool_name"),
            "tool_args": context.get("tool_args"),
            "tenant_id": context.get("tenant_id"),
        })

    # 错误事件
    if event_type.startswith("error:"):
        entry["level"] = "ERROR"
        entry["error_detail"] = context.get("error")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

### 3.3 技术审计日志格式

```jsonl
{"timestamp": "2026-04-23T14:30:00.123", "level": "INFO", "event": "agent:start", "session_id": "sess_001", "user_id": "feishu_user_001", "tenant_id": "STORE_001"}
{"timestamp": "2026-04-23T14:30:01.456", "level": "INFO", "event": "tool:call", "session_id": "sess_001", "tool_name": "sparql_query", "tool_args": {"query": "SELECT ?product ..."}, "tenant_id": "STORE_001"}
{"timestamp": "2026-04-23T14:30:02.789", "level": "INFO", "event": "tool:result", "session_id": "sess_001", "tool_name": "sparql_query", "result": "12 items returned"}
{"timestamp": "2026-04-23T14:30:05.012", "level": "ERROR", "event": "error:timeout", "session_id": "sess_001", "error_detail": "SPARQL query timeout after 30s"}
{"timestamp": "2026-04-23T14:30:10.345", "level": "INFO", "event": "agent:end", "session_id": "sess_001", "end_reason": "completed"}
```

---

## 四、Layer 2 — 业务事件层

### 4.1 业务事件类型

| 事件 | 触发时机 | 记录内容 |
|------|---------|---------|
| `ontology:query` | SPARQL 查询执行 | 查询内容、返回条数、耗时 |
| `discount:approve` | 折扣审批通过 | 商品、折扣率、审批人、有效期 |
| `discount:reject` | 折扣审批拒绝 | 商品、申请人、拒绝原因 |
| `discount:request` | 折扣申请提交 | 商品、申请折扣率、申请人 |
| `task:create` | 任务创建 | 任务类型、关联商品、优先级 |
| `task:complete` | 任务完成 | 任务ID、完成时间、操作人 |
| `task:cancel` | 任务取消 | 任务ID、取消原因、操作人 |
| `permission:check` | 权限校验 | 用户、权限点、结果（通过/拒绝）|
| `permission:change` | 权限变更 | 变更者、被变更者、旧角色、新角色 |
| `expiry:scan` | 临期扫描执行 | 扫描时间、临期商品数量、处理建议 |
| `本体:modify` | TTL 本体变更 | 变更类型（增/删/改）、变更内容 |

### 4.2 业务事件 Hook 配置

**目录结构：**

```
~/.hermes/hooks/
└── store-ontology-business/
    ├── HOOK.yaml
    └── handler.py
```

**HOOK.yaml：**

```yaml
name: store-ontology-business
description: 门店大脑业务事件审计
events:
  - ontology:*
  - discount:*
  - task:*
  - permission:*
  - expiry:*
```

**handler.py：**

```python
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

BUSINESS_LOG = Path.home() / ".hermes" / "hooks" / "store-ontology-business"
BUSINESS_LOG.mkdir(parents=True, exist_ok=True)
LOG_FILE = BUSINESS_LOG / "business_audit.jsonl"


async def handle(event_type: str, context: dict):
    """记录业务操作事件"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "tenant_id": context.get("tenant_id"),      # 门店ID
        "user_id": context.get("user_id"),          # 操作用户
        "action": context.get("action"),            # 操作类型
        "target": context.get("target"),             # 操作对象
        "result": context.get("result"),            # 操作结果
        "detail": context.get("detail", {}),       # 详细信息
    }

    # 折扣相关事件额外记录
    if event_type.startswith("discount:"):
        entry["discount_rate"] = context.get("discount_rate")
        entry["product_name"] = context.get("product_name")
        entry["is_premium"] = context.get("is_premium", False)

    # 权限变更事件额外记录
    if event_type == "permission:change":
        entry["old_role"] = context.get("old_role")
        entry["new_role"] = context.get("new_role")
        entry["changed_by"] = context.get("changed_by")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

### 4.3 业务事件触发方式

业务事件通过工具层或中间件触发：

```python
# 在 store_ontology_tools.py 中触发审计事件

def trigger_business_event(event_type: str, context: dict):
    """触发业务审计事件"""
    # 通过 Hermes 的内部事件系统发送
    # 实际实现依赖 Hermes 的事件发布机制
    pass


def approve_discount(product_name: str, discount_rate: float, task_id: str = None) -> str:
    """审批折扣"""
    user_id = get_current_user_id(task_id)
    perms = get_user_permissions(user_id)

    # 权限检查
    if discount_rate > 0.30 and "canApprove" not in perms["permissions"]:
        trigger_business_event("discount:reject", {
            "user_id": user_id,
            "product_name": product_name,
            "discount_rate": discount_rate,
            "reason": "权限不足",
        })
        return json.dumps({"error": "权限不足，需要 canApprove 权限"})

    # 执行审批
    result = do_approve_discount(product_name, discount_rate)

    # 记录审计事件
    trigger_business_event("discount:approve", {
        "user_id": user_id,
        "tenant_id": perms["tenant_id"],
        "product_name": product_name,
        "discount_rate": discount_rate,
        "is_premium": discount_rate > 0.30,
        "result": "APPROVED",
    })

    return json.dumps({"status": "approved", "product": product_name})
```

---

## 五、Layer 3 — 合规审计层（RBAC 审计本体）

### 5.1 审计本体（TBOX）

```turtle
@prefix store: <http://store-ontology.example.org/> .
@prefix audit: <http://store-ontology.example.org/audit/> .
@prefix owl:   <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .

# ── 审计事件类 ──────────────────────────────────────────────
audit:AuditEvent a rdfs:Class ; rdfs:label "审计事件" .

# ── 审计事件属性 ────────────────────────────────────────────
audit:eventId a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "事件ID" .

audit:eventType a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "事件类型" .

audit:eventTime a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:dateTime ;
    rdfs:label "事件时间" .

audit:tenantId a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "门店ID" .

audit:userId a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "操作用户ID" .

audit:action a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "操作动作" .

audit:targetEntity a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "目标实体" .

audit:result a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "操作结果" .

audit:detail a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "详细信息（JSON）" .

audit:ipAddress a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "IP地址" .

audit:sessionId a owl:DatatypeProperty ;
    rdfs:domain audit:AuditEvent ;
    rdfs:range xsd:string ;
    rdfs:label "会话ID" .

# ── 事件类型枚举 ────────────────────────────────────────────
audit:DiscountApproved a audit:AuditEvent ; rdfs:label "折扣审批通过" .
audit:DiscountRejected a audit:AuditEvent ; rdfs:label "折扣审批拒绝" .
audit:PremiumDiscountApproved a audit:AuditEvent ; rdfs:label "高级折扣审批通过" .
audit:PermissionChanged a audit:AuditEvent ; rdfs:label "权限变更" .
audit:RoleAssigned a audit:AuditEvent ; rdfs:label "角色分配" .
audit:OntologyModified a audit:AuditEvent ; rdfs:label "本体修改" .
audit:DataExported a audit:AuditEvent ; rdfs:label "数据导出" .
audit:LoginFailed a audit:AuditEvent ; rdfs:label "登录失败" .
audit:ExpireScanExecuted a audit:AuditEvent ; rdfs:label "临期扫描执行" .
audit:TaskCreated a audit:AuditEvent ; rdfs:label "任务创建" .
audit:TaskCompleted a audit:AuditEvent ; rdfs:label "任务完成" .
```

### 5.2 审计事件 ABOX 示例

```turtle
# ── 高级折扣审批审计 ──────────────────────────────────────────
audit:EVT-20260423-001 a audit:PremiumDiscountApproved ;
    audit:eventId "EVT-20260423-001" ;
    audit:eventTime "2026-04-23T14:30:00"^^xsd:dateTime ;
    audit:tenantId "STORE_001" ;
    audit:userId "feishu_user_001" ;
    audit:action "approve_discount" ;
    audit:targetEntity "嫩豆腐" ;
    audit:result "APPROVED" ;
    audit:sessionId "sess_abc123" ;
    audit:detail """{"discount_rate": 0.45, "original_rate": 0.30, "approver_name": "张三", "reason": "临期出清", "valid_until": "2026-04-25"}""" .

# ── 普通折扣申请审计 ─────────────────────────────────────────
audit:EVT-20260423-002 a audit:DiscountApproved ;
    audit:eventId "EVT-20260423-002" ;
    audit:eventTime "2026-04-23T14:35:00"^^xsd:dateTime ;
    audit:tenantId "STORE_001" ;
    audit:userId "feishu_user_002" ;
    audit:action "approve_discount" ;
    audit:targetEntity "日式味噌" ;
    audit:result "APPROVED" ;
    audit:detail """{"discount_rate": 0.25, "approver_name": "张三"}""" .

# ── 权限变更审计 ─────────────────────────────────────────────
audit:EVT-20260423-003 a audit:PermissionChanged ;
    audit:eventId "EVT-20260423-003" ;
    audit:eventTime "2026-04-23T15:00:00"^^xsd:dateTime ;
    audit:tenantId "STORE_001" ;
    audit:userId "feishu_user_005" ;
    audit:action "assign_role" ;
    audit:targetEntity "feishu_user_005" ;
    audit:result "ROLE_CHANGED" ;
    audit:detail """{"old_role": "StoreClerk", "new_role": "StoreManager", "changed_by": "feishu_user_001", "changed_by_name": "张三"}""" .

# ── 本体修改审计 ─────────────────────────────────────────────
audit:EVT-20260423-004 a audit:OntologyModified ;
    audit:eventId "EVT-20260423-004" ;
    audit:eventTime "2026-04-23T16:00:00"^^xsd:dateTime ;
    audit:tenantId "STORE_001" ;
    audit:userId "system" ;
    audit:action "ttl_modify" ;
    audit:targetEntity "WORKTASK-MODULE.ttl" ;
    audit:result "MODIFIED" ;
    audit:detail """{"change_type": "ADD", "entity": "store:NearExpiryRule", "entity_uri": "http://store-ontology.example.org/NearExpiryRule", "before": "", "after": "rule definition", "operator": "AI Agent"}""" .

# ── 临期扫描执行审计 ─────────────────────────────────────────
audit:EVT-20260423-005 a audit:ExpireScanExecuted ;
    audit:eventId "EVT-20260423-005" ;
    audit:eventTime "2026-04-23T09:00:00"^^xsd:dateTime ;
    audit:tenantId "STORE_001" ;
    audit:userId "system" ;
    audit:action "scan_expiry" ;
    audit:targetEntity "STORE_001" ;
    audit:result "COMPLETED" ;
    audit:detail """{"near_expiry_count": 15, "products": ["嫩豆腐", "日式味噌", "..."], "scan_duration_ms": 234}""" .

# ── 登录失败审计 ─────────────────────────────────────────────
audit:EVT-20260423-006 a audit:LoginFailed ;
    audit:eventId "EVT-20260423-006" ;
    audit:eventTime "2026-04-23T08:00:00"^^xsd:dateTime ;
    audit:tenantId "STORE_001" ;
    audit:userId "feishu_user_999" ;
    audit:action "login" ;
    audit:result "FAILED" ;
    audit:ipAddress "192.168.1.100" ;
    audit:detail """{"reason": "invalid_token", "attempt_count": 3}""" .
```

---

## 六、审计查询接口

### 6.1 折扣审批查询

```sparql
PREFIX audit: <http://store-ontology.example.org/audit/>
PREFIX store: <http://store-ontology.example.org/>

# 查找某门店某时间范围内的所有折扣审批记录
SELECT ?eventId ?eventTime ?userId ?product ?discountRate ?result ?detail
WHERE {
  ?event a audit:DiscountApproved , audit:DiscountRejected ;
         audit:eventId ?eventId ;
         audit:eventTime ?eventTime ;
         audit:userId ?userId ;
         audit:targetEntity ?product ;
         audit:result ?result ;
         audit:detail ?detail .
  FILTER(?eventTime >= "2026-04-01T00:00:00"^^xsd:dateTime)
  FILTER(?eventTime < "2026-05-01T00:00:00"^^xsd:dateTime)
}
ORDER BY DESC(?eventTime)
```

### 6.2 高级折扣审批查询（超出正常区间）

```sparql
PREFIX audit: <http://store-ontology.example.org/audit/>

# 查找所有高级折扣（>30%）审批记录
SELECT ?eventId ?eventTime ?userId ?product ?detail
WHERE {
  ?event a audit:PremiumDiscountApproved ;
         audit:eventId ?eventId ;
         audit:eventTime ?eventTime ;
         audit:userId ?userId ;
         audit:targetEntity ?product ;
         audit:detail ?detail .
}
ORDER BY DESC(?eventTime)
LIMIT 100
```

### 6.3 权限变更查询

```sparql
PREFIX audit: <http://store-ontology.example.org/audit/>

# 查找某门店的权限变更历史
SELECT ?eventId ?eventTime ?targetUser ?oldRole ?newRole ?changedBy
WHERE {
  ?event a audit:PermissionChanged ;
         audit:eventId ?eventId ;
         audit:eventTime ?eventTime ;
         audit:targetEntity ?targetUser ;
         audit:detail ?detail .
  # JSON 提取需要在应用层处理
}
ORDER BY DESC(?eventTime)
```

### 6.4 本体修改追溯

```sparql
PREFIX audit: <http://store-ontology.example.org/audit/>

# 查找所有本体修改记录
SELECT ?eventId ?eventTime ?action ?targetEntity ?detail
WHERE {
  ?event a audit:OntologyModified ;
         audit:eventId ?eventId ;
         audit:eventTime ?eventTime ;
         audit:action ?action ;
         audit:targetEntity ?targetEntity ;
         audit:detail ?detail .
}
ORDER BY DESC(?eventTime)
```

### 6.5 登录失败查询（安全告警）

```sparql
PREFIX audit: <http://store-ontology.example.org/audit/>

# 查找某用户在某时间段内的登录失败记录
SELECT ?eventId ?eventTime ?userId ?ipAddress ?detail
WHERE {
  ?event a audit:LoginFailed ;
         audit:eventId ?eventId ;
         audit:eventTime ?eventTime ;
         audit:userId ?userId ;
         audit:ipAddress ?ipAddress ;
         audit:detail ?detail .
  FILTER(?eventTime >= "2026-04-23T00:00:00"^^xsd:dateTime)
}
ORDER BY ?userId ?eventTime
```

---

## 七、日志流转架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户操作层                                │
│   飞书 Bot / Web / CLI → Hermes AIAgent → 本体工具执行          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌───────────┐    ┌────────────┐   ┌────────────┐
   │ Layer 1   │    │ Layer 2    │   │ Layer 3    │
   │ 技术审计   │    │ 业务事件    │   │ 合规审计   │
   │           │    │            │   │            │
   │ Gateway   │    │ Gateway    │   │ ABOX       │
   │ Hooks     │    │ Hooks      │   │ 审计本体   │
   │           │    │            │   │            │
   │ 技术日志   │    │ 业务日志   │   │ 审计事件   │
   │ .jsonl    │    │ .jsonl     │   │ TTL        │
   └─────┬─────┘    └─────┬──────┘   └─────┬─────┘
         │                 │                 │
         ▼                 ▼                 ▼
   ~/.hermes/hooks/  ~/.hermes/hooks/   modules/
   store-ontology-   store-ontology-    audit/
   audit/            business/           AUDIT-MODULE.ttl
   technical_audit   business_audit     (TBOX)
   .jsonl           .jsonl              data/audit/
                                        audit_events.ttl
                                        (ABOX)
         │                 │                 │
         └────────┬────────┴─────────────────┘
                  ▼
           ┌─────────────┐
           │  审计服务   │
           │  Audit      │
           │  Service    │
           │             │
           │ SPARQL 查询 │
           └──────┬──────┘
                  │
                  ▼
           ┌─────────────┐
           │  报表生成   │
           │  Cron Job   │
           │  + 飞书推送 │
           └─────────────┘
```

---

## 八、文件结构

```
store-ontology/
├── modules/
│   └── module1-worktask/
│       ├── WORKTASK-MODULE.ttl      ← 临期打折本体
│       └── RBAC-MODULE.ttl          ← 权限本体
│   └── audit/
│       └── AUDIT-MODULE.ttl         ← 审计本体（TBOX）★
│
├── data/
│   └── audit/
│       ├── audit_events.ttl         ← 合规审计事件（ABOX）★
│       └── .gitkeep
│
├── app/
│   └── services/
│       ├── audit_service.py         ← 审计服务（记录 + 查询）★
│       ├── sparql_service.py
│       └── permission_aware_sparql.py
│
└── hooks/                           ← 项目级 Hooks（非 ~/.hermes/hooks/）
    ├── technical_audit/
    │   ├── HOOK.yaml
    │   └── handler.py
    └── business_audit/
        ├── HOOK.yaml
        └── handler.py

~/.hermes/hooks/                      ← 全局 Hooks（用户级）
└── store-ontology-audit/
    ├── HOOK.yaml
    └── handler.py
```

---

## 九、与 Hermes 原生能力的对应关系

| store-ontology 审计需求 | Hermes 原生能力 | 对应关系 |
|------------------------|----------------|---------|
| 记录工具调用 | `tool:call` / `tool:result` 事件 | Gateway Hooks |
| 记录会话开始/结束 | `agent:start` / `agent:end` 事件 | Gateway Hooks |
| 记录消息历史 | `sessions` + `messages` 表 | Session Storage |
| 记录 Token 消耗 | `sessions.input_tokens` 等列 | Session Storage |
| 记录推理详情 | `messages.reasoning` 列 | Session Storage |
| 记录业务操作 | 自定义 Hooks 拦截工具层 | Plugin Hooks |
| 权限变更追溯 | RBAC 本体 + ABOX | store-ontology 自建 |
| 合规审计查询 | SPARQL 查询 | 本体层 |
| 审计报告生成 | `cron` 定时任务 + 报表技能 | Scheduled Tasks |
| 会话链路追踪 | `parent_session_id` 链 | Session Storage |
| 平台来源过滤 | `sessions.source` 列 | Session Storage |

---

## 十、审计服务实现

```python
# app/services/audit_service.py

import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

AUDIT_NS = "http://store-ontology.example.org/audit/"
STORE_NS = "http://store-ontology.example.org/"


class AuditService:
    """门店大脑审计服务"""

    def __init__(self, audit_ttl_path: str, ttl_module_path: str):
        self.graph = Graph()
        # 加载审计本体
        self.graph.parse(ttl_module_path, format="turtle")
        # 加载已有审计事件
        if Path(audit_ttl_path).exists():
            self.graph.parse(audit_ttl_path, format="turtle")
        self.audit_ttl_path = audit_ttl_path

    def log_event(
        self,
        event_type: str,
        tenant_id: str,
        user_id: str,
        action: str,
        target: str,
        result: str,
        detail: Optional[Dict] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """记录一条审计事件"""
        event_id = f"EVT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(self.graph)}"

        event_uri = URIRef(f"{AUDIT_NS}{event_id}")

        # 类型
        event_class = URIRef(f"{AUDIT_NS}{event_type}")
        self.graph.add((event_uri, RDF.type, event_class))

        # 基本属性
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}eventId"), Literal(event_id)))
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}eventTime"), Literal(datetime.now())))
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}tenantId"), Literal(tenant_id)))
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}userId"), Literal(user_id)))
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}action"), Literal(action)))
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}targetEntity"), Literal(target)))
        self.graph.add((event_uri, URIRef(f"{AUDIT_NS}result"), Literal(result)))

        if detail:
            self.graph.add((
                event_uri,
                URIRef(f"{AUDIT_NS}detail"),
                Literal(json.dumps(detail, ensure_ascii=False))
            ))

        if session_id:
            self.graph.add((event_uri, URIRef(f"{AUDIT_NS}sessionId"), Literal(session_id)))

        if ip_address:
            self.graph.add((event_uri, URIRef(f"{AUDIT_NS}ipAddress"), Literal(ip_address)))

        # 持久化
        self._persist()
        return event_id

    def query_events(
        self,
        event_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """查询审计事件"""
        query = f"""
        PREFIX audit: <{AUDIT_NS}>
        PREFIX store: <{STORE_NS}>
        SELECT ?eventId ?eventTime ?userId ?action ?target ?result ?detail
        WHERE {{
          ?event a ?type ;
                 audit:eventId ?eventId ;
                 audit:eventTime ?eventTime ;
                 audit:userId ?userId ;
                 audit:action ?action ;
                 audit:targetEntity ?target ;
                 audit:result ?result .
          OPTIONAL {{ ?event audit:detail ?detail . }}
        """

        filters = []
        if event_type:
            filters.append(f'FILTER(?type = audit:{event_type})')
        if tenant_id:
            filters.append(f'FILTER(?tenantId = "{tenant_id}")')
        if start_time:
            filters.append(f'FILTER(?eventTime >= "{start_time.isoformat()}"^^xsd:dateTime)')
        if end_time:
            filters.append(f'FILTER(?eventTime < "{end_time.isoformat()}"^^xsd:dateTime)')
        if user_id:
            filters.append(f'FILTER(?userId = "{user_id}")')

        if filters:
            query += "  FILTER(" + " && ".join(filters) + ")\n"

        query += f"}}\nORDER BY DESC(?eventTime)\nLIMIT {limit}"

        results = self.graph.query(query)
        return [
            {
                "eventId": str(row.eventId),
                "eventTime": row.eventTime,
                "userId": str(row.userId),
                "action": str(row.action),
                "target": str(row.target),
                "result": str(row.result),
                "detail": json.loads(row.detail) if row.detail else None,
            }
            for row in results
        ]

    def _persist(self):
        """持久化到 TTL 文件"""
        self.graph.serialize(self.audit_ttl_path, format="turtle")
```

---

## 十一、审计报告 Cron Job

```yaml
# ~/.hermes/crontab 中配置
人才网审计报告:
  cron: "0 9 * * *"  # 每天早上 9 点
  prompt: |
    生成昨日审计报告，包含：
    1. 折扣审批统计（通过/拒绝数量、平均折扣率、高级折扣占比）
    2. 权限变更记录
    3. 登录失败告警（超过 3 次的账号）
    4. Token 消耗统计
    5. 临期扫描执行情况

    数据来源：
    - 技术审计日志：~/.hermes/hooks/store-ontology-audit/technical_audit.jsonl
    - 业务审计日志：~/.hermes/hooks/store-ontology-business/business_audit.jsonl
    - 合规审计本体：store-ontology/data/audit/audit_events.ttl

    输出格式：
    - 飞书消息卡片
    - 推送给总部管理员（feishu_user_004）
```

---

## 十二、参考资料

- [Hermes Agent — Session Storage](https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage)
- [Hermes Agent — Event Hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)
- [Hermes Agent — Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)
- [Hermes Agent — Scheduled Tasks (Cron)](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
