# 演进路线

> **状态**：部分已落地、部分前瞻。每节顶部用 ✅/🔜 标注当前状态；底部「阶段总览」表给出全局快照。**前瞻章节仅供方向参考，不可据此认为系统已具备这些能力。**
> **来源**：本文档从历史设计（`archive/legacy-Harness-Design.md` 的多组织/RBAC×ABAC/审计/观测，以及目标架构的 v2 项）摘要而来。完整原始设计见归档文档。

每节明确标注"当前实现仅 X，本节描述目标 Y"，避免混淆现状与前瞻。

---

## 1. v2-存储：JSON → PostgreSQL+JSONB（✅ 代码已完成；默认部署仍走 JSON）

**当前实现**：✅ 代码已完成（**PG + JSON 双后端**，2026-06-22）。配了 `DATABASE_URL` 就走 PostgreSQL+JSONB；未配或连不上时自动回落 `JSONFileRepository`，上层 Repository 接口不变。

> ⚠️ **注意默认行为**：仓库根 `.env` 当前**未配** `DATABASE_URL`，所以开箱即用的实例仍走 JSON 文件。要启用 PG：在 `.env` 加 `DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology`，`docker compose up -d` 起 PG，再跑 `agent/scripts/import_to_pg.py` 迁移数据。迁移后重启后端，日志不再出现 `回落 JSON` 即生效。

**已落地**（WP1–WP10，设计见 `docs/superpowers/plans/2026-06-22-wp7-10-admin-ontology-crud.md`）：
- **PG schema**（`agent/sql/schema.sql`）：`object_types` / `object_type_properties` / `link_types` / `action_types` / `entities` 五表；关系列存核心查询字段，JSONB 存复杂结构（parameters/side_effects/properties）。含 TenantContext 过滤索引（`workspace_name + org_unit_id`）+ JSONB GIN 索引 + `updated_at` 触发器。pgvector 扩展已建（embedding 列预留，本轮注释掉）。
- **连接层**（`agent/engine/db.py`）：psycopg 3 + psycopg-pool 单例连接池（4–8 连接）；`transaction()` 上下文自动 commit/rollback；`is_pg_enabled()` / `ping()` / `migrate()` helper；`DATABASE_URL` 缺失抛 `PGNotConfigured` 让上层回落。
- **双 Repository**：`PgDataRepository`（`pg_data_repo.py`，业务数据）+ `PgOntologyRepository`（`pg_ontology_repo.py`，本体 schema 读写）。`workspace_bootstrap.py:89-111` 按 `is_pg_enabled() and ping()` 选实现，PG 加载失败回落 JSON 并打印告警。
- **迁移脚本**（`agent/scripts/import_to_pg.py`）：TTL/YAML/JSON → PG 幂等 upsert，支持 `--workspace` / `--skip-data` / `--skip-schema` / `--dry-run`。
- **Admin 本体 CRUD**（WP7–WP10）：`admin_ontology_api.py` 做 JSON↔dataclass 转换 + `require_admin` 鉴权；`main.py` 加 9 个 POST/PUT/DELETE 端点（3 collections × POST/PUT/DELETE），写后 `invalidate_workspace(ws)` 失效缓存；前端 admin 页 tab 化 + 全字段编辑器。

**🔜 仍待实现（更远期）**：
- **GraphRepository（图存储）**：复杂关系遍历（如多层 OrgTree 路径、跨品类聚合），列为更远期。
- **embedding / RAG**：schema 已预留 `entities.embedding vector(1536)` + ivfflat 索引位，待语义检索场景启用。
- **水平扩展验证**：多 uvicorn worker/实例下连接池与缓存失效的实测（每进程一池已就绪，跨进程缓存失效待验证）。

---

## 2. v2-权限：submission_criteria → 完整 RBAC×ABAC

**当前实现**：✅ 已完成（中版实用 RBAC×ABAC，2026-06-22）。

**已落地**（设计文档 [`docs/superpowers/specs/2026-06-22-v2-auth-rbac-design.md`](../superpowers/specs/2026-06-22-v2-auth-rbac-design.md)）：
- **认证**：JWT + bcrypt + `/api/auth/{login,refresh,me,logout}` + `auth_middleware`（强制模式 `AUTH_REQUIRED=true`，跨 ws 越权防护）。
- **identity domain**（第 4 类必备 capability domain）：User/Role/PermissionGrant/Session 本体 + 数据；User credentials 存 workspace 的 `users.json`，agent 层零身份数据。
- **PermissionEvaluator**（`agent/engine/permission.py`）：5 类资源（tool/object/property/action/link）+ 正反向语法（roles/except）+ allow-by-default + system_admin 短路 + PermissionGrant runtime override（deny 优先）。求值顺序：system_admin → Grant → TTL 元数据 → allow-by-default。
- **TTL 权限元数据**：`:read_roles` / `:read_except` / `:write_roles` / `:write_except`（ObjectType 属性级，含嵌套 `:property [ ... ]`）；Link 的 `:use_roles` / `:use_except`。
- **tool_manifest.yaml**：Tool 不在 TTL，用 YAML 声明（内核 8 工具 + 各 workspace 专属）。
- **OrgTree 5 级**：`agent/engine/org_tree.py`，descendants/visible_units 接入。
- **信任修复**：actor 不再可被 LLM 自报（删 execute_action 的 actor_role 参数），从 auth_ctx → Employee.user_id 派生。
- **属性级权限**：query_entity 等 tool 在返回时 mask 不可读属性 + 文本提示（不静默裁剪）。
- **dashboard 越权修复**：改用请求级 `tenant_ctx.get()`（取代 `inst.tenant_context` 的 `org_unit_id="*"`）。

**🔜 仍待实现（重型机制留接口预留）**：
- **6 种 PermissionMode / 6 层 cascade**（来自 `archive/legacy-Harness-Design.md` §3.1/§3.2）。
- **DeepImmutable 快照冻结 + HMAC 校验**（§3.3）。
- **26 个生命周期钩子**（§10）。
- **submission_criteria 操作符全集**：现支持 `is/is_not`；`gte/lte/matches/includes/value_ref` + 嵌套 AND/OR 留 v3。
- **CategoryScope coverage_depth / RuleSource 优先级**。

---

## 3. v2-本体：零售工作目录深化 + Interface/transfer/restock

**当前实现**：✅ 已完成（组织 5 级 + 品类 5 级 + 4 类必备 domain，2026-06-22）。

**已落地**：
- **组织 5 级**：`Brand → OrgGroup → Channel → Region → Store`（生鲜部门特有 `Dept` 第 6 级）。OrgUnit 字段含 `company_code` / `profit_center_code` / `cost_center_code`（财务核算）。OrgTree（`agent/engine/org_tree.py`）支持 descendants/ancestors/visible_units。
- **品类 5 级**：`Department → CategoryGroup → Category → SubCategory → Variety`。Product 加 `category_id` 引用 Category.id（保留旧 category 字符串做 deprecated 兼容）。
- **4 类必备 capability domain**：`register_workspace_dir` 校验 workspace 含 organization/personnel/category/identity 四类必备 domain + 各类必备 Object Type（OrgUnit/Employee/Category/User+Role+PermissionGrant）。缺则启动失败。
- **personnel domain 独立**：Employee 从 organization 拆出，加 `user_id`（反向引用 identity User）+ `department_id`。`EmployeeRole` 词汇表对齐 submission_criteria.roles（store_manager/store_clerk/region_cat_mgr/system_admin/...）。
- **三家 workspace 全部迁移**：retail/jjy 含 6 domain（marketing/organization/personnel/category/finance/identity）；customerA 含 5 domain（maintenance/organization/personnel/category/identity）。

**🔜 仍待实现**：
- **DC（配送中心）维度**：正交于组织维度的配送中心（legacy §1.2）。
- **职能域 Domain 维度**：legacy 三维 scope（Domain×OrgScope×CategoryScope）之一。
- **Interface Type / Shared Property**：跨 Object 共享形状，元数据预留。
- **transfer/restock Action 契约**：当前工作目录聚焦 clearance + customerA，调拨/补货契约留后续。

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

## 10. v2-agent 治理与运维（🔜 规划中，评估回填）

> 来源：[`palantir-implementation-assessment.md`](./palantir-implementation-assessment.md) v2 评审引入的"agent 治理/运维"第四评估轴。架构落地形态见 [`00-architecture.md`](./00-architecture.md) §12。这一轴当前 roadmap 完全缺失，是企业上 agent 的前提。

**当前实现**：权限治理已落地（§2 RBAC×ABAC + RLS + 列级）；auth 事件审计已落地（`auth_audit.py`）。但 **Action 级审计 / 决策追溯 / LLM 成本治理 / agent 行为监控 / 自治分级**五块全缺。

**🔜 P0（治理+运维闭环，必须优先）**：
- **Action Log**（F-AT-36）：✅ 已落地（feat/action-log 分支）— 每笔 Action 物化为 `action_logs`（PG 表 / JSON 文件），executor 内部日志点覆盖所有触发来源，8 类 failure_type，admin 查询 API（list + detail）。见 [spec](superpowers/specs/2026-06-22-action-log-design.md) / [plan](superpowers/plans/2026-06-24-action-log.md)。
- **Auditability 补齐**（F-XC-09）：✅ 部分落地 — Action 级审计可查（随 Action Log）；完整谱系（agent 上下文）待 Decision Lineage 升级。
- **Decision Lineage**（F-XC-01）：🔜 — actor 类型（人 vs agent）+ trigger_source 已随 Action Log 落地；端到端谱系（LLM 版本 / Skill / 会话 ID）待 P1 注入 agent contextvar（schema 字段已预留）。
- **Action Metrics**（F-AT-40/41）：从 Action Log 聚合，成功率 / 失败分类 / P95 时延，per-action-type + per-workspace。agent 运维可观测性核心。
- **notification 投递**（§9 side effects）：当前 `notification` 副作用声明了但投递 no-op。agent 做关键操作必须通知到人——人机协同底线，当前 no-op 是真实风险。

**🔜 P1（V1 增强）**：
- **agent 身份**（F-PM-18）：agent 作为服务账号被授权 / 审计 / 限流，区分"人触发 vs agent 自动触发"。
- **安全变更机制**（F-BR-06 / F-CM-02）：生产本体演进——变更前校验下游引用 + 灰度 + 回滚。轻量版，非完整 Git 分支。
- **Usage / Limits**（§24）：LLM 成本治理——token 追踪 + 速率 + 配额 + 熔断。企业上 agent 第一道门槛。
- **agent ops 仪表盘**（F-OM-08）：agent 行为监控 + 异常告警（异常时间改数据 / 批量失败 / token 突增），与 notification 投递协同。
- **人用操作台**（§11/§14）：店长 / 区经理 / 运营的看板 / 数据探索 / 报表 / 实体详情页（非 agent 对话面）——当前 dashboard 只读 + admin 只读浏览，远不够零售运营。
- **Writeback Connectors**（F-XC-05）：ERP / WMS / POS / OMS 真实集成，替代 mock webhook。企业零售第一天刚需。
- **批量声明式规则层**（§19）：无 LLM 在环的确定性规则（补货点扫描 / 合规扫描 / 临期预警），区别于 submission_criteria。

**🔜 P2（V2 方向）**：渐进自治（F-XC-08，自治级别可声明）、多跳遍历（供应链穿透）、地理数据建模（门店网络）、时间分配原语（排班 / 补货周期 / 档期）、Semantic Search / RAG、Cardinality 显式声明、Interface / Shared Property、Git 式 Branching、Object Edit History、Permission 管理 UI。

---

## 11. Palantir 对标（参照系，📊 持续维护）

> 本平台本体设计的主要参考是 Palantir Foundry Ontology（[`reference/palantir-ontology-docs/`](./reference/palantir-ontology-docs/)）。两份对标文档构成"参照系 ↔ 项目侧"的完整映射，roadmap 的优先级判定应与之对照：

- [`palantir-ontology-functional-requirements.md`](./palantir-ontology-functional-requirements.md) — 从 Palantir 资料提炼的功能需求清单（36 节、~350 条 F-XX-NN），**只描述 Palantir 侧**。
- [`palantir-implementation-assessment.md`](./palantir-implementation-assessment.md) — 对需求清单的项目侧实现识别（四档判定 + **四轴方法论**）。

**四轴评估方法论**（每条"要不要做 X 能力"过这四轴）：
1. **架构轴**：Palantir 抽象按"描述世界（KEEP）/ 执行计算展示（DEMOTE→转换）/ 专有前端或重型治理（DROP）"分档。
2. **场景轴**：按**零售企业平台最小能力集**判，不按 clearance 单场景判。
3. **建模-可视化分离轴**：Palantir 耦合销售的数据建模（轻）和 UI（重）要拆分判——建模部分常 🟡，可视化前端常 ⛔。
4. **agent 治理/运维轴**：每个"⛔"过一遍"agent 上生产后是否治理/运维刚需"。

**当前判定统计**（v2，34 节）：完全 2 / 部分 15 / 转换 11 / 不建议 6。v1→v2 把 16 处保守判定上浮（不建议 12→6），反映"企业零售 + agent 治理/运维"视角下平台需要的能力面更宽。本 roadmap 的 §10 即该方法论在"治理/运维轴"的落地。

---

## 阶段总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| **已实现（内核 + retail + customerA）** | 内核多工作目录架构 + Repository 多 workspace 隔离/锁/原子写/edits-only + 声明式 ActionExecutor（locator_field 数据驱动）+ per-process 状态机 + preview→confirm 闭环 + 折扣单一事实源 + Action YAML 契约 + CRUD 降级 + clearance 8 Action + customerA 6 Action + tenant 上下文注入 | ✅ |
| **✅ v2-tenant动态（数据层）** | route.ts 静态 header → 前端 headers prop 动态注入 + 工具 _tc_ctx 从 contextvar 读 + Repository 按 workspace+org_unit 过滤 | ✅ 完成 |
| ✅ v2-agent 隔离 | 工具/skill/本体 prompt 按 workspace 隔离（agent per-workspace 构建） | ✅ 完成 |
| ✅ **v2-认证 + RBAC×ABAC + 组织品类 5 级** | JWT 认证 + identity domain（User/Role/PermissionGrant）+ PermissionEvaluator（5 类资源 + 正反向 + allow-by-default）+ OrgTree 5 级 + 4 类必备 domain + 信任修复 + 强制 auth | ✅ 完成（2026-06-22，详见 [`docs/superpowers/specs/2026-06-22-v2-auth-rbac-design.md`](../superpowers/specs/2026-06-22-v2-auth-rbac-design.md)） |
| ✅ **v2-存储（PG+JSONB 双后端）** | JSON → PostgreSQL+JSONB（`db.py` 连接池 + `PgDataRepository`/`PgOntologyRepository` + `import_to_pg.py` 迁移 + admin 本体 CRUD + 失效）；代码已完成，`DATABASE_URL` 缺失自动回落 JSONFileRepository（**当前默认部署仍走 JSON**） | ✅ 代码完成（2026-06-22，详见 §1） |
| 🔜 v2-权限重型机制 | 6 PermissionMode / 6 cascade / HMAC 快照 / 26 hooks / 操作符全集 / CategoryScope coverage_depth | 接口预留 |
| 🔜 v2-本体深化 | DC 维度 / 职能域 Domain / Interface Type / transfer/restock 契约 | 未开始 |
| 🔜 v2-自动化 | 真实 POS/审批对接 + 定时器 LLM 唤醒 | webhook 模拟 + 计算式报损已实现 |
| 🔜 v2-Agent | 单 Agent → subagent/多 Agent | 架构预留 |
| 🔜 v2-UI | A2UI + 多工作目录切换 UI + 图表 + 审计 UI | 登录页 + 动态 workspace 选择器已实现；其余未开始 |
| 🔜 v2-长流程 | 后端自动化 → 可选 BPM 引擎增强 | 未开始 |
| 🔜 **v2-agent 治理与运维** | Action Log + Decision Lineage + Action Metrics + notification 投递（P0）/ agent 身份 + 安全变更 + Usage-Limits + agent ops 仪表盘 + 人用操作台 + Writeback Connectors + 批量规则（P1） | 规划中（评估回填，见 §10、架构 §12） |
