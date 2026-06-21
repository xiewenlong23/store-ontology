> **🗄 归档说明**：brainstorming 产出（spec（设计决策）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# 临期出清场景：业务本体重新建模

> **状态**：目标模型，待 review
> **日期**：2026-06-20
> **依据规范**：`docs/业务本体建模规范.md`（下称"建模规范"）
> **依据场景**：目标架构 spec §1.4「生产场景验证：临期出清跨天流程」（13+ 步）
> **范围**：仅临期出清场景的 Object / Link / Action Type 重新建模。**不含**调拨(transfer)/补货(restock)——它们是独立场景。
> **性质**：这是**目标模型设计**，不是代码改动。提取为 `store.ttl` + `ontology/actions/*.yaml` 属于（待启动的）实现计划。

---

## 0. 为什么必须重做

现有 `store.ttl` + `models/schemas.py` + `tools.py` 是按"单轮对话 demo"建模的：一个 `clearance` Action 把"创建任务 + 提交 + 执行"揉成一次 Preview→Confirm。**生产场景（跨天、多驱动者、需审批与回滚）暴露出这不是一个 Action，而是一条工作流。** 现有建模与规范冲突之处见 §1，重做结论见 §2-§7。

---

## 1. 现状违规盘点（对照建模规范 §8）

逐条核对现有代码，标注违规条目与出处：

| # | 违规点 | 现状（证据） | 违反规范 | 重做处置 |
|---|---|---|---|---|
| 1 | **Action 粒度过粗** | `clearance` 一个 Action 经 `execute_action→confirm_action` 直接建 Task(pending)，把"建单/提交/执行"三件事合一 | §5.2 边界、§5.6 可组合性、§8 反模式 13 Golden Hammer | 拆为 8 个细粒度 Action（§4） |
| 2 | **折扣语义三处矛盾** | `tools.py` 硬编码 `{T1:60,T2:40,T3:20}`（减扣%）；`discount_rules.json` 是 `{0.5,0.7,0.9}`（乘数）；`clearance-workflow/SKILL.md` 是 `{70%,50%,30% off}`（减扣%）。数值与语义维度都不一致 | §6.2 单位口径、§8 反模式 1/8/9 | 单一事实源 + 统一减扣百分比（§6） |
| 3 | **`manages` 方向反转** | `store.ttl`：`manages: Employee→Store, via=manager_id`，但 `manager_id` 是 **Store** 的字段。`traverse_relation` 能跑纯靠巧合 | §4.3 via 归属原则、§8 反模式 3 | 反转为 `Store→Employee`（§3.2） |
| 4 | **`LinkTypes` 常量与 TTL 不一致** | `schemas.py` 的 `HAS_NEAR_EXPIRY_PRODUCT`/`BELONGS_TO`/`SUBJECT_TO` 在 TTL 里不存在或名字不同 | §7.3 一致性、§8 反模式 4 | 删除未用常量，对齐 TTL |
| 5 | **SKILL.md 引用幽灵实体** | `store-ontology/SKILL.md` 引用 `DiscountRule`、`get_near_expiry_products`、`belongs_to`（均不存在） | §7.3、§8 反模式 5 | Skill 文档同步重写（实现计划） |
| 6 | **CRUD 绕过治理** | `update_entity` 可直改 NearExpiryProduct.status，绕过审批 | §5.2、§1.3、§8 反模式 6 | NearExpiryProduct/Task/LossReport 标记 `edits_only_via_actions`（§3） |
| 7 | **Task 状态无约束** | `TaskStatus` 枚举(pending/executing/completed/failed/cancelled)与跨天流程不符，`update_task` 可任意改 status | §5.5 状态机、§8 反模式 7 | 换为 6 态工作流状态机 + 合法迁移表（§5） |
| 8 | **裸数值无单位** | 折扣以乘数/百分比混存，数量字段无单位说明 | §6.2、§8 反模式 8 | 所有数值字段带单位（§3.1） |
| 9 | **`type` 作泛化属性名** | `Task.type: ActionType`——`type` 无业务含义，且枚举耦合 | §2.2 命名、§1.2 原则 2 DDD | 重命名 `type → task_type`（§3.1） |
| 10 | **缺元数据字段** | Object/Action 无 `status`/`visibility`/`edits_only_via_actions`；Action 只有扁平 params | §3.1 元数据、§5.1 契约要素 | 补全元数据与契约要素（§3、§4） |
| 11 | **直接读写文件** | `tools.py` `_load_json/_save_json` 无租户过滤无锁 | §6.3、§8 反模式 10 | 数据层改走 Repository（实现计划） |
| 12 | **tasks.json 遗留 schema** | 种子用旧字段 `action_type/near_expiry_product_id/input_params`，`query_task` 靠 `setdefault` 打补丁 | §7.3 一致性 | 迁移种子数据到新 schema（§7） |

---

## 2. 重做总览

| 资源 | 现状 | 重做后 | 变化 |
|---|---|---|---|
| **Object Type** | 6（缺 LossReport） | **7**（+LossReport） | +1，全补元数据 |
| **Link Type** | 7（manages 反转、缺执行人/报损关系） | **10** | +3，修 1 方向 |
| **Action Type** | 3（clearance/transfer/restock，契约弱） | clearance 拆为 **8**；transfer/restock 保留 | 拆解，全补 YAML 契约 |
| **折扣规则** | 三处矛盾 | **单一事实源** discount_rules.json + `calculate_discount()` | 统一减扣百分比 |
| **Task 状态** | 5 态无约束 | **6 态 + 合法迁移表** | 状态机化 |

存储格式决策（沿用架构 spec §3.4）：**Object/Link Type 用 TTL**（扩 parser 识别新元数据谓词），**Action Type 用 YAML**（`ontology/actions/*.yaml`）。

---

## 3. 重新建模：Object Type（7 个）

每个补全建模规范 §3.1 元数据：`status` / `visibility` / `edits_only_via_actions`；数值字段带单位（§3.3、§6.2）；软引用字段配 Link（§4）。

### 3.1 Task（出清任务，重灾区，重点）

```ttl
store:Task a rdfs:Class ;
    rdfs:label "出清任务"@zh , "Task"@en ;
    rdfs:comment "受治理工作流的载体。一次出清从建单到完成/报损的完整记录"@zh ;
    store:properties "id:string,task_type:TaskType,target_id:string,store_id:string,assignee_id:string,status:TaskStatus,discount_percent:int,planned_quantity:int,sold_quantity:int,params_json:dict,result_json:dict,priority:Priority,notes:string,created_at:datetime,started_at:datetime,completed_at:datetime" ;
    store:storage "tasks.json" ;
    store:status "active" ;
    store:visibility "prominent" ;
    store:edits_only_via_actions "true" .
```

**字段口径**（写进 description，符合 §6.2）：

| 字段 | 类型 | 单位/口径 | 说明 |
|---|---|---|---|
| `task_type` | enum TaskType | — | clearance/transfer/restock。**替换原泛化 `type`**（违规 9） |
| `target_id` | string | — | 指向 NearExpiryProduct.id（配 Link `created_for`） |
| `assignee_id` | string | — | 执行人，指向 Employee.id（配 Link `assigned_to`，新增） |
| `status` | enum TaskStatus | — | 见 §5 状态机 |
| `discount_percent` | int | **减扣百分比 0-100**，50=五折 | 单一事实源计算后写入（§6） |
| `planned_quantity` | int | **件** | 计划出清数量 |
| `sold_quantity` | int | **件** | POS 累计已售，由 deduct_stock 递增 |

### 3.2 NearExpiryProduct（临期商品）

```ttl
store:NearExpiryProduct a rdfs:Class ;
    rdfs:label "临期商品"@zh , "Near Expiry Product"@en ;
    rdfs:comment "即将过期的商品批次实例，出清的标的物"@zh ;
    store:properties "id:string,product_id:string,store_id:string,batch_no:string,production_date:date,expiry_date:date,stock_quantity:int,days_left:int,discount_tier:DiscountTier,status:NearExpiryProductStatus" ;
    store:storage "near_expiry_products.json" ;
    store:status "active" ;
    store:edits_only_via_actions "true" .   # 写只能经 Action（违规 6 处置）
```

| 字段 | 单位/口径 |
|---|---|
| `stock_quantity` | **件**，由 deduct_stock 扣减 |
| `days_left` | **天** |
| `discount_tier` | T1/T2/T3，决定 discount_percent 默认值（§6） |
| `status` | NearExpiryProductStatus：`expiring` / `clearance` / `sold_out` / `expired` / `scrapped` |

**说明**：`status` 由 Action 设定，不是自由字段——`create_clearance_task`→`clearance`、`complete_task`→`sold_out`、`create_loss_report`→`scrapped`；`expired` 由后端定时器设。"正在出清中"不靠查 status，靠查关联 Task 的状态（单一事实源，避免状态重复）。

### 3.3 LossReport（报损单，新增）

报损是出清的失败路径产物，有独立标识、被 Task 与 NearExpiryProduct 双重引用、需审计 → 符合建模规范 §3.4「何时建新 Object Type」，升为独立实体。

```ttl
store:LossReport a rdfs:Class ;
    rdfs:label "报损单"@zh , "Loss Report"@en ;
    rdfs:comment "到期未售罄的报损记录，由 create_loss_report 创建"@zh ;
    store:properties "id:string,task_id:string,target_id:string,loss_quantity:int,loss_value:float,loss_reason:string,status:LossReportStatus,created_at:datetime" ;
    store:storage "loss_reports.json" ;
    store:status "active" ;
    store:edits_only_via_actions "true" .
```

| 字段 | 单位/口径 |
|---|---|
| `task_id` | 指向原出清 Task.id（配 Link `has_loss_report`） |
| `target_id` | 指向 NearExpiryProduct.id（配 Link `written_off`） |
| `loss_quantity` | **件** |
| `loss_value` | **元**，= loss_quantity × cost_price（计算模块算） |

### 3.4 其余 4 个 Object Type（结构不变，补元数据）

```ttl
store:Region a rdfs:Class ;
    rdfs:label "区域"@zh , "Region"@en ;
    store:properties "id:string,name:string,code:string" ;
    store:storage "regions.json" ; store:status "active" .

store:Store a rdfs:Class ;
    rdfs:label "门店"@zh , "Store"@en ;
    store:properties "id:string,name:string,region_id:string,address:string,manager_id:string,created_at:datetime" ;
    store:storage "stores.json" ; store:status "active" .

store:Employee a rdfs:Class ;
    rdfs:label "员工"@zh , "Employee"@en ;
    store:properties "id:string,name:string,store_id:string,role:EmployeeRole,phone:string" ;
    store:storage "employees.json" ; store:status "active" .

store:Product a rdfs:Class ;
    rdfs:label "商品"@zh , "Product"@en ;
    store:properties "id:string,name:string,category:string,brand:string,unit:string,cost_price:float,retail_price:float" ;
    store:storage "products.json" ; store:status "active" .
```

- `cost_price`/`retail_price`：单位**元**（§6.2 金额带后缀，已合规）。
- 新增枚举（须在 `schemas.py` 同步，§7.3）：
  - `TaskStatus`: created / pending_approval / approved / accepted / in_progress / completed / rejected / scrapped
  - `NearExpiryProductStatus`: expiring / clearance / sold_out / expired / scrapped
  - `TaskType`: clearance / transfer / restock
  - `LossReportStatus`: pending / confirmed
  - `DiscountTier` / `Priority` / `EmployeeRole`：保留

---

## 4. 重新建模：Link Type（10 个）

### 4.1 清单（含 via 归属标注，对照 §4.3）

| # | api_name | 读法 | domain → range | via（在哪一侧） |
|---|---|---|---|---|
| 1 | `located_in` | 门店位于区域 | Store → Region | `region_id`（domain 侧） |
| 2 | `has_employee` | 门店拥有员工 | Store → Employee | `store_id`（**range 侧**，须注记） |
| 3 | `has_near_expiry` | 门店拥有临期商品 | Store → NearExpiryProduct | `store_id`（**range 侧**） |
| 4 | `is_instance_of` | 临期商品是商品的实例 | NearExpiryProduct → Product | `product_id`（domain 侧） |
| 5 | `manages` | 门店的店长（管理） | **Store → Employee** | `manager_id`（domain 侧）— **修正方向** |
| 6 | `has_task` | 门店有任务 | Store → Task | `store_id`（**range 侧**） |
| 7 | `created_for` | 任务针对临期商品 | Task → NearExpiryProduct | `target_id`（domain 侧） |
| 8 | `assigned_to` | 任务指派给员工 | Task → Employee | `assignee_id`（domain 侧）— **新增** |
| 9 | `has_loss_report` | 任务产生报损单 | Task → LossReport | `task_id`（**range 侧**）— **新增** |
| 10 | `written_off` | 报损单核销临期商品 | LossReport → NearExpiryProduct | `target_id`（domain 侧）— **新增** |

### 4.2 关键修正：`manages` 方向（违规 3）

```ttl
# 修正前（违规：via=manager_id 不在 Employee 上）
store:manages a rdfs:Property ;
    rdfs:domain store:Employee ; rdfs:range store:Store ; store:via "manager_id" .

# 修正后（manager_id 是 Store 的字段，按 §4.3 应从 Store 出发）
store:manages a rdfs:Property ;
    rdfs:label "管理"@zh , "manages"@en ;
    rdfs:comment "门店通过 manager_id 指向其店长（一个 Employee）"@zh ;
    rdfs:domain store:Store ; rdfs:range store:Employee ; store:via "manager_id" .
```

### 4.3 via-on-range 必须注记（§4.3 硬约束）

`has_employee`/`has_near_expiry`/`has_task`/`has_loss_report` 的外键在 **range 侧**（被引用方持有指回 domain 的字段）。TTL description 必须写明，避免方向歧义。例：

```ttl
store:has_employee a rdfs:Property ;
    rdfs:label "拥有员工"@zh , "has employee"@en ;
    rdfs:comment "Store 的员工集合。via store_id 在 Employee（range）上，指回 Store"@zh ;
    rdfs:domain store:Store ; rdfs:range store:Employee ; store:via "store_id" .
```

### 4.4 反向遍历

需要反向遍历时显式建第二条 Link（§4.4），不用一条 Link 隐含双向。MVP 仅出清所需方向，`works_at`(Employee→Store) 等反向 Link 按需补充，本轮不建。

---

## 5. 重新建模：Action Type（8 个 YAML 契约）

> 原 `clearance` 单体 Action **降级为 deprecated**，被以下 8 个细粒度 Action 取代（违规 1 处置）。transfer/restock 不在本场景，保留不动。

每个 Action 含建模规范 §5.1 全部要素：`target_object_type` / `edits_object_types`(provenance) / `parameters`(带 constraint) / `submission_criteria`(独立于粗粒度 RBAC) / `side_effects`(声明式)。

### 5.1 create_clearance_task（步骤 7，LLM）

```yaml
api_name: create_clearance_task
display_name: 创建出清任务
description: 为临期商品建出清单，进入 created 态
status: active
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]   # 同时改商品状态 + 建任务
parameters:
  - { name: target_id,        type: string, required: true, description: "临期商品实例ID" }
  - { name: store_id,         type: string, required: true }
  - { name: assignee_id,      type: string, required: true,  description: "执行人(员工)ID" }
  - { name: discount_percent, type: int,    required: true,  constraint: "0..100", description: "减扣百分比(0-100整数)，50=五折" }
  - { name: planned_quantity, type: int,    required: true,  constraint: ">0",     description: "计划出清数量(件)" }
  - { name: priority,         type: enum,   required: false, default: medium }
  - { name: notes,            type: string, required: false }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is_not, value: expired,  fail_msg: "已过期商品不能出清" }
    - { field: target.status, operator: is_not, value: scrapped, fail_msg: "已报损商品不能出清" }
side_effects:
  - { type: create_object, object_type: Task, fields: { task_type: clearance, status: created, discount_percent, planned_quantity, sold_quantity: 0 } }
  - { type: update_object, object_type: NearExpiryProduct, fields: { status: clearance } }
  - { type: notification, template: clearance_task_created, recipients: [assignee_id, manager_id] }
```

> `discount_percent` 由计算模块 `calculate_discount()` 按 tier 算出后由 LLM 传入（§6 单一事实源），Action 只校验范围与记录。

### 5.2 submit_for_approval（步骤 8，LLM）

```yaml
api_name: submit_for_approval
display_name: 提交审批
description: 出清任务提交审批，created → pending_approval
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id, type: string, required: true }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is, value: created, fail_msg: "仅 created 态可提交审批" }
side_effects:
  - { type: state_transition, target: Task, from: created, to: pending_approval }
  - { type: notification, template: approval_requested, recipients: [manager_id] }
```

### 5.3 approve_clearance（步骤 9，后端自动化·审批回调）

```yaml
api_name: approve_clearance
display_name: 审批通过
description: 审批回调通过任务，pending_approval → approved。由后端自动化调用（无 LLM）
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id,      type: string, required: true }
  - { name: approver_id,  type: string, required: true }
  - { name: comment,      type: string, required: false }
submission_criteria:
  roles: [region_cat_mgr]   # 审批权在区域品类经理
  conditions:
    - { field: target.status, operator: is, value: pending_approval, fail_msg: "仅待审批任务可审批" }
side_effects:
  - { type: state_transition, target: Task, from: pending_approval, to: approved }
  - { type: notification, template: clearance_approved, recipients: [assignee_id] }
```

> 此 Action 印证建模规范 §1.2：**Action 是 LLM 与后端共用的变更契约**——只有后端调它，但它仍是 Action（而非裸代码），保证审计/权限/状态校验统一。架构 spec §4.2 列的 7 个名字未显式含 approve，本建模补它是状态机的必然需求。

### 5.4 accept_task（步骤 10，人/系统）

```yaml
api_name: accept_task
display_name: 接受任务
description: 执行人接单，approved → accepted
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id,     type: string, required: true }
  - { name: assignee_id, type: string, required: true }
submission_criteria:
  roles: [store_manager, clerk]
  conditions:
    - { field: target.status, operator: is, value: approved }
side_effects:
  - { type: state_transition, target: Task, from: approved, to: accepted }
```

### 5.5 print_labels（步骤 11，人）

```yaml
api_name: print_labels
display_name: 打折签打印
description: 打印折扣签并陈列，accepted → in_progress；side effect 对接打印机
target_object_type: Task
edits_object_types: [Task]
parameters:
  - { name: task_id,    type: string, required: true }
  - { name: label_count, type: int,   required: true, constraint: ">0" }
submission_criteria:
  roles: [store_manager, clerk]
  conditions:
    - { field: target.status, operator: is, value: accepted }
side_effects:
  - { type: state_transition, target: Task, from: accepted, to: in_progress }
  - { type: external_call, service: printer, action: print_discount_labels }
```

### 5.6 deduct_stock（步骤 12，后端自动化·POS 事件）

```yaml
api_name: deduct_stock
display_name: 扣减库存
description: POS 扫码扣库存并累计已售，不改任务状态。后端自动化调用
target_object_type: NearExpiryProduct
edits_object_types: [NearExpiryProduct, Task]
parameters:
  - { name: target_id, type: string, required: true, description: "临期商品实例ID" }
  - { name: task_id,   type: string, required: true }
  - { name: quantity,  type: int,    required: true, constraint: ">0", description: "本次扣减(件)" }
submission_criteria:
  roles: [system_pos]   # 系统角色（双消费者中的"系统"侧）
  conditions:
    - { field: target.status, operator: is, value: clearance }
    - { field: task.status,   operator: is, value: in_progress }
side_effects:
  - { type: update_object, object_type: NearExpiryProduct, transform: "stock_quantity -= quantity" }
  - { type: update_object, object_type: Task,              transform: "sold_quantity += quantity" }
```

### 5.7 complete_task（步骤 13，后端自动化·盘点）

```yaml
api_name: complete_task
display_name: 完成任务
description: 售罄结单，in_progress → completed；商品 sold_out
target_object_type: Task
edits_object_types: [Task, NearExpiryProduct]
parameters:
  - { name: task_id,   type: string, required: true }
  - { name: target_id, type: string, required: true }
submission_criteria:
  roles: [store_manager, system_inventory]
  conditions:
    - { field: target.status,         operator: is,  value: in_progress }
    - { field: target.sold_quantity,  operator: gte, value_ref: planned_quantity, fail_msg: "未售罄不可完成，请走报损" }
side_effects:
  - { type: state_transition, target: Task, from: in_progress, to: completed }
  - { type: update_object,    object_type: NearExpiryProduct, fields: { status: sold_out } }
```

### 5.8 create_loss_report（步骤 14，后端定时器→LLM）

```yaml
api_name: create_loss_report
display_name: 报损
description: 到期未售罄，建报损单，in_progress → scrapped；商品 scrapped
target_object_type: Task
edits_object_types: [Task, NearExpiryProduct, LossReport]
parameters:
  - { name: task_id,       type: string, required: true }
  - { name: target_id,     type: string, required: true, description: "临期商品实例ID" }
  - { name: loss_quantity, type: int,    required: true, constraint: ">0", description: "报损数量(件)" }
  - { name: loss_reason,   type: string, required: true }
submission_criteria:
  roles: [store_manager, region_cat_mgr]
  conditions:
    - { field: target.status, operator: is, value: in_progress }
side_effects:
  - { type: state_transition, target: Task, from: in_progress, to: scrapped }
  - { type: update_object,    object_type: NearExpiryProduct, fields: { status: scrapped } }
  - { type: create_object,    object_type: LossReport, fields: { task_id, target_id, loss_quantity, loss_reason } }
  - { type: notification,     template: loss_report_created, recipients: [manager_id] }
```

---

## 6. Task 状态机（建模规范 §5.5、§8 反模式 7 处置）

合法迁移表（沿用架构 spec §1.5），每条标注触发它的 Action：

```python
TASK_TRANSITIONS = {
    "created":          ["pending_approval", "scrapped"],          # submit_for_approval / cancel
    "pending_approval": ["approved", "rejected", "scrapped"],      # approve_clearance / reject / cancel
    "approved":         ["accepted", "scrapped"],                  # accept_task / cancel
    "accepted":         ["in_progress", "scrapped"],               # print_labels / cancel
    "in_progress":      ["completed", "scrapped"],                 # complete_task / create_loss_report
}
# 终态：completed / rejected / scrapped（不可再迁移）
# reject_clearance（pending_approval→rejected）属审批支路，非 13 步主路径，本轮不单独建模，实现时按 approve 的对偶补
```

**执行器约束**：每个带 `state_transition` 副作用的 Action，`confirm` 前查此表——`from` 不匹配则拒绝（违规 7 处置）。状态迁移只由 Action 触发，`update_task` 不允许直改 `status`（Task 标记 edits-only-via-actions，违规 6 处置）。

---

## 7. 折扣：单一事实源（建模规范 §6.2、§8 反模式 1/8/9 处置）

### 7.1 语义统一

全系统统一 **减扣百分比（0-100 int）**：50 = 五折 = 减 50%。

### 7.2 discount_rules.json 迁移（乘数 → 减扣百分比）

```json
[
  {"id": "rule_T1", "tier": "T1", "days_min": 0,  "days_max": 3,  "discount_percent": 50, "description": "即将过期，5折(减50%)"},
  {"id": "rule_T2", "tier": "T2", "days_min": 4,  "days_max": 7,  "discount_percent": 30, "description": "中期临期，7折(减30%)"},
  {"id": "rule_T3", "tier": "T3", "days_min": 8,  "days_max": 14, "discount_percent": 10, "description": "初期临期，9折(减10%)"}
]
```

迁移映射（值）：`discount_rate 0.5→50, 0.7→30, 0.9→10`；字段 `discount_rate→discount_percent`。

### 7.3 单一计算函数

```python
# business/discount.py —— 唯一事实源
def calculate_discount(discount_tier: str) -> int:
    """返回减扣百分比(0-100 int)。读 discount_rules.json。tools/SKILL 只引用，不重复定义。"""
    rules = load_discount_rules()
    return next(r["discount_percent"] for r in rules if r["tier"] == discount_tier)
```

### 7.4 同步删除的重复定义

- `tools.py` 删 `tier_discount = {"T1":60,"T2":40,"T3":20}`（违规 2）
- `clearance-workflow/SKILL.md` 删折扣数值，改"由 discount_tier 决定，见 discount_rules.json"（违规 5）
- `query_task` 的 `float→int` 转换 hack 删除（语义统一后不需要）

---

## 8. 13 步流程 → 概念映射（重做后）

更新架构 spec §1.4 表，落实为本建模的具体资源名：

| # | 步骤 | 驱动者 | 归属（重做后） |
|---|---|---|---|
| 1 | 定时作业唤醒 agent | 调度器 | Agent 入口(headless) |
| 2 | 取库存商品+生产日期 | LLM | Tool `query_near_expiry`/`query_entity`（读，无 Action） |
| 3 | 取临期定义 | LLM | Tool 读本体数据 `discount_rules.json` |
| 4 | 判断哪些/多少要出清 | LLM 推理 | Skill `clearance-workflow` 指导 |
| 5 | 计算折扣 | 代码 | 普通函数 `calculate_discount()` |
| 6 | 定执行人/起止 | LLM 推理 | Skill 指导 |
| 7 | 创建出清单 | LLM | **Action `create_clearance_task`**（建 Task=created，商品→clearance） |
| 8 | 发起审批 | LLM | **Action `submit_for_approval`**（created→pending_approval） |
| 9 | 审批完成 | 系统 | **Action `approve_clearance`**（后端回调，→approved） |
| 10 | 接受任务 | 人/系统 | **Action `accept_task`**（→accepted） |
| 11 | 打折签+陈列 | 人 | **Action `print_labels`**（→in_progress，对接打印机） |
| 12 | POS 扣库存 | 系统 | **Action `deduct_stock`**（后端 POS，stock-/sold+） |
| 13 | 售罄完成 | 系统 | **Action `complete_task`**（后端盘点，→completed，商品→sold_out） |
| 14 | 到期未售罄→报损 | 系统→LLM | **Action `create_loss_report`**（定时器→唤醒 LLM，→scrapped，建 LossReport） |

**校验结论**：
- 8 个 Action 覆盖全部"变更"步骤；读步骤(2/3)是纯 Tool，无 Action（符合 §1.2 读写分离）。
- 步骤 9/12/13 无 LLM 在环——后端自动化**直接调 Action**，证明 Action 不可被 Tool 取代（建模规范 §1.2 第 3 点双消费者）。
- 长流程不靠单一 Skill 装下，涌现自「Task 状态机 + Action 迁移 + 后端自动化」（架构 spec §1.5）。

---

## 9. 对照建模规范 §9 检查清单自验

| 清单项 | 结论 |
|---|---|
| **命名** Object PascalCase 单数 / Link·Action snake_case | ✅（§3、§4、§5） |
| 每个资源中英文 label | ✅ |
| `api_name` 全局唯一 | ✅ |
| 软引用字段 `{type}_id` 形式 | ✅（target_id/assignee_id/region_id/store_id/product_id/task_id） |
| Object 有主键 `id` | ✅ |
| 元数据齐全（api_name/display/description/properties/storage/status） | ✅（全补，违规 10） |
| 属性类型取自白名单，无 string 存日期/数值 | ✅ |
| 枚举属性代码侧有 Enum | ✅（§3.4 列出，须同步 schemas.py，违规 4） |
| 核心实体按需标 edits_only_via_actions | ✅（Task/NEP/LossReport，违规 6） |
| 无 Kitchen Sink | ✅（报损独立成 LossReport 而非塞进 Task，§3.4） |
| Link domain/range/via 齐全 | ✅ |
| `via` 确属于 domain 或 range | ✅（manages 已修正，§4.2） |
| via-on-range 已注记 | ✅（§4.3） |
| Action 用 YAML 定义于 ontology/actions/ | ✅（§5） |
| 有 target_object_type + edits_object_types(provenance) | ✅（每条都有） |
| parameters 带声明式 constraint | ✅（0..100 / >0 等） |
| submission_criteria 与粗粒度 RBAC 分层 | ✅（roles + conditions，§5.4） |
| side_effects 声明式，不在执行器硬编码 | ✅ |
| 多 Object 写入保证原子性 | ✅（execute→confirm 原子写，§5.6） |
| 不属"该用 CRUD"的场景 | ✅（全是受治理事务） |
| 百分比统一减扣 int / 金额元 / 数量带单位 | ✅（§6、§3.1） |
| 存储文件名 snake_case 复数，路径含 tenant | ⚠️ 文件名合规；tenant 路径属实现计划（§6.3） |
| 代码常量与本体一致，冲突以本体为准 | ✅（LinkTypes 删旧/TaskStatus 换新，违规 4/7） |
| Skill 文档同步 | ⚠️ 待实现计划重写 SKILL.md（违规 5） |
| 破坏性变更走 deprecation | ✅（原 `clearance` 标 deprecated，§5） |

**遗留项（⚠️）**：tenant 存储路径、SKILL.md 重写属于实现计划范畴，不在本建模设计内。

---

## 10. 落地说明

- 本文档是**目标模型设计**，不含代码改动。
- 提取为实际文件属于架构 spec §8「MVP」实现列：
  - `backend/ontology/store.ttl` → 按 §3/§4 重写（parser 须扩识别 `store:status`/`store:visibility`/`store:edits_only_via_actions` 谓词）
  - `backend/ontology/actions/*.yaml` → 按 §5 新建 8 个文件
  - `backend/models/schemas.py` → 按 §3.4 同步枚举、删旧 LinkTypes、Task 字段重命名
  - `backend/ontology/tools.py` → 删折扣硬编码、`execute_action`/`confirm_action` 改为瘦路由器读 YAML 契约
  - `data/discount_rules.json` → 按 §7.2 迁移
  - `data/tasks.json` → 按 §12（违规 12）迁移种子 schema
- 建议下一步：用 `writing-plans` 把本建模 + 架构 spec §8 MVP 列转为实现计划。
