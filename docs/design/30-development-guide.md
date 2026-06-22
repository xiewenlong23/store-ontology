# 平台开发规范

> **状态**：✅ 当前（已实现）。本规范回答"怎么开发内核/工作目录代码"：Tool/Skill 开发、错误处理、多 workspace、代码规范、测试。
> **配套**：架构总览见 [`00-architecture.md`](./00-architecture.md)；建模硬规范见 [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md)；**新增 Object/Link/Action 的操作步骤见 [`manual/01-onboarding.md`](./manual/01-onboarding.md)**（Phase A-F）。

---

## 1. 本体开发规范

> 本节是 [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md) 的工程化补充，侧重**操作步骤**。建模原则、命名约定、反模式详见建模规范；**新增 Object/Link/Action 的完整 Phase A-F 流程见 [`manual/01-onboarding.md`](./manual/01-onboarding.md)**。

### 1.1 Object Type 放哪

- **TTL 文件**：`workspace/<pack>/ontology/domains/<域>/domain.ttl`（每个能力域一个 TTL）。
- **种子数据**：`workspace/<pack>/data/<entity_type>.json`（空数组或种子）。
- **Pydantic 镜像**：`agent/engine/schemas.py`（如需静态校验）。

```turtle
###  http://example.org/storeontology#NewObject
:NewObject a :Class ;
    rdfs:label "New Object"@en ;
    rdfs:comment "新实体的业务描述" ;
    :storageFile "new_objects.json" ;
    :labelZH "新实体"@zh ;
    :propertyList "id:string, name:string, status:string" ;
    :edits_only_via_actions "true" .   # 受治理实体加此标记（见架构 §2.3）
```

### 1.2 Link Type 放哪

同能力域的 `domain.ttl`。**via 归属原则**（建模规范 §4.3，最易错）：`via` 字段必须属于 range 对象（终点）。如 `Store → Employee, via="store_id"`，`store_id` 是 Employee 的属性。

### 1.3 Action Type 放哪

- **域内 Action**（操作能力域实体）：`workspace/<pack>/ontology/domains/<域>/actions/*.yaml`。
- **流程专属 Action**（状态迁移类，如 submit/approve）：价值链流程的 `actions_dir`（如 `workspace/retail/skills/clearance_workflow/actions/`）。
- 每个 Action 一个 YAML，含 `api_name`/`target_object_type`/`edits_object_types`/`locator_field`/`parameters`/`submission_criteria`/`side_effects`。详见 [`20-api-data-contract.md`](./20-api-data-contract.md) §3 与建模规范 §5。

> **重要**：Action 是**声明式**的——执行逻辑由 `ActionExecutor` 按 `side_effects` 数据驱动执行，**不需要在 executor 里为每个新 Action 加分支代码**。新增 Action 只加 YAML，零改内核。

### 1.4 本体变更自检清单

完整清单见建模规范 §9。快速版：
- [ ] TTL 格式正确，Parser 可解析
- [ ] `api_name` / `storageFile` / `labelZH` 均已填写
- [ ] `via` 字段归属正确（属于 range 对象）
- [ ] 种子数据 `workspace/<pack>/data/*.json` 已创建，每条带 `workspace_name`（+ `org_unit_id` 若需 org 隔离）
- [ ] 受治理实体标记 `edits_only_via_actions "true"`
- [ ] 不存在 Anti-pattern（建模规范 §8）
- [ ] 相关 SKILL.md 已更新（告知 LLM 新实体/工具）

---

## 2. Tool 开发规范

### 2.1 Tool 分类

| 类别 | 适用场景 | 现状 | 示例 |
|------|---------|------|------|
| **内核工具（固定）** | 通用原子操作，所有工作目录共享 | ✅ 8 个 | `query_entity`/`create_entity`/`update_entity`/`traverse_relation`/`execute_action`/`confirm_action`/`query_task`/`update_task` |
| **工作目录工具（聚合）** | 工作目录专属读操作 | ✅ 按工作目录聚合 | retail: `query_near_expiry`；customerA: `query_repair_tickets` |
| **OS 原子工具** | 操作系统级底层操作 | 🔜 预留，未实现 | `http_call`/`db_query` |

> **通用 CRUD 降级**：`create_entity`/`update_entity` 被 `edits_only_via_actions` 拦截——对核心实体的写操作会被 Repository 拒绝（抛 `ActionRequiredError`）。详见架构 §2.3。

### 2.2 Tool 编写规范

```python
from langchain_core.tools import tool
import agent.tools.shared as shared

@tool
def new_tool_name(
    required_param: str,                            # 必填，有类型注解
    optional_param: str = None,                     # 可选，有默认值
    workspace_name: str = "jjy",       # 内核工具标配：workspace 隔离
    org_unit_id: str = "*",                         # 内核工具标配：org 范围
) -> str:                                           # 返回必须是 str
    """工具的一句话描述（注入 LLM prompt）。

    Args:
        required_param: 参数说明（注入 prompt）
        workspace_name + org_unit_id 决定可见范围。
    """
    tc = shared._tc(workspace_name, org_unit_id)
    # ... 经 shared._get_repo(tc) / shared._get_executor() 操作 ...
    return shared._wrap({"type": "new_type", ...}, "人类可读摘要")
```

**规则**：
- 所有参数有类型注解；返回 `str`
- docstring 第一行注入 LLM prompt——写清楚
- 内核工具标配 `workspace_name` + `org_unit_id` 参数，经 `shared._tc()` 构造 `TenantContext`
- 经 `shared._wrap(data, summary)` 统一返回格式（summary + `<!--COPILOTKIT_DATA-->`）

#### 错误处理

```python
@tool
def my_tool(...) -> str:
    try:
        ...
    except OntologyError as e:        # 业务/校验错误
        return shared._wrap({"success": False, "error": str(e)}, f"操作失败: {e}")
    # 不抛异常到 Tool 之外——全部捕获转错误消息，LLM 能读到并自行修正
```

- 错误信息返回为纯文本/JSON，LLM 能读到并自行修正
- 区分：参数错误 → LLM 可修正；权限错误 → 告知用户；内部错误 → 建议重试

### 2.3 Tool 注册流程

1. **内核工具**：写在 `agent/tools/{query,crud,action}_tools.py`，已自动加入 `main.tools` 列表。
2. **工作目录工具**：写在工作目录的 `tools_module`（如 `workspace/retail/skills/clearance_workflow/tools.py`），导出 `TOOLS` 列表；`_build_ws_tools(ws_name)` 自动聚合。
3. **SKILL.md**：新 Tool 改变 LLM 可用操作时，更新相关 Skill 的 `allowed_tools` 与工具使用策略。

---

## 3. Skill 开发规范

### 3.1 创建新 Skill 步骤

1. **确定类型**：`workflow`（流程编排）还是 `domain_knowledge`（领域知识）。
2. **创建目录**：`workspace/<pack>/skills/<skill_name>/SKILL.md`（workspace Skill，高优先级）；或 `agent/skills/<skill_name>/SKILL.md`（系统 Skill，所有 workspace 共享，低优先级）。
3. **编写 SKILL.md**（frontmatter + 内容）：

```markdown
---
name: new-skill
description: 简短描述
type: workflow
allowed_tools: query_entity, execute_action, confirm_action
license: MIT
---
# Skill 标题
## 何时使用
## 步骤
### Step 1：...
## 禁止事项
```

4. **验证加载**：启动后端，在对话中触发 Skill 加载（SkillsMiddleware 按需加载），确认内容进 Agent 上下文。

### 3.2 Skill 编写规则

| 规则 | 说明 |
|------|------|
| **allowed_tools 必填** | 限制 Skill 能建议 LLM 使用的 Tool 范围 |
| **不重复定义数据值** | 折扣率等数值引用本体数据（`discount_rules.json`），不在 Skill 重复写 |
| **工具名/实体名必须准确** | 引用 Tool 函数名（`query_near_expiry`）、Object Type TTL 定义名（`NearExpiryProduct`），不用别名 |
| **步骤可操作** | 每步有明确 Tool 调用或判断，不写"分析数据"等模糊指令 |
| **禁止事项明确** | 列出 LLM 不应做的事（跳过 preview、操作过期商品等） |

### 3.3 Skill 目录结构（2 级加载）

```
workspace/retail/skills/              ← workspace skills（高优先级，根路径）
├── store_ontology/SKILL.md           ← 领域知识
└── clearance_workflow/SKILL.md       ← 流程编排
agent/skills/                         ← 系统 skills（低优先级，/system/<name>/ 路由）
└── platform-help/SKILL.md
```

`CompositeBackend` 把系统 skills 挂在 `/system/` 路由，workspace skills 在根路径（同名时 workspace 覆盖系统）。

---

## 4. 权限开发规范

> **现状说明**：✅ 认证 + 完整 RBAC×ABAC 权限引擎已落地（2026-06-22，详见架构文档 §11）。本节先讲既有两项（edits-only / submission_criteria），再讲 v2 权限开发（§4.3）。审计日志仍 🔜 v2。

### 4.1 edits-only-via-actions 使用

标记 Object Type 为"只能通过 Action 修改"：
1. **TTL 元数据**：`:edits_only_via_actions "true"`
2. **Repository 检查**：`Repository.write()` 自动查 `edits_only_via_actions`，为 True 且未 `bypass_action_check` 时抛 `ActionRequiredError`
3. **Action 执行器绕过**：`ActionExecutor` 内部 `bypass_action_check=True`；通用 CRUD 不传，自然被拦截

### 4.2 submission_criteria（Action 级门控）

`submission_criteria` 独立于粗粒度 RBAC（§4.3）：粗粒度答"谁能用 execute_action"，submission_criteria 答"给定 user+参数，这个 action 实例能否提交"。现已支持 `roles` 白名单 + 操作符全集 `is`/`is_not`/`gte`/`lte`/`gt`/`lt`/`matches`/`includes`/`value_ref`（架构文档 §11.7）。🔜 嵌套 AND/OR 逻辑留 v2。

### 4.3 认证与权限开发（v2，✅ 已落地）

> 详见架构文档 §11 与 [`docs/superpowers/specs/2026-06-22-v2-auth-rbac-design.md`](../superpowers/specs/2026-06-22-v2-auth-rbac-design.md)。本节给开发者日常接入要点。

**认证接入**：
- JWT（HS256，access 2h + refresh 7d）+ bcrypt 密码 hash。端点 `/api/auth/{login,refresh,me,logout}`（API 契约见 `20-api-data-contract.md` §1.4）。
- `auth_middleware`（`agent/main.py`）：验签 + token.ws 白名单含 `X-Workspace`（跨 ws 越权防护）→ `auth_ctx` contextvar。
- **强制模式** `AUTH_REQUIRED=true`（默认）：无 token / 过期 / 跨 ws 越权 → 401；豁免 `/api/auth/login` + `/health`。开发兜底设 `=false`。
- **新增 admin 端点鉴权**：用 `require_admin(actor)` 统一辅助（`agent/engine/admin_ontology_api.py`），`system_admin` 角色或 bootstrap 初始 `admin` 账号放行，其余 403。**禁止** 在各端点手写角色判断。

**PermissionEvaluator 求值**（`agent/engine/permission.py`）：
- 5 类资源：`can_use_tool` / `can_read_object`+`can_write_object` / `readable_properties`+`denied_properties`+`can_write_property` / `can_execute_action` / `can_traverse_link`。
- 正反向语法 + `*` 通配；求值顺序：`system_admin` 短路 → PermissionGrant runtime override（deny 优先）→ TTL 元数据 → allow-by-default。
- **Tool 接入**：5 个内核工具已全部接入（query/query_task 读 + 属性 mask；traverse_relation 遍历校验；execute_action/confirm_action tool+action 级；create/update_entity 写校验）。新增 Tool 时**必须** 在 `tool_manifest.yaml` 声明权限（见下）。

**Tool 权限声明（tool_manifest.yaml）**：
- Tool 不在 TTL，用 YAML 声明（替代"Tool 在 TTL"）。内核 8 工具默认声明在 `agent/tools/manifest.yaml`；各 workspace 专属工具声明在 `workspace/<pack>/tool_manifest.yaml`。
- 未声明 = allow-by-default（开发友好，但生产前**应当** 显式声明受治理工具的 roles）。

**actor 派生（信任修复，WP6）**：
- actor 一律从 `shared._get_actor()` 派生：`auth_ctx` → `Employee.user_id` → role。**禁止** 让 LLM 自报 actor/role（`execute_action` 已删 `actor_role` 参数）。
- 兜底：contextvar 缺失 / `AUTH_REQUIRED=false` + anonymous → `system_admin`（开发/测试）；生产强制时 anonymous 拒。

**TTL 权限元数据**：建模侧（ObjectType 属性级 `:read_roles`/`:read_except`/`:write_*` + 嵌套 `:property[]`、Link 的 `:use_roles`/`:use_except`）的写法见 `40-ontology-modeling-spec.md` §12.3。

---

## 5. 错误处理规范

### 5.1 Tool 层错误分类

| 错误类型 | 异常（`agent/engine/errors.py`） | Tool 返回 | LLM 行为 |
|---------|--------------------------------|----------|---------|
| 参数错误 | `ValidationError` | "参数错误：{字段+约束}" | LLM 修正重试 |
| 实体不存在 | `EntityNotFoundError` | "未找到：{type} id={id}" | LLM 告知用户/创建 |
| Action 不存在 | — | "Action Type '{name}' 不存在，可用：{列表}" | LLM 修正 action_type |
| Action 校验失败 | `SubmissionCriteriaError` | "提交被拒：{fail_msg}" | LLM 告知用户约束 |
| 违反治理（绕过 Action） | `ActionRequiredError` | "{type} 写操作必须走 Action" | LLM 改用 execute_action |
| Preview 过期 | — | "预览已过期，请重新 execute_action" | LLM 重新 preview |
| 内部错误 | `Exception` | "内部错误，请稍后重试" | LLM 告知用户 |

### 5.2 Repository 层原子写入 + 文件锁

- **JSON 后端**（`agent/engine/repository.py`）：`fcntl.flock` 文件锁（Unix）+ 临时文件 `os.replace` 原子替换 + 写入前 `.bak` 备份。
- **PG 后端**（`agent/engine/pg_data_repo.py`）：由数据库事务保证原子性（已落地，见 §5.3 / roadmap §1）。后端选择由 `is_pg_enabled() and ping()` 决定，缺失回落 JSON。

### 5.3 存储后端开发（v2，✅ 已落地）

> 详见 roadmap §1。本节给开发者启用 / 切换后端的要点。

**双后端架构**：
- Repository 接口不变；实现二选一：`JSONFileRepository`（默认）或 `PgDataRepository` + `PgOntologyRepository`（PG）。
- `workspace_bootstrap.py` 按 `is_pg_enabled() and ping()` 选实现；PG 加载失败回落 JSON 并打印告警（日志出现「回落 JSON」即未生效）。
- `agent/engine/db.py`：psycopg 3 + psycopg-pool 单例连接池（4–8 连接/进程）；`transaction()` 上下文自动 commit/rollback；`DATABASE_URL` 缺失抛 `PGNotConfigured` 让上层回落。

**启用 PG 步骤**：
1. `.env` 加 `DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology`。
2. `docker compose up -d` 起 PG（compose 已含 pgvector 扩展）。
3. 跑迁移：`python agent/scripts/import_to_pg.py`（TTL/YAML/JSON → PG 幂等 upsert；支持 `--workspace retail` / `--skip-data` / `--skip-schema` / `--dry-run`）。
4. 重启后端，日志不再出现「回落 JSON」即生效。

**多副本部署注意**：每进程一个连接池已就绪；进程内 `WorkspaceAgentInstance` 缓存经 `invalidate_workspace(ws)` 失效（admin 写后触发），但**跨进程缓存失效通知机制 defer**（roadmap §1）。单进程 uvicorn 部署够用。

**Schema（`agent/sql/schema.sql`）**：`object_types` / `object_type_properties` / `link_type` / `action_types` / `entities` 五表；关系列存核心查询字段，JSONB 存复杂结构（parameters/side_effects/properties）；含 TenantContext 过滤索引（`workspace_name + org_unit_id`）+ JSONB GIN 索引 + `updated_at` 触发器。pgvector 扩展已建（embedding 列预留，本轮注释掉）。

---

## 6. 多 workspace 开发规范

### 6.1 TenantContext（`agent/engine/tenant.py`）

```python
@dataclass(frozen=True)
class TenantContext:
    workspace_name: str           # 硬隔离边界
    org_unit_id: str = "*"        # workspace 内权限范围（'*'=总部全可见）

    def matches(self, record: dict) -> bool: ...   # 判断记录对当前上下文是否可见
    @classmethod
    def from_headers(cls, headers) -> "TenantContext": ...  # X-Workspace 优先，回退 X-Customer-ID
```

### 6.2 各层传递

| 层 | 代码位置 | 传递方式 |
|----|---------|---------|
| Middleware | `agent/main.py` | 读 `X-Workspace` → `TenantContext` → contextvar `tenant_ctx` |
| Tool | 每个 `@tool` | 参数 `workspace_name`/`org_unit_id` → `shared._tc()`；或 shared helper 从 `tenant_ctx` contextvar 解析 |
| Repository | `Repository.read/write(tc, ...)` | 显式 `TenantContext` 参数，按 `workspace_name`+`org_unit_id` 过滤 |
| 自动化（定时器/webhook） | 注册时绑定 workspace/executor | headless，无前端 |

### 6.3 Repository 过滤实现

`Repository.read(entity_type, tc, filters)` 按 `tc.matches(record)` 过滤（list comprehension）。旧数据（只有 `customer_id` 无 `workspace_name`）视为 `jjy` + 通配 org（向后兼容）。

---

## 7. 代码规范

### 7.1 命名约定

| 类别 | 规范 | 示例 |
|------|------|------|
| Python 文件 | snake_case | `state_machine.py`, `discount_rules.json` |
| Python 类 | PascalCase | `ObjectType`, `WorkspaceDef`, `ValueChainProcess` |
| Python 函数 | snake_case | `build_ontology_prompt`, `calculate_discount` |
| Python 常量 | UPPER_SNAKE_CASE | `TASK_TRANSITIONS`, `TERMINAL_STATES` |
| Tool 函数名 | snake_case | `query_entity`, `execute_action` |
| Tool JSON type | snake_case | `near_expiry_list`, `action_preview` |
| Action api_name | snake_case | `create_clearance_task` |
| TTL Object Type | PascalCase | `NearExpiryProduct`, `Task` |
| TTL Link Type | snake_case | `has_near_expiry`, `located_in` |
| 前端组件 | PascalCase | `HomePage` |
| 前端文件 | kebab-case | `home-page.tsx`, `route.ts` |
| Skill 目录 | kebab_case 或 snake_case | `clearance_workflow`, `store_ontology` |

### 7.2 类型注解

所有 Python 函数必须有类型注解。`from __future__ import annotations` 或 `X | None` 语法。

### 7.3 模块组织（as-built）

```
agent/                          # 后端
├── main.py                     # 入口：FastAPI + per-workspace agent 构建 + 自写 endpoint + webhook
├── engine/                     # 核心引擎（内核，不依赖任何工作目录符号）
│   ├── parser.py / repository.py / executor.py / action_loader.py
│   ├── state_machine.py / preview_cache.py / pack.py（WorkspaceDef/CapabilityDomain/ValueChainProcess）
│   ├── workspace.py（WorkspaceConfig）/ workspace_bootstrap.py / tenant.py / bootstrap.py
│   ├── scheduler.py / schemas.py / errors.py / discount_stub.py / onboarding.py
├── tools/                      # 系统原子 Tool（query/crud/action + shared）
└── skills/                     # 系统 Skill（platform-help）
workspace/                      # workspace 层（工作目录 + 客户实例）
├── jjy/{config.yaml, workspace.py, ontology/domains/, data/, skills/}
├── retail/{workspace.py, ontology/domains/<域>/, data/, skills/}
└── customerA/{workspace.py, ontology/domains/, data/, skills/}
```

> 注：`engine/pack.py` 文件名保留历史，但内容是 `WorkspaceDef`（不含 IndustryPack）。

**导入规则**：`engine/` 不 import 任何 `workspace/` 符号（内核不依赖工作目录）。工作目录通过注册表（`register_workspace_dir`）在 import 时自报家门，`bootstrap()` 统一发现。

---

## 8. 测试规范

### 8.1 测试结构

```
agent/tests/
├── conftest.py                  # pytest fixtures（sys.path 配置、tmp_data_dir 等）
├── _clearance_helper.py         # 测试辅助：从 retail pack 构建 clearance executor
├── e2e/                         # 端到端（含 ScriptedLLM 的 Agent 对话）
└── test_*.py                    # 单元 + 集成
```

### 8.2 运行方式

```bash
cd agent
/opt/miniconda3/envs/store-ontology/bin/python -m pytest -q            # 全部
/opt/miniconda3/envs/store-ontology/bin/python -m pytest tests/test_tools.py -v  # 单文件
```

> **注意**：必须用 conda env 的 Python（`/opt/miniconda3/envs/store-ontology/bin/python`，3.11+），系统 Python 无项目依赖。

### 8.3 测试原则

| 原则 | 说明 |
|------|------|
| **Parser 可独立测试** | EntityRegistry 只依赖 TTL/YAML 字符串，用 fixture 传入 |
| **Repository 可 monkeypatch** | Tool 测试 monkeypatch `shared._get_repo`/`_get_executor` 指向临时数据 |
| **Tool 返回字符串** | 测试返回值是合法字符串格式（含 COPILOTKIT_DATA 或错误文本） |
| **不测 LLM 调用** | 集成测试用 ScriptedLLM mock |
| **数据隔离** | 每个测试用例用独立临时数据目录（`tmp_path` fixture），不污染 `workspace/*/data/` |
| **pack 注册隔离** | 测 pack 的测试用 `clear_workspace_dirs()` fixture 清理全局注册表 |
