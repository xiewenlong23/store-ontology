# 门店大脑（store-ontology）PRD V1.0

> 编制日期：2026年5月12日
> 编制人：昊晴（AI助手）
> 状态：草稿（待确认）
> 基于：D1-D10 决策 + 合理默认推断

---

## 一、项目概述

### 1.1 项目名称与定位

**项目名称**：门店大脑（store-ontology）

**一句话定位**：基于 CopilotKit 前端 + Deep Agents/LangGraph 后端 + 本体（TBOX/ABOX）的零售门店 AI 助手，通过自然语言对话完成临期折扣决策、任务派发和商品查询。

**核心用户**：门店店长 + 店员（面向员工，非顾客）

**核心场景优先级**：
1. **P0** 临期折扣决策（AI 推荐 + 店长审批）
2. **P1** 门店任务管理（任务创建/派发/状态追踪）
3. **P1** 商品信息查询（保质期/库存/品类）

### 1.2 技术选型结论

| 层级 | 选型 | 依据 |
|------|------|------|
| 前端 | CopilotKit | D1 |
| 后端 Agent | Deep Agents + LangGraph 混用 | D2 |
| 部署 | FastAPI 自托管 | D3 |
| ABOX 生产 | NebulaGraph | D4 |
| ABOX 测试 | JSON 文件 | D4 |
| SPARQL 引擎 | GraphDB | D5 |
| 审批人 | 店长 | D6 |
| 可观测性 | LangSmith 接入 | D7 |
| 审计 生产 | PostgreSQL | D8 |
| 审计 测试 | 文件 | D8 |
| 外部系统 | MCP Server | D9 |
| 多租户 | 共享实例 | D10 |

### 1.3 成功指标

- 临期折扣推荐准确率 > 90%（与人工判断对比）
- 单次对话响应时间 < 3秒（P99）
- 任务完成率 > 85%（7日内）
- 试点门店：1-3 家

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        飞书小程序 / Web                       │
│  <CopilotKit前端>  ──── SSE 流式 ──── CopilotKit Runtime     │
│  identifyUser: user_id@store_id                            │
└────────────────────┬────────────────────────────────────────┘
                     │ AG-UI 协议（SSE）
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 自托管服务                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              CopilotKit Remote Endpoint                │  │
│  │  agents=lambda context: [LangGraphAgent(...)]        │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │              Deep Agents + LangGraph                  │  │
│  │  • create_deep_agent()                               │  │
│  │  • interrupt_on per-tool 配置                        │  │
│  │  • StateGraph 精确编排（复杂场景）                    │  │
│  └─────────────────────────┬────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │                   Skill Registry                       │  │
│  │  SKILL.md 格式 ── allowed-tools ── 动态配置          │  │
│  └─────────────────────────┬────────────────────────────┘  │
│                            │                                │
│  ┌──────────────┐  ┌──────▼──────┐  ┌──────────────────┐  │
│  │ 临期折扣Skill │  │ 任务管理Skill│  │ 商品查询Skill    │  │
│  └──────────────┘  └─────────────┘  └──────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌─────────────────┐    ┌─────────────────────────────────┐
│  GraphDB        │    │  MCP Server（ERP/WMS/CRM）       │
│  TBOX + ABOX   │    │  langchain-mcp-adapters 接入     │
│  SPARQL 查询   │    └─────────────────────────────────┘
│  store_id 过滤 │
└─────────────────┘

数据层：
  生产：NebulaGraph（ABOX）+ GraphDB（TBOX）
  测试：JSON 文件（ABOX）+ TTL 文件（TBOX）
  审计：PostgreSQL（生产）/ 文件（测试）
```

### 2.2 部署架构

- **形式**：Docker Compose 单节点（初期）
- **服务**：FastAPI + GraphDB + NebulaGraph + PostgreSQL
- **扩展**：后续可迁移 K8s

---

## 三、TBOX 本体设计

### 3.1 文件格式

- **格式**：TTL（Turtle），OWL2 DL 子集
- **位置**：`/ontology/tbox/modules/`
- **验证工具**：rapper（CLI）

### 3.2 核心本体模块

| 模块 | 类 | 核心属性 | 业务规则 |
|------|-----|---------|---------|
| **临期折扣模块** | DiscountRule, ExemptProduct, DiscountTask | rule_id, tier, discount_rate, exemption_flag | T1/T2/T3 折扣率、豁免条件 |
| **任务模块** | WorkTask, TaskAssignment | task_id, store_id, assignee, status, deadline | pending→approved→executed 状态机 |
| **商品模块** | Product, Category | product_id, name, category, shelf_date | 保质期计算 |
| **员工模块** | Employee, Role | employee_id, role, store_id | 总部/店长/店员角色 |

### 3.3 业务规则 vs Skill 代码划分

| 归属 | 内容 |
|------|------|
| **TBOX（本体层）** | 折扣层级定义（T1/T2/T3）、豁免商品列表、审批流程状态机、品类从属关系 |
| **Skill 代码** | SPARQL 查询执行、LLM 推理逻辑、外部 API 调用、计算公式实现 |

---

## 四、ABOX 数据设计

### 4.1 存储方案

| 环境 | 存储 | 配置 |
|------|------|------|
| **测试/开发** | JSON 文件 | `data/abox/*.json` |
| **生产** | NebulaGraph | 分布式图数据库 |
| **SPARQL 接口** | GraphDB | 统一查询入口 |

### 4.2 核心实体

```
Store（门店）
  - store_id（PK）
  - store_name
  - region

Product（商品）
  - product_id（PK）
  - product_name
  - category（引用 Category）
  - shelf_date（保质期）
  - store_id（所属门店）

DiscountTask（折扣任务）
  - task_id（PK）
  - product_id（FK）
  - store_id（FK）
  - discount_tier（T1/T2/T3）
  - status（pending/approved/rejected/executed）
  - created_by（employee_id）
  - approved_by（店长 employee_id）
  - approved_at

Employee（员工）
  - employee_id（PK）
  - role（总部/店长/店员）
  - store_id（FK）
```

### 4.3 store_id 强制过滤

**所有 ABOX SPARQL 查询必须包含 store_id 过滤条件。** 无 store_id 时返回空结果。

```sparql
# 正确示例
SELECT ?product ?name WHERE {
  ?product a :Product .
  ?product :shelf_date ?date .
  ?product :belongsToStore :STORE_001 .
}

# 错误示例（缺少 store_id 过滤）
SELECT ?product ?name WHERE {
  ?product a :Product .
  ?product :shelf_date ?date .
}
```

---

## 五、Skill 设计

### 5.1 第一期 Skill 清单

| Skill | 功能 | 风险等级 | HITL |
|-------|------|---------|------|
| **临期折扣推荐** | 分析商品保质期，推荐折扣层级 | 高 | 需要（approve/reject） |
| **折扣审批** | 店长审批折扣申请 | 高 | 需要（approve/edit/reject） |
| **任务管理** | 创建/查询/更新门店任务 | 中 | 可选 |
| **商品查询** | 查询商品信息（保质期/库存） | 低 | 不需要 |
| **陈列调整建议** | 根据销售数据给出陈列建议 | 中 | 不需要 |

### 5.2 SKILL.md 格式

每个 Skill 一个目录，遵循 Agent Skills 规范：

```
skills/
├── discount-skill/
│   ├── SKILL.md
│   └── references/
│       └── discount-rules.md
├── task-skill/
│   ├── SKILL.md
│   └── references/
│       └── task-api.md
└── product-skill/
    ├── SKILL.md
    └── references/
        └── product-schema.md
```

### 5.3 allowed-tools 动态配置

Skill 的 `allowed-tools` 不写死在 SKILL.md，通过配置中心动态注入：

```yaml
# config/skills.yaml
skills:
  discount-skill:
    allowed-tools:
      - sparql_query
      - calculate_discount
    roles:
      - 店长
      - 总部
    max_discount_rate: 0.70
```

---

## 六、Agent 运行时编排

### 6.1 Deep Agents + LangGraph 混用策略

| 场景 | 框架 | 原因 |
|------|------|------|
| **简单多步任务** | Deep Agents | `interrupt_on` 配置简单，开箱即用 |
| **复杂条件分支** | LangGraph | `interrupt()` 精确控制执行流 |
| **第一期** | Deep Agents 为主 | 快速上线，验证核心流程 |

### 6.2 HITL 人工审批配置

```python
interrupt_on = {
    # 折扣审批：店长必须审核
    "execute_discount": {
        "allowed_decisions": ["approve", "edit", "reject"]
    },
    # 任务创建：不需要审批
    "create_task": {
        "allowed_decisions": ["approve", "reject"]
    },
    # 商品查询：不需要审批
    "query_product": False,
}
```

### 6.3 审批流程

```
用户发起折扣请求
    ↓
Deep Agents 拦截（interrupt_on）
    ↓
店长收到飞书推送（CopilotKit 前端渲染审批卡）
    ↓
店长选择：批准 / 修改参数 / 拒绝
    ↓
Agent 继续执行（approve → 执行折扣 / edit → 修改后执行 / reject → 记录拒绝原因）
    ↓
审计日志写入 PostgreSQL
```

---

## 七、权限控制

### 7.1 角色体系

| 角色 | 门店数据 | Skill | 审批权限 | 说明 |
|------|---------|-------|---------|------|
| **总部** | 全部门店 | 全部 | 无限制 | 管理规则、查看所有数据 |
| **店长** | 本店 | 全部 | 本店折扣 ≤ 70% | 日常运营管理 |
| **店员** | 本店 | 查询类 | 无 | 执行任务、发起折扣申请 |

### 7.2 身份注入

```typescript
// 飞书小程序端
<CopilotKit
  runtimeUrl="/api/copilotkit"
  properties={{
    authorization: feishu_user_token,  // 飞书登录态
    store_id: current_store_id,
    role: user_role,
  }}
>
```

后端从 `config["configurable"]["copilotkit_auth"]` 解析 `user_id` 和 `store_id`。

### 7.3 数据权限矩阵

| 操作 | 总部 | 店长（本门店） | 店员（本门店） | 其他门店店长 |
|-------|------|---------------|--------------|-------------|
| 查看本店商品 | ✅ | ✅ | ✅ | ❌ |
| 查看全部门店商品 | ✅ | ❌ | ❌ | ❌ |
| 发起折扣申请 | ✅ | ✅ | ✅ | ❌ |
| 审批折扣（≤70%） | ✅ | ✅ | ❌ | ❌ |
| 审批折扣（>70%） | ✅ | ❌ | ❌ | ❌ |
| 创建任务 | ✅ | ✅ | ❌ | ❌ |
| 查看任务 | ✅ | ✅（本店） | ✅（本店） | ❌ |

---

## 八、审计设计

### 8.1 审计范围

| 事件类型 | 字段 | 存储 |
|---------|------|------|
| Agent 调用 | session_id, user_id, store_id, timestamp, model | PostgreSQL / 文件 |
| 工具执行 | tool_name, parameters, result, duration_ms | PostgreSQL / 文件 |
| HITL 审批 | approver_id, decision, comment, task_id | PostgreSQL / 文件 |
| 折扣决策 | product_id, discount_tier, approved_by, final_rate | PostgreSQL |
| 异常/错误 | error_type, stack_trace, user_id | PostgreSQL / 文件 |

### 8.2 防篡改机制

```sql
CREATE TABLE audit_log (
  id UUID PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  store_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload JSONB NOT NULL,
  output_hash TEXT NOT NULL,  -- SHA256(payload + secret_key)
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 8.3 HITL 审批记录

```sql
CREATE TABLE hitl_approval (
  id UUID PRIMARY KEY,
  task_id TEXT NOT NULL,
  approver_id TEXT NOT NULL,
  decision TEXT NOT NULL,  -- approve / edit / reject
  original_params JSONB,
  final_params JSONB,
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 九、可观测性

### 9.1 LangSmith 配置

```python
import os
os.environ["LANGSMITH_API_KEY"] = "..."
os.environ["LANGSMITH_PROJECT"] = "store-ontology"

# LangGraph 配置
agent = create_deep_agent(
    model="...",
    tools=[...],
    langsmith_tracing=True,
)
```

**追踪内容**：
- Skill Match 决策路径
- Tool 调用链路（name / params / result / duration）
- TBOX SPARQL 查询语句和结果
- ABOX 数据过滤结果
- HITL 中断和恢复事件

### 9.2 结构化日志

```python
import structlog
logger = structlog.get_logger()

logger.info(
    "agent_tool_executed",
    user_id=user_id,
    store_id=store_id,
    session_id=session_id,
    tool_name="execute_discount",
    params={"task_id": "T001", "rate": 0.5},
    duration_ms=234,
)
```

### 9.3 CopilotKit Inspector

开发环境启用，生产环境关闭。

---

## 十、MCP 外部系统对接

### 10.1 对接范围（第一期）

| 系统 | 方向 | 功能 |
|------|------|------|
| **ERP** | MCP Server 消费 | 商品主数据（品名/品类/进价） |
| **WMS** | MCP Server 消费 | 库存数据（实时库存量） |
| **飞书审批** | MCP Server 提供 | 店长飞书审批通知 |

### 10.2 MCP Server 实现

```python
# ERP MCP Server 示例
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("erp")

@mcp.tool()
async def get_product_info(product_id: str) -> dict:
    """从 ERP 获取商品主数据"""
    ...

# 接入 Deep Agents
from langchain_mcp_adapters import load_mcp_server
erp_server = load_mcp_server("erp")
```

---

## 十一、非功能性需求

| 指标 | 要求 | 说明 |
|------|------|------|
| **响应时间** | P99 < 3秒 | 单次对话端到端 |
| **并发** | 支持 50 并发用户 | 共享实例模式 |
| **可用性** | 99.5% | 单节点 Docker |
| **内容安全** | LLM 输出过滤 | 防止错误折扣决策 |
| **数据脱敏** | 进价/供应商信息 | 对店员隐藏 |
| **合规** | 零售数据合规 | 折扣决策留存依据 |

---

## 十二、落地里程碑

| 阶段 | 内容 | 时长 | 交付物 |
|------|------|------|--------|
| **Phase 1** | CopilotKit 前端集成（飞书小程序） | 2周 | 基础对话 UI + 身份注入 |
| **Phase 2** | Deep Agents 后端部署 + 临期折扣 Skill | 2周 | 折扣推荐 + 店长审批 |
| **Phase 3** | GraphDB + TTL 本体 + SPARQL 查询 | 2周 | TBOX/ABOX 分离 |
| **Phase 4** | HITL 审批流 + 权限矩阵 | 1周 | 完整审批链路 |
| **Phase 5** | 审计日志 + LangSmith 接入 | 1周 | 可观测性 |
| **Phase 6** | MCP Server（ERP/WMS）对接 | 2周 | 外部系统集成 |
| **Phase 7** | 生产环境（NebulaGraph + PG）迁移 | 1周 | 生产就绪 |

**预计总工期**：11 周（约 3 个月）

---

## 十三、待确认项

以下内容基于合理默认推断，**需要谢文龙确认**：

| # | 问题 | 默认推断 | 需确认 |
|---|------|---------|-------|
| 1 | 试点门店数量 | 1-3 家 | 确认具体是哪几家 |
| 2 | 临期折扣 T1/T2/T3 阈值 | T1:7天/T2:5天/T3:3天 | 确认品类是否有差异 |
| 3 | 豁免商品清单 | 进口/有机/鲜食类 | 补充完整品类 |
| 4 | 审批时效要求 | 24小时内 | 确认是否加急 |
| 5 | 飞书小程序是否从零开发 | 是 | 确认是否有现成入口 |
| 6 | MCP Server 优先级 | ERP → WMS → 飞书审批 | 确认接入顺序 |
| 7 | 折扣 > 70% 是否需要总部审批 | 是（默认） | 确认阈值 |
| 8 | 第一期上线哪几个 Skill | 折扣 + 任务 + 商品查询 | 确认优先级 |

---

## 十四、参考文档

- [CopilotKit+LangGraph+DeepAgents架构方案](https://www.feishu.cn/docx/ZE57dJSaaoaza4x2YLNcoSOenAc)
- [CopilotKit 官方文档](https://docs.copilotkit.ai/)
- [LangGraph 官方文档](https://docs.langchain.com/oss/python/langgraph/)
- [Deep Agents 官方文档](https://docs.langchain.com/oss/python/deep-agents/)
- [Agent Skills 规范](https://github.com/agentskills/agentskills)
- [store-ontology 设计问题清单](./STORE-ONTOLOGY-DESIGN-QUESTIONS.md)
