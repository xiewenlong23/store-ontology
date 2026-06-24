# Action Log 设计

> **徽章**：📋 spec
> **状态**：待 review → 待写实施 plan
> **来源**：[`palantir-implementation-assessment.md`](../design/palantir-implementation-assessment.md) §7 P0（F-AT-36）+ §36 P0（F-XC-01 Decision Lineage / F-XC-09 Auditability）
> **架构依据**：[`00-architecture.md`](../design/00-architecture.md) §12.2（Decision Lineage 与审计闭环）
> **日期**：2026-06-22

## 1. 目标与非目标

### 1.1 目标（P0）

每笔 Action 执行物化为**可查询的审计记录**（决策即数据），解决生产环境 agent 黑箱问题：

1. **审计追溯**（Auditability, F-XC-09）：任何对象被改时，能回答"谁、何时、经哪个 Action、改了什么"。
2. **决策谱系基础**（Decision Lineage, F-XC-01）：记录触发来源（user / agent / scheduler / webhook）+ actor 身份，区分"人触发 vs agent 自动触发"。
3. **Metrics 数据源**（Action Metrics, F-AT-40/41，P0 同源）：Log 经聚合即可产出成功率 / 失败分类 / 时延，本 spec 不实现 Metrics UI，但保证 Log 结构可聚合。

### 1.2 非目标

- **不实现** Action Metrics 仪表盘 UI（§12.4 P0 的第二项，单独 spec）。
- **不实现** Action Revert / Undo（P1，依赖 Log 但单独 spec）。
- **不实现** 完整 Decision Lineage 的 agent 运行时上下文捕获（LLM 版本 / Skill / 会话 ID）——schema 预留字段，P1 注入。
- **不实现** LLM 可查询的 `query_action_log` Tool（审计是人的职责，避免 LLM 误用/泄露）。
- **不动** `auth_audit.py`（认证事件审计独立保留，职责不同）。

## 2. 已确认设计决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | 存储形态 | 独立 `action_logs` 表（PG）/ `action_logs.json`（JSON） | 治理数据与业务数据分离，不被 admin 数据浏览混入，不受 edits_only 影响，schema 可定制 |
| D2 | 日志点 | `executor.execute()` 内部 try/except | 覆盖所有触发来源（LLM 对话 / automation.py / webhook / admin），是 Decision Lineage 正确粒度 |
| D3 | agent 上下文 | 轻量：触发来源 + actor（id+role+type） | 满足 P0 核心"区分人 vs agent"；LLM 版本/Skill/会话 schema 预留，P1 注入 |
| D4 | failure_type | 对齐现状 8 类 | 覆盖现有 raise 点，不过度设计 |
| D5 | 查询面 | 仅 admin（人用）：admin API + admin 控制台页 | 审计是治理/运维轴，给人看；LLM 不直接查 |
| D6 | 保留策略 | 永久保留（MVP） | 简单，审计完整；远期按 org 策略归档 |

## 3. 数据模型

### 3.1 action_logs schema

**PG**（新增表，加入 `sql/schema.sql`）：

```sql
CREATE TABLE IF NOT EXISTS action_logs (
    log_id              text NOT NULL,             -- UUID hex，主键
    workspace_name      text NOT NULL,             -- 租户隔离（与 entities 一致）
    timestamp           timestamptz NOT NULL DEFAULT now(),
    action_type         text NOT NULL,             -- 如 create_clearance_task
    outcome             text NOT NULL,             -- success / failure
    failure_type        text,                      -- failure 时填，8 类枚举（见 §3.3）；success 为 NULL
    error_message       text,                      -- failure 时的异常消息
    -- actor（D3 轻量）
    actor_id            text,                      -- user_id 或 agent:<source>
    actor_role          text,                      -- 角色
    actor_type          text NOT NULL,             -- user / agent
    trigger_source      text NOT NULL,             -- llm_session / automation / webhook / admin_api
    -- 影响对象
    edits_object_types  text[] NOT NULL DEFAULT '{}',  -- Action 声明的 edits_object_types
    affected_objects    jsonb NOT NULL DEFAULT '{}',   -- {object_type: [pk, ...]}，实际被改的对象
    -- Action 上下文
    params              jsonb,                     -- 校验后的参数（可能含敏感数据，见 §7）
    duration_ms         integer,                   -- execute() 耗时（为 Metrics 预留）
    -- agent 运行时上下文（D3 P1 预留，P0 不填）
    llm_model           text,
    skill_id            text,
    session_id          text,
    PRIMARY KEY (log_id)
);

CREATE INDEX IF NOT EXISTS idx_action_logs_ws_time
    ON action_logs (workspace_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_action_logs_ws_action
    ON action_logs (workspace_name, action_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_action_logs_ws_actor
    ON action_logs (workspace_name, actor_id, timestamp DESC);
```

**JSON 后端**：`workspace/<ws>/data/action_logs.json`，append-only array（与 auth_audit rolling 模式同构，但不截断——D6 永久保留）。每条 entry 结构与 PG 列一一对应（timestamp 为 ISO 字符串）。

### 3.2 日志点与触发来源识别

`executor.execute()` 改造（伪代码）：

```python
def execute(self, action_type, params, *, actor, tenant_id, trigger_source="llm_session"):
    import time
    t0 = time.monotonic()
    log_entry = self._init_log(action_type, actor, tenant_id, trigger_source)
    try:
        action = self.actions.get(action_type)
        if not action:
            raise ValidationError(f"未知 Action Type: {action_type}")  # → unknown_action
        params = self._validate_params(action, params)                   # → invalid_param
        target = self._load_target(action, params, tenant_id)            # → entity_not_found
        self._check_submission(action, actor, target, params, tenant_id) # → permission_denied / submission_failed
        changes = self._run_side_effects(action, params, tenant_id)      # → side_effect_error / illegal_transition / entity_not_found
        log_entry.update_success(changes)
        return {"ok": True, "action": action_type, "created": changes["created"], "updated": changes["updated"]}
    except OntologyError as e:
        log_entry.update_failure(self._classify_failure(e), str(e))
        raise  # 重抛，调用方仍按原逻辑处理
    except Exception as e:
        log_entry.update_failure("unclassified", str(e))
        raise
    finally:
        log_entry.duration_ms = int((time.monotonic() - t0) * 1000)
        self._write_log(log_entry)  # 审计失败不应阻断请求（内部 try/except 兜底）
```

**触发来源（trigger_source）由调用方传入**：

| 调用方 | trigger_source | 传法 |
|---|---|---|
| `confirm_action` Tool（LLM 对话） | `llm_session` | `executor.execute(..., trigger_source="llm_session")` |
| `automation.py` job | `automation` | 同上 |
| `routers/webhooks.py` | `webhook` | 同上 |
| admin API（未来直调） | `admin_api` | 同上 |
| 默认（未指定） | `llm_session` | 向后兼容 |

**关键**：`execute()` 签名新增 `trigger_source` keyword 参数（默认 `llm_session`），所有现有调用点显式传值。automation.py 和 webhooks.py 是 agent 自主触发的核心场景，必须显式标注。

### 3.3 failure_type 8 类枚举

对齐 executor 现有 raise 点（每类 → 对应异常/位置）：

| failure_type | 触发位置 | 现有异常 |
|---|---|---|
| `unknown_action` | `execute()` 顶部的 `actions.get(action_type)` 未命中 | `ValidationError("未知 Action Type")` |
| `invalid_param` | `_validate_params` 缺必填 / 约束不满足 | `ValidationError("缺少必填参数" / "不满足约束")` |
| `permission_denied` | `_check_submission` roles 白名单不通过 | `ValidationError("角色无权提交")` |
| `submission_failed` | `_check_submission` conditions 不通过 | `ValidationError(cond.fail_msg)` |
| `entity_not_found` | `_load_target` 或 `_run_side_effects` 中 read_one 未命中 | `EntityNotFoundError` |
| `illegal_transition` | `_run_side_effects` state_transition 状态机校验失败 | `ValidationError("非法状态迁移")` |
| `side_effect_error` | `_run_side_effects` 其它异常（如 create_object 失败） | `OntologyError` 子类 |
| `unclassified` | 上述未覆盖的异常 | 任意 `Exception` |

**分类实现**：`_classify_failure(exc)` 基于异常类型 + 消息文本启发式分类（如 `EntityNotFoundError` → `entity_not_found`；`ValidationError` 消息含"角色"→`permission_denied`、含"非法状态"→`illegal_transition`、含"缺少必填"/"约束"→`invalid_param`、含"未知 Action"→`unknown_action`、其余 →`submission_failed`）。分类失败 → `unclassified`。

### 3.4 affected_objects 捕获

`_run_side_effects` 已返回 `{created: {obj_type: [rec]}, updated: {obj_type: [rec]}}`（L206-258）。`update_success(changes)` 从中提取每对象的 `id`，组装 `{object_type: [pk, ...]}` 存入 `affected_objects`。

**失败时**：`affected_objects` 为 `{}`（副作用未执行或部分执行——部分执行的情况记已执行的 changes，尽力而为）。

## 4. 存储层

### 4.1 ActionLogRepository（新增）

新增 `agent/engine/action_log_repo.py`，提供 PG 和 JSON 双后端实现：

```python
class ActionLogRepository:
    storage_kind: str  # "pg" / "json"
    def write(self, entry: ActionLogEntry) -> None: ...       # append
    def query(self, ws_name: str, *, action_type=None, actor_id=None,
              outcome=None, failure_type=None,
              since: datetime=None, until: datetime=None,
              limit: int=100, offset: int=0) -> List[ActionLogEntry]: ...
    def count(self, ws_name: str, **filters) -> int: ...
```

**PG 实现**：直接操作 `action_logs` 表，支持上述所有 filter（索引见 §3.1）。
**JSON 实现**：`workspace/<ws>/data/action_logs.json`，append + 全量过滤分页（与 auth_audit 同构，但不截断）。

**工厂**：`build_action_log_repo(ws_name)` —— PG 可用则 PgActionLogRepository，否则 JSONFileActionLogRepository。与 `build_data_repository` 同模式。

### 4.2 ActionLogEntry dataclass

新增 `agent/engine/action_log.py`：

```python
@dataclass
class ActionLogEntry:
    log_id: str                  # uuid4().hex
    workspace_name: str
    timestamp: str               # ISO，写入时定
    action_type: str
    outcome: str                 # success / failure
    failure_type: Optional[str]
    error_message: Optional[str]
    actor_id: Optional[str]
    actor_role: Optional[str]
    actor_type: str              # user / agent
    trigger_source: str
    edits_object_types: List[str]
    affected_objects: dict       # {obj_type: [pk]}
    params: dict
    duration_ms: Optional[int]
    llm_model: Optional[str]     # P1
    skill_id: Optional[str]      # P1
    session_id: Optional[str]    # P1

    @classmethod
    def init(cls, action_type, actor, tenant, trigger_source): ...
    def update_success(self, changes: dict): ...
    def update_failure(self, failure_type: str, error_message: str): ...
```

## 5. 执行链路改造点

| 文件 | 改动 |
|---|---|
| `agent/engine/executor.py` | `execute()` 加 try/except/finally + 日志写入；签名加 `trigger_source` 参数；注入 `log_repo`（构造函数） |
| `agent/engine/action_log.py` | 新文件：ActionLogEntry dataclass |
| `agent/engine/action_log_repo.py` | 新文件：ActionLogRepository + PG/JSON 双实现 |
| `agent/engine/workspace_bootstrap.py` | `WorkspaceAgentInstance` 加 `log_repo` 字段；`bootstrap_workspace` 构造并注入 executor |
| `agent/tools/shared.py` | `_get_executor()` 不变（executor 已含 log_repo） |
| `agent/tools/action_tools.py` | `confirm_action` 调 `execute(..., trigger_source="llm_session")` |
| `workspace/retail/skills/clearance_workflow/automation.py` | 所有 `executor.execute(...)` 调用加 `trigger_source="automation"` |
| `agent/routers/webhooks.py` | approval/pos handler 的 execute 调用加 `trigger_source="webhook"` |
| `agent/sql/schema.sql` | 新增 `action_logs` 表 + 3 个索引 |
| `agent/engine/db.py:migrate()` | 无需改（schema.sql 幂等执行） |

## 6. 查询接口（仅 admin）

### 6.1 Admin API（新增 router）

新增 `agent/routers/action_logs.py`，挂在 `/api/admin/customers/{cid}/action-logs`：

- `GET /api/admin/customers/{cid}/action-logs` — 列表查询，支持 query params：`action_type` / `actor_id` / `outcome` / `failure_type` / `since` / `until` / `limit`（默认 100）/ `offset`。返回 `{items: [...], total: N}`。
- `GET /api/admin/customers/{cid}/action-logs/{log_id}` — 单条详情（含完整 params / affected_objects）。

**权限**：`require_admin(ws)`（与现有 admin router 一致，system_admin 或 bootstrap admin）。

### 6.2 Admin 控制台 UI（前端）

`frontend/app/admin/` 加新 tab "操作审计"，与"数据浏览"/"本体编辑"并列：
- 列表视图：时间 / Action / 结果 / actor / 触发来源 / 耗时，支持上方 filter。
- 点行展开详情：params + affected_objects + error_message。

**P0 简化**：UI 可后置到 P1（API 先行，UI 随 admin 控制台整体增强一并做）。MVP 可只交付 API + CLI 查询脚本。

## 7. 安全与隐私

### 7.1 params 敏感数据

`params` 可能含敏感字段（如 password）。**MVP 策略**：全量记录（审计完整性优先），但 admin API 返回时对已知敏感字段名（`password` / `password_hash` / `token` / `secret`）做掩码（显示 `***`）。敏感字段名集合可配置，默认硬编码。

### 7.2 租户隔离

所有查询强制 `workspace_name` 过滤（与 entities 一致），admin API 从 URL `{cid}` 取 workspace，不信任客户端传入的 workspace_name。

### 7.3 审计写入不阻断请求

`_write_log` 内部 try/except 兜底，写入失败只 log warning，不抛异常（与 `auth_audit.py` 同原则）。

## 8. 测试策略

- **executor 单测**：每种 failure_type 各一例（mock actions/registry/repo 触发各类异常），断言 log_entry 正确分类 + 重抛原异常。
- **success 路径单测**：断言 affected_objects 正确提取 + outcome=success。
- **ActionLogRepository 双后端测试**：PG（用真实 PG 或 mock）+ JSON（临时文件），write/query/count 往返。
- **trigger_source 测试**：confirm_action / automation / webhook 三路径分别传正确值。
- **admin API 测试**：权限拒绝（非 admin）+ filter 正确性 + 租户隔离。
- **集成测试**：end-to-end 跑一笔 clearance Action，查 Log 确认完整链路。

## 9. 与后续 P0/P1 的衔接

| 后续项 | 如何依赖本 spec |
|---|---|
| **Action Metrics**（P0） | 从 `action_logs` 聚合（`GROUP BY action_type, outcome, failure_type`），本 spec 已保证 Log 结构可聚合 + `duration_ms` 预留 |
| **Auditability 完整闭环**（P0） | 本 spec 即闭环主体 |
| **Decision Lineage 完整**（P0 升级 P1） | 本 spec 已留 `llm_model/skill_id/session_id` 字段，P1 注入 agent contextvar |
| **Action Revert**（P1） | 读 Log 的 affected_objects 反演副作用（仅 edits，不重放 notification/external_call） |
| **agent 身份**（P1） | 本 spec 的 `actor_type=agent` + `trigger_source` 已为区分人/agent 奠基；P1 的 agent 服务账号体系补 actor_id 规范 |
| **agent ops 仪表盘**（P1） | 本 spec 的 admin API + Log 是仪表盘数据源 |

## 10. 开放问题（待 review 时确认）

1. **JSON 后端文件增长**：永久保留 + append-only，高频 workspace 文件会膨胀。MVP 可接受？还是 JSON 后端加 10000 条滚动（PG 后端不滚）？
2. **admin UI 是否 P0**：§6.2 建议 UI 后置 P1，MVP 只交付 API。是否接受？
3. **params 掩码字段集合**：默认硬编码 `password/password_hash/token/secret` 是否够？还是要从 ontology 元数据推导（per-property sensitivity，远期）？
