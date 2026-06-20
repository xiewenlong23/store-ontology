# P2：行业包 + 能力域/价值链流程双轴 设计

> **状态**：基于 APaaS 总 spec §2 细化，待 review
> **日期**：2026-06-20
> **依赖**：P1（多客户租户地基，已完成）
> **性质**：把现有扁平 `VerticalConfig`（本体+工作流+状态机揉一起）重构为三级结构：`IndustryPack` > `CapabilityDomain`（原子）+ `ValueChainProcess`（跨域编排）。现有 clearance / equipment_repair 平滑迁移。

---

## 0. 目标

1. 引入 `IndustryPack` / `CapabilityDomain` / `ValueChainProcess` 三级数据结构。
2. 拆分现有 `VerticalConfig`：本体/Action 归 Domain，状态机/编排归 Process。
3. clearance 迁移为 retail-pack 的一个 ValueChainProcess（跨域调 Action）。
4. bootstrap 从扫 `verticals/*/config.py` 升级为扫 `packs/*/pack.py`。
5. **向后兼容**：P1 的 117 测试不破。迁移期间 `VerticalConfig` 作为适配层保留。

## 1. 三级数据结构

### 1.1 CapabilityDomain（能力域）

提供原子 Object/Link/Action + 域内规则源。**不含工作流/状态机**。

```python
@dataclass
class CapabilityDomain:
    name: str                    # "marketing" / "supply_chain" / "organization" / "finance"
    display_name: str            # "营销域"
    ttl_path: str                # 该域的 Object/Link 定义（TTL）
    actions_dir: str             # 该域的 Action YAML 目录
    rules_dir: Optional[str]     # 域内规则数据源目录（如 discount_rules.json）
    description: str = ""
```

### 1.2 ValueChainProcess（价值链流程）

跨域编排：有自己的状态机 + Skill + 专属工具。调用多个 Domain 的 Action。

```python
@dataclass
class ValueChainProcess:
    name: str                    # "clearance" / "procurement"
    display_name: str            # "出清"
    workflow_object_type: str    # "Task" / "RepairTicket"
    workflow_object_id_field: str = "task_id"
    state_transitions: Dict[str, List[str]] = field(default_factory=dict)
    terminal_states: List[str] = field(default_factory=list)
    skills_dir: Optional[str] = None
    tools_module: Optional[str] = None    # "processes.clearance.tools"
    system_prompt_intro: str = ""
    description: str = ""
```

### 1.3 IndustryPack（行业包）

聚合多个 CapabilityDomain + 多个 ValueChainProcess。

```python
@dataclass
class IndustryPack:
    name: str                    # "retail" / "logistics" / "manufacturing"
    display_name: str            # "零售行业包"
    domains: List[CapabilityDomain] = field(default_factory=list)
    processes: List[ValueChainProcess] = field(default_factory=list)
    data_dir: str = ""           # 行业包默认数据目录（客户 copy 的源）
```

## 2. clearance 迁移方案

现有 clearance 把 7 Object + 8 Action + 状态机 + Skill + 工具全揉在一个 VerticalConfig。迁移为：

```
packs/retail/                         # 行业包
  pack.py                             # 声明 IndustryPack
  domains/
    marketing/                        # 营销域能力
      domain.ttl                      # Product, NearExpiryProduct, PriceRule
      actions/                        # create_clearance_task（定价部分）
      rules/                          # discount_rules.json
    supply_chain/                     # 供应链域能力
      domain.ttl                      # Inventory
      actions/                        # deduct_stock
    organization/                     # 组织域能力
      domain.ttl                      # Store, Employee, Region
      actions/                        # accept_task, print_labels（执行人相关）
    finance/                          # 财务域能力
      domain.ttl                      # LossReport, Task（Task 归财务？还是组织？见§3）
      actions/                        # create_loss_report, complete_task
  processes/
    clearance/                        # 出清价值链流程
      process.py                      # 声明 ValueChainProcess（状态机 + 跨域编排）
      skills/                         # clearance-workflow, store-ontology
      tools.py                        # query_near_expiry
```

### 迁移原则
- **TTL 按域拆分**：现有 store.ttl 的 Object 按"主要归属域"分到各 domain.ttl。Link 跟着 domain 走（跨域 Link 放在"主动方"域）。
- **Action 按主要操作对象归属域**：create_clearance_task 的 target 是 NearExpiryProduct（营销域）；deduct_stock 改库存（供应链域）；create_loss_report 建报损单（财务域）。
- **状态机归 Process**：Task 的状态迁移表归 clearance process，不归任何单域。
- **工具归 Process**：query_near_expiry 是 clearance 流程的专属读工具，归 process。

### §3 Task 归属问题
Task 是工作流载体（跨域），不纯属于任何单域。**决策**：Task 的 Object 定义归 organization 域（它是组织内的执行单元），但状态机/生命周期归 clearance process 管理。这与"Task 是谁建的"无关——组织域提供 Task 类型，clearance 流程用它的状态机。

## 3. equipment_repair 迁移

equipment_repair 是独立场景（非零售四域）。两种选择：
- **A**：作为 retail-pack 的另一个 ValueChainProcess（但它不属于零售价值链）。
- **B**：作为独立行业包 `equipment-maintenance-pack`（但它和零售共享 Store/Employee）。

**决策**：P2 阶段 equipment_repair 暂保持现有 vertical 结构不动（作为兼容验证用），仅 clearance 迁移到新三级结构。equipment_repair 的迁移留 P3（客户自定义 + onboarding 时，按需归入合适行业包）。这避免 P2 过大。

## 4. bootstrap 升级

```python
def bootstrap() -> None:
    """扫描 packs/*/pack.py 注册 IndustryPack，
    + 扫描 verticals/*/config.py 注册遗留 VerticalConfig（兼容）。"""
    # 1. 新结构：packs
    _discover_packs()
    # 2. 旧结构：verticals（兼容期保留）
    _discover_verticals()
```

`IndustryPack` 注册到 pack 注册表；`VerticalConfig` 继续注册到 vertical 注册表。两者的 registry 合并后供 executor/tools 使用。

## 5. VerticalConfig 兼容适配

P2 期间 `VerticalConfig` 不删除（equipment_repair 仍用它）。新增一个适配函数把 `IndustryPack` 的 domains + processes 合并为等价的 registry：

```python
def pack_to_registry(pack: IndustryPack) -> EntityRegistry:
    """合并 pack 下所有 domain 的 Object/Link + 所有 action_dirs 的 Action。"""
```

executor/tools 不关心 Action 来自 domain 还是 process——它按 Action 名路由。

## 6. 不在 P2 范围
- equipment_repair 迁移（留 P3）
- 客户 copy/onboarding（留 P3）
- 运营看板（留 P4）
- 数据库存储（留 P5a）
