# 平台开发规范

> **版本**：0.1.0（MVP）
> **最后更新**：2026-06-20

---

## 1. 本体开发规范

> 本节是 [`docs/业务本体建模规范.md`](../业务本体建模规范.md) 的工程化补充，侧重于**操作步骤**。建模原则和命名约定参见原文档。

### 1.1 新增 Object Type 步骤

1. **定义 TTL**：在 `backend/ontology/store.ttl` 中添加 Object Type 定义

```turtle
###  http://example.org/storeontology#NewObject

:NewObject a :Class ;
    rdfs:label "New Object"@en ;
    rdfs:comment "新实体的业务描述" ;
    :storageFile "new_objects.json" ;
    :labelZH "新实体"@zh ;
    :propertyList "id:string, name:string, status:string" .
```

2. **创建数据文件**：在 `data/` 下创建 `new_objects.json`（空数组 `[]` 或含种子数据）

3. **更新 Pydantic 模型**：在 `backend/models/schemas.py` 中添加对应的 `BaseModel`

```python
class NewObject(BaseModel):
    id: str
    name: str
    status: str
```

4. **验证 Parser**：启动后端，调用 `query_entity(entity_type="NewObject")` 确认 Parser 正确解析

5. **检查约束**：
   - [ ] `api_name`（TTL 中的 Class URI）唯一
   - [ ] `storageFile` 与 `data/` 下文件名一致
   - [ ] `labelZH` 已填写
   - [ ] 属性类型在白名单内（string / integer / float / datetime / enum）

### 1.2 新增 Link Type 步骤

1. **定义 TTL**：在 `store.ttl` 中添加

```turtle
###  http://example.org/storeontology#has_new_thing

:has_new_thing a :LinkType ;
    rdfs:label "has new thing"@en ;
    :domain :ParentObject ;
    :range :ChildObject ;
    :via "parent_id" ;
    :labelZH "拥有新事物"@zh .
```

2. **验证 via 所有权**：`via` 字段**必须属于 range 对象（终点）**。如 `Store → Employee, via="store_id"`，`store_id` 是 Employee 的属性。这是"via 所有权原则"——反模式见建模规范。

3. **测试遍历**：调用 `traverse_relation(source_type="ParentObject", source_id="xxx", relation="has_new_thing")`

### 1.3 新增 Action Type 步骤（YAML）

1. **创建 YAML 文件**：`backend/ontology/actions/new_action.yaml`

```yaml
api_name: new_action
display_name: 新操作
description: 描述这个 Action 的业务语义
status: active
target_object_type: TargetObject
edits_object_types: [TargetObject, Task]
parameters:
  - { name: param1, type: string, required: true, description: "参数说明" }
submission_criteria:
  roles: [store_manager]
  conditions: []
side_effects: []
```

2. **扩展 Parser**：`OntologyParser` 需支持从 `actions/*.yaml` 加载 Action Type（MVP 新增功能）

3. **在 `execute_action` 中添加处理分支**：新的 action_type 需要对应的预览逻辑

4. **在 `confirm_action` 中添加执行逻辑**：实际写入逻辑

5. **检查约束**：
   - [ ] YAML 文件名与 `api_name` 一致
   - [ ] `target_object_type` 对应的 Object Type 存在
   - [ ] `edits_object_types` 中所有 Object Type 存在
   - [ ] `submission_criteria.roles` 中所有角色在 RBAC 中有定义

### 1.4 本体变更自检清单

> 完整清单见 [`docs/业务本体建模规范.md`](../业务本体建模规范.md) 的 Review Checklist 章节。

快速版：

- [ ] TTL 格式正确，Parser 可解析
- [ ] `api_name` / `storageFile` / `labelZH` 均已填写
- [ ] `via` 字段归属正确（属于 range 对象）
- [ ] 数据文件 `data/*.json` 已创建
- [ ] Pydantic 模型已更新（如需）
- [ ] 不存在 Anti-pattern（Kitchen Sink / Golden Hammer / System Mirror）
- [ ] 相关 SKILL.md 已更新（如有新的实体/工具需要告知 LLM）

---

## 2. Tool 开发规范

### 2.1 Tool 分类

| 类别 | 适用场景 | 权限 | 示例 |
|------|---------|------|------|
| **OS 原子工具** | 操作系统级底层操作 | 仅 admin | `http_call` / `db_query`（MVP 不实现） |
| **业务查询工具** | 读操作，查数据 | RBAC 白名单 | `query_entity` / `query_near_expiry` |
| **CRUD 工具** | 通用创建/更新（降级） | RBAC，受 `edits_only_via_actions` 限制 | `create_entity` / `update_entity` |
| **Action 执行工具** | Preview/Confirm 模式 | RBAC + submission_criteria | `execute_action` / `confirm_action` |
| **任务操作工具** | 任务状态/备注更新 | RBAC | `update_task` |

### 2.2 Tool 编写规范

#### 函数签名

```python
from langchain_core.tools import tool

@tool
def new_tool_name(
    required_param: str,         # 必填参数，有类型注解
    optional_param: str = None,  # 可选参数，有默认值
) -> str:                        # 返回类型必须是 str
    """工具的一句话描述（会注入 LLM prompt）。
    
    Args:
        required_param: 参数说明（注入 prompt 的参数描述）
        optional_param: 可选参数说明
    
    Returns:
        人类可读的结果描述
    """
    ...
```

**规则**：
- 所有参数必须有**类型注解**
- 返回类型必须是 `str`
- docstring 第一行是工具描述（会注入 LLM prompt）
- `Args` 部分的描述也会注入 prompt——写清楚让 LLM 理解参数含义

#### 返回值格式

```python
def format_tool_result(human_text: str, json_type: str, data: any) -> str:
    """格式化 Tool 返回值。"""
    payload = json.dumps({"type": json_type, "data": data}, ensure_ascii=False)
    return f"{human_text}\n<!--COPILOTKIT_DATA-->\n{payload}\n<!--/COPILOTKIT_DATA-->"
```

- `human_text`：人类可读的摘要（LLM 会读这段做推理）
- `json_type`：前端渲染组件选择标识（见 API 与数据契约规范的速查表）
- `data`：结构化数据（前端 renderToolCalls 消费）

#### 错误处理

```python
@tool
def my_tool(param: str) -> str:
    try:
        # 业务逻辑
        result = do_something(param)
        return format_tool_result("操作成功", "success_result", {"id": result.id})
    except EntityNotFoundError as e:
        return f"错误：{e}。请检查参数后重试。"
    except PermissionDeniedError as e:
        return f"权限不足：{e}。当前角色无法执行此操作。"
    except ValueError as e:
        return f"参数错误：{e}。"
    except Exception as e:
        return f"内部错误：{e}。请稍后重试或联系管理员。"
```

**规则**：
- 错误信息返回为纯字符串（不嵌 JSON），LLM 能读到并自行修正
- 区分错误类型：参数错误 → LLM 可修正；权限错误 → 告知用户；内部错误 → 建议重试
- 不抛异常到 Tool 之外——所有异常在 Tool 内捕获并转为错误消息

### 2.3 Tool 注册流程

新增 Tool 后需在 **两处** 注册：

1. **`backend/ontology/tools.py`**：编写 `@tool` 函数

2. **`backend/main.py`**：添加到 tools 列表

```python
# main.py
tools = [
    query_entity, create_entity, update_entity, traverse_relation,
    execute_action, confirm_action, query_task, update_task,
    query_near_expiry,
    new_tool_name,  # ← 在这里添加
]
```

3. **`backend/skills/`**：如果新 Tool 改变了 LLM 可用的操作，更新相关 SKILL.md 的工具使用策略

---

## 3. Skill 开发规范

### 3.1 创建新 Skill 步骤

1. **确定类型**：`workflow`（流程编排）还是 `domain_knowledge`（领域知识）

2. **创建目录和文件**：

```
backend/skills/store-ontology/
└── new-skill/
    └── SKILL.md
```

> **注意**：Skill 目录名用 kebab-case，放在 `backend/skills/store-ontology/` 下（与 `store-ontology` 目录平级）。

3. **编写 SKILL.md**：

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
描述触发条件。

## 步骤
### Step 1：描述
- 调用 `tool_name(param=value)` 获取数据
- 判断逻辑...

### Step 2：描述
...

## 禁止事项
- **禁止**xxx
```

4. **验证加载**：启动后端，在对话中触发 Skill 加载（SkillsMiddleware 会按需加载），确认 Skill 内容出现在 Agent 上下文中

### 3.2 Skill 编写规则

| 规则 | 说明 |
|------|------|
| **allowed_tools 必填** | 限制 Skill 能建议 LLM 使用的 Tool 范围 |
| **不重复定义数据值** | 折扣率等数值引用本体数据（`discount_rules.json`），不在 Skill 中重复写 |
| **工具名必须准确** | 引用 Tool 函数名（如 `query_near_expiry`），不用别名 |
| **实体名必须准确** | 引用 Object Type 的 TTL 定义名（如 `NearExpiryProduct`），不用别名 |
| **步骤可操作** | 每个步骤有明确的 Tool 调用或判断逻辑，不写"分析数据"等模糊指令 |
| **禁止事项明确** | 列出 LLM 不应做的事情（跳过 preview、操作过期商品等） |

### 3.3 Skill 目录结构

```
backend/skills/
└── store-ontology/                  ← SkillsMiddleware 的 skill_filter 路径
    ├── SKILL.md                     ← 领域知识 Skill（store-ontology）
    └── clearance-workflow/
        └── SKILL.md                 ← 流程 Skill（clearance-workflow）
```

- `FilesystemBackend` 以 `backend/skills/` 为根，`skill_filter=["/store-ontology/"]` 过滤
- 每个 Skill 是 `backend/skills/{skill_name}/SKILL.md`
- Skill 内的子 Skill（如 `clearance-workflow`）是 `{skill_name}/{sub_skill_name}/SKILL.md`

---

## 4. 权限开发规范

### 4.1 RBAC 角色定义

MVP 使用简化 RBAC，3 个角色：

| 角色 | 说明 | 可用 Tool |
|------|------|----------|
| `admin` | 系统管理员 | 全部 Tool（含 OS 原子工具） |
| `store_manager` | 门店经理 | 业务查询 + Action 执行 + 任务操作 |
| `clerk` | 店员 | 业务查询（只读） |

### 4.2 edits-only-via-actions 使用

标记一个 Object Type 为"只能通过 Action 修改"：

1. **TTL 元数据**：在 Object Type 定义中添加（MVP 扩展 TTL Parser 支持）

2. **Repository 检查**：`Repository.write()` 自动检查目标 Object Type 的 `edits_only_via_actions` 标记

3. **bypass**：Action 执行器（`confirm_action`、`update_task` 状态迁移）通过 `bypass_action_check=True` 绕过

```python
# Repository 层检查逻辑
def write(self, entity_type, entity_id, data, tenant_id, bypass_action_check=False):
    obj_def = registry.object_types.get(entity_type)
    if obj_def and obj_def.edits_only_via_actions and not bypass_action_check:
        raise ActionRequiredError(
            f"{entity_type} 的写操作必须通过 Action Type 执行，"
            f"不能使用通用 CRUD。请使用 execute_action + confirm_action。"
        )
    # 正常写入...
```

### 4.3 PermissionEvaluator 接口

```python
class PermissionEvaluator(Protocol):
    def check(self, tool_name: str, context: RequestContext) -> bool:
        """检查当前用户是否有权调用指定 Tool。
        
        context 包含：user_id, role, tenant_id, tool_params
        返回 True 允许，False 拒绝。
        """
        ...
```

MVP 实现 `MVPRbacEvaluator`：role → tool 白名单映射。

---

## 5. 错误处理规范

> 策略层面见[目标架构设计文档 · 附录 C](../superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md)。本节补充 Tool 层实现规范。

### 5.1 Tool 层错误分类

| 错误类型 | Python 异常 | Tool 返回 | LLM 行为 |
|---------|-------------|----------|---------|
| **参数错误** | `ValueError` | "参数错误：{具体字段和约束}" | LLM 修正参数重试 |
| **实体不存在** | `EntityNotFoundError` | "未找到：{entity_type} id={entity_id}" | LLM 告知用户或创建 |
| **Action 不存在** | `ActionNotFoundError` | "Action Type '{name}' 不存在，可用：clearance/transfer/restock" | LLM 修正 action_type |
| **权限不足** | `PermissionDeniedError` | "权限不足：{reason}" | LLM 告知用户 |
| **Action 校验失败** | `SubmissionCriteriaError` | "提交被拒：{fail_msg}" | LLM 告知用户约束 |
| **Preview 过期** | `PreviewExpiredError` | "预览已过期（超过5分钟），请重新执行 execute_action" | LLM 重新 preview |
| **数据一致性** | `DataConflictError` | "数据冲突：{详情}" | LLM 告知用户 |
| **内部错误** | `Exception` | "内部错误，请稍后重试" | LLM 告知用户重试 |

### 5.2 Repository 层原子写入

```python
import json
import os
import tempfile

def atomic_write_json(path: str, data):
    """原子写入 JSON 文件（写临时文件 + rename）。"""
    dir_name = os.path.dirname(path)
    # 写临时文件
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        # 原子替换
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)  # 清理临时文件
        raise
```

### 5.3 文件锁（MVP 并发控制）

```python
import fcntl

def with_file_lock(lock_path, timeout=5.0):
    """文件锁上下文管理器（Unix only）。"""
    lock = open(lock_path, "w")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield lock
    except BlockingIOError:
        raise TimeoutError(f"无法在 {timeout}s 内获取文件锁")
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
```

---

## 6. 多租户开发规范

### 6.1 RequestContext

```python
from dataclasses import dataclass

@dataclass
class RequestContext:
    tenant_id: str          # 必填，由 middleware 注入
    user_id: str = None     # 可选，未来认证实现
    role: str = None        # 可选，未来认证实现
```

### 6.2 各层传递

| 层 | 代码位置 | 传递方式 |
|----|---------|---------|
| Middleware | `backend/main.py`（FastAPI middleware） | 读取 `X-Tenant-ID` header → `RequestContext` |
| Agent | `create_deep_agent()` | `RequestContext` 传入，注入系统提示 Layer 3 |
| Tool | 每个 `@tool` 函数 | 通过闭包或 contextvars 获取 `RequestContext` |
| Repository | `Repository.read/write()` | 显式参数 `tenant_id` |

### 6.3 Repository 过滤实现

```python
class JSONFileRepository:
    def read(self, entity_type: str, tenant_id: str, **filters) -> list:
        data = self._load_json(entity_type)
        # tenant_id 过滤
        if tenant_id:
            data = [item for item in data if item.get("tenant_id") == tenant_id]
        # 其他过滤条件...
        return data
```

> MVP 阶段现有数据不迁移到 `data/tenant/` 结构，所有现有数据默认属于 `tenant_default`。tenant_id 过滤在查询时实现。

---

## 7. 代码规范

### 7.1 命名约定

| 类别 | 规范 | 示例 |
|------|------|------|
| **文件名** | snake_case | `store.ttl`, `parser.py`, `discount_rules.json` |
| **Python 类** | PascalCase | `ObjectType`, `EntityRegistry`, `PermissionEvaluator` |
| **Python 函数/方法** | snake_case | `build_ontology_prompt`, `calculate_discount` |
| **Python 常量** | UPPER_SNAKE_CASE | `TASK_TRANSITIONS`, `DEFAULT_TENANT` |
| **Tool 函数名** | snake_case | `query_entity`, `execute_action` |
| **Tool JSON type** | snake_case | `near_expiry_list`, `action_preview` |
| **YAML Action Type api_name** | snake_case | `clearance`, `create_clearance_task` |
| **TTL Object Type** | PascalCase | `NearExpiryProduct`, `Task` |
| **TTL Link Type** | snake_case | `has_near_expiry`, `located_in` |
| **前端组件** | PascalCase | `HomePage`, `GoldenLayout` |
| **前端文件** | kebab-case | `home-page.tsx`, `route.ts` |
| **Skill 目录** | kebab-case | `clearance-workflow`, `store-ontology` |

### 7.2 类型注解

所有 Python 函数必须有类型注解：

```python
# ✅ 正确
def calculate_discount(discount_tier: str) -> int:
    ...

def query_entity(entity_type: str, entity_id: str | None = None) -> str:
    ...

# ❌ 错误
def calculate_discount(discount_tier):
    ...
```

### 7.3 模块组织

```
backend/
├── main.py                 # 入口：FastAPI + Agent + 端点
├── models/                  # 数据模型
│   └── schemas.py          # Pydantic 模型 + Enums
├── ontology/                # 本体层
│   ├── store.ttl           # Object/Link Type 定义
│   ├── actions/            # Action Type 定义（YAML）
│   ├── parser.py           # Parser + EntityRegistry
│   └── tools.py            # Tool 函数
├── business/                # 计算逻辑
│   └── discount.py         # 折扣计算
├── repository/              # 数据访问抽象
│   ├── base.py             # Repository 接口
│   └── json_repository.py  # JSON 实现
├── permissions/            # 权限
│   ├── evaluator.py        # 接口
│   └── rbac.py             # RBAC 实现
└── skills/                  # Skill 文档
    └── store-ontology/     # Skill 目录
```

**导入规则**：
- 不允许循环导入
- `tools.py` 通过 `_get_registry()` 延迟导入 Parser（打破潜在循环）
- `main.py` 导入 `tools.py` 中的 Tool 函数和 Parser 的 `build_system_prompt`
- `models/schemas.py` 被多层引用，不依赖其他业务模块

---

## 8. 测试规范

### 8.1 测试结构（MVP 新增）

```
backend/
└── tests/
    ├── __init__.py
    ├── conftest.py                # pytest fixtures
    ├── unit/
    │   ├── __init__.py
    │   ├── test_parser.py         # TTL/YAML Parser 测试
    │   ├── test_schemas.py        # Pydantic 模型测试
    │   ├── test_discount.py       # 计算逻辑测试
    │   ├── test_repository.py     # Repository 层测试
    │   └── test_permission.py     # 权限引擎测试
    └── integration/
        ├── __init__.py
        ├── test_tools.py          # Tool 端到端测试
        └── test_agent.py          # Agent 对话测试
```

### 8.2 运行方式

```bash
cd backend

# 运行全部测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行单个文件
pytest tests/unit/test_parser.py

# 运行并显示覆盖率
pytest --cov=backend tests/
```

### 8.3 测试原则

| 原则 | 说明 |
|------|------|
| **Parser 可独立测试** | EntityRegistry 只依赖 TTL/YAML 字符串，不依赖文件系统（用 fixture 传入） |
| **Repository 可 mock** | Tool 测试中 mock Repository，不依赖实际 JSON 文件 |
| **Tool 返回字符串** | 测试 Tool 的返回值是合法的字符串格式（含 COPILOTKIT_DATA 或纯错误文本） |
| **不测 LLM 调用** | 集成测试中 mock LLM，不实际调用 API |
| **数据隔离** | 每个测试用例使用独立的临时数据目录，不污染 `data/` |

### 8.4 fixture 示例

```python
# tests/conftest.py
import pytest
import tempfile
import json
from pathlib import Path

@pytest.fixture
def tmp_data_dir(tmp_path):
    """创建临时数据目录，含种子数据。"""
    data = tmp_path / "data"
    data.mkdir()
    (data / "stores.json").write_text(json.dumps([
        {"id": "store_001", "name": "测试门店", "region_id": "region_001"}
    ]))
    return data

@pytest.fixture
def sample_ttl():
    """返回测试用 TTL 内容。"""
    return """
    @prefix : <http://example.org/storeontology#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    :TestObject a :Class ;
        rdfs:label "Test Object"@en ;
        :storageFile "test_objects.json" ;
        :labelZH "测试对象"@zh ;
        :propertyList "id:string, name:string" .
    """
```
