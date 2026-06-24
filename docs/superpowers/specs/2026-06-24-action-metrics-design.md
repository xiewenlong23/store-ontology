# Action Metrics 设计

> **徽章**：📋 spec
> **状态**：待 review → 待写实施 plan
> **来源**：[`palantir-implementation-assessment.md`](../../design/palantir-implementation-assessment.md) §7 P0（F-AT-40/41）+ §36 P0（F-XC-09 Auditability 的可观测维度）
> **架构依据**：[`00-architecture.md`](../../design/00-architecture.md) §12.4（agent 可观测性——Action Metrics 是三件套之一）
> **数据源依赖**：[`action-log-design.md`](./2026-06-22-action-log-design.md) 已落地的 `action_logs`（PG 表 / JSON 文件）
> **日期**：2026-06-24

## 1. 目标与非目标

### 1.1 目标（P0）

从已落地的 `action_logs` 聚合产出 **agent 运维可观测性指标**，解决"生产环境 agent 是黑箱"的另一半（Action Log 解决了"记什么"，Metrics 解决"聚合看什么"）：

1. **成功率与时延**（F-AT-40）：per-action-type + overall 的 total/success/failure/success_rate/p95_duration。
2. **失败分类计数**（F-AT-41）：按 8 类 failure_type 聚合，支撑"agent 健康诊断"（哪类失败最多）。
3. **为 agent ops 仪表盘（§12.4 P1）奠基**：本 spec 只交付聚合 API + 数据结构，仪表盘前端随 admin 控制台整体增强 P1 一并做。

### 1.2 非目标

- **不实现** admin 控制台 dashboard 页（P1，与 Action Log admin UI 同批）。
- **不实现** 告警规则 / 阈值触发（属 §20 agent ops 仪表盘的告警维度，P1）。
- **不实现** 物化预算表（M1 决策为按需现算，无调度 job、无独立 metrics 表）。
- **不实现** per-actor / per-trigger_source 维度（M4 决策为 overall + per-action_type + per-failure_type；per-actor 远期）。
- **不动** executor、不动 schema、不动 workspace_bootstrap（纯读路径，复用 ActionLogRepository）。
- **不实现** LLM 可查询 Tool（审计/运维是 admin 人的职责，与 Action Log §6 一致）。

## 2. 已确认设计决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| M1 | 聚合策略 | 按需现算（查询时从 action_logs 聚合） | 零额外存储 / 零调度 / 数据始终新鲜；MVP 规模（手动 + 30min scheduler tick）下 action_logs 30 天窗几千行，PG 有索引毫秒级，JSON 全量扫也够 |
| M2 | 默认时间窗 | 30 天（对齐 Palantir Action Metrics） | `since`/`until` query param 可覆盖 |
| M3 | P95 计算 | PG `percentile_cont(0.95) WITHIN GROUP`；JSON 排序取 idx | 双后端各自最优；JSON 端 `duration_ms` 排序后取 `ceil(0.95 * n)` |
| M4 | 聚合维度 | overall + per-action_type + per-failure_type | per-actor / per-trigger_source 远期（YAGNI MVP） |
| M5 | 交付范围 | 仅 admin API | UI 随 admin 控制台 P1（与 Action Log 一致） |
| M6 | 失败分类 | 复用 Action Log 的 8 类 failure_type | 数据源已分类，无需重新定义 |

## 3. API 设计

### 3.1 端点

```
GET /api/admin/customers/{cid}/action-metrics
```

**Query params**（全部可选）：
- `since`（ISO timestamp）：窗口起点，默认 30 天前
- `until`（ISO timestamp）：窗口终点，默认 now
- `action_type`（string）：过滤特定 action——**overall 与 by_action_type 都只统计该 action**（聚焦看单一 action 健康度时用）。通常不传，看全貌。
- `trigger_source`（string）：可选过滤（`llm_session`/`automation`/`webhook`/`admin_api`），默认不过滤

**鉴权**：`require_admin(ws)`（与 Action Log admin API、admin.py 一致）。

### 3.2 响应结构

```json
{
  "window": {"since": "2026-05-25T...", "until": "2026-06-24T..."},
  "filters": {"action_type": null, "trigger_source": null},
  "overall": {
    "total": 150,
    "success": 142,
    "failure": 8,
    "success_rate": 0.947,
    "p95_duration_ms": 187
  },
  "by_action_type": {
    "create_clearance_task": {
      "total": 50, "success": 48, "failure": 2,
      "success_rate": 0.96, "p95_duration_ms": 210
    },
    "deduct_stock": { "total": 80, "success": 80, "failure": 0, "success_rate": 1.0, "p95_duration_ms": 15 },
    ...
  },
  "by_failure_type": {
    "invalid_param": 3,
    "permission_denied": 2,
    "submission_failed": 1,
    "entity_not_found": 1,
    "illegal_transition": 1,
    "unknown_action": 0,
    "side_effect_error": 0,
    "unclassified": 0
  }
}
```

**约定**：
- `success_rate` 保留 3 位小数（`round(total and success/total, 3)`，`total=0` 时为 `null`）。
- `p95_duration_ms`：`total=0` 或所有 duration 为 None 时为 `null`。
- `by_failure_type` **始终列出全 8 类**（含 0 计数），便于前端稳定渲染。
- `by_action_type` 只含窗口内有日志的 action（空 action 不列）。

## 4. 存储层扩展

### 4.1 ActionLogRepository 新增 aggregate() 方法

在 `ActionLogRepository` 抽象 + 两实现上加：

```python
def aggregate(self, ws_name: str, *, since=None, until=None,
              action_type=None, trigger_source=None) -> dict:
    """聚合 action_logs 产出 Metrics（spec §3.2 结构）。"""
    raise NotImplementedError
```

**PG 实现**：单条 SQL，多 GROUP BY 集合 + `percentile_cont`：
```sql
-- overall（一行）
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE outcome='success') AS success,
       COUNT(*) FILTER (WHERE outcome='failure') AS failure,
       COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms), 0) AS p95
FROM action_logs
WHERE workspace_name=%s AND timestamp BETWEEN %s AND %s [+可选 action_type/trigger_source]

-- by_action_type（GROUP BY action_type，同上聚合列）
-- by_failure_type（GROUP BY failure_type，COUNT）
```
3 条 SQL（或 1 条带 UNION/CASE 的）即可。索引 `idx_action_logs_ws_time` + `idx_action_logs_ws_action` 覆盖。

**JSON 实现**：`_load()` 全量读 → Python `Counter` + 排序百分位：
```python
rows = [r for r in self._load() if r["workspace_name"]==ws_name and 时间窗内]
# overall / by_action_type 用 Counter；p95 = sorted(durations)[ceil(0.95*n)-1]
# by_failure_type 用 Counter(failure_type)，补齐 8 类 0 值
```

### 4.2 不新增表、不新增字段

复用 Action Log 的 `action_logs` 表/文件。`duration_ms`、`failure_type`、`outcome`、`action_type`、`trigger_source` 列均已存在。

## 5. 执行链路改造点

| 文件 | 改动 |
|---|---|
| `agent/engine/action_log_repo.py` | `ActionLogRepository` 抽象加 `aggregate()`；`JSONFileActionLogRepository` + `PgActionLogRepository` 各实现 |
| `agent/routers/action_metrics.py` | 新文件：1 个 GET 端点，鉴权 + 调 `repo.aggregate()` + 返回 JSON |
| `agent/routers/__init__.py` | 导出 `action_metrics_router` |
| `agent/main.py` | include `action_metrics_router` |

**不动**：executor / schema / workspace_bootstrap / action_log.py（纯读路径）。

## 6. 测试策略

- **repo 聚合单测**（JSON 必跑）：构造已知 log 集（混合 success/failure/多 action_type/多 failure_type/已知 duration），断言 overall/by_action_type/by_failure_type 数值精确匹配。
- **边界**：空 log（total=0，success_rate=null，p95=null）；单条；全 failure；窗口过滤生效。
- **PG 聚合测试**：PG 可用时跑（用真实 action_logs 表插数据 + 聚合），不可用 skip（与 Action Log PG 测试同模式）。
- **API 测试**：鉴权（非 admin 403）、空响应结构正确、有数据响应正确、query param 过滤（since/until/action_type/trigger_source）。
- **回归**：跑 Action Log 现有测试确认 aggregate() 加入不破坏现有 query/count/write。

## 7. 与后续 P0/P1 的衔接

| 后续项 | 如何依赖本 spec |
|---|---|
| **agent ops 仪表盘**（§12.4 P1 / §20） | 本 spec 的 admin API 是仪表盘的数据源；告警规则（threshold→notification）在仪表盘 spec 里做 |
| **Decision Lineage 运维视图** | per-actor 维度（M4 远期）补上后，可看"哪个 agent 自主触发最多失败" |
| **notification 投递**（P0 并列项） | 独立 spec，不依赖本 spec；但告警规则会同时依赖两者（Metrics 检测异常 + notification 投递） |
| **Writeback Connectors**（P1） | 外部监控系统集成时，本 spec 的 JSON 是出口格式 |

## 8. 开放问题（待 review 时确认）

1. **时间窗默认 30 天是否合适**：clearance 场景 30 天可能 log 量小；是否默认 7 天更实用？倾向 30 天（对齐 Palantir，且 admin 可传 since 覆盖）。
2. **是否加 per-trigger_source 维度**：当前 M4 不做（只支持 trigger_source 过滤）。若 reviewer 认为区分"llm 失败 vs automation 失败"是运维刚需，可加。
3. **P95 还是 P50/P99 都给**：当前只 P95。是否同时返回 P50/P99？倾向 MVP 只 P95（YAGNI），前端要再加。
