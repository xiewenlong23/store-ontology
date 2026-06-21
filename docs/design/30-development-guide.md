# 平台开发规范

> **状态**：✅ 当前（已实现）。本规范回答"怎么开发内核/行业包代码"：Tool/Skill 开发、错误处理、多 workspace、代码规范、测试。
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
| **内核工具（固定）** | 通用原子操作，所有行业包共享 | ✅ 8 个 | `query_entity`/`create_entity`/`update_entity`/`traverse_relation`/`execute_action`/`confirm_action`/`query_task`/`update_task` |
| **行业包工具（聚合）** | 行业包专属读操作 | ✅ 按行业包聚合 | retail: `query_near_expiry`；equipment_repair: `query_repair_tickets` |
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
    workspace_name: str = "customer_default",       # 内核工具标配：workspace 隔离
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
2. **行业包工具**：写在行业包的 `tools_module`（如 `workspace/retail/skills/clearance_workflow/tools.py`），导出 `TOOLS` 列表；`main._aggregate_pack_tools()` 自动聚合。
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

> **现状说明**：当前已落地的只有 Action 级 `submission_criteria`（角色白名单 + 条件）和 Repository 的 workspace 隔离。完整 RBAC 引擎、审计日志留 v2（见 [`roadmap.md`](./roadmap.md)）。

### 4.1 edits-only-via-actions 使用

标记 Object Type 为"只能通过 Action 修改"：
1. **TTL 元数据**：`:edits_only_via_actions "true"`
2. **Repository 检查**：`Repository.write()` 自动查 `edits_only_via_actions`，为 True 且未 `bypass_action_check` 时抛 `ActionRequiredError`
3. **Action 执行器绕过**：`ActionExecutor` 内部 `bypass_action_check=True`；通用 CRUD 不传，自然被拦截

### 4.2 submission_criteria（Action 级门控）

`submission_criteria` 独立于（未来的）粗粒度 RBAC：粗粒度答"谁能用 execute_action"，submission_criteria 答"给定 user+参数，这个 action 实例能否提交"。MVP 支持 `roles` 白名单 + `is`/`is_not` 条件。完整操作符（gte/matches/value_ref）留 v2。

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

已实现在 `agent/engine/repository.py`：`fcntl.flock` 文件锁（Unix）+ 临时文件 `os.replace` 原子替换 + 写入前 `.bak` 备份。v2 换 PG 后由数据库事务保证。

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

`Repository.read(entity_type, tc, filters)` 按 `tc.matches(record)` 过滤（list comprehension）。旧数据（只有 `customer_id` 无 `workspace_name`）视为 `customer_default` + 通配 org（向后兼容）。

---

## 7. 代码规范

### 7.1 命名约定

| 类别 | 规范 | 示例 |
|------|------|------|
| Python 文件 | snake_case | `state_machine.py`, `discount_rules.json` |
| Python 类 | PascalCase | `ObjectType`, `IndustryPack`, `ValueChainProcess` |
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
├── main.py                     # 入口：FastAPI + Agent + 端点 + webhook
├── engine/                     # 核心引擎（内核，不依赖任何行业包符号）
│   ├── parser.py / repository.py / executor.py / action_loader.py
│   ├── state_machine.py / preview_cache.py / pack.py
│   ├── workspace.py / workspace_bootstrap.py / tenant.py / bootstrap.py
│   ├── scheduler.py / schemas.py / errors.py
├── tools/                      # 系统原子 Tool（query/crud/action + shared）
└── skills/                     # 系统 Skill（platform-help）
workspace/                      # workspace 层（行业包 + 客户实例）
├── customer_default/config.yaml
├── retail/{pack.py, ontology/domains/<域>/, data/, skills/}
└── equipment_repair/{pack.py, ontology/domains/, data/, skills/}
```

**导入规则**：`engine/` 不 import 任何 `workspace/` 符号（内核不依赖行业包）。行业包通过注册表（`register_pack`）在 import 时自报家门，`bootstrap()` 统一发现。

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
| **pack 注册隔离** | 测 pack 的测试用 `clear_packs()` fixture 清理全局注册表 |
