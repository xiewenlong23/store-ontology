# 演进路线

> **状态**：🔮 前瞻（**未实现**）。本文件描述的所有机制**均未落地**，仅供方向参考。**不可据此认为系统已具备这些能力。**
> **来源**：本文档从历史设计（`archive/legacy-Harness-Design.md` 的多组织/RBAC×ABAC/审计/观测，以及目标架构的 v2 项）摘要而来。完整原始设计见归档文档。

每节明确标注"当前实现仅 X，本节描述目标 Y"，避免混淆现状与前瞻。

---

## 1. v2-存储：JSON → PostgreSQL+JSONB

**当前实现**：`JSONFileRepository`（`agent/engine/repository.py`），JSON 文件 + `fcntl.flock` 文件锁 + 临时文件原子替换 + `.bak` 备份。

**🔜 目标（未实现）**：换 `PostgresRepository`（PostgreSQL + JSONB），由数据库事务保证一致性与并发，上层 Repository 接口不变。支持水平扩展（多 uvicorn worker/实例）。GraphRepository（图存储）列为更远期。

---

## 2. v2-权限：submission_criteria → 完整 RBAC×ABAC

**当前实现**：仅 Action 级 `submission_criteria`（`roles` 白名单 + `is`/`is_not` 条件，见 [`00-architecture.md`](./00-architecture.md) §3.4）+ Repository 的 workspace/org_unit 隔离。

**🔜 目标（未实现）**：完整 RBAC×ABAC 融合模型（来自 `archive/legacy-Harness-Design.md` §3）：
- **PermissionEvaluator 接口**（内核）：每个工具调用前 `permission_gate.check(tool, context)`，失败抛 `PermissionDenied` + 写审计。
- **三维 scope**：Domain（职能域）× OrgScope（组织范围）× CategoryScope（品类范围）。
- **6 种 PermissionMode / 6 层 cascade**：组织调整时权限自动适应（"三不变"原则：组织调整/品类调整/职能域调整 ≠ 权限重配）。
- **DeepImmutable 快照冻结 + HMAC 校验**：权限状态不可变快照。
- **submission_criteria 操作符全集**：`is`/`is_not`（已有）+ `gte`/`matches`/`includes`/`value_ref` + 嵌套逻辑。
- **26 个生命周期钩子**。

> 这些重型机制当前**接口预留**，未实现。详见 `archive/legacy-Harness-Design.md` §3.1（六种权限模式/六层瀑布）、§3.3（快照冻结）、§3.6（求值引擎）。

---

## 3. v2-本体：零售工作目录深化 + Interface/transfer/restock

**当前实现**：retail 工作目录扁平组织（Region/Store）+ Product 的扁平 `category` 字符串；clearance 8 Action 完整，customerA 6 Action 完整。

**🔜 目标（未实现）**：
- **组织 5 级**：Brand → OrgGroup → Channel → Region → Store（收敛为现有 Region/Store，扩展留 v2）。每级带财务核算字段（company_code / profit_center_code / cost_center_code）。
- **品类 5 级**：现用扁平字符串，5 级树留 v2（生鲜部门特有多一级）。
- **DC 配送中心**：正交于组织维度的配送中心，现不实现。
- **职能域 Domain**：正交于组织维度的职能划分。
- **Interface Type / Shared Property**：跨 Object 共享形状，元数据预留，MVP 不实现。
- **transfer/restock Action 契约补全**：当前工作目录聚焦 clearance + customerA，调拨/补货契约留后续。

详见 `archive/legacy-Harness-Design.md` §1（多组织架构）、§2（品类维度）、§1.2（DC 维度）、§1.3（职能域维度）。

---

## 4. v2-自动化：真实系统集成 + LLM 唤醒

**当前实现**：`AutomationScheduler`（APScheduler 封装）+ webhook 模拟端点（`/api/webhooks/approval`、`/api/webhooks/pos`）+ 计算式报损（loss_quantity = planned - sold，无 LLM）。

**🔜 目标（未实现）**：
- **真实 POS/审批系统对接**：替换 webhook 模拟端点。
- **定时器 LLM 唤醒**：到期报损等场景由定时器回调 `agent.ainvoke()`，用 LLM 做报损推理（当前是计算式）。
- **可选 BPM/Workflow 引擎增强**：承载更复杂的跨天流程编排。

---

## 5. v2-Agent：单 Agent → 多 Agent 协作

**当前实现**：单 Agent（`create_deep_agent` + SkillsMiddleware + SummarizationMiddleware），系统提示合并所有工作目录本体。

**🔜 目标（未实现）**：subagent / 多 Agent 协作（Planner / Tool / Reasoner / Reporter 四角色）。架构预留扩展点，deepagents 本身支持 subagent。

详见 `archive/legacy-ontologyagent-design-CN.md` 第4层 Agent 设计。

---

## 6. v2-UI：手写 renderToolCalls → A2UI 标准 + 多工作目录切换

**当前实现**：CopilotKit v1.57 + 9 个手写 `renderToolCalls` + workspace 切换 UI + CopilotChat key 隔离对话。前端 `headers` prop 动态注入 `X-Workspace` + `X-Org-Unit-ID`（已完成）。

**🔜 目标（未实现）**：
- **A2UI 标准渲染**（node_modules 已有但未启用）。
- **ECharts 图表**、**权限管理 UI**、**审计查询 UI**。

---

## 7. v2-长流程：后端自动化 → 可选 BPM 引擎

**当前实现**：工作流 Object + per-process 状态机 + 后端自动化（定时器/webhook）承载长流程，不引入 BPM 引擎。

**🔜 目标（未实现）**：可选 BPM/Workflow 引擎增强（更复杂的跨步骤编排、人工审批流、SLA）。列为远期可选项。

---

## 8. v2-tenant 动态：静态 header → 动态注入

**当前实现**：✅ 已完成（数据层 + agent 层）。前端 CopilotKit `headers` prop 函数式注入 `X-Workspace` + `X-Org-Unit-ID`，CopilotKit runtime 自动透传给后端，middleware 存入 contextvar，工具经 `_tc_ctx()` 读取，Repository 按 workspace_name + org_unit 过滤。详见 `docs/superpowers/specs/2026-06-21-v2-tenant-dynamic-design.md`。

---

## 9. v2-agent 隔离：工具/skill/本体按 workspace 隔离（✅ 已完成）

> **状态**：✅ 已完成。去掉 IndustryPack 中间层，每个工作目录独立 agent 实例（工具/skill/本体隔离）。

**已完成**：
- 去掉 `IndustryPack` 中间层：工作目录直接声明 `CapabilityDomain[]` + `ValueChainProcess[]`（经 `workspace.py` 注册）
- per-workspace agent 隔离：`build_workspace_graph(ws_name)` 只含该工作目录的工具/skill/prompt；`get_or_build_ws_agent(ws_name)` 缓存 per-workspace agent
- 自写网关 endpoint：按 `X-Workspace` 路由 + `agent.clone()` per-request 隔离
- 验证：jjy agent 只含 `query_near_expiry` + `NearExpiryProduct`；customerA agent 只含 `query_repair_tickets` + `RepairTicket`。工具/本体/skill 完全隔离。
- 前端 `CopilotChat key={selectedWorkspace}` 切换时重置聊天，对话 session 隔离

---

## 阶段总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| **已实现（内核 + retail + customerA）** | 内核多工作目录架构 + Repository 多 workspace 隔离/锁/原子写/edits-only + 声明式 ActionExecutor（locator_field 数据驱动）+ per-process 状态机 + preview→confirm 闭环 + 折扣单一事实源 + Action YAML 契约 + CRUD 降级 + clearance 8 Action + customerA 6 Action + tenant 上下文注入 | ✅ |
| **✅ v2-tenant动态（数据层）** | route.ts 静态 header → 前端 headers prop 动态注入 + 工具 _tc_ctx 从 contextvar 读 + Repository 按 workspace+org_unit 过滤 | ✅ 完成（156 测试，playwright 验证数据隔离） |
| ✅ v2-agent 隔离 | 工具/skill/本体 prompt 按 workspace 隔离（agent per-workspace 构建） | ✅ 完成 |
| 🔜 v2-存储 | JSON → PostgreSQL+JSONB | 未开始 |
| 🔜 v2-权限 | submission_criteria → 完整 RBAC×ABAC（三维 scope、6 层 cascade、快照冻结、操作符全集） | 接口预留 |
| 🔜 v2-本体 | 零售工作目录深化（组织5级/品类5级/DC/职能域）；transfer/restock 契约 | 未开始 |
| 🔜 v2-自动化 | 真实 POS/审批对接 + 定时器 LLM 唤醒 | webhook 模拟 + 计算式报损已实现 |
| 🔜 v2-Agent | 单 Agent → subagent/多 Agent | 架构预留 |
| 🔜 v2-UI | 手写 renderToolCalls → A2UI + 多工作目录切换 + 图表 + 审计 UI | 未开始 |
| 🔜 v2-长流程 | 后端自动化 → 可选 BPM 引擎增强 | 未开始 |
