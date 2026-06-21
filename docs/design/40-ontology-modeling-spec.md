# 业务本体建模规范

> **状态**：✅ 当前（生效中的建模硬规范，随 OntologyAgent 内核演进同步更新）。
> **适用范围**：OntologyAgent 平台内核本体 + 所有行业包（零售、物流、制造……）的领域建模。
> **关联文档**：[`00-architecture.md`](./00-architecture.md)（平台架构，下称"架构文档"）、`workspace/retail/ontology/domains/`（现有零售行业包本体）。
> **性质**：本文件是**规范性**文档（规范 = 必须遵守的约定）。它不解释"系统是什么"（那是架构文档的职责），只规定"怎么建模才合规"。

---

## 0. 怎么读这份文档

- 出现 **必须 / 禁止 / 应当 / 不推荐** 的条款是硬规范，建模 review 时逐条核对。
- 第 1-2 节是总则，所有建模者必读。
- 第 3-5 节是三种资源类型（Object / Link / Action）的建模细则，按需查阅。
- 第 6 节起是数据约定、版本演进、反模式、检查清单，建模完成后用第 9 节的清单自查。
- 所有示例取自现有零售临期行业包（`workspace/retail/ontology/domains/`），既是样板也是回归基线。

---

## 1. 总则

### 1.1 建模对象的边界

**本体的定位是组织的运营层（operational layer）/ 数字孪生**——它位于原始数据之上、应用之下，把数字资产连接到现实世界实体（门店、商品、任务）。它不是数据库 schema 的镜像，而是用业务语言描述"这个组织在运营什么、能做什么"。这与 Palantir Foundry Ontology 的定位一致（详见 `reference/palantir-ontology-docs/summary.md` §一）。

OntologyAgent 的本体承载两类元素：

| 类别 | 元素 | 回答的问题 |
|---|---|---|
| **语义元素**（描述"是什么"） | **Object Type** / **Link Type** | 业务里有哪些"东西"？它们之间是什么关系？ |
| **动态元素**（描述"做什么"） | **Action Type** | 对东西的哪些"变更"是受治理的业务事务？要什么参数、谁能动、动完有什么副作用？ |

**不承载**计算逻辑（不引入 Palantir 式 Function 作为本体元素），计算逻辑是普通 Python 模块，通过 Tool 暴露给 LLM。详细分工见架构文档 §1。Interface Type（抽象形状）与 Shared Property（跨类型共享属性）列为 v2，MVP 不实现（见 §1.3）。

### 1.2 建模原则

借鉴 Palantir 的四大方法论（领域驱动 / DRY / 开放扩展封闭修改 / 组合优于继承），结合 LLM agent 时代的消费者特征，落地为以下原则：

1. **声明式优先**：本体描述"是什么 / 能做什么"，不描述"怎么做"。执行逻辑（校验、计算、副作用触发）写在执行器/计算模块里，本体里只声明契约。
2. **领域驱动（DDD，Palantir 原则 1）**：建模**现实世界的实体与关系**，而不是源系统表或技术构件。Object Type 用业务语言命名（`Employee`、`WorkOrder`），不要镜像数据库表名（`MirrorSourceSystemTable`）；Link 代表真实关系（"该员工管理该门店"），而不是外键本身。
3. **单一事实源 / DRY（Palantir 原则 2，Rule of Three）**：一个概念只在一处定义。业务规则数值（如折扣率）定义在本体数据文件里，**禁止**在代码里硬编码、在 Skill 文档里重复定义。同一语义出现三次就该重构——跨 Object 共享的形状用 Interface/Shared Property（v2）抽取，不要在三处复制粘贴。
4. **开放扩展、封闭修改（OCP，Palantir 原则 3）**：核心 Object Type 保持稳定；新业务需求优先通过**新增** Object/Link/Action 或实现 Interface 来满足，而非反复修改既有定义。必须改既有定义时走 §7 的 deprecation 流程。
5. **组合优于继承（Palantir 原则 4）**：避免宽而稀疏、塞满可选字段的"大杂烩" Object Type；跨类型共享的特征用 Interface（v2）建模，Object Type 实现多个 Interface 获得多态，而不是建深层继承树。
6. **读写分离**：读操作（查询）不经 Action Type，是纯 Tool；**受治理的写操作**（业务事务）必须经 Action Type。通用 CRUD 仅限非业务数据或管理/开发场景（见 §5.2）。
7. **edits-only-via-actions**：核心业务实体可锁定为"只能通过 Action 修改"，防止通用 CRUD 绕过治理（架构文档 §1.3）。
8. **面向两个消费者**：本体同时被 **LLM**（经 `build_ontology_prompt` 注入提示词）和 **后端自动化**（直接读 registry）消费。命名与描述要让 LLM 能理解、让代码能稳定引用。

> 第 2-5 条直接对齐 Palantir summary.md §五的四大原则；第 6-7 条是 OntologyAgent 针对 LLM 消费者做的本地化强化（Palantir 原本靠 Function + Workshop 应用层承载，agent 时代改由 Action + Tool 承载）。

### 1.3 借鉴 Palantir，有意偏离之处

本规范吸收 Palantir 本体方法论，但在消费者差异处有意偏离。明确记录，避免后续被"对齐 Palantir"的诉求带偏方向：

| Palantir 原版 | 本规范的处理 | 理由 |
|---|---|---|
| **Function** 作为本体元素（注册到本体、被 Workshop/派生列/聚合发现绑定） | **不引入** Function 本体元素。计算逻辑是普通 Python 模块，经 Tool 暴露给 LLM | agent 时代消费者是 LLM，计算经 Tool（schema 注入 prompt）调用即足够；Tool 就是 LLM 时代的 Function（架构文档 §1.1） |
| **Interface Type**（抽象形状、多态） | 列为 **v2**，MVP 不实现，元数据预留 | MVP 范围够用即止；跨 Object 共享形状的需求先靠命名约定 + `dict` 属性临时承载 |
| **Shared Property**（跨类型共享的标准化属性） | 列为 **v2**，MVP 用命名约定替代（同语义字段统一命名，如所有 `created_at` 同名同类型） | 同上，避免过早抽象 |
| **Ontology Branching / Proposal / Change Management**（git 式本体分支） | 列为 **v2**；MVP 用 `status` + §7 deprecation 流程 + 代码 review 替代 | MVP 团队规模小，分支管理收益低于成本 |
| **Object Explorer / Workshop / Quiver**（消费侧应用） | MVP 用 CopilotKit renderToolCalls；A2UI 标准渲染留 v2 | 消费层是前端范畴，不进本体建模规范 |
| **Cardinality 显式声明**（1:1/1:N/N:N） | MVP 默认 N:N，不显式声明；显式基数列 v2（见 §4.4） | 当前外键字段实现天然支持 N:N，声明收益有限 |
| **Object Type 必须有 backing datasource** | 类比：必须有对应 `storage` 文件 + Repository 实现 | 采纳，已体现为 §3.1 的 `storage` 必填 |

> 一句话：**借"描述世界"的方法论，换"执行/消费"的机制。** Palantir 为前 LLM 时代的"人 + 应用"设计，本规范为 LLM 时代的 agent 设计。

---

## 2. 命名规范

### 2.1 总表

| 对象 | 规则 | 示例 |
|---|---|---|
| Object Type `api_name` | PascalCase，**单数** | `Store`、`NearExpiryProduct`、`Task` |
| 属性 `name` | snake_case | `region_id`、`created_at`、`discount_tier` |
| Link Type `api_name` | snake_case，动词短语或介词 | `located_in`、`has_employee`、`created_for` |
| Action Type `api_name` | snake_case，动词或动宾短语 | `clearance`、`create_clearance_task`、`submit_for_approval` |
| 枚举类型名 | PascalCase | `TaskStatus`、`ProductStatus`、`DiscountTier` |
| 枚举值 | snake_case 小写 | `low_stock`、`pending_approval`、`T1`（既有缩写可保留） |
| 存储文件名 | snake_case **复数** + `.json` | `stores.json`、`near_expiry_products.json` |
| TTL 前缀 | 行业包 级常量（现 能力域的 TTL prefix） | 如 `retail:Store`、`retail:clearance` |

### 2.2 硬约束

- **必须** 同时提供中英文 `rdfs:label`：`"门店"@zh , "Store"@en`。中文供 LLM/UI 理解，英文供代码与跨行业包复用。
- `api_name` **必须** 全局唯一（跨 Object/Link/Action 命名空间）。
- **禁止** 用 `id`、`type`、`name`、`data`、`value` 这类无业务含义的词作为 Object Type 的 `api_name`。`id`/`name` 只能作属性名。
- 软引用属性名 **必须** 是 `{被引用类型小写}_id` 形式（如 `region_id` 引用 Region，`product_id` 引用 Product），并 **必须** 与对应 Link Type 的 `via` 字段一致（见 §4.3）。
- 单位/语义易混的字段，**必须** 在 `description` 注明单位与口径（见 §6.2）。

---

## 3. Object Type 建模规范

Object Type = 业务实体类型定义。借鉴 Palantir 的三层结构，Type 定义 schema、Object 是单个实例、Object Set 是实例聚合（MVP 中 Object Set 由 `Repository.read()` 返回的列表承载，不单独抽象为概念）。

```
Object Type（类型）   ← 定义 schema，如 NearExpiryProduct
    ↓ 实例化
Object（对象）        ← 单个实体，如 "ne_prod_001"
    ↓ 聚合
Object Set（对象集）  ← 一组对象，如 "某门店所有临期商品"（= Repository.read 返回列表）
```

### 3.1 必备元数据

每个 Object Type **必须** 声明以下元数据（当前 `workspace/retail/ontology/domains/<域>/domain.ttl` 缺 `status`/`visibility`/`edits_only_via_actions`，需在内核元数据扩展时补齐，见架构文档 §3.1）：

| 元数据 | 必填 | 说明 |
|---|---|---|
| `api_name` | 是 | PascalCase 单数，如 `NearExpiryProduct` |
| `display_name` | 是 | 中英文 label |
| `description` | 是 | 一句话业务含义，写给 LLM 和人看 |
| `properties` | 是 | 属性列表（见 §3.3） |
| `storage` | 是 | 存储文件名，如 `near_expiry_products.json` |
| `status` | 是 | `active` / `experimental` / `deprecated`（默认 `active`） |
| `visibility` | 否 | `prominent` / `normal` / `hidden`（默认 `normal`） |
| `edits_only_via_actions` | 否 | `true` 时该实体写操作锁定为只能经 Action（默认 `false`） |
| `tenant_id` | 隐式 | 由存储路径承载，不在元数据里重复（见 §6.3） |

### 3.2 标识符

- **必须** 有且仅有一个主键属性，名为 `id`，类型 `string`。
- 主键值建议格式 `{type_prefix}_{seq}`，如 `store_001`、`ne_prod_001`、`task_20260620_001`。
- **主键不可变**：实例创建后 `id` 永不修改。改名等于删除+新建。
- rid（Palantir 式持久化标识）是 v2 概念，MVP 用 `id` 即可（架构文档 附录 B（Palantir 参考）第 5 点）。

### 3.3 属性规范

- 每个属性声明 `name:type`，类型取自 §6.1 白名单。
- `description` 里写明业务含义；易混字段写明单位（§6.2）。
- 枚举属性类型写枚举类型名，如 `status:ProductStatus`、`discount_tier:DiscountTier`。枚举类型 **必须** 在代码侧（`agent/engine/schemas.py`）有对应的 `Enum` 定义，且值与本体一致。
- 软引用属性（`xxx_id`）**必须** 指向一个已定义的 Object Type，并配对一条 Link Type（§4）。
- 时间字段：日期用 `date`（`YYYY-MM-DD`），时间戳用 `datetime`（ISO8601）。**禁止** 用 `string` 存日期。
- **属性来源分类**（借鉴 Palantir，MVP 简化）：Local Property（直接定义在本 Object Type 上）是 MVP 唯一形式；Shared Property（跨多个 Object Type 共享的标准化属性，如 `created_at` 统一语义）列为 v2，MVP 阶段靠**命名约定**统一（同语义字段一律同名同类型），不引入共享机制。
- **禁止 1:1 映射源系统列**：源系统字段（如 `dtLastInspMod`）必须按业务语义重命名（`last_inspection_date`），不要把数据库列名原样搬进本体（Kitchen Sink 反模式，见 §8）。

### 3.4 何时建新 Object Type

**应当** 新建 Object Type：当一组实例有独立的标识、独立的生命周期、且被多种关系/Action 引用（如 `Task` 被 `has_task`/`created_for` 引用、被多个 Action 操作）。

**不推荐** 新建 Object Type：当一个"东西"只是某个实体的属性集合、没有独立标识与生命周期（这种情况用 `dict` 属性或拆成多个标量属性）。

**组合优于继承（Palantir 原则 4）**：
- 避免建一个塞满可选字段的"大杂烩" Object Type（如把门店、员工、商品的字段全塞进一个 `Record`）。这是 Kitchen Sink 反模式，会破坏领域边界、让 LLM 难以理解。
- 跨多个 Object Type 共享的特征（如"都有负责人 assignee"、"都有地理位置"），**应当** 等待 v2 的 Interface 抽象建模（Object Type 实现多个 Interface 获得多态），而非建深层继承树或复制字段。MVP 期间用命名约定（统一 `assignee_id`/`location` 字段名）过渡。
- 核心 Object Type 应当稳定；新增业务实体优先**新增** Object Type（OCP，§1.2 原则 4），而非往既有类型里塞字段。

---

## 4. Link Type 建模规范

Link Type = 两个 Object Type 之间的关系。

### 4.1 必备元数据

| 元数据 | 必填 | 说明 |
|---|---|---|
| `api_name` | 是 | snake_case 动词短语 |
| `display_name` | 是 | 中英文 label |
| `domain` | 是 | 源 Object Type |
| `range` | 是 | 目标 Object Type |
| `via` | 是 | 实现该关系的外键字段名（见 §4.3） |

### 4.2 方向语义

`domain → range` 读作「domain（动词）range」：

| Link | 读法 | 含义 |
|---|---|---|
| `located_in: Store → Region` | Store 位于 Region | Store 通过 `region_id` 归属到 Region |
| `has_employee: Store → Employee` | Store 拥有 Employee | Store 通过 `store_id` 找到它的员工 |
| `created_for: Task → NearExpiryProduct` | Task 针对 NearExpiryProduct | Task 通过 `target_id` 指向被操作的临期商品 |

### 4.3 via 归属原则（关键，来自真实 bug）

> **`via` 字段属于哪一方，Link 就应当从「拥有该字段的一方」出发。**

`workspace/retail/ontology/domains/<域>/domain.ttl` 现有 bug：`manages: Employee → Store, via="manager_id"`，但 `manager_id` 是 **Store** 的属性（不是 Employee 的）。`traverse_relation("Employee", "emp_001", "manages")` 能跑通纯属巧合（碰巧 `store_001.manager_id == "emp_001"`）。正确写法：

```
store:manages  →  domain: Store, range: Employee, via: manager_id
# 读作：Store 通过 manager_id 指向它管理的 Employee（店长）
```

**硬约束**：
- `via` 指向的字段 **必须** 存在于 `domain` 或 `range` 之一的属性列表中。
- 若 `via` 在 `domain` 上：`domain` 主动持有外键，`range` 是被引用方。
- 若 `via` 在 `range` 上：`range` 持有外键指回 `domain`（如 `has_employee: Store → Employee, via: store_id`，`store_id` 在 Employee 上）。这种情况 **必须** 在 Link 的 description 里说明，避免方向歧义。

### 4.4 基数与双向

Cardinality（基数）决定关系的数量。借鉴 Palantir 的三类基数：

| 基数 | 说明 | 示例 |
|---|---|---|
| 1:1 | 一个 domain 对应一个 range | 员工 → 工号档案 |
| 1:N | 一个 domain 对应多个 range | Store → Employee（一个门店多个员工） |
| N:N | 多对多，需通过外键字段实现 | Store ↔ NearExpiryProduct（一个门店多个临期商品） |

- MVP 默认 **N:N（多对多）**，通过 `via` 外键字段实现，不显式声明基数。原因：当前外键字段实现天然支持 N:N，显式声明收益有限。
- 显式基数声明（1:1/1:N/N:N）列为 v2（对应 Palantir Link Type 的 Cardinality 配置）。
- **自引用 Link**（同一 Object Type 内部的关系，如 Employee → Employee 的"直接下属"）**允许**：domain 与 range 是同一个 Object Type，`via` 字段指向自身的外键（如 `manager_id` 指向另一个 Employee）。建模时 **必须** 在 description 说明方向，避免与跨类型 Link 混淆。
- 若两个方向都需要遍历（如 Store↔Employee），**应当** 定义两条 Link（`has_employee: Store→Employee` 与反向的 `works_at: Employee→Store`），**不推荐** 用一条 Link 隐含双向语义。借鉴 Palantir：Link Type 的复用优先于新建，但跨 Ontology 的 Link 不允许（MVP 单 Ontology，无此问题）。

---

## 5. Action Type 建模规范（核心）

Action Type = 受治理业务事务的 **声明式变更契约**。它是 LLM 与后端自动化共用的变更入口（架构文档 §1.2、§1.4）。模板见 [`manual/templates/action.yaml.template`](./manual/templates/action.yaml.template)（填法见 [`manual/02-templates.md`](./manual/02-templates.md)）。

### 5.1 必备要素

存储格式为 **YAML**（`workspace/<pack>/ontology/domains/<域>/actions/{api_name}.yaml`），不用 TTL（架构文档 §3.4）：

```yaml
api_name: clearance
display_name: 出清
description: 对临期商品进行出清处理，创建 Task 记录
status: active
target_object_type: NearExpiryProduct        # 主操作对象
edits_object_types: [NearExpiryProduct, Task] # provenance：声明会改哪些 Object
parameters:
  - { name: discount,   type: int,    required: true, constraint: "0..100" }
  - { name: quantity,   type: int,    required: true, constraint: ">0" }
  - { name: notes,      type: string, required: false }
submission_criteria:                          # 细粒度门控，独立于粗粒度 RBAC
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is_not, value: expired, fail_msg: "已过期商品不能出清" }
side_effects:
  - { type: notification, template: clearance_created, recipients: [assignee_id, manager_id] }
```

| 要素 | 必填 | 说明 |
|---|---|---|
| `api_name` / `display_name` / `description` / `status` | 是 | 同前 |
| `target_object_type` | 是 | 主操作对象的 Object Type |
| `edits_object_types` | 是 | **provenance 声明**：列出本次 Action 会写到的所有 Object Type。execute_action 路由器据此判断是否触碰 edits-only-via-actions 实体 |
| `parameters` | 是 | 入参列表，每项 `name/type/required/constraint` |
| `submission_criteria` | 否 | 谁能提交 + 参数级条件（§5.4） |
| `side_effects` | 否 | 副作用声明（§5.5） |

### 5.2 何时建 Action Type（边界）

**必须** 用 Action Type 的场景：
- 业务事务（出清、调拨、补货、审批、报损）。
- 需要审计、权限校验、状态迁移、副作用的写操作。
- LLM 与后端自动化都要触发的变更（共用同一契约是 Action 不可替代的价值）。

**不应当** 用 Action Type 的场景：
- 读操作（用 `query_*` Tool，读无副作用、不需治理）。
- 非业务数据的简单增改（辅助配置、临时记录）→ 用降级的 CRUD。
- 开发/管理场景的数据修补 → 用受限的 CRUD（admin 角色）。

> 核心业务实体（NearExpiryProduct、Task 等）应标记 `edits_only_via_actions: true`，使上述"不应当"场景也无法绕过 Action（架构文档 §1.3）。通用 CRUD（`create_entity`/`update_entity`）**禁止** 用于这些实体。

### 5.3 parameters 声明式约束

- `constraint` 用可读表达式声明取值范围：`"0..100"`、`">0"`、`"<stock_quantity"`、枚举值列表。
- 约束 **必须** 声明在本体里，execute_action 路由器统一校验，**禁止** 把校验逻辑散落在执行器代码里。
- 参数语义易混时（金额、百分比），在参数 `description` 注明口径（§6.2）。

### 5.4 submission_criteria（独立于粗粒度 RBAC）

两层权限，**不可混淆**：

| 层 | 问题 | 实现位置 |
|---|---|---|
| 粗粒度 RBAC | 这个角色能用 `execute_action` 工具吗？ | 权限引擎 role→tool 白名单 |
| submission_criteria | 给定这个用户 + 这组参数，这个 action 实例能提交吗？ | Action 定义里声明式 |

MVP `submission_criteria` 只实现 `roles` 白名单 + 简单参数条件（`is`/`is_not`/`equals`）；Palantir 式操作符全集与嵌套逻辑留 v2。

### 5.5 side_effects 声明

- 副作用（通知、状态迁移、外部回调）**声明** 在本体里，执行器按声明触发。
- **禁止** 在 execute_action 路由器里硬编码某个 Action 的副作用——那会让 Action 定义与行为分离，违反单一事实源。
- 状态机迁移作为副作用的一种：`{ type: state_transition, target: Task, from: pending_approval, to: approved }`，合法转换表（dict）见架构文档 §1.5。

### 5.6 原子性与可组合性（借鉴 Palantir）

Action 是 Ontology 中**改变数据的交易单位**，借鉴 Palantir 的两条关键性质：

- **原子性**：一个 Action 是一笔事务，要么全部成功，要么全部回滚。`confirm_action` 执行多个 Object 的多处修改时，必须用原子写入（临时文件 + rename）保证不出现"改了一半"的中间态（架构文档 附录 A（数据一致性））。失败时不留部分写入。
- **可组合**：一个 Action 可修改多个 Object 的多个 Property（如 `clearance` 同时改 NearExpiryProduct.status 并创建 Task 记录），这通过 `edits_object_types` 声明。**禁止** 把一个业务事务拆成多个 Action 让调用方拼装——那会破坏原子性，调用方中途失败就产生不一致。

这两条性质正是 Action 不可被通用 CRUD 取代的根本原因：CRUD 是单字段单点的写，没有原子性与副作用编排能力。

---

## 6. 数据约定

### 6.1 属性类型白名单

| 类型 | 语义 | 示例字段 |
|---|---|---|
| `string` | 文本 | `name`、`address` |
| `int` | 整数（数量、百分比） | `stock_quantity`、`discount` |
| `float` | 浮点（金额） | `cost_price`、`retail_price` |
| `bool` | 布尔 | `is_active` |
| `date` | 日期 `YYYY-MM-DD` | `expiry_date`、`production_date` |
| `datetime` | ISO8601 时间戳 | `created_at`、`completed_at` |
| `enum` | 枚举（引用 Enum 类型） | `status`、`discount_tier` |
| `dict` | JSON 对象（自由结构） | `params_json`、`result_json` |

**禁止** 用 `string` 存日期/数值/枚举。需要复合结构时用 `dict`，并在 `description` 描述其 schema。

### 6.2 单位与口径（硬规范，来自真实 bug）

历史上折扣在 **三处** 定义且语义维度不一（乘数 0.5 vs 减扣百分比 50 vs 百分号 50%），是典型违规。统一约定：

- **百分比**：全系统统一为「**减扣百分比**」，即「减 X%」，取值 0-100 的 `int`。例：`discount: 50` = 五折 = 减 50%。
- **金额**：单位「元」，`float`，字段名带业务后缀（`cost_price`/`retail_price`，不用裸 `price`/`amount`）。
- **数量**：`int`，单位在 `description` 注明（件/箱/千克）。
- **时间区间**：用整数字段 + 单位后缀（`days_left`、`hours_remaining`），**禁止** 用裸数字无单位。
- **任何易混量**：在字段/参数 `description` 里写明"单位 + 口径"，如 `discount: "减扣百分比（0-100 整数），50 表示五折"`。

### 6.3 存储与多租户

- 存储文件名 = 对应 Object Type 的 `{snake_case 复数}.json`，一一对应。
- 路径：`workspace/<pack>/data/{storage_file}`。租户隔离由路径承载（架构文档 §3.3）。
- 同一 Object Type 的所有实例存在同一个文件里（JSON 数组）。
- **禁止** 直接读写文件；**必须** 经 Repository 接口（`repository.read/write`），由它负责租户过滤、文件锁、edits-only-via-actions 检查。

---

## 7. 版本与演进规范

### 7.1 status 生命周期

| status | 含义 | 可见性 | 能否被生产引用 |
|---|---|---|---|
| `experimental` | 实验中，随时可改 | 仅开发 | 不推荐 |
| `active` | 稳定，正式可用 | 全部 | 推荐 |
| `deprecated` | 废弃，保留读取兼容 | 全部 + 警告 | 不推荐，给迁移窗口后删除 |

### 7.2 变更分级

| 变更类型 | 等级 | 处理方式 |
|---|---|---|
| 新增 Object/Link/Action | 兼容 | 直接加，`status: experimental` 先观察 |
| 新增属性 / 枚举值 / Action 参数 | 兼容 | 直接加；新增参数 `required: false` |
| 修改属性 `description`/label | 兼容 | 直接改 |
| 重命名属性 / 改属性类型 / 删除元素 | **破坏性** | 走 deprecation：旧元素标 `deprecated` 保留至少一个发布周期 + 新元素并行上线 + 提供迁移说明；迁移完成后删旧元素 |
| 改 `id`/`api_name` | **禁止** | 不可变；要改只能删旧建新 |

### 7.3 单一事实源一致性

- Object/Link Type 的权威定义在 **TTL**（`workspace/retail/ontology/domains/<域>/domain.ttl`），代码常量（如 `agent/engine/schemas.py` 的 `LinkTypes`）**必须** 与 TTL 一致。
- 当前 `LinkTypes` 常量与 TTL 不一致（`HAS_NEAR_EXPIRY_PRODUCT`/`BELONGS_TO`/`SUBJECT_TO` 在 TTL 里不存在或名字不同）是违规，需修。
- Action Type 权威定义在 **YAML**（`ontology/actions/`），代码里的 `ActionType` 枚举 **必须** 与 YAML 一致。
- 发现两处定义冲突时，以本体定义文件（TTL/YAML）为准，修代码，**禁止** 反过来。

---

## 8. 反模式（禁止）

分两组：A 组来自本仓库真实 bug，B 组来自 Palantir 方法论的经典反模式（本地化为 agent 场景）。两组都要在 review 时核对。

### 8.1 本仓库真实 bug 衍生（A 组）

以下每条都对应一个真实发生过的 bug：

| # | 反模式 | 真实案例 | 正确做法 |
|---|---|---|---|
| 1 | **语义维度混用** | 折扣三处定义：乘数 0.5 / 减扣百分比 50 / 百分号 50% off | 全系统统一为减扣百分比 int（§6.2） |
| 2 | **业务规则硬编码在代码/Skill** | `tools.py` 硬编码 `{T1:60,T2:40,T3:20}`；SKILL.md 重复写折扣值 | 单一事实源 = 本体数据文件 + 一个计算函数 |
| 3 | **Link via 字段不属于 domain/range** | `manages: Employee→Store, via=manager_id`，但 manager_id 是 Store 的字段 | via 归属原则（§4.3） |
| 4 | **代码常量与本体定义不一致** | `LinkTypes` 引用 TTL 里不存在的 link | TTL 为准，修代码（§7.3） |
| 5 | **文档引用不存在的实体/工具** | SKILL.md 引用 `DiscountRule`、`get_near_expiry_products`、`belongs_to`（均不存在） | 文档与本体同步，review 时核对 |
| 6 | **通用 CRUD 绕过 Action 治理** | `update_entity` 能直接改 NearExpiryProduct.status，绕过审批 | edits-only-via-actions（§5.2、架构文档 §1.3） |
| 7 | **状态字段无状态机约束** | Task.status 自由改写，无合法迁移约束 | 状态迁移用 Action + 迁移表（架构文档 §1.5） |
| 8 | **裸数值无单位** | `discount: 0.5` 不知是乘数还是百分比 | 单位写进 description + 统一口径（§6.2） |
| 9 | **一处概念多处定义** | 折扣同时存在于 code / json / skill 三处 | 单一事实源，其它处只引用 |
| 10 | **直接读写数据文件** | `tools.py` 直接 `_load_json`/`_save_json`，无租户过滤无锁 | 必须经 Repository（§6.3） |

### 8.2 Palantir 经典反模式，本地化（B 组）

借鉴 Palantir summary.md §七，落到 OntologyAgent 场景：

| # | 反模式 | 描述 | 本地化正确做法 |
|---|---|---|---|
| 11 | **Kitchen Sink（大杂烩）** | 一个 Object Type 塞满无关字段，镜像源系统表 | 按领域实体拆分（§3.4 组合优于继承）；字段来源重命名（§3.3） |
| 12 | **系统镜像（Mirror Source System）** | Object Type 等于数据库表，表名/列名原样搬进来 | 按业务语义建模，Object Type 代表现实世界实体（§1.2 DDD） |
| 13 | **Golden Hammer（金色锤子）** | 用通用 CRUD / Skill 去处理本该用 Action 承载的受治理人工决策（审批、状态变更） | 人工决策与受治理写入必须走 Action Type；通用 CRUD 仅限非业务数据（§5.2） |
| 14 | **孤岛建模** | 单人/单团队闭门设计本体，不与其他建模者对齐 | 跨团队协作，防止重复定义；Shared Property / Interface（v2）抽取共性（§1.2 DRY） |
| 15 | **无文档实体** | Object/Property/Action 不写业务含义描述，只留技术字段 | 每个资源必须有 description（§3.1、§5.1 必填）；review 时核对 |
| 16 | **深继承树** | 用 Object Type 继承堆叠出深层层次来表达共享特征 | 用 Interface（v2）多实现，组合优于继承（§3.4） |

---

## 9. 建模检查清单（Review Checklist）

提交本体变更前逐项自查（全部 ✅ 才算合规）：

**命名**
- [ ] Object Type 用 PascalCase 单数；Link/Action 用 snake_case
- [ ] 每个资源都有中英文 label
- [ ] `api_name` 全局唯一
- [ ] 软引用字段是 `{type}_id` 形式

**Object Type**
- [ ] 有主键 `id`（string，值格式规范）
- [ ] 元数据齐全（api_name/display_name/description/properties/storage/status）
- [ ] 属性类型取自白名单，无 string 存日期/数值
- [ ] 枚举属性在代码侧有对应 Enum 定义
- [ ] 核心业务实体按需标记 `edits_only_via_actions`
- [ ] 未把无关字段塞进单个 Object Type（无 Kitchen Sink，§3.4）

**Link Type**
- [ ] domain/range/via 三件套齐全
- [ ] `via` 字段确实属于 domain 或 range（§4.3）
- [ ] 方向读起来语义通顺

**Action Type**
- [ ] 用 YAML 定义于 `ontology/actions/`
- [ ] 有 target_object_type + edits_object_types（provenance）
- [ ] parameters 带声明式 constraint
- [ ] submission_criteria 与粗粒度 RBAC 分层正确
- [ ] side_effects 声明式，不在执行器硬编码
- [ ] 多 Object 写入保证原子性（§5.6），未把一个事务拆成多个 Action 让调用方拼装
- [ ] 不属于"应当用 CRUD"的场景（§5.2）

**数据约定**
- [ ] 百分比统一为减扣百分比 int；金额单位元；数量/区间字段带单位
- [ ] 存储文件名 snake_case 复数，路径含 tenant_id

**一致性**
- [ ] 代码常量（LinkTypes/ActionType 枚举）与本体定义一致，冲突时以本体为准
- [ ] 相关 Skill 文档已同步，不引用不存在的实体/工具
- [ ] 破坏性变更走 deprecation 流程

---

## 10. 完整样例：临期出清（clearance）

以现有零售行业包 为例，展示 Object / Link / Action 三者的完整建模。这是新行业包 建模的参考样板。

### 10.1 涉及的 Object Type（节选）

```ttl
store:NearExpiryProduct a rdfs:Class ;
    rdfs:label "临期商品"@zh , "Near Expiry Product"@en ;
    rdfs:comment "即将过期的商品实例"@zh ;
    store:properties "id:string,product_id:string,store_id:string,batch_no:string,production_date:date,expiry_date:date,stock_quantity:int,days_left:int,discount_tier:DiscountTier,status:ProductStatus" ;
    store:storage "near_expiry_products.json" .
# 内核元数据扩展后补：status=active, edits_only_via_actions=true
```

- 软引用 `product_id`→Product、`store_id`→Store，各自配一条 Link。
- `discount_tier:DiscountTier`、`status:ProductStatus` 均为枚举，代码侧有对应 Enum。
- `days_left:int` 单位"天"，在 description 注明。

### 10.2 涉及的 Link Type

```ttl
store:has_near_expiry a rdfs:Property ;    # Store → NearExpiryProduct, via store_id
    rdfs:label "拥有临期商品"@zh ;
    rdfs:domain store:Store ; rdfs:range store:NearExpiryProduct ; store:via "store_id" .

store:is_instance_of a rdfs:Property ;     # NearExpiryProduct → Product, via product_id
    rdfs:label "是...的实例"@zh ;
    rdfs:domain store:NearExpiryProduct ; rdfs:range store:Product ; store:via "product_id" .

store:created_for a rdfs:Property ;        # Task → NearExpiryProduct, via target_id
    rdfs:label "针对"@zh ;
    rdfs:domain store:Task ; rdfs:range store:NearExpiryProduct ; store:via "target_id" .
```

三条 Link 的 `via` 字段（`store_id`/`product_id`/`target_id`）均确实存在于 domain 或 range 上，符合 §4.3。

### 10.3 Action Type（clearance，YAML）

见 §5.1 的完整 YAML。要点：
- `target_object_type: NearExpiryProduct`，`edits_object_types: [NearExpiryProduct, Task]`（出清会改临期商品状态 + 创建 Task 记录）。
- `discount` 参数 `constraint: "0..100"`，语义为减扣百分比（§6.2）。
- `submission_criteria.conditions` 拦截已过期商品（`status is_not expired`）。
- 副作用声明发通知，不硬编码在执行器。

### 10.4 端到端一致性核对

- 折扣数值：只存在于本体数据 `discount_rules.json`（减扣百分比格式）+ 一个 `calculate_discount()` 函数读它。代码、Skill 只引用，不重复定义。（修 bug 1/2/9）
- Task 状态迁移：由 Action（submit/accept/complete）+ 迁移表驱动，不被 `update_entity` 直接改。（修 bug 6/7）
- 所有数据读写经 Repository，带 tenant 过滤与文件锁。（修 bug 10）

---

## 11. 建模创建顺序

借鉴 Palantir summary.md §十的 6 步顺序，本地化为"无 Function"的 5 步。新建一个行业包 或扩展领域时，按此顺序建模：

```
1. 梳理领域实体 → 定义 Object Type（语义基础）
   先回答"业务里有哪些现实世界的东西"，用业务语言命名（§1.2 DDD）

2. 定义 Property（Object 的特征）
   标准化命名 + 业务语义重命名（不镜像源系统列），统一单位口径（§3.3、§6.2）

3. 定义 Link Type（实体间关系）
   确定 domain/range/via，验证 via 归属正确（§4.3），需要双向就建两条

4. 定义 Action Type（运营行为）
   捕获受治理的业务事务：参数 + 约束 + submission_criteria + 副作用（§5）
   读操作不留 Action，受治理写操作必须留 Action（§5.2）

5. 抽取业务规则数值 → 本体数据文件 + 计算函数（单一事实源）
   折扣、阈值等规则不进代码硬编码、不进 Skill 重复定义（§6.2）
```

> Palantir 第 4 步 Interface（抽象形状）和第 6 步 Function（复杂计算）本规范列为 v2：Interface 留待有跨类型共享需求时引入，Function 不引入（计算经 Tool 暴露，§1.3）。

---

## 附录：与参考文档的对应关系

### A. 与架构文档 的对应

| 本规范章节 | 架构文档 对应 |
|---|---|
| §1.1 建模边界与定位 | §1 四概念分工、§1.1 不引入 Function |
| §1.2 原则 6-7 读写分离、edits-only-via-actions | §1.2、§1.3 |
| §1.3 借鉴偏离表 | §1.1、§3.1、§8（演进路线 v2 项） |
| §5.2 Action 边界 | §1.2 第 4-6 点 |
| §5.4 submission_criteria | §3.4、附录 B.2 |
| §5.5 side_effects / 状态机 | §1.5 |
| §5.6 原子性 | 附录 A 数据一致性 |
| §6.2 单位口径 | §4.5 折扣语义统一 |
| §6.3 存储多租户 | §3.3 |
| §7.3 一致性 / §8.1 反模式 | 架构文档附录 A（本仓库真实 bug 衍生） |

### B. 与 Palantir summary.md 的借鉴对应

| 本规范章节 | Palantir 对应 | 借鉴 / 偏离 |
|---|---|---|
| §1.1 本体定位（运营层 / 数字孪生） | summary §一 | 借鉴定位表述 |
| §1.2 原则 2-5（DDD/DRY/OCP/组合） | summary §五四大原则 | 全部借鉴，本地化为 agent 消费者 |
| §1.3 借鉴偏离表 | summary §三 3.2 Function、§2.4 Interface、§6.1 Branching | 明确记录：Function 不引入、Interface/Branching 列 v2 |
| §3 Object→Object Set 三层 | summary §二 2.1 | 借鉴三层概念，Object Set 用 Repository 列表承载 |
| §3.3 Local/Shared Property | summary §二 2.2 | 借鉴分类，Shared Property 列 v2 |
| §3.4 组合优于继承 / Kitchen Sink | summary §五原则 4、§七 | 借鉴，本地化 |
| §4.4 Cardinality 三类 + 自引用 | summary §二 2.3 | 借鉴分类表，MVP 默认 N:N |
| §5.1-5.5 Action 契约要素 | summary §三 3.1、§四安全模型 | 借鉴参数/规则/submission criteria/side effects/双层权限 |
| §5.6 原子性 / 可组合 | summary §三 3.1 | 借鉴，本地化到 confirm_action 原子写入 |
| §6.3 元数据 status/visibility | summary §六 6.3 Metadata | 借鉴元数据全集 |
| §7.1 status 生命周期 | summary §六 6.3 | 借鉴三态 |
| §8.2 反模式 B 组 | summary §七 | 借鉴 5 条经典反模式，本地化 |
| §11 创建顺序 | summary §十 | 借鉴 6 步顺序，本地化为 5 步（无 Function） |

本规范是架构文档 中"怎么建模"部分的展开与硬化，同时是 Palantir 方法论在 LLM agent 时代的落地裁剪。架构变更或 Palantir 借鉴策略调整时，三份文档（架构文档、本规范、Palantir summary）需同步。
