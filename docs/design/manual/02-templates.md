# 模板说明与索引

> **状态**：✅ 当前。模板都在 [`templates/`](./templates/) 目录，每个有占位符，填法见下。

---

## 模板速查

| 模板 | 产出 | 用于 Phase |
|------|------|-----------|
| [`workspace.py.template`](./templates/workspace.py.template) | `workspace/<pack>/workspace.py` | F（注册） |
| [`ws-tools.py.template`](./templates/ws-tools.py.template) | `workspace/<pack>/skills/<process>/tools.py` | E.1（专属工具） |
| [`ontology.ttl.template`](./templates/ontology.ttl.template) | `workspace/<pack>/ontology/domains/<域>/domain.ttl` | A（能力域建模） |
| [`action.yaml.template`](./templates/action.yaml.template) | `workspace/<pack>/ontology/domains/<域>/actions/*.yaml` 或 `skills/<process>/actions/*.yaml` | B（Action 契约） |
| [`state_machine.py.template`](./templates/state_machine.py.template) | `workspace/<pack>/skills/<process>/state_machine.py` | C（状态机） |
| [`seed-object.json.template`](./templates/seed-object.json.template) | `workspace/<pack>/data/<entity_type>.json` | D（种子数据） |
| [`skill-workflow.md.template`](./templates/skill-workflow.md.template) | `workspace/<pack>/skills/<process>/SKILL.md` | E.2（流程 Skill） |
| [`skill-knowledge.md.template`](./templates/skill-knowledge.md.template) | `workspace/<pack>/skills/<topic>/SKILL.md` | E.2（领域知识 Skill） |

---

## 关键占位符填法

### `workspace.py`：WorkspaceDef + CapabilityDomain + ValueChainProcess

```python
DOMAIN_X = CapabilityDomain(
    name="<domain_x>",          # snake_case 能力域名
    display_name="<域中文名>",
    ttl_path=...,               # workspace/<pack>/ontology/domains/<domain_x>/domain.ttl 绝对路径
    actions_dir=...,            # workspace/<pack>/ontology/domains/<domain_x>/actions
    rules_dir=...)              # 可选；该域的数值规则 JSON 目录

PROCESS_Y = ValueChainProcess(
    name="<process_y>",          # snake_case 流程名
    display_name="<流程中文名>",
    workflow_object_type="<WorkflowObject>",        # PascalCase，如 Task/RepairTicket
    workflow_object_id_field="<workflow_object>_id", # Action 参数里定位它的键名
    state_transitions=<WORKFLOW>_TRANSITIONS,        # 从 state_machine.py import
    terminal_states=list(TERMINAL_STATES),
    skills_dir=...,             # workspace/<pack>/skills
    tools_module="workspace.<pack>.skills.<process>.tools",
    actions_dir=...,            # workspace/<pack>/skills/<process>/actions（流程专属 Action）
    system_prompt_intro="你是<场景>助手。")

PACK = WorkspaceDef(
    name="<pack>", display_name="<工作目录中文名>",
    domains=[DOMAIN_X, ...],
    processes=[PROCESS_Y, ...],
    data_dir=...)
register_workspace_dir(PACK)
```

### `locator_field`（Action，最易填错）

声明 Action 用哪个参数定位 target 记录：
- **target 是工作流对象**（Task/RepairTicket 等）：填定位它的 id 参数名 → `locator_field: task_id` / `locator_field: ticket_id`
- **target 是标的物**（如 deduct_stock 的 NearExpiryProduct）：填 `target_id`

executor 据此定位 target 记录，取代旧的硬编码。

### `workflow_object_type` + `workflow_object_id_field`

在 `ValueChainProcess` 上声明：
- `workflow_object_type`：状态机载体对象（PascalCase，如 `Task`）
- `workflow_object_id_field`：它在 Action 参数里的定位键（snake_case + `_id`，如 `task_id`）

executor 的 submission_criteria 条件可用 `<workflow_object_lower>.status` 引用其状态（如 `task.status` / `repair_ticket.status`）。

### TTL `prefix`

从 `domain.ttl` 的 `@prefix <name>: <...> .` 行读取（parser 动态解析，不硬编码）。每个能力域用自己一致的前缀即可。

---

## 每个模板的常见错误

| 模板 | 常见错误 | 正确做法 |
|------|---------|---------|
| `workspace.py` | `register_workspace_dir` 忘了调 / 路径用相对路径 | 必须 `register_workspace_dir(PACK)`；路径用 `os.path.join(_BASE, ...)` 绝对路径 |
| `action.yaml` | `locator_field` 填错 / 忘填 | target 是工作流对象填其 id 参数名 |
| `domain.ttl` | via 归属反了 / 忘 `:labelZH` | via 必须属于 range 对象 |
| `state_machine.py` | 终态漏了 / 迁移表缺分支 | 终态进 `TERMINAL_STATES`；画状态图核对完整性 |
| `seed-object.json` | 忘 `workspace_name` | 每条带 `workspace_name: "jjy"` |
| `SKILL.md` | 工具名/实体名写错 / 折扣数值重复定义 | 用真实函数名/Object 名；数值引用本体 JSON |

---

## 占位符替换技巧

模板里的占位符用 `<...>` 或 `{{...}}` 标记。替换时：
- `<pack>` → 工作目录名（snake_case），如 `customerA`
- `<domain_x>` → 能力域名（snake_case），如 `maintenance`
- `<process_y>` → 流程名（snake_case），如 `repair`
- `<WorkflowObject>` → 工作流对象类名（PascalCase），如 `RepairTicket`
- `<workflow_object>` → 其 snake_case，如 `repair_ticket`

逐个 Phase 替换，每个 Phase 完成后用对应验证清单核对。
