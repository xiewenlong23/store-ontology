# 门店大脑（store-ontology）技术设计方案 V1.0

> 编制日期：2026年5月12日
> 编制人：昊晴（AI助手）
> 状态：草稿
> 依据：CopilotKit+LangGraph架构方案（飞书ZE57dJSaaoaza4x2YLNcoSOenAc）+ PRD V1.0
> 用途：指导 Phase 1-7 详细实现

---

## 一、整体架构

### 1.1 架构分层

```
┌────────────────────────────────────────────────────────────────┐
│                        飞书小程序 / Web 前端                      │
│  CopilotKit React SDK ──── identifyUser(user_id@store_id)       │
└─────────────────────────────┬──────────────────────────────────┘
                              │ HTTPS + SSE
┌─────────────────────────────▼──────────────────────────────────┐
│                      FastAPI 自托管服务                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │            CopilotKit Remote Endpoint                    │  │
│  │  CopilotKitRemoteEndpoint(agents=lambda...)             │  │
│  │  properties: { authorization, store_id, role }          │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            │                                   │
│  ┌─────────────────────────▼────────────────────────────────┐  │
│  │              Deep Agents Runtime                          │  │
│  │  create_deep_agent()                                     │  │
│  │  ├── interrupt_on per-tool 配置（折扣审批等）              │  │
│  │  ├── subagents（临期分析/审批/对话隔离）                  │  │
│  │  └── checkpointer=MemorySaver                            │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            │                                   │
│  ┌─────────────────────────▼────────────────────────────────┐  │
│  │              LangGraph StateGraph                         │  │
│  │  复杂场景：精确 interrupt() 断点控制                      │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            │                                   │
│  ┌─────────────────────────▼────────────────────────────────┐  │
│  │                 Skill Registry                            │  │
│  │  动态 allowed-tools 注入 ── config/skills.yaml           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  临期    │  │  折扣    │  │  任务    │  │  商品    │   │
│  │  分析    │  │  审批    │  │  管理    │  │  查询    │   │
│  │  Skill   │  │  Skill   │  │  Skill   │  │  Skill   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────┬──────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌───────────────┐  ┌─────────────────────┐
│    GraphDB      │  │  NebulaGraph  │  │   MCP Server         │
│  TBOX + ABOX   │  │  ABOX(生产)   │  │  ERP / WMS / 飞书   │
│  SPARQL 查询    │  │  JSON(测试)   │  │  langchain-mcp-     │
│                 │  └───────────────┘  │  adapters 接入       │
└─────────────────┘                     └─────────────────────┘

数据持久层：
  PostgreSQL：audit_log / hitl_approval（生产）
  文件：audit_log（测试）
```

### 1.2 技术栈汇总

| 组件 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 前端框架 | CopilotKit React SDK | latest | 对话 UI + 流式响应 |
| 后端框架 | FastAPI | 0.110+ | 自托管服务 |
| Agent 运行时 | Deep Agents SDK | latest | Skill + interrupt_on |
| Agent 编排 | LangGraph | latest | 复杂场景精确控制 |
| SPARQL 引擎 | GraphDB | 10+ | TBOX/ABOX 统一查询 |
| ABOX 生产 | NebulaGraph | 3.x | 图数据库存储 |
| ABOX 测试 | JSON 文件 | - | 开发调试 |
| 审计数据库 | PostgreSQL | 15+ | 结构化审计 |
| MCP 适配器 | langchain-mcp-adapters | latest | 外部系统集成 |
| 可观测性 | LangSmith | - | 全链路追踪 |

---

## 二、项目目录结构

```
store-ontology/
├── .git/
├── .gitignore
│
├── app/                          # FastAPI 主应用
│   ├── __init__.py
│   ├── main.py                    # 入口：FastAPI() + CopilotKit 挂载
│   ├── config.py                  # 配置加载（settings）
│   ├── models.py                  # Pydantic 模型
│   ├── routers/
│   │   ├── agent.py               # /api/copilotkit — CopilotKit Runtime 端点
│   │   ├── admin.py               # /api/admin — 管理接口
│   │   └── health.py              # /health — 健康检查
│   ├── middleware/
│   │   └── auth.py                # JWT / 飞书 Token 验证
│   └── dependencies.py             # FastAPI 依赖注入
│
├── agents/                        # Deep Agents + LangGraph
│   ├── __init__.py
│   ├── deep_agent_factory.py      # create_deep_agent() 工厂
│   ├── state.py                   # AgentState 定义
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── triage.py              # 意图分流节点
│   │   ├── discount_node.py       # 临期折扣分析节点
│   │   ├── task_node.py           # 任务管理节点
│   │   ├── product_node.py        # 商品查询节点
│   │   └── hitl_approval_node.py  # HITL 审批节点
│   ├── edges.py                   # LangGraph 边定义
│   └── interrupts.py              # interrupt_on 配置
│
├── skills/                        # Skill 注册表（Agent Skills 规范）
│   ├── discount-skill/
│   │   ├── SKILL.md               # Skill 元数据
│   │   └── references/
│   │       ├── discount-rules.md   # 折扣规则参考
│   │       └── tbox-schema.md     # TBOX 类定义引用
│   ├── task-skill/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── task-api.md
│   ├── product-skill/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── product-schema.md
│   └── display-skill/
│       ├── SKILL.md
│       └── references/
│           └── display-rules.md
│
├── tools/                         # 工具函数（LangChain @tool）
│   ├── __init__.py
│   ├── registry.py                # 工具注册表
│   ├── sparql_tool.py             # SPARQL 查询工具
│   ├── discount_tools.py           # 折扣计算工具
│   ├── task_tools.py              # 任务 CRUD 工具
│   ├── product_tools.py           # 商品查询工具
│   └── mcp_tools.py              # MCP 外部系统工具
│
├── ontology/                      # TTL 本体（TBOX）
│   ├── tbox/
│   │   ├── modules/
│   │   │   ├── 01-product/
│   │   │   │   └── PRODUCT-MODULE.ttl
│   │   │   ├── 02-discount/
│   │   │   │   └── DISCOUNT-MODULE.ttl
│   │   │   ├── 03-task/
│   │   │   │   └── TASK-MODULE.ttl
│   │   │   ├── 04-employee/
│   │   │   │   └── EMPLOYEE-MODULE.ttl
│   │   │   └── 05-display/
│   │   │       └── DISPLAY-MODULE.ttl
│   │   ├── import_modules.ttl     # 模块导入声明
│   │   └── store-ontology.ttl     # 主本体（整合所有模块）
│   └── abox/
│       ├── products.json         # 测试数据（开发用）
│       ├── tasks.json
│       └── employees.json
│
├── config/
│   ├── skills.yaml                # Skill allowed-tools 动态配置
│   ├── roles.yaml                 # 角色权限矩阵
│   ├── hitl.yaml                  # HITL 审批规则配置
│   └── mcp.yaml                  # MCP Server 连接配置
│
├── mcp_impl/                      # MCP Server 实现（mcp/ 因与 pip 包名冲突而改名）
│   ├── erp_mcp.py                # ERP 商品主数据
│   ├── wms_mcp.py               # WMS 库存
│   └── feishu_mcp.py            # 飞书审批通知
│
├── db/                           # 数据库相关
│   ├── postgres/
│   │   ├── init.sql              # PostgreSQL 表结构
│   │   └── migrations/
│   │       └── 001_init.sql
│   └── nebula/
│       └── init_schema.ngql      # NebulaGraph Schema
│
├── audit/                        # 审计模块
│   ├── __init__.py
│   ├── logger.py                 # structlog 配置
│   └── audit_service.py          # 审计写入服务
│
├── observability/                # 可观测性
│   ├── langsmith.py             # LangSmith 配置
│   └── tracing.py               # 链路追踪工具
│
├── tests/                        # 测试
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/
│   ├── validate_ttl.py           # TTL 语法验证
│   ├── load_abox.py             # ABOX 数据导入
│   └── init_db.py               # 数据库初始化
│
├── Dockerfile
├── docker-compose.yml             # 完整本地开发环境
├── Dockerfile.dev
├── requirements.txt
├── pyproject.toml
├── CLAUDE.md
└── docs/
    ├── STORE-ONTOLOGY-DESIGN-QUESTIONS.md
    └── PRD-STORE-ONTOLOGY-V1.md
```

---

## 三、CopilotKit 前端集成

### 3.1 前端组件结构

```tsx
// src/App.tsx
import { CopilotKit } from "@copilotkit/react";
import { CopilotPopup } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { MainStoreApp } from "./components/MainStoreApp";
import { FeishuTokenProvider } from "./auth/FeishuTokenProvider";

export default function App() {
  return (
    <FeishuTokenProvider>
      <CopilotKit
        runtimeUrl="/api/copilotkit"
        properties={{
          // 飞书身份注入
          authorization: getFeishuToken(),     // Bearer token
          store_id: getCurrentStoreId(),       // 当前门店 ID
          role: getUserRole(),                  // 总部/店长/店员
          employee_id: getEmployeeId(),        // 员工 ID
        }}
      >
        <MainStoreApp />
        <CopilotPopup defaultOpen={false} />
      </CopilotKit>
    </FeishuTokenProvider>
  );
}
```

### 3.2 飞书身份注入流程

```
飞书小程序登录
    ↓
获取飞书 OAuth2 Access Token（user_access_token）
    ↓
前端将 token 注入 CopilotKit properties.authorization
    ↓
CopilotKit 自动转发为 Bearer Token
    ↓
FastAPI /api/copilotkit 端点接收
    ↓
CopilotKitRemoteEndpoint 解析 properties
    ↓
LangGraph Agent Node 通过 config["configurable"]["copilotkit_auth"] 获取用户身份
```

### 3.3 渐进式渲染（Generative UI）

```tsx
// 临期折扣审批卡片（CopilotKit 自动渲染）
import { CopilotCard, CopilotText, CopilotButton } from "@copilotkit/react-ui";

function DiscountApprovalCard({ discountRequest }) {
  return (
    <CopilotCard>
      <CopilotText>
        商品 **{discountRequest.product_name}** 临期 **{discountRequest.days_left}** 天
       建议折扣：**{discountRequest.suggested_rate * 100}%**
      </CopilotText>
      <div style={{ display: "flex", gap: "8px" }}>
        <CopilotButton
          onClick={() => approve(discountRequest.task_id)}
        >
          批准
        </CopilotButton>
        <CopilotButton
          onClick={() => reject(discountRequest.task_id)}
          variant="secondary"
        >
          拒绝
        </CopilotButton>
      </div>
    </CopilotCard>
  );
}
```

### 3.4 飞书推送通知集成

> ⚠️ **遵循 PRD 原则**：HITL 审批时，店长通过飞书收到推送通知（PRD 第六章审批流程）。

CopilotKit 的 HITL 中断触发后，通过 feishu_mcp 将审批请求推送至店长飞书：

```python
# agents/nodes/hitl_approval_node.py
from mcp.feishu_mcp import send_approval_notification

async def hitl_approval_node(state: AgentState, config: RunnableConfig):
    """HITL 审批节点：中断等待店长审批，同时推送飞书通知"""

    discount_task = state["pending_discount_task"]

    # 1. 通过 feishu_mcp 推送飞书通知
    await send_approval_notification(
        approver_store_id=state["store_id"],
        task_id=discount_task["task_id"],
        product_name=discount_task["product_name"],
        suggested_rate=discount_task["suggested_rate"],
        message=f"商品「{discount_task['product_name']}」距过期 {discount_task['days_left']} 天，请审批折扣",
    )

    # 2. 中断等待店长审批
    # CopilotKit 前端自动渲染审批卡片
    interrupt("HITL_APPROVAL_REQUIRED")

    return {"hitl_approver": state["store_id"]}
```

飞书推送内容示例：
```
📋 折扣审批请求

商品：蒙牛特仑苏（750ml）
距过期：5 天
建议折扣：20%

请尽快审批 ✅批准 ❌拒绝
```

推送通过飞书应用消息（IM）发送至店长。店长可在飞书内直接操作，无需切换至门店大脑小程序。

---

## 四、后端 Agent 实现

### 4.1 FastAPI 入口

```python
# app/main.py
from fastapi import FastAPI
from copilotkit import CopilotKitRemoteEndpoint, CopilotKitState
from agents.deep_agent_factory import create_store_brain_agent
from app.config import settings

app = FastAPI(title="门店大脑 API")

# CopilotKit Remote Endpoint
sdk = CopilotKitRemoteEndpoint(
    agents=lambda context: [
        create_store_brain_agent(
            user_id=context["properties"].get("employee_id"),
            store_id=context["properties"].get("store_id"),
            role=context["properties"].get("role"),
            auth_token=context["properties"].get("authorization"),
        )
    ],
)

# 挂载 CopilotKit AG-UI 端点
sdk.mount(app, "/api/copilotkit")

@app.get("/health")
def health():
    return {"status": "ok"}
```

### 4.2 AgentState 定义

```python
# agents/state.py
from copilotkit import CopilotKitState
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AgentState(CopilotKitState):
    """门店大脑 Agent 状态"""

    # 用户上下文
    user_id: str
    store_id: str
    role: str  # 总部/店长/店员

    # 会话上下文
    session_id: str
    current_task_id: Optional[str] = None

    # 业务状态
    pending_discount_task: Optional[dict] = None
    pending_task_approval: Optional[dict] = None

    # HITL 状态
    hitl_required: bool = False
    hitl_approver: Optional[str] = None

    # 分析结果
    analysis_result: Optional[dict] = None

    # 消息历史（CopilotKitState 自带）
    # messages: list[BaseMessage]
```

### 4.3 Deep Agents 工厂

```python
# agents/deep_agent_factory.py
from deepagents import create_deep_agent, FilesystemPermission
from agents.state import AgentState
from agents.interrupts import get_interrupt_config
from tools.registry import get_tools
from config import settings

def create_store_brain_agent(
    user_id: str,
    store_id: str,
    role: str,
    auth_token: str,
) -> DeepAgent:
    """创建门店大脑 Deep Agent"""

    # 加载 Skill
    skills = load_agent_skills("skills/")

    # 构建 Agent
    agent = create_deep_agent(
        model=settings.DEFAULT_MODEL,  # "minimax:MiniMax-M2.7-flash"
        tools=get_tools(store_id=store_id, role=role),
        skills=skills,
        interrupt_on=get_interrupt_config(role),
        checkpointer=MemorySaver(),
        state_schema=AgentState,
        langsmith_tracing=True,
        langsmith_project="store-ontology",
    )

    return agent
```

### 4.4 interrupt_on 配置

```python
# agents/interrupts.py

def get_interrupt_config(role: str) -> dict:
    """根据角色返回 HITL 配置"""

    base_config = {
        # 查询类工具：不需要审批
        "sparql_query_product": False,
        "query_task": False,
        "query_discount_history": False,

        # 写入类工具：需要店长或总部审批
        "create_task": {"allowed_decisions": ["approve", "reject"]},
        # 注意：店员的 create_task 由店长审批；店长可直接执行不需要审批（由角色权限控制）
    }

    if role == "店长":
        # 店长：可审批本店折扣 ≤ 70%
        config = {
            **base_config,
            "execute_discount": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "max_rate": 0.70,
            },
            "approve_discount": {
                "allowed_decisions": ["approve", "edit", "reject"],
            },
        }
    elif role == "总部":
        # 总部：无限制审批
        config = {
            **base_config,
            "execute_discount": {
                "allowed_decisions": ["approve", "edit"],
            },
            "approve_discount": {
                "allowed_decisions": ["approve", "edit"],
            },
        }
    else:
        # 店员：只能发起，不能审批
        config = {
            **base_config,
            "execute_discount": False,  # 店员不能执行折扣
            "approve_discount": False,  # 店员不能审批
        }

    return config
```

### 4.5 LangGraph 复杂场景（备用）

```python
# agents/graph.py — 用于复杂条件分支场景
from langgraph.graph import StateGraph, END
from agents.state import AgentState

def build_store_graph():
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("triage", triage_node)
    graph.add_node("discount", discount_analysis_node)
    graph.add_node("task", task_management_node)
    graph.add_node("product", product_query_node)
    graph.add_node("hitl", hitl_approval_node)
    graph.add_node("execute", execute_action_node)

    # 边
    graph.add_edge("triage", "discount", condition=lambda s: s["intent"] == "discount")
    graph.add_edge("triage", "task", condition=lambda s: s["intent"] == "task")
    graph.add_edge("triage", "product", condition=lambda s: s["intent"] == "query")
    graph.add_edge("discount", "hitl", condition=lambda s: s["hitl_required"])
    graph.add_edge("discount", "execute", condition=lambda s: not s["hitl_required"])
    graph.add_edge("hitl", "execute")
    graph.add_edge("execute", END)

    return graph.compile()
```

---

## 五、Skill 定义

### 5.1 discount-skill/SKILL.md

```markdown
---
name: discount-skill
description: 临期折扣分析与推荐 — 根据商品保质期计算折扣层级并推荐最优折扣率
version: 1.0.0
triggers:
  - "临期"
  - "打折"
  - "折扣"
  - "快过期"
# allowed-tools 由 config/skills.yaml 动态注入，此处不硬编码
# allowed-tools 动态配置见 config/skills.yaml
emitted-events:
  - discount_task_created
  - discount_approved
  - discount_rejected
config:
  tiers:
    T1: { days: 7, rate: 0.20 }
    T2: { days: 5, rate: 0.30 }
    T3: { days: 3, rate: 0.50 }
  exemptions:
    - 进口食品
    - 有机商品
    - 鲜食
references:
  - discount-rules.md
  - tbox-schema.md
```

> ⚠️ **遵循 PRD 原则**：Skill 的 `allowed-tools` 不写死在 SKILL.md，通过 `config/skills.yaml` 动态注入。

### 5.2 task-skill/SKILL.md

```markdown
---
name: task-skill
description: 门店任务管理 — 创建、查询、更新门店工作任务
version: 1.0.0
triggers:
  - "任务"
  - "待办"
  - "工作安排"
# allowed-tools 由 config/skills.yaml 动态注入，此处不硬编码
# allowed-tools 动态配置见 config/skills.yaml
emitted-events:
  - task_created
  - task_assigned
  - task_completed
config:
  status-flow:
    - pending
    - in_progress
    - pending_approval
    - approved
    - rejected
    - executed
    - completed
references:
  - task-api.md
```

> ⚠️ **遵循 PRD 原则**：Task 状态机增加 `rejected` 状态（与 PRD 一致）。

### 5.3 product-skill/SKILL.md

```markdown
---
name: product-skill
description: 商品信息查询 — 查询商品保质期、库存、品类等信息
version: 1.0.0
triggers:
  - "查商品"
  - "保质期"
  - "库存"
  - "这个产品"
# allowed-tools 由 config/skills.yaml 动态注入，此处不硬编码
# allowed-tools 动态配置见 config/skills.yaml
emitted-events: []
config:
  max-results: 20
references:
  - product-schema.md
```

> ⚠️ **遵循 PRD 原则**：Skill 的 `allowed-tools` 不写死在 SKILL.md，通过 `config/skills.yaml` 动态注入。

### 5.4 display-skill/SKILL.md

```markdown
---
name: display-skill
description: 陈列调整建议 — 根据销售数据给出陈列位置调整建议
version: 1.0.0
triggers:
  - "陈列"
  - "摆放"
  - "货架"
  - "调整位置"
# allowed-tools 由 config/skills.yaml 动态注入，此处不硬编码
# allowed-tools 动态配置见 config/skills.yaml
emitted-events:
  - display_suggestion_created
config:
  max-results: 10
references:
  - display-rules.md
```

> ⚠️ **遵循 PRD 原则**：补全 PRD 中提到的第5个 Skill（陈列调整建议）。目录结构已存在，本节补充完整定义。

---

## 六、工具函数（Tools）

### 6.1 SPARQL 查询工具

```python
# tools/sparql_tool.py
from langchain.tools import tool
from rdflib import Graph
from config import settings

@tool
def sparql_query_product(store_id: str, category: str = None, days_until_expiry: int = None) -> str:
    """
    查询门店商品，可按品类和临期天数过滤。
    所有查询必须带 store_id 过滤。
    """
    query = f"""
    PREFIX store: <http://store-ontology.org/ontology/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?product ?name ?category ?shelf_date ?days_left
    WHERE {{
        ?product rdf:type store:Product .
        ?product store:productName ?name .
        ?product store:category ?category .
        ?product store:shelfDate ?shelf_date .
        ?product store:belongsToStore ?store .
        ?store store:storeId "{store_id}" .

        FILTER(?days_left <= {days_until_expiry or 999})
    }}
    ORDER BY ?days_left
    LIMIT 20
    """

    # 连接 GraphDB
    g = Graph()
    g.parse(settings.GRAPHDB_ENDPOINT, format="turtle")
    results = g.query(query)

    return "\n".join([
        f"- {row.name} ({row.category}): 距过期 {row.days_left} 天"
        for row in results
    ])
```

### 6.2 折扣计算工具

```python
# tools/discount_tools.py
from langchain.tools import tool
from datetime import datetime, timedelta

TIER_CONFIG = {
    "T1": {"days": 7, "rate": 0.20},
    "T2": {"days": 5, "rate": 0.30},
    "T3": {"days": 3, "rate": 0.50},
}

EXEMPT_CATEGORIES = ["进口食品", "有机商品", "鲜食"]

@tool
def calculate_discount(product_name: str, category: str, shelf_date: str) -> str:
    """
    计算商品折扣层级。
    返回：tier, suggested_rate, reason
    """
    # 检查豁免
    if category in EXEMPT_CATEGORIES:
        return f"豁免商品（{category}），建议保持原价或小幅折扣"

    # 计算距过期天数
    shelf = datetime.strptime(shelf_date, "%Y-%m-%d")
    days_left = (shelf - datetime.now()).days

    # 确定层级
    for tier, config in TIER_CONFIG.items():
        if days_left <= config["days"]:
            return (
                f"折扣层级：{tier}\n"
                f"建议折扣率：{config['rate']*100}%\n"
                f"距过期天数：{days_left} 天\n"
                f"商品：{product_name}"
            )

    return "商品未达到临期标准，无需折扣"
```

### 6.3 工具注册表

```python
# tools/registry.py
from typing import Optional

TOOL_REGISTRY = {}

def get_tools(store_id: str, role: str) -> list:
    """根据用户角色返回可用工具列表"""

    base_tools = [
        sparql_query_product,
        calculate_discount,
        query_product_detail,
    ]

    if role in ["店长", "总部"]:
        # 有审批权限
        base_tools.extend([
            create_discount_task,
            approve_discount,
            reject_discount,
            create_task,
            update_task_status,
            assign_task,
        ])

    if role == "总部":
        # 总部额外权限
        base_tools.extend([
            update_discount_rule,
            create_employee,
            view_all_stores,
        ])

    return base_tools
```

---

## 七、TBOX 本体设计（TTL）

### 7.1 产品模块（简化版）

```turtle
# ontology/tbox/modules/01-product/PRODUCT-MODULE.ttl
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix store: <http://store-ontology.org/ontology/> .

# 本体元数据
<http://store-ontology.org/ontology/ProductModule>
    a owl:Ontology ;
    rdfs:label "门店产品本体模块"@zh ;
    rdfs:comment "定义商品、品类、门店等核心实体"@zh ;
    owl:versionInfo "1.0.0" ;
    owl:imports <http://store-ontology.org/ontology/EnumsModule> .

# 类定义
store:Product a owl:Class ;
    rdfs:label "商品"@zh ;
    rdfs:comment "零售门店商品实体"@zh .

store:Category a owl:Class ;
    rdfs:label "品类"@zh ;
    rdfs:comment "商品品类分类"@zh .

store:Store a owl:Class ;
    rdfs:label "门店"@zh ;
    rdfs:comment "零售门店"@zh .

# 属性定义
store:productName a owl:DatatypeProperty ;
    rdfs:label "商品名称"@zh ;
    rdfs:domain store:Product ;
    rdfs:range xsd:string .

store:shelfDate a owl:DatatypeProperty ;
    rdfs:label "保质期"@zh ;
    rdfs:domain store:Product ;
    rdfs:range xsd:date .

store:category a owl:ObjectProperty ;
    rdfs:label "所属品类"@zh ;
    rdfs:domain store:Product ;
    rdfs:range store:Category .

store:belongsToStore a owl:ObjectProperty ;
    rdfs:label "所属门店"@zh ;
    rdfs:domain store:Product ;
    rdfs:range store:Store .
```

### 7.2 折扣模块（简化版）

```turtle
# ontology/tbox/modules/02-discount/DISCOUNT-MODULE.ttl
@prefix store: <http://store-ontology.org/ontology/> .

<http://store-ontology.org/ontology/DiscountModule>
    a owl:Ontology ;
    owl:imports <http://store-ontology.org/ontology/ProductModule> .

# 折扣层级枚举（引用枚举模块）
store:DiscountTier a owl:Class ;
    rdfs:label "折扣层级"@zh .

# 折扣任务
store:DiscountTask a owl:Class ;
    rdfs:label "折扣任务"@zh ;
    rdfs:subClassOf store:Task .

store:discountTier a owl:DatatypeProperty ;
    rdfs:label "折扣层级"@zh ;
    rdfs:domain store:DiscountTask ;
    rdfs:range store:DiscountTier .

store:suggestedRate a owl:DatatypeProperty ;
    rdfs:label "建议折扣率"@zh ;
    rdfs:domain store:DiscountTask ;
    rdfs:range xsd:decimal .

store:approvedRate a owl:DatatypeProperty ;
    rdfs:label "审批折扣率"@zh ;
    rdfs:domain store:DiscountTask ;
    rdfs:range xsd:decimal .

store:taskStatus a owl:ObjectProperty ;
    rdfs:label "任务状态"@zh ;
    rdfs:domain store:Task ;
    rdfs:range store:TaskStatus .

# 折扣规则
store:DiscountRule a owl:Class ;
    rdfs:label "折扣规则"@zh .

store:tierT1 a store:DiscountTier ;
    store:tierDays 7 ;
    store:tierRate 0.20 .

store:tierT2 a store:DiscountTier ;
    store:tierDays 5 ;
    store:tierRate 0.30 .

store:tierT3 a store:DiscountTier ;
    store:tierDays 3 ;
    store:tierRate 0.50 .

# 豁免品类
store:ExemptCategory a owl:Class ;
    rdfs:label "豁免品类"@zh .

store:进口食品 a store:ExemptCategory ;
    store:exemptReason "进口食品不参与临期折扣"@zh .

store:有机商品 a store:ExemptCategory ;
    store:exemptReason "有机商品不参与临期折扣"@zh .
```

---

## 八、权限控制实现

### 8.1 角色权限配置

```yaml
# config/roles.yaml
roles:
  总部:
    store_access: all
    skills:
      - discount-skill
      - task-skill
      - product-skill
      - display-skill
    discount_approval_limit: 1.0  # 无限制
    can_update_rules: true
    can_create_employee: true

  店长:
    store_access: own
    skills:
      - discount-skill
      - task-skill
      - product-skill
    discount_approval_limit: 0.70
    can_update_task: true
    can_assign_task: true

  店员:
    store_access: own
    skills:
      - product-skill
    discount_approval_limit: 0.0  # 不能审批
    can_create_discount_request: true
    can_view_task: true
    can_update_own_task: true
```

### 8.2 Auth 中间件

```python
# app/middleware/auth.py
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings

async def verify_token(authorization: str) -> dict:
    """验证飞书 Access Token，返回用户信息"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.replace("Bearer ", "")

    # 调用飞书 API 验证 token
    user_info = await feishu_api.get_user_info(token)

    return {
        "user_id": user_info["user_id"],
        "store_id": user_info["store_id"],
        "role": user_info["role"],  # 从飞书用户信息获取角色
        "employee_id": user_info["employee_id"],
    }
```

---

## 九、MCP Server 实现

### 9.1 ERP MCP Server

```python
# mcp_impl/erp_mcp.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("erp")

@mcp.tool()
async def get_product_info(product_id: str) -> dict:
    """从 ERP 获取商品主数据"""
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            f"{ERP_API}/product/query",
            json={"product_id": product_id},
            headers={"Authorization": f"Bearer {ERP_TOKEN}"},
        )
        data = await resp.json()
        return {
            "product_id": data["product_id"],
            "name": data["product_name"],
            "category": data["category"],
            "cost_price": data["cost_price"],  # 内部使用，不暴露给店员
            "supplier": data["supplier"],        # 内部使用
        }

@mcp.tool()
async def get_all_products(store_id: str) -> list[dict]:
    """获取门店所有商品"""
    ...
```

### 9.2 MCP 接入配置

```yaml
# config/mcp.yaml
mcp_servers:
  erp:
    command: python
    args: ["-m", "mcp.erp_mcp"]
    env:
      ERP_API: "https://erp.internal/api"
      ERP_TOKEN: "${ERP_TOKEN}"

  wms:
    command: python
    args: ["-m", "mcp.wms_mcp"]
    env:
      WMS_API: "https://wms.internal/api"
      WMS_TOKEN: "${WMS_TOKEN}"

  feishu:
    command: python
    args: ["-m", "mcp.feishu_mcp"]
    env:
      FEISHU_APP_ID: "${FEISHU_APP_ID}"
      FEISHU_APP_SECRET: "${FEISHU_APP_SECRET}"
```

---

## 十、数据库 Schema

### 10.1 PostgreSQL（审计）

```sql
-- db/postgres/init.sql

-- 审计日志表
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    action TEXT NOT NULL,          -- agent_call / tool_execute / hitl_approval
    payload JSONB NOT NULL,
    output_hash TEXT NOT NULL,     -- SHA256(payload || secret_key) 防篡改
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_store ON audit_log(store_id);
CREATE INDEX idx_audit_session ON audit_log(session_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- HITL 审批记录表
CREATE TABLE hitl_approval (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id TEXT NOT NULL,
    task_type TEXT NOT NULL,       -- discount / task / display
    approver_id TEXT NOT NULL,
    decision TEXT NOT NULL,        -- approve / edit / reject
    original_params JSONB,
    final_params JSONB,
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_hitl_task ON hitl_approval(task_id);
CREATE INDEX idx_hitl_approver ON hitl_approval(approver_id);
```

### 10.2 NebulaGraph Schema（生产 ABOX）

```cypher
-- db/nebula/init_schema.ngql

CREATE SPACE store_ontology_v1 (partition_num=15, replica_factor=1, vid_type=INT64);

USE store_ontology_v1;

-- 标签定义
CREATE TAG product(
    product_id int64,
    product_name string,
    shelf_date datetime,
    category string,
    store_id int64
);

CREATE TAG store(
    store_id int64,
    store_name string,
    region string
);

CREATE TAG discount_task(
    task_id int64,
    product_id int64,
    discount_tier string,
    suggested_rate double,
    approved_rate double,
    status string,
    created_at timestamp
);

CREATE TAG employee(
    employee_id int64,
    name string,
    role string,
    store_id int64
);

-- 边定义
CREATE EDGE belongs_to();
CREATE EDGE has_task();
CREATE EDGE approved_by();
CREATE EDGE created_by();
```

---

## 十一、Docker Compose 部署

```yaml
# docker-compose.yml
version: "3.9"

services:
  # FastAPI 主服务
  store-brain:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEFAULT_MODEL=minimax:MiniMax-M2.7-flash
      - GRAPHDB_ENDPOINT=http://graphdb:7200/repositories/store-ontology
      - NEO4J_HOST=nebula
      - POSTGRES_HOST=postgres
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
      - FEISHU_APP_ID=${FEISHU_APP_ID}
      - FEISHU_APP_SECRET=${FEISHU_APP_SECRET}
    depends_on:
      - graphdb
      - nebula
      - postgres
    restart: unless-stopped

  # SPARQL 引擎
  graphdb:
    image: ontotext/graphdb:10.4
    ports:
      - "7200:7200"
    volumes:
      - graphdb_data:/var/lib/graphdb
      - ./ontology/tbox:/opt/graphdb/conf/ontology

  # 图数据库（生产）
  nebula:
    image: vesoft/nebula-graph:3.8
    ports:
      - "9669:9669"
    volumes:
      - nebula_data:/var/lib/nebula

  # PostgreSQL（审计）
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=store_ontology
      - POSTGRES_USER=store_user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./db/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql

  # 测试用 JSON ABOX（开发）
  # 无需单独服务，app 直接读文件

volumes:
  graphdb_data:
  nebula_data:
  pg_data:
```

---

## 十二、测试策略

### 12.1 单元测试

```python
# tests/unit/test_discount_tools.py
def test_calculate_discount_t1():
    """T1 层级：7天内过期 → 20%折扣"""
    result = calculate_discount.invoke({
        "product_name": "蒙牛特仑苏",
        "category": "常温奶",
        "shelf_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    })
    assert "T1" in result
    assert "20%" in result

def test_calculate_discount_exempt():
    """豁免商品不打折"""
    result = calculate_discount.invoke({
        "product_name": "日本明治酸奶",
        "category": "进口食品",
        "shelf_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    })
    assert "豁免" in result

# tests/unit/test_sparql_tool.py
def test_sparql_requires_store_id():
    """SPARQL 查询必须包含 store_id 过滤"""
    with pytest.raises(ValidationError):
        sparql_query_product.invoke({
            "store_id": "",  # 空 store_id
            "category": "常温奶"
        })
```

### 12.2 集成测试

```python
# tests/integration/test_agent_flow.py
async def test_discount_flow_with_hitl():
    """完整折扣流程：用户请求 → AI分析 → 店长审批 → 执行"""
    # 1. 模拟店长登录
    token = get_manager_token(store_id="STORE_001")

    # 2. 发起折扣请求
    response = await acclient.post(
        "/api/copilotkit",
        json={
            "message": "这批牛奶还有5天过期，怎么处理",
            "properties": {
                "authorization": f"Bearer {token}",
                "store_id": "STORE_001",
                "role": "店长",
            }
        }
    )

    # 3. 验证 HITL 中断
    result = response.json()
    assert result["interrupt"] == True
    assert result["task_id"] is not None
```

---

## 十三、开发任务分解

> ⚠️ **遵循 PRD 里程碑结构**：与 PRD V1.0 第十二章保持一致。

| Phase | 任务 | 负责 | 工作量 |
|-------|------|------|--------|
| **Phase 1** | CopilotKit 前端集成（飞书小程序） | 前端 | 2周 |
| 1.1 | 飞书登录 + Token 获取 | 前端 | |
| 1.2 | CopilotKit SDK 集成 | 前端 | |
| 1.3 | identifyUser 身份注入 | 前端 | |
| 1.4 | Generative UI 审批卡片 | 前端 | |
| 1.5 | 飞书推送通知集成（CopilotKit → 飞书） | 前端 | |
| **Phase 2** | Deep Agents 后端部署 + 临期折扣 Skill | 后端 | 2周 |
| 2.1 | FastAPI 骨架 + CopilotKitRemoteEndpoint | 后端 | |
| 2.2 | AgentState 定义 | 后端 | |
| 2.3 | create_deep_agent 工厂 | 后端 | |
| 2.4 | interrupt_on 配置 | 后端 | |
| 2.5 | 折扣 Skill（discount-skill）开发 | 后端 | |
| **Phase 3** | GraphDB + TTL 本体 + SPARQL 查询 | 后端 | 2周 |
| 3.1 | GraphDB 部署 | DevOps | |
| 3.2 | TTL 本体编写（4个模块） | 后端 | |
| 3.3 | SPARQL 查询工具 | 后端 | |
| 3.4 | ABOX 数据导入（测试数据） | 后端 | |
| **Phase 4** | HITL 审批流 + 权限矩阵 | 后端 | 1周 |
| 4.1 | HITL 审批节点（hitl_approval_node） | 后端 | |
| 4.2 | 权限矩阵实现（角色 + Skill 粒度） | 后端 | |
| 4.3 | 飞书审批通知推送（feishu_mcp） | 后端 | |
| **Phase 5** | 审计日志 + LangSmith 接入 | 后端 | 1周 |
| 5.1 | PostgreSQL Schema | DevOps | |
| 5.2 | structlog + audit_service | 后端 | |
| 5.3 | LangSmith 接入 | 后端 | |
| **Phase 6** | MCP Server（ERP/WMS）对接 | 后端 | 2周 |
| 6.1 | ERP MCP Server | 后端 | |
| 6.2 | WMS MCP Server | 后端 | |
| 6.3 | langchain-mcp-adapters 接入 | 后端 | |
| **Phase 7** | 生产环境（NebulaGraph + PG）迁移 | DevOps | 1周 |
| 7.1 | NebulaGraph 部署 | DevOps | |
| 7.2 | Docker Compose 生产配置 | DevOps | |
| 7.3 | 端到端测试 | 全员 | |

**预计总工期**：11 周（约 3 个月），与 PRD V1.0 保持一致。

---

## 十四、参考文档

- [CopilotKit 官方文档](https://docs.copilotkit.ai/)
- [LangGraph 官方文档](https://docs.langchain.com/oss/python/langgraph/)
- [Deep Agents 官方文档](https://docs.langchain.com/oss/python/deep-agents/)
- [CopilotKit+LangGraph架构方案](https://www.feishu.cn/docx/ZE57dJSaaoaza4x2YLNcoSOenAc)
- [PRD V1.0](./PRD-STORE-ONTOLOGY-V1.md)
- [设计问题清单](./STORE-ONTOLOGY-DESIGN-QUESTIONS.md)
