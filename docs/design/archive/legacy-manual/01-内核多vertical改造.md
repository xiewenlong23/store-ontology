> **🗄 归档说明**：原 `docs/manual/` 下接入手册，已被 [`manual/`](../../manual/) 重写版取代（对齐 pack/能力域/价值链流程模型）。保留作历史追溯。

---

# 内核多 vertical 改造记录

> **状态**：已完成（Batch 1-3 已合并，53/53 测试通过）
> **性质**：这是一份**改造记录 + 内核新机制说明**，不是待办清单。新接入者读它理解"内核为什么现在 scenario-agnostic"。
> **对应代码**：本分支 `docs/vertical-onboarding-manual` 的 Batch 1-3 提交。

---

## 0. 改造前的问题

改造前，内核（理应 scenario-agnostic 的代码）有 **8 处泄漏**直接耦合到 clearance 领域：

| # | 泄漏点 | 旧位置 | 问题 |
|---|---|---|---|
| L1 | TTL/actions/data 路径硬编码 | `parser.py` `get_ontology_parser` | 单一 `store.ttl` / 单一 `actions/`，无法并存第二 vertical |
| L2 | TTL prefix 硬编码 `store:` | `parser.py` `PREFIX = "store:"` | 第二 vertical 不能用自己的命名空间 |
| L3 | 系统提示硬编码 clearance 文案 | `parser.py` `build_system_prompt` | `你是门店临期商品管理助手` / `用 query_task` |
| L4 | executor target 定位硬编码 `"Task"` | `executor.py` `_load_target` | `target_type == "Task"` 专属 clearance 工作流对象 |
| L5 | 状态机硬编码 clearance 迁移表 | `state_machine.py` `TASK_TRANSITIONS` | 全局唯一状态机，新工作流无法有自己的迁移图 |
| L6 | 内核 import clearance 折扣 | `tools.py` `query_near_expiry` | `from business.discount import ...` 在内核模块 |
| L7 | `tools=[...]` / `skills=[...]` 硬编码 | `main.py` | 新工具/skill 必须改 main.py |
| L8 | `store_context` 出清文案硬编码 | `main.py` | 提示词写死 clearance 工作流步骤 |

---

## 1. 改造方案（3 Batch）

### Batch 1：参数化 vertical（解锁并存地基）

**新增 `backend/ontology/vertical.py`** —— `VerticalConfig` dataclass，聚合一个 vertical 的全部路径与元信息：

```python
@dataclass
class VerticalConfig:
    name: str                    # "clearance" / "equipment_repair"
    ttl_path: str
    actions_dir: str
    data_dir: str
    skills_dir: str = None
    system_prompt_intro: str = ""
    workflow_object_type: str = None      # "Task" / "RepairTicket"
    workflow_object_id_field: str = "task_id"   # 定位工作流对象的参数名
    state_transitions: dict = {}          # per-vertical 状态迁移表
    terminal_states: list = []
    tools_module: str = None              # "verticals.clearance.tools"
```

加全局注册表：`register_vertical` / `get_vertical` / `all_verticals`。

**`get_ontology_parser(vertical=...)` 参数化**（L1）：三种调用方式 —— vertical name（推荐）/ 显式路径（测试）/ 默认（注册表第一个）。parser 缓存改为 `dict[vertical_name, OntologyParser]`，取代全局单例。

**TTL prefix 动态读取**（L2）：`OntologyParser._read_prefix()` 从 `@prefix <name>: <...> .` 行提取，不硬编码。

**`backend/ontology/bootstrap.py`**：启动时 `pkgutil` 扫描 `verticals/*/config.py`，import 之（每个 config.py 在 import 时 `register_vertical`）。

### Batch 2：去领域硬编码（让内核真正 scenario-agnostic）

**`build_system_prompt(intro)` 参数化**（L3）：开场白来自 `VerticalConfig.system_prompt_intro`，结尾去掉 `用 query_task`。通用部分（实体/关系/Action 列表）仍从 registry 自动生成。

**executor 定位键数据驱动**（L4）：
- `ActionDefinition` 新增 `locator_field`（YAML 里声明，如 `task_id` / `ticket_id`）。
- `_load_target` 优先级：`action.locator_field` > config 的 workflow 对象约定 > `target_id`。
- `_resolve_condition_obj` 的 workflow 对象别名按 `config.workflow_object_type` 通用化（旧 `task.xxx` → 新 `<workflow_object>.xxx`）。
- **关键区分**：`locator_field` 定位 **target**；`workflow_object_id_field` 定位**工作流对象**（二者可能是不同参数，如 deduct_stock 的 target 是 NearExpiryProduct 但要查 Task 状态）。

**状态机数据驱动**（L5）：`is_valid_transition(from, to, transitions, terminals)` 接受 per-vertical 表；不传则用 clearance 默认（向后兼容）。executor 从 `config.state_transitions` 取。

**拆 discount 出 kernel**（L6）：
- `query_near_expiry` 从 `ontology/tools.py` **下沉**到 `verticals/clearance/tools.py`。
- `business/discount` 成为 clearance vertical 私有模块。
- 内核 `ontology/tools.py` 不再 `import business.discount`；保留 re-export 仅过渡期兼容。
- 每个 vertical 的工具模块导出 `TOOLS = [...]` 列表。

### Batch 3：main.py 配置化（接入零改内核）

**`tools = 内核固定 + _aggregate_vertical_tools()`**（L7）：内核 8 个工具固定；vertical 工具从各 `config.tools_module` 的 `TOOLS` 聚合。

**`skills = _aggregate_skill_paths()`**（L7）：扫描各 `config.skills_dir`，只收含 `SKILL.md` 的目录（过滤 `tmp/` / `__pycache__`）。

**`_build_combined_prompt()`**（L8）：合并所有 vertical 的本体提示（多 vertical 共存）；`store_context` 去出清硬编码，改为领域无关的 Preview→Confirm 说明。

**`verticals/clearance/config.py`**：clearance 的 VerticalConfig，import 时注册。

---

## 2. 改造后的内核契约（新接入者必读）

内核只认三个东西，不认任何领域名词：

1. **`VerticalConfig`**：vertical 自报家门（路径 + 工作流 + 工具模块）。
2. **registry**：`backend/verticals/*/config.py` import 时 `register_vertical`，`bootstrap()` 统一发现。
3. **声明式契约**：TTL（Object/Link）+ YAML（Action，含 `locator_field`）+ JSON（种子）。

**vertical 侧的契约**：
- 必须有 `config.py`，构造 `VerticalConfig` 并 `register_vertical`。
- 工作流 vertical 在 config 里填 `workflow_object_type` / `workflow_object_id_field` / `state_transitions` / `terminal_states`。
- 专属工具（如读 NearExpiryProduct）放 `verticals/<name>/tools.py`，导出 `TOOLS` 列表。
- TTL prefix 自洽即可（动态读取）。

---

## 3. 验证：改造没破坏 clearance

- 53/53 测试通过（含 clearance 全流程回归：create→submit→approve→accept→print→deduct→complete / create_loss_report）。
- `import main` 正常：bootstrap 注册 clearance，9 个工具聚合（8 内核 + 1 clearance 专属），skill 路径 `['/store-ontology/']`。
- executor locator_field 数据驱动：7 个 Task-targeting clearance action 显式声明 `locator_field: task_id`（deduct_stock 用 `target_id`，因 target 是 NearExpiryProduct）。

---

## 4. 已知限制（留 v2）

- **schemas.py 未拆**：`models/schemas.py` 仍是 clearance 的 Pydantic 镜像。新 vertical 建自己的 `verticals/<name>/schemas.py`（见 02 Phase D）。内核不依赖 schemas.py（校验在 Action constraint + Repository 层）。
- **共享实体未抽象**：多个 vertical 若都需要 Region/Store，目前各自带副本；共享组织层留 v2。
- **前端未多 vertical 化**：renderToolCalls 仍 clearance 专用；多 vertical UI 留 v2。
- **tenant × vertical 二维权限**：当前 tenant 隔离已工作，vertical 级权限隔离留 v2。
