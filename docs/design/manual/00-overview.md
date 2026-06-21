# 新业务场景接入总览

> **状态**：✅ 当前（生效中，随内核多行业包架构同步更新）。
> **受众**：要在本平台落地一个新业务场景的工程师 / 架构师。
> **配套**：[`01-onboarding.md`](./01-onboarding.md)（标准流程 Phase A-F）、[`02-templates.md`](./02-templates.md)、[`03-worked-example-equipment-repair.md`](./03-worked-example-equipment-repair.md)。
> **依据规范**：[`40-ontology-modeling-spec.md`](../40-ontology-modeling-spec.md)。

---

## 0. 一句话定位

**OntologyAgent = 本体驱动的通用 AI Agent 平台。** 通用内核（存储 / workspace 隔离 / Agent harness / Tool-Skill 体系）固定不变；每个业务场景作为一个 **行业包（IndustryPack）**，在本体之上声明式建模即可接入，**新增行业包零改内核**。

一个行业包 = 多个**能力域**（CapabilityDomain，原子 Object/Link/Action）+ 多个**价值链流程**（ValueChainProcess，跨域编排带状态机 + Skill + 专属工具）。retail 行业包（含 clearance 出清流程）是第一个；equipment_repair（含 repair 流程）是第二个 worked example。本文档教你接入第三个。

---

## 1. kernel / 行业包 边界

下表是接入新行业包时"复用什么 / 新增什么"的速查。

| 文件 / 目录 | 性质 | 新行业包怎么对待 |
|---|---|---|
| `agent/engine/parser.py` | **内核** | 复用。TTL prefix 动态读、prompt intro 来自 ValueChainProcess |
| `agent/engine/repository.py` | **内核** | 复用。多 workspace 隔离 / 锁 / 原子写 / edits-only |
| `agent/engine/executor.py` | **内核** | 复用。声明式瘦路由器，target 定位数据驱动（locator_field） |
| `agent/engine/action_loader.py` | **内核** | 复用。YAML → ActionDefinition |
| `agent/engine/state_machine.py` | **内核** | 复用。`is_valid_transition(transitions, terminals)` 接受 per-process 表 |
| `agent/engine/preview_cache.py` | **内核** | 复用。preview→confirm 闭环 |
| `agent/engine/pack.py` | **内核** | 复用。`IndustryPack`/`CapabilityDomain`/`ValueChainProcess` + 注册表 |
| `agent/engine/workspace.py` / `workspace_bootstrap.py` | **内核** | 复用。`WorkspaceConfig` + `bootstrap_workspace` 装配 |
| `agent/engine/tenant.py` | **内核** | 复用。`TenantContext`（workspace_name + org_unit_id） |
| `agent/engine/bootstrap.py` | **内核** | 复用。自动发现 `workspace/*/pack.py` |
| `agent/engine/scheduler.py` | **内核** | 复用。`AutomationScheduler` |
| `agent/tools/*.py` | **内核**（含 8 个内核工具） | 复用内核 8 个工具（query_entity/create/update/traverse/execute/confirm/query_task/update_task） |
| `agent/main.py` | **内核** | 复用。tools/skills/prompt 从 pack 注册表聚合 |
| `workspace/<pack>/pack.py` | **行业包** | **新行业包在此新建**：声明 `IndustryPack` 并 `register_pack` |
| `workspace/<pack>/ontology/domains/<域>/domain.ttl` | **行业包** | 新行业包建自己的能力域 TTL |
| `workspace/<pack>/ontology/domains/<域>/actions/*.yaml` | **行业包** | 新行业包建自己的域内 Action |
| `workspace/<pack>/skills/<process>/actions/*.yaml` | **行业包** | 价值链流程的专属 Action（状态迁移类） |
| `workspace/<pack>/skills/<process>/` | **行业包** | 场景单元（SKILL.md + tools.py + 可选 automation.py/state_machine.py） |
| `workspace/<pack>/data/*.json` | **行业包** | 新行业包的种子数据（每条带 workspace_name） |
| `agent/engine/schemas.py` | **行业包**（Pydantic 镜像） | 新行业包按需建自己的 schemas |

**判断口诀**：如果一段代码提到具体的领域名词（NearExpiryProduct / clearance / 折扣 / 出清），它是行业包；如果只认 `IndustryPack` 和 pack 注册表，它是 kernel。

---

## 2. 三步法

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1（每次新增行业包）：按 01-onboarding.md 走 Phase A-F    │
│   A 建模（能力域 TTL）→ B Action 契约（YAML）→ C 状态机      │
│   → D 种子数据 → E 工具/Skill → F 注册（pack.py，重启即生效） │
├─────────────────────────────────────────────────────────────┤
│ Step 2：验证清单（对照建模规范 §9）                            │
│   命名 / 元数据 / via 归属 / Action 边界 / 原子性 / 一致性     │
├─────────────────────────────────────────────────────────────┤
│ Step 3：重启后端，bootstrap 自动发现新行业包                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 命名与目录约定

### 3.1 行业包标识

- 行业包名：`snake_case`，如 `retail` / `equipment_repair` / `inventory_count`。
- 目录：`workspace/<pack_name>/`，内含 `pack.py`（注册入口）。
- 能力域名：`snake_case`，如 `marketing` / `organization` / `finance` / `maintenance`。
- 价值链流程名：`snake_case`，如 `clearance` / `repair`。

### 3.2 TTL prefix

- 每个能力域用自己的 prefix，从 `domain.ttl` 的 `@prefix <name>: <...> .` 行读取（parser 动态解析）。
- prefix 只需在该能力域的 TTL 内一致；不影响其它域/行业包。

### 3.3 存储隔离

- **每个行业包的种子数据放 `workspace/<pack>/data/`**，每个实体类型一个 JSON（如 `tasks.json`、`near_expiry_products.json`）。
- TTL 的 `:storage "<file>.json"` 写文件名；`IndustryPack.data_dir` 指向 `workspace/<pack>/data`。
- 每条数据带 `workspace_name`（+ `org_unit_id` 若需 org 隔离）。

### 3.4 Action / Skill 命名

- Action api_name：`snake_case` 动词短语，**建议加流程前缀**避免跨行业包冲突（如 `create_clearance_task` 而非 `create_task`）。
- Skill 目录：`workspace/<pack>/skills/<process_or_topic>/SKILL.md`。

---

## 4. 什么时候该建行业包，什么时候不该

**应当建行业包**：一组业务实体有独立的生命周期、受治理的写操作（Action）、跨多步的工作流。如：设备维修工单、库存盘点、会员退换货。

**不应当建行业包**（用现有工具即可）：一次性查询、纯读取报表、单条 CRUD。这些用内核 `query_entity` / `create_entity`（降级 CRUD）即可，不必建模成行业包。

判断见建模规范 §3.4（何时建新 Object Type）与 §5.2（何时建 Action Type）—— 行业包是"一组能力域 + 价值链流程"的集合，粒度比单个 Object 大。

---

## 5. 阅读路线

- **第一次接入**：读本文 → [`01-onboarding.md`](./01-onboarding.md)（跟 Phase A-F）→ 遇填法疑问查 [`02-templates.md`](./02-templates.md) → 卡住看 [`03-...`](./03-worked-example-equipment-repair.md) 完整例子对照。
- **后续接入**：直接 [`01-onboarding.md`](./01-onboarding.md) → [`02-templates.md`](./02-templates.md) 查模板。
- **想理解内核装配**：[`00-architecture.md`](../00-architecture.md) §4（Tool 两类 + 依赖装配）。
