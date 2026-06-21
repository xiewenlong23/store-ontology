> **🗄 归档说明**：本文档为零售深度特化愿景（多组织 / RBAC×ABAC 六层权限瀑布 / 审计 / 观测）。其前瞻机制已摘要进 [`roadmap.md`](../roadmap.md)（醒目标注"未实现"）。保留作历史追溯。**请勿据此文档认为这些机制已落地。**

---

# AI 门店大脑 - Harness Engineering 设计文档

> 本文档定义 AI 门店大脑的 Harness 工程体系：多组织架构、权限管理、日志与审计、可观测性。采用 RBAC × ABAC 融合模型，以**关系型权限规则**为核心，确保组织调整时权限可自动适应，无需手动重配。

**设计原则（三不变）**：
- 组织调整 ≠ 权限重配
- 品类调整 ≠ 权限重配
- 职能域调整 ≠ 权限重配

---

## 1. 多组织架构设计

### 1.1 组织维度（Org Dimension）

```
Brand（零售集团）
  └── OrgGroup（利润中心 / 成本中心）
        ├── company_code: string        # 公司代码（财务核算用）
        ├── profit_center_code: string  # 利润中心代码
        └── cost_center_code: string    # 成本中心代码
              └── Channel（业态）
                    └── Region（销售运营区域）
                          └── Store（门店）
```

| 层级 | 实体 | 关键属性 | 说明 |
|------|------|---------|------|
| Brand | Brand | id, name | 零售集团顶层 |
| L2 | OrgGroup | id, name, company_code, profit_center_code, cost_center_code | 独立核算单元 |
| L3 | Channel | id, name, type ∈ {hyper, supermarket, convenience, app} | 业态类型 |
| L4 | Region | id, name, channel_id | 销售运营区域 |
| L5 | Store | id, name, region_id, address, manager_id | 最小运营单元 |

**Channel 类型枚举**：

```typescript
enum ChannelType {
  HYPER       = "hyper",       // 大卖场（AA店）
  SUPERMARKET = "supermarket", // 标超
  CONVENIENCE = "convenience", // 社区店（生鲜加强型）
  APP         = "app"          // 线上/到家（App/小程序/第三方平台）
}
```

**Link Types（组织内关系）**：

| Link Type | 源 → 目标 | 说明 |
|-----------|----------|------|
| belongs_to | Store → Region | 门店归属区域 |
| operates_in | Region → Channel | 区域运营某业态 |
| child_of | Region → OrgGroup | 区域归属核算单元 |
| part_of | OrgGroup → Brand | 核算单元归属品牌 |

### 1.2 配送中心维度（DC Dimension，正交于组织）

DC（Distribution Center，配送中心）是独立于 Region 的供应链实体，按仓型分类：

```typescript
enum DCType {
  FRESH   = "fresh",   // 生鲜仓（区域）
  GROCERY = "grocery", // 杂货仓（区域）
  CENTRAL = "central"  // 央仓（全国）
}
```

| 层级 | 实体 | 关键属性 | 说明 |
|------|------|---------|------|
| DC | DistributionCenter | id, name, region_id?, type: DCType, capacity | DC实体 |

**供应关系**：

```
央仓（CENTRAL）
  └── 补货 ──→ 区域杂货仓（GROCERY）
                    └── 配送 ──→ 门店

生鲜仓（FRESH）
  └── 直采/供应商直送 ← 门店 ← 本地采购

动销慢商品从央仓补货到区域杂货仓
```

**Link Types（DC 关系）**:

| Link Type | 源 → 目标 | 说明 |
|-----------|----------|------|
| supplies_from | DC (grocery) → DC (central) | 杂货仓由央仓补货 |
| delivers_to | DC → Store | DC 配送至门店 |
| attached_to | DC → Region | DC 归属区域（fresh/grocery型）|

### 1.3 职能域维度（Domain Dimension，正交于组织）

职能域决定「能用哪些功能」，与组织维度正交。

```typescript
enum Domain {
  HQ_SUPPORT = "hq_support",     // 总部支持域（财务/HR/IT）
  SUPPLY_CHAIN = "supply_chain", // 供应链域（采购部门 + DC物流）
  RETAIL_OPS = "retail_ops"       // 超市运营域（门店销售）
}
```

| 职能域 | 包含部门 | 可用功能 |
|--------|---------|---------|
| HQ_SUPPORT | 财务部、HR、IT部 | 系统配置、报表查看、全局设置 |
| SUPPLY_CHAIN | 采购部、DC物流部 | 采购管理、供应商管理、DC库存管理、损耗审批 |
| RETAIL_OPS | 门店运营部 | 门店销售、门店调价、门店损耗上报 |

**Link Types（职能域关系）**:

| Link Type | 源 → 目标 | 说明 |
|-----------|----------|------|
| belongs_to | Employee → Domain | 员工归属职能域 |
| manages | DC → Domain (supply_chain) | DC 归属供应链域 |

---

## 2. 品类维度设计

### 2.1 品类层级（5级，生鲜部门特有多一级）

```
Department（部门）
  └── CategoryGroup（大类）
        └── Category（中类）
              └── SubCategory（小类）
                    └── Variety（次小类，仅生鲜部门）
```

**部门枚举**：

```typescript
enum Department {
  FRESH   = "fresh",   // 生鲜
  FOOD    = "food",    // 食品
  DAILY   = "daily",   // 日配/日用品
  NON_FOOD = "non_food" // 非食品
}
```

**品类层级说明**：

| 层级 | 层级ID | 生鲜部门示例 | 非生鲜部门示例 | 最末级? |
|------|--------|------------|--------------|--------|
| L1 | department | 生鲜 | 食品 | ✗ |
| L2 | category_group | 水果 | 粮油调味 | ✗ |
| L3 | category | 热带水果 | 食用油 | ✗ |
| L4 | sub_category | 香蕉 | 花生油 | ✗ |
| L5 | variety | 皇帝蕉 | null | ✓ 非生鲜无此级 |

**品类实体定义**：

```typescript
interface Category {
  id: string;
  name: string;
  level: "department" | "category_group" | "category" | "sub_category" | "variety";
  parent_id: string | null;  // 上级品类ID，顶级为null
  department: Department;    // 归属部门
  is_leaf: boolean;         // 是否最末级
}
```

**Link Types（品类关系）**:

| Link Type | 源 → 目标 | 说明 |
|-----------|----------|------|
| parent_of | Category → Category | 品类层级关系 |
| belongs_to | Category → Department | 品类归属部门 |
| has_category | Store → Category | 门店经营某品类（可选，用于限制门店经营品类范围）|

---

## 3. 权限管理设计

### 3.1 权限模型概述

采用 **RBAC × ABAC 融合模型**，三维正交：

```
最终权限 = 职能域（Domain） × 组织范围（OrgScope） × 品类范围（CategoryScope）
```

- **职能域（Domain）**：决定「能用哪些功能」（Feature List）
- **组织范围（OrgScope）**：决定「能在哪个组织范围内操作」
- **品类范围（CategoryScope）**：决定「能操作哪些品类」

### 3.1.1 六种权限模式（PermissionMode）

权限模式定义**默认行为策略**，影响规则匹配失败时的处理方式。

```typescript
enum PermissionMode {
  // 默认放行（仅记录审计日志），用于公共查询类工具
  ALLOW_ALL = "allow_all",

  // 默认拒绝（显式规则才放行），用于写操作/敏感操作
  DENY_ALL = "deny_all",

  // 标准 RBAC：按角色+Domain 查规则库
  RBAC = "rbac",

  // 工具级白名单：按工具名本身放行（不查组织/品类）
  TOOL_LEVEL = "tool_level",

  // 组织级过滤：先 OrgScope 过滤，再按角色规则匹配
  ORG_LEVEL = "org_level",

  // 不拦截，仅记录审计（用于调试/灰度观察）
  AUDIT_ONLY = "audit_only",
}

// 全局权限模式配置（启动时快照，运行时不可变）
interface GlobalPermissionConfig {
  mode: PermissionMode;

  // 各工具的覆盖模式（优先级高于全局）
  tool_overrides: Record<string, PermissionMode>;

  // 快照版本（防 TOCTOU）
  snapshot_version: string;
  snapshot_timestamp: string;
}

// 默认配置
const DEFAULT_PERMISSION_CONFIG: GlobalPermissionConfig = {
  mode: PermissionMode.DENY_ALL,
  tool_overrides: {
    // 公共查询工具：只读，不写数据
    "ontology.store.query": PermissionMode.ALLOW_ALL,
    "ontology.category.tree": PermissionMode.ALLOW_ALL,
    "builtin.date": PermissionMode.ALLOW_ALL,

    // 写操作工具：必须显式授权
    "ontology.store.create": PermissionMode.DENY_ALL,
    "ontology.store.update": PermissionMode.DENY_ALL,
    "price.adjust": PermissionMode.DENY_ALL,
    "loss_report.create": PermissionMode.DENY_ALL,

    // 调试/灰度：只记录不拦截
    "permission.evaluate": PermissionMode.AUDIT_ONLY,
  },
  snapshot_version: "1.0.0",
  snapshot_timestamp: "",  // 启动时写入
};
```

### 3.1.2 六层权限瀑布（Cascade）

对 Agent 的每一次操作，从外到内分 **6 层验证**，每层失败则拒绝：

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 1：Domain 检查（最外层）                                    │
│  用户是否属于正确的职能域（HQ_SUPPORT / SUPPLY_CHAIN / RETAIL_OPS）│
│  失败 → 403 Forbidden                                            │
├────────────────────────────────────────────────────────────────┤
│  Layer 2：Role 检查                                              │
│  用户角色是否匹配当前操作的允许角色列表                             │
│  失败 → 403 Forbidden                                            │
├────────────────────────────────────────────────────────────────┤
│  Layer 3：OrgScope 检查（逻辑引用解析）                            │
│  用户组织范围是否覆盖操作发生的门店/DC                             │
│  （scope_type 动态解析为具体门店列表，门店划拨时自动适应）          │
│  失败 → 403 Forbidden                                            │
├────────────────────────────────────────────────────────────────┤
│  Layer 4：CategoryScope 检查                                     │
│  用户品类范围是否覆盖目标 SKU 的品类路径                           │
│  （按 5 级品类树向上回溯匹配，coverage_depth 控制深度）            │
│  失败 → 403 Forbidden                                            │
├────────────────────────────────────────────────────────────────┤
│  Layer 5：Action 检查                                            │
│  操作类型（price.adjust / loss_report.create）是否在规则允许列表   │
│  失败 → 403 Forbidden                                            │
├────────────────────────────────────────────────────────────────┤
│  Layer 6：Params 检查（最内层）                                   │
│  操作参数是否满足约束条件：                                       │
│    - price_range：调价幅度是否在 ±X% 区间内                      │
│    - amount_limit：损耗金额是否超限                               │
│    - frequency_limit：操作频率是否超限                             │
│    - time_validity：操作时间是否在有效期内                        │
│  失败 → 422 Unprocessable Entity                                 │
└────────────────────────────────────────────────────────────────┘
           ↓
    全部通过 → 写入 AuditLogEntry（含快照）→ 执行操作
```

**六层验证代码流程**：

```python
async def evaluate_permission_cascade(context: PermissionContext, request: PermissionRequest) -> PermissionResult:
    # Layer 1：Domain
    if not check_domain(context):
        return PermissionResult(granted=False, rejected_at="domain")

    # Layer 2：Role（按角色查规则库）
    rules = await get_rules_for_role(context.role, context.domain)
    if not rules:
        return PermissionResult(granted=False, rejected_at="role")

    # Layer 3：OrgScope（逻辑引用动态解析）
    for rule in rules:
        if not check_org_scope(rule, context, request.store_id):
            continue
        # Layer 4：CategoryScope（向上回溯匹配）
        if not check_category_scope(rule, context, request.category_path):
            continue
        # Layer 5：Action
        if not check_action(rule, request.action):
            continue
        # Layer 6：Params（最内层约束）
        params_check = check_params_constraints(rule, request.params)
        if not params_check.passed:
            return PermissionResult(granted=False, rejected_at="params", constraint_detail=params_check)

        # 全部通过
        return PermissionResult(granted=True, rule_id=rule.rule_id)

    return PermissionResult(granted=False, rejected_at="org_scope")
```

### 3.1.3 快照冻结 + DeepImmutable 权限状态

**设计原则**：权限配置在 **Agent 启动时**一次性快照加载，**运行过程中不可修改**。使用 `DeepImmutable` + `Object.freeze` + **原子 swap**，彻底消除 TOCTOU 竞态。

```python
import copy, json, hmac
from types import MappingProxyType

class FrozenPermissionConfig:
    """
    启动时快照，运行期只读。
    - DeepImmutable：Object.freeze 冻结所有层级
    - HMAC 指纹：每次求值验证防篡改
    - 原子 swap：updatePermissions() 原子替换，不原地修改
    """
    def __init__(self, config_path: str):
        with open(config_path) as f:
            raw = yaml.safe_load(f)

        # 深度冻结（递归 freeze 嵌套对象）
        self._config = deep_freeze(raw)
        self._timestamp = datetime.utcnow().isoformat() + "Z"
        self._checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        return hmac_sha256(
            json.dumps(self._config, sort_keys=True, default=str),
            SNAPSHOT_SECRET
        )

    def verify(self) -> bool:
        """每次权限求值前验证快照完整性"""
        return self._compute_checksum() == self._checksum

    def get_rules(self, role: Role) -> FrozenList[PermissionRule]:
        """返回只读列表，运行时无法修改"""
        assert self.verify(), "Permission config tampered"
        rules = self._config["rules"]
        return [r for r in rules if r["subject"]["role"] == role]


def deep_freeze(obj):
    """递归冻结：使嵌套对象不可变"""
    if isinstance(obj, dict):
        return MappingProxyType({k: deep_freeze(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        return tuple(deep_freeze(item) for item in obj)
    return obj


class PermissionContext:
    """
    权限上下文 = DeepImmutable（启动时快照，永不修改）
    所有变更通过原子 swap 生成新上下文
    """
    mode: PermissionMode
    rules: FrozenList[PermissionRule]
    trustLevel: TrustLevel
    sessionOverrides: FrozenMapping[str, RuleTier]

    def apply_update(self, update: PermissionUpdate) -> "PermissionContext":
        """
        原子替换：返回新 PermissionContext 实例，运行时不可原地修改。
        老请求持有老的上下文引用（快照不变）。
        """
        next_rules = apply_rule_update(list(self.rules), update)
        next_overrides = dict(self.sessionOverrides)
        next_overrides.update(update.session_overrides)
        return PermissionContext(
            mode=self.mode,
            rules=deep_freeze(next_rules),
            trustLevel=self.trustLevel,
            sessionOverrides=deep_freeze(next_overrides),
        )
```

### 3.1.4 规则来源追踪（Source Tracking）

每条规则记录来源（user / project / session / system），支持审计和冲突仲裁。

```typescript
// 规则来源枚举
type RuleSource = "user" | "project" | "session" | "system";

// 固定优先级：system > project > session > user
const RULE_SOURCE_PRIORITY: Record<RuleSource, number> = {
  "system": 4,    // 最高：企业级策略，不可被用户覆盖
  "project": 3,   // 项目级： OrgGroup/Region 配置
  "session": 2,   // 会话级：当前会话临时规则
  "user": 1,      // 用户级：个人配置
};

interface TrackedPermissionRule extends PermissionRule {
  source: RuleSource;
  created_at: string;
  created_by: string;
  source_id: string;         // 来源标识（user_id / project_id / org_unit_id）
}

function evaluateRulesWithSource(
    rules: TrackedPermissionRule[],
    tool: ToolCall,
): PermissionResult {
  // 过滤匹配规则的来源和内容
  const matched = rules.filter(r =>
    r.tool === tool.name && matchesContent(r.pattern, tool.input)
  );

  // 优先级仲裁：system > project > session > user
  matched.sort((a, b) =>
    RULE_SOURCE_PRIORITY[b.source] - RULE_SOURCE_PRIORITY[a.source]
  );

  // deny 优先于 allow，allow 优先于 ask
  if (matched.some(r => r.tier === "deny"))  return { granted: false, reason: "denied_by_source", tier: "deny" };
  if (matched.some(r => r.tier === "allow")) return { granted: true, reason: "allowed_by_source", tier: "allow" };
  if (matched.some(r => r.tier === "ask"))   return { granted: false, reason: "requires_approval", tier: "ask" };

  return { granted: false, reason: "no_matching_rule" };
}
```

> **Enterprise policy layer**：`system` 来源的规则优先级最高，用户无法通过 `user` 级配置覆盖企业安全策略。

### 3.1.5 工具接口即扩展点（Tool Interface = Extension Point）
### 3.1.4 工具接口即扩展点（Tool Interface = Extension Point）

工具是 Agent 的**唯一外部交互入口**，也是唯一的**扩展机制**。不修改 Agent 核心代码，只需注册新工具即可扩展能力。

```typescript
// 工具扩展点接口（任何符合此接口的类自动成为可用工具）
interface ToolExtension {
  readonly name: string;           // 唯一标识，LLM 通过此名称调用
  readonly description: string;     // 业务描述，LLM 通过此理解何时调用
  readonly category: ToolCategory; // 工具分类：ontology | business | system | builtin

  // 权限需求（注册时声明，运行时不可绕过）
  readonly requiredPermissions: {
    resourceType: ResourceType;
    actions: string[];
  };

  // 执行约束
  readonly constraints: {
    timeoutMs: number;
    maxRetries: number;
    cacheable: boolean;
  };

  execute(input: Record<string, any>, context: FrozenPermissionContext): Promise<ToolResult>;
}

// 注册中心（启动时扫描，自动发现所有工具）
class ToolRegistry {
  private tools = new Map<string, ToolExtension>();

  register(tool: ToolExtension): void {
    // 注册时自动校验接口完整性
    validateToolInterface(tool);
    // 按名称索引（LLM 通过 name 调用）
    this.tools.set(tool.name, tool);
  }

  async execute(
    name: string,
    args: Record<string, any>,
    context: FrozenPermissionContext
  ): Promise<ToolResult> {
    const tool = this.tools.get(name);
    if (!tool) throw new ToolNotFoundError(name);

    // 权限检查（工具接口统一入口，无法绕过）
    await permissionGate.check(tool, context);

    // 执行
    return tool.execute(args, context);
  }
}
```

**扩展方式**：

```
新增业务工具（无需改 Agent 核心代码）：
  1. 实现 ToolExtension 接口
  2. 注册到 ToolRegistry（装饰器自动完成）
  3. LLM 自动发现并可调用该工具
```

### 3.2 角色（Role）

角色定义职责，不携带 OrgScope。角色通过 PermissionGrant 与 OrgScope/CategoryScope 解耦。

```typescript
enum Role {
  SYSTEM_ADMIN     = "system_admin",      // 系统管理员（Brand级）
  HQ_CATEGORY_DIR  = "hq_category_dir",   // 总部品类总监（Brand级品类）
  HQ_PROCUREMENT  = "hq_procurement",     // 总部采购经理
  REGION_MANAGER  = "region_manager",     // 区域总经理
  REGION_CAT_MGR  = "region_cat_mgr",    // 区域品类经理
  DC_MANAGER      = "dc_manager",         // DC经理
  DC_OPERATOR     = "dc_operator",        // DC仓管
  STORE_MANAGER   = "store_manager",      // 门店店长
  STORE_CLERK     = "store_clerk",       // 门店店员
  HQ_DC_MGR       = "hq_dc_mgr"          // 总部DC管理（央仓）
}
```

### 3.3 PermissionRule（权限规则）— 核心数据结构

**设计原则**：权限规则不硬编码组织路径，而是通过**逻辑引用**（scope_type + 参数）实现组织调整自动适应。

```typescript
interface PermissionRule {
  rule_id: string;              // 规则唯一标识
  name: string;                 // 规则名称（业务可读）
  description: string;          // 规则描述

  // Subject：谁
  subject: {
    role: Role;                 // 角色
    domain: Domain;             // 职能域
  };

  // Object：对什么（品类+资源类型）
  object: {
    category_scope: CategoryScope;
    resource_type: ResourceType;
  };

  // Constraints：约束条件
  constraints: PermissionConstraints;

  // Audit：审计配置
  audit: AuditConfig;
}

type ResourceType =
  | "price"           // 定价
  | "promotion"       // 促销
  | "loss_report"     // 损耗报损/报溢
  | "stock_transfer"  // 库存调拨
  | "supplier"        // 供应商管理
  | "procurement"     // 采购
  | "dc_inventory"    // DC库存
  | "store_inventory"; // 门店库存

interface CategoryScope {
  // 品类范围：可指定到任意级别
  department?: Department | "*";
  category_group?: string | "*";
  category?: string | "*";
  sub_category?: string | "*";
  variety?: string | "*";

  // 向下覆盖层级深度（0=仅当前级，99=所有下级）
  coverage_depth: number;  // 0-99
}

interface OrgScope {
  // OrgScope 逻辑引用类型
  scope_type: OrgScopeType;

  // 各 scope_type 对应的参数
  region_id?: string | "*";      // 区域ID
  channel_type?: ChannelType | "*"; // 业态类型
  store_ids?: string[];          // 精确门店列表（specific_stores时用）
  dc_id?: string;                // DC ID（dc_scope时用）
  dc_type?: DCType;              // DC类型（dc_type_scope时用）
}

type OrgScopeType =
  | "region_all_channels"    // 某区域内所有业态的所有门店
  | "channel_in_region"       // 某区域内指定业态的所有门店
  | "all_channels_of_type"    // 全国所有指定业态门店
  | "specific_stores"         // 精确指定的门店列表
  | "specific_dcs"            // 精确指定的DC列表
  | "dc_type_scope"           // 全国所有指定类型DC（央仓管理员用）
  | "org_group_scope"         // 某OrgGroup内所有组织单元
  | "brand_scope";            // 全国范围（仅系统管理员）
```

### 3.4 典型权限规则示例

#### PR-001：总部品类总监（全品类全渠道）

```json
{
  "rule_id": "PR-001",
  "name": "总部品类总监权限",
  "description": "总部品类总监可管理所有品类、所有渠道、所有区域",
  "subject": {
    "role": "hq_category_dir",
    "domain": "supply_chain"
  },
  "object": {
    "category_scope": {
      "department": "*",
      "coverage_depth": 99
    },
    "resource_type": "price"
  },
  "constraints": {
    "price_range": {
      "type": "percentage",
      "min_pct": -30,
      "max_pct": 30,
      "reference": "总部标准进价"
    }
  },
  "audit": {
    "requires_approval": false,
    "notify_roles": []
  }
}
```

#### PR-002：区域品类经理（杂货，指定业态）

```json
{
  "rule_id": "PR-002",
  "name": "区域品类经理-杂货调价权限",
  "description": "区域品类经理可对杂货品类在总部设定区间内调整售价，仅限指定业态",
  "subject": {
    "role": "region_cat_mgr",
    "domain": "supply_chain"
  },
  "object": {
    "category_scope": {
      "department": "food",
      "coverage_depth": 99
    },
    "resource_type": "price"
  },
  "constraints": {
    "price_range": {
      "type": "percentage",
      "min_pct": -15,
      "max_pct": 0,
      "reference": "总部建议价"
    },
    "sku_filter": {
      "type": "price_sensitive",
      "source": "总部采购标注"
    },
    "validity": {
      "start": "2026-01-01T00:00:00Z",
      "end": "2026-12-31T23:59:59Z",
      "duration_max_days": 30
    }
  },
  "audit": {
    "requires_approval": false,
    "notify_roles": ["hq_category_dir"]
  }
}
```

#### PR-003：门店店长（生鲜调价权限）

```json
{
  "rule_id": "PR-003",
  "name": "门店店长-生鲜调价权限",
  "description": "门店店长可在总部标准售价±10%区间内调整生鲜商品售价，有效期8小时",
  "subject": {
    "role": "store_manager",
    "domain": "retail_ops"
  },
  "object": {
    "category_scope": {
      "department": "fresh",
      "coverage_depth": 99
    },
    "resource_type": "price"
  },
  "constraints": {
    "price_range": {
      "type": "percentage",
      "min_pct": -10,
      "max_pct": 10,
      "reference": "总部标准售价"
    },
    "validity": {
      "type": "duration",
      "duration_max_hours": 8
    }
  },
  "audit": {
    "requires_approval": false,
    "notify_roles": ["region_cat_mgr"]
  }
}
```

#### PR-004：区域品类经理（促销权限）

```json
{
  "rule_id": "PR-004",
  "name": "区域品类经理-促销审批权限",
  "description": "区域品类经理可创建并执行本区域促销活动",
  "subject": {
    "role": "region_cat_mgr",
    "domain": "supply_chain"
  },
  "object": {
    "category_scope": {
      "department": "*",
      "coverage_depth": 99
    },
    "resource_type": "promotion"
  },
  "constraints": {
    "org_scope": {
      "scope_type": "region_all_channels",
      "region_id": "${current_user.region_id}"
    },
    "promotion_type": ["discount", "bundle"],
    "max_discount_pct": 30,
    "requires_stocks_check": true
  },
  "audit": {
    "requires_approval": true,
    "approval_role": "hq_category_dir",
    "approval_threshold_amount": 50000
  }
}
```

#### PR-005：DC仓管（损耗上报权限）

```json
{
  "rule_id": "PR-005",
  "name": "DC仓管-损耗报损权限",
  "description": "DC仓管可上报本DC的损耗，支持金额和次数限制",
  "subject": {
    "role": "dc_operator",
    "domain": "supply_chain"
  },
  "object": {
    "category_scope": {
      "department": "*",
      "coverage_depth": 99
    },
    "resource_type": "loss_report"
  },
  "constraints": {
    "org_scope": {
      "scope_type": "specific_dcs",
      "dc_id": "${current_user.dc_id}"
    },
    "amount_limit": {
      "type": "per_incident",
      "max_amount": 5000,
      "currency": "CNY"
    },
    "frequency_limit": {
      "type": "per_month",
      "max_count": 20
    },
    "requires_photo": true,
    "requires_reason": true
  },
  "audit": {
    "requires_approval": true,
    "approval_role": "dc_manager",
    "approval_threshold": 1000
  }
}
```

#### PR-006：总部DC经理（央仓管理权限）

```json
{
  "rule_id": "PR-006",
  "name": "总部DC经理-央仓管理权限",
  "description": "总部DC经理可管理全国所有央仓",
  "subject": {
    "role": "hq_dc_mgr",
    "domain": "supply_chain"
  },
  "object": {
    "category_scope": {
      "department": "*",
      "coverage_depth": 99
    },
    "resource_type": "dc_inventory"
  },
  "constraints": {
    "org_scope": {
      "scope_type": "dc_type_scope",
      "dc_type": "central"
    }
  },
  "audit": {
    "requires_approval": false,
    "notify_roles": []
  }
}
```

### 3.5 组织调整的自动适应机制

权限规则中的 `org_scope` 通过**逻辑引用**声明，运行时由 Permission Evaluator 动态解析为具体门店/DC列表。

**示例：门店划拨**

```
调整前：华南区直营 → Store S101, S102
调整后：Store S102 划入西南区直营

规则 PR-002 的 org_scope：
  scope_type = "channel_in_region"
  region_id = "华南区"         ← 逻辑引用，不含具体门店ID
  channel_type = "hyper"

运行时解析结果：
  调整前 → 有效门店：[S101, S102]  （规则不变，自动生效）
  调整后 → 有效门店：[S101]         （S102 自动脱离）
```

**示例：新增 Region**

```
新增「华西区」后：
  规则 PR-001（总部品类总监）：scope_type = "brand_scope" → 自动覆盖全国，无需任何修改
  规则 PR-002（区域品类经理）：scope_type = "region_all_channels" → 每个区域一条规则，区域新增时新增规则即可
```

### 3.6 权限求值引擎（Permission Evaluator）

```typescript
interface PermissionContext {
  user_id: string;
  role: Role;
  domain: Domain;
  region_id?: string;      // 当前所在区域
  store_ids?: string[];    // 归属门店列表
  dc_id?: string;          // 归属DC
}

interface PermissionRequest {
  action: ResourceType;      // 操作类型
  resource_id: string;      // 目标资源ID（如 SKU ID）
  store_id?: string;        // 操作发生的门店
  dc_id?: string;           // 操作发生的DC
  category_path: string[];  // 品类路径 [department, category_group, category, sub_category, variety]
  params: Record<string, any>; // 操作参数（如调价幅度）
}

interface PermissionResult {
  granted: boolean;
  rule_id?: string;
  constraints_checked: ConstraintsCheckResult;
  resolved_org_scope?: {
    stores: string[];
    dcs: string[];
  };
  reason?: string;          // 拒绝原因
}
```

**求值流程**：

```
1. 收集用户上下文（user_id, role, domain, region_id, store_ids, dc_id）
2. 查询用户角色对应的所有 PermissionRule（按 role + domain 过滤）
3. 对每条规则：
   a. 检查 category_scope 是否覆盖目标品类
   b. 检查 org_scope 是否覆盖操作发生的门店/DC
   c. 检查 constraints（价格区间、金额限制、频率限制、时间限制）
   d. 如全部通过，返回 granted=true
4. 如无规则通过，返回 granted=false
5. 写入 AuditLogEntry（含快照）
```

---

## 4. 日志与审计设计

### 4.1 AuditLogEntry（审计日志条目）

审计日志必须记录**权限求值时的快照**（而非引用），确保组织调整后历史可追溯。

```typescript
interface AuditLogEntry {
  // 唯一标识
  audit_id: string;              // AUD-{date}-{seq}

  // 时间
  timestamp: string;             // ISO8601，含时区

  // 操作者（Who）
  actor: {
    user_id: string;
    username: string;
    role: Role;
    domain: Domain;
    org_path: string;            // 如：集团/华南区/直营/S101
  };

  // 操作（What）
  action: {
    type: ResourceType;         // 操作类型
    resource_id: string;         // 目标资源ID
    resource_name?: string;      // 资源名称（冗余存储，防未来引用失效）
    params: Record<string, any>; // 操作参数
  };

  // 匹配规则
  rule_matched: {
    rule_id: string;
    rule_name: string;
  } | null;                       // null 表示无规则匹配（拒绝操作）

  // 约束检查详情
  constraints_checked: {
    category_match: boolean;
    org_match: boolean;
    price_range?: {
      reference_price: number;
      actual_price: number;
      min_pct: number;
      max_pct: number;
      actual_pct: number;
      passed: boolean;
    };
    amount_limit?: {
      max_amount: number;
      actual_amount: number;
      currency: string;
      passed: boolean;
    };
    frequency_limit?: {
      max_count: number;
      current_count: number;
      period: string;
      passed: boolean;
    };
    time_validity?: {
      valid_from: string;
      valid_to: string;
      action_time: string;
      passed: boolean;
    };
  };

  // 组织快照（TOCTOU防护）
  org_snapshot: {
    region_id: string;
    region_name: string;
    channel_type: ChannelType;
    stores_in_scope: string[];   // 权限规则覆盖的所有门店
    store_in_action: string;      // 操作实际发生的门店
    dc_in_action?: string;        // 操作实际发生的DC
    dcs_in_scope?: string[];      // 权限规则覆盖的所有DC
    company_code?: string;
    profit_center?: string;
  };

  // 品类快照
  category_snapshot: {
    department: string;
    category_group: string;
    category: string;
    sub_category: string;
    variety?: string;            // 仅生鲜品类有值
    is_leaf: boolean;
  };

  // 结果
  result: {
    outcome: "SUCCESS" | "REJECTED" | "PENDING_APPROVAL";
    approved_by?: string;
    approval_comment?: string;
    rejected_reason?: string;
  };

  // 追踪
  trace_id?: string;             // OpenTelemetry trace ID
  span_id?: string;
}
```

### 4.2 审计日志存储

**存储策略**：

| 场景 | 存储格式 | 保留周期 |
|------|---------|---------|
| 操作审计（Action Audit） | JSON Lines（结构化）| 1年 |
| 价格变更历史 | JSON Lines + 专用索引 | 3年（财务合规）|
| 损耗审批记录 | JSON Lines + 财务归档 | 5年（财务合规）|
| 系统配置变更 | JSON Lines | 永久 |

**文件结构**：

```
data/audit/
  {year}/
    {month}/
      action-{date}.jsonl     # 操作审计（每日一个文件）
      price-{date}.jsonl      # 价格变更（每日一个文件）
      loss-{date}.jsonl       # 损耗记录（每日一个文件）
```

### 4.3 审计查询 API

```typescript
// 查询审计日志
interface AuditQuery {
  start_date?: string;
  end_date?: string;
  user_id?: string;
  role?: Role;
  action_type?: ResourceType;
  resource_id?: string;
  rule_id?: string;
  outcome?: "SUCCESS" | "REJECTED";
  region_id?: string;
  department?: Department;
  limit?: number;
  offset?: number;
}
```

---

## 5. 可观测性设计

### 5.1 指标体系（品类 × 组织 双维度）

#### 5.1.1 品类运营指标（按5级品类维度聚合）

```typescript
interface CategoryMetrics {
  // 维度标识
  dimensions: {
    department: Department;
    category_group?: string;
    category?: string;
    sub_category?: string;
    variety?: string;
  };

  // 销售指标
  sales: {
    revenue: number;            // 销售额
    revenue_yesterday: number;   // 昨日销售额
    revenue_won?: number;       // 环比（可选）
    units_sold: number;          // 销售数量
    avg_price: number;           // 客单价
    transactions: number;        // 交易笔数
  };

  // 利润指标
  profit: {
    gross_margin: number;       // 毛利额
    gross_margin_rate: number;  // 毛利率
    margin_rate_yesterday: number;
  };

  // 库存指标
  inventory: {
    stock_value: number;        // 库存金额
    stock_units: number;        // 库存数量
    turnover_days: number;      // 周转天数
    stockout_rate: number;      // 缺货率
  };

  // 损耗指标
  loss: {
    loss_amount: number;        // 损耗金额
    loss_rate: number;          // 损耗率 = 损耗金额 / 销售额
    loss_reports_count: number; // 损耗上报次数
  };

  // 价格指标
  pricing: {
    price_compliance_rate: number;  // 价格执行率 = 实际售价 / 总部指导价
    avg_discount_rate: number;      // 平均折扣率
    price_adjustments_count: number;// 调价次数
  };
}
```

#### 5.1.2 组织运营指标（按组织维度聚合）

```typescript
interface OrgMetrics {
  // 维度标识
  dimensions: {
    org_group_id?: string;
    channel_type?: ChannelType;
    region_id?: string;
    store_id?: string;
    dc_id?: string;
  };

  // 整体运营
  operations: {
    total_stores: number;            // 门店总数
    active_stores: number;           // 活跃门店数
    total_skus: number;              // 在架SKU数
    new_skus_this_month: number;     // 本月新增SKU
  };

  // 销售汇总
  sales: {
    total_revenue: number;
    revenue_by_dept: Record<Department, number>;
    sales_target: number;
    achievement_rate: number;        // 目标完成率
  };

  // 供应链指标
  supply_chain: {
    dc_inventory_value: number;
    fresh_stockout_rate: number;     // 生鲜缺货率
    grocery_stockout_rate: number;   // 杂货缺货率
    delivery_compliance_rate: number; // 配送履约率
    central_replenishment_lead_time: number; // 央仓补货周期（天）
  };

  // 品类结构
  category_mix: {
    fresh_ratio: number;             // 生鲜销售占比
    food_ratio: number;
    daily_ratio: number;
    non_food_ratio: number;
  };

  // 价格管控
  pricing_control: {
    avg_price_deviation: number;     // 价格平均偏离度
    unauthorized_discounts: number;   // 超权限折扣次数
    promotion_effectiveness: number;  // 促销投入产出比
  };
}
```

#### 5.1.3 跨维度交叉指标（品类 × 组织）

```typescript
// 例：华南区 × 生鲜品类 的综合指标
interface CrossMetrics {
  region_id: string;
  department: Department;
  metrics: CategoryMetrics & OrgMetrics;  // 合并
}

// 用于热力图分析
// 行：Region（华南/华东/华北/华西）
// 列：Department（生鲜/食品/日配/非食品）
// 值：毛利额 / 损耗率 / 周转天数
```

### 5.2 Trace 链路设计

全链路追踪，从用户操作到数据库持久化全程可追溯。

```typescript
interface TraceSpan {
  span_id: string;
  parent_span_id?: string;
  trace_id: string;
  operation_name: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  attributes: {
    user_id?: string;
    role?: string;
    domain?: string;
    action?: string;
    resource_id?: string;
    rule_matched?: string;
    permission_granted?: boolean;
    org_scope_resolved?: string[];
    category_scope_resolved?: string[];
    llm_model?: string;
    llm_latency_ms?: number;
    tool_calls?: string[];
    error?: string;
  };
}
```

**Trace 链路示例**：

```
[Trace: T-2026-05-25-001]
├── span_001: user_request          (user_id=U-10086, action=price.adjust)
├── span_002: permission_evaluate  (rule_id=PR-003, granted=true)
│   ├── span_002a: category_match   (fresh, passed=true)
│   ├── span_002b: org_match        (S101 in 华南区, passed=true)
│   └── span_002c: price_range_check(-8% in [-10%, +10%], passed=true)
├── span_003: audit_log_write       (audit_id=AUD-2026-05-25-001)
├── span_004: tool_execute         (tool=update_sku_price)
├── span_005: llm_response          (model=MiniMax-M2.7-highspeed, latency=320ms)
└── span_006: response_sent
```

### 5.3 健康检查与告警

```typescript
interface HealthCheck {
  service: string;
  status: "healthy" | "degraded" | "down";
  checks: {
    database: boolean;         // JSON文件可读写
    llm_api: boolean;           // MiniMax API 可连通
    permission_engine: boolean; // 权限引擎响应正常
    audit_log: boolean;        // 审计日志写入正常
  };
  timestamp: string;
}

// 告警规则
interface AlertRule {
  name: string;
  condition: string;            // 如：loss_rate > 0.05 && revenue < 10000
  severity: "warning" | "critical";
  channels: ("feishu" | "email")[];
  recipients: string[];
}
```

### 5.4 结构化日志格式

所有应用日志使用统一 JSON 格式，便于采集和分析。

```typescript
interface AppLog {
  level: "INFO" | "WARN" | "ERROR" | "DEBUG";
  timestamp: string;
  service: string;              // "permission-engine" | "audit-logger" | "ontology-api"
  trace_id?: string;
  span_id?: string;
  message: string;
  context: {
    user_id?: string;
    role?: string;
    action?: string;
    resource_id?: string;
    duration_ms?: number;
    error?: string;
    stack?: string;
  };
}
```

---

## 6. 本体论 Schema 更新

### 6.1 实体定义（JSON Schema）

#### OrgUnit（新/更新）

```typescript
// OrgUnit 合并 Brand/OrgGroup/Channel/Region/Store 五级
interface OrgUnit {
  id: string;
  name: string;
  level: "brand" | "org_group" | "channel" | "region" | "store";
  parent_id: string | null;

  // OrgGroup 层特有
  company_code?: string;
  profit_center_code?: string;
  cost_center_code?: string;

  // Channel 层特有
  channel_type?: ChannelType;

  // Store 层特有
  address?: string;
  manager_id?: string;
  dc_ids?: string[];             // 归属DC列表（可多选）

  // 通用
  created_at: string;
  updated_at: string;
}
```

#### DistributionCenter（新增）

```typescript
interface DistributionCenter {
  id: string;
  name: string;
  type: DCType;                  // fresh / grocery / central
  region_id?: string;            // 区域DC有归属区域，央仓无
  capacity: number;              // 容量（吨或立方米）
  manager_id?: string;
  contact_phone?: string;
  created_at: string;
  updated_at: string;
}
```

#### Category（新/更新）

```typescript
interface Category {
  id: string;
  name: string;
  level: "department" | "category_group" | "category" | "sub_category" | "variety";
  parent_id: string | null;
  department: Department | null; // 顶级部门有值
  is_leaf: boolean;
  created_at: string;
  updated_at: string;
}
```

#### PermissionRule（新增）

```typescript
// 参见 3.3 节定义
interface PermissionRule {
  rule_id: string;
  name: string;
  description: string;
  subject: { role: Role; domain: Domain; };
  object: { category_scope: CategoryScope; resource_type: ResourceType; };
  constraints: PermissionConstraints;
  audit: AuditConfig;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

#### AuditLogEntry（新增）

```typescript
// 参见 4.1 节定义
interface AuditLogEntry { /* ... */ }
```

### 6.2 数据文件结构

```
data/
  audit/
    {year}/
      {month}/
        action-{date}.jsonl
        price-{date}.jsonl
        loss-{date}.jsonl
  ontology/
    org_units.json        # 组织单元（Brand→OrgGroup→Channel→Region→Store）
    distribution_centers.json
    categories.json       # 品类树（5级）
    permission_rules.json # 权限规则库
  store/
    {store_id}/
      inventory.json
      tasks.json
      near_expiry.json
  metrics/
    {year}/
      {month}/
        category_metrics.jsonl
        org_metrics.jsonl
```

---

## 7. API 设计

### 7.1 权限相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/permission/evaluate | 权限求值（内部调用）|
| GET | /api/permission/rules | 查询权限规则列表 |
| GET | /api/permission/rules/{rule_id} | 查询单条规则 |
| POST | /api/permission/rules | 创建权限规则 |
| PUT | /api/permission/rules/{rule_id} | 更新权限规则 |
| GET | /api/permission/user/{user_id}/effective | 查询用户有效权限（展开后的）|

### 7.2 组织相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/org/tree | 获取完整组织树 |
| GET | /api/org/regions/{region_id}/stores | 查询区域下所有门店 |
| GET | /api/org/stores/{store_id}/dc | 查询门店归属DC |
| GET | /api/dc/{dc_id}/stores | 查询DC配送的所有门店 |
| GET | /api/dc?type={dc_type} | 按类型查询DC列表 |

### 7.3 品类相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/category/tree | 获取完整品类树 |
| GET | /api/category/{category_id}/path | 获取品类完整路径（向上）|
| GET | /api/category/{category_id}/children | 获取子类目 |
| GET | /api/category/leaf | 获取所有末级品类（用于SKU级别查询）|
| GET | /api/category/department/{dept}/hierarchy | 获取某部门完整品类层级 |

### 7.4 审计相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/audit/logs | 查询审计日志（支持多维度过滤）|
| GET | /api/audit/logs/{audit_id} | 查询单条审计记录 |
| GET | /api/audit/summary | 审计汇总统计 |

### 7.5 可观测性 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/metrics/category | 品类指标（支持多级品类维度聚合）|
| GET | /api/metrics/org | 组织指标（支持Region/Channel/Store维度）|
| GET | /api/metrics/cross | 交叉指标（品类×组织热力图）|
| GET | /api/health | 健康检查 |
| GET | /api/traces/{trace_id} | 查询Trace详情 |

---

## 8. Agentic Loop

> 管理 Agent 的核心循环：流式响应处理、用户取消、背压控制、容错恢复。核心原则：**AsyncGenerator 是唯一的组合原语**（禁止混用 callback/promise/event-emitter）。

### 8.1 循环流程（AsyncGenerator 实现）

```python
async def* agent_loop(state: AgentState) -> AsyncGenerator[StreamEvent]:
    """
    核心原则：
    - 单一组合原语：async function* yield 事件
    - 取消 = .return()，背压 = loop 在 yield 处阻塞
    - 状态每次迭代替换（非修改），任何中间状态可序列化调试
    """
    while True:
        # 1. 组装上下文（含 context pipeline）
        state = await prepare_context(state)  # 包含 5-stage context pipeline

        # 2. LLM 流式推理
        stream = await llm.stream_message(state.messages)
        response = accumulate_response(stream, lambda delta: agent_loop.emit(
            {"type": "text_delta", "delta": delta}
        ))

        state = append_message(state, response)

        # 3. 无工具调用 → 结束
        if not response.tool_calls:
            await agent_loop.emit({"type": "done", "state": state})
            return

        # 4. 流式工具执行（工具结果增量发送给 LLM）
        tool_results = await execute_tools_streaming(
            response.tool_calls,
            state.frozen_context,
            on_delta=lambda tr: agent_loop.emit({"type": "tool_result", "result": tr})
        )
        state = append_tool_results(state, tool_results)

        # 5. 持久化（先写盘，再继续）← Crash-resilient
        await persist_session(state)  # 写盘后再进入下一轮

        # 6. 继续检查
        decision = check_continuation(state)
        if decision == "stop":
            await agent_loop.emit({"type": "stopped", "state": state})
            return

        await agent_loop.emit({"type": "turn_complete", "state": state})
```

### 8.2 Per-Conversation Engine

每个会话创建独立 Engine 实例，隔离消息历史、文件缓存、累计用量，支持序列化/恢复。

```python
class QueryEngine:
    conversation_id: str
    messages: list[Message] = []
    file_cache: dict[str, FileState] = {}
    usage: Usage = {"input_tokens": 0, "output_tokens": 0}
    frozen_context: FrozenPermissionContext  # 快照冻结的权限上下文

    async def submit_message(self, user_msg: str) -> AsyncGenerator[StreamEvent]:
        """
        每个 submitMessage() 是独立的 generator 生命周期。
        engine 是会话生命周期单元：创建 → 运行 → 持久化 → 恢复 → 销毁。
        """
        self.messages.append(Message(role="human", content=user_msg))

        # 写盘先于 LLM 调用（Crash-resilient）
        await persist_session(self)

        async for event in agent_loop(AgentState(
            messages=self.messages,
            file_cache=self.file_cache,
            frozen_context=self.frozen_context,
            config=self.config,
        )):
            if event.type in ("turn_complete", "done"):
                self.messages = event.state.messages
                self.usage.input_tokens += event.state.turn_usage.input
                self.usage.output_tokens += event.state.turn_usage.output
            yield event

    def serialize(self) -> PersistedSession:
        """序列化当前状态，用于 crash recovery"""
        return {
            "conversation_id": self.conversation_id,
            "messages": self.messages,
            "file_cache": self.file_cache,
            "usage": self.usage,
            "frozen_context": self.frozen_context,
        }

    @staticmethod
    def resume(data: PersistedSession) -> "QueryEngine":
        """从持久化状态重建 engine"""
        engine = QueryEngine()
        engine.conversation_id = data["conversation_id"]
        engine.messages = data["messages"]
        engine.file_cache = data["file_cache"]
        engine.usage = data["usage"]
        engine.frozen_context = data["frozen_context"]
        return engine
```

### 8.3 Crash-Resilient Persistence

**核心原则**：状态在可能崩溃点之前必须落盘。

```
崩溃边界：LLM API 调用（网络请求）
↓ 在调用前
用户消息 + 当前 tool_calls → 写入 session file
↓ 调用成功
继续执行，状态保留在内存
↓ 调用失败（网络/超时）
Session file 包含完整上下文 → resume 时从断点继续
```

```python
async def prepare_context(state: AgentState) -> AgentState:
    # 1. 读盘恢复（如有）
    persisted = await read_session_file(state.conversation_id)
    if persisted:
        state = PersistedSession.resume(persisted)
    else:
        # 2. Context Pipeline（5-stage）
        state = await run_context_pipeline(state)
    return state

async def persist_session(state: AgentState) -> None:
    """每个 turn 结束后持久化，可序列化调试"""
    path = f"data/sessions/{state.conversation_id}.json"
    await atomic_write(path, json.dumps(state.serialize()))
    # 原子写：先写 .tmp，再 rename，防止写坏覆盖


**流式工具执行**（P0）：工具结果在执行过程中**增量发送给 LLM**，不等待全部完成。

```python
async def execute_tools_streaming(
    tool_calls: list[ToolCall],
    frozen_context: FrozenPermissionContext,
    on_delta: Callable[[ToolResult], None],  # 增量回调
) -> list[ToolResult]:
    """
    工具结果流式返回，而非等全部执行完。
    LLM 可在工具执行期间继续接收 text_delta。
    """
    # 1. 并发/串行分区（读并行，写串行）
    batches = partition_tool_calls(tool_calls)
    all_results = []

    for batch in batches:
        if batch.mode == "parallel":
            # 读工具：并发执行
            results = await asyncio.gather(*[
                tool_registry.execute(tc, frozen_context) for tc in batch.calls
            ])
        else:
            # 写工具：串行执行（防止数据竞争）
            results = [await tool_registry.execute(tc, frozen_context) for tc in batch.calls]

        for result in results:
            on_delta(result)  # 增量发送给 LLM/UI
            all_results.append(result)

    return all_results


def partition_tool_calls(calls: list[ToolCall]) -> list[Batch]:
    """
    读/写分区 + 队列上限：
    - isConcurrencySafe=true → 读工具 → 并行
    - isConcurrencySafe=false → 写工具 → 串行
    - MAX_TOOL_USE_CONCURRENCY=10 上限防止 OOM
    """
    MAX_CONCURRENCY = 10
    batches = []
    read_batch = []

    for call in calls:
        tool = tool_registry.get(call.name)
        if tool.is_concurrency_safe and len(read_batch) < MAX_CONCURRENCY:
            read_batch.append(call)
        else:
            if read_batch:
                batches.append(Batch(mode="parallel", calls=read_batch))
                read_batch = []
            batches.append(Batch(mode="serial", calls=[call]))

    if read_batch:
        batches.append(Batch(mode="parallel", calls=read_batch))

    return batches
```

**Token 实时追踪**（P0）：流式期间计算 token 用量，超预算时提前中断。

```python
class TokenBudgetTracker:
    """
    流式期间实时追踪，超预算时触发中断。
    避免请求结束后才发现超支。
    """
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.input_tokens = 0
        self.output_tokens = 0

    def on_input_tokens(self, count: int) -> None:
        self.input_tokens += count
        self._check()

    def on_output_tokens(self, count: int) -> None:
        self.output_tokens += count
        self._check()

    def _check(self) -> None:
        total = self.input_tokens + self.output_tokens
        if total > self.max_tokens:
            raise TokenBudgetExceeded(f"Budget exceeded: {total}/{self.max_tokens}")
```

**Compaction Circuit Breaker**（P1）：摘要连续失败 3 次后熔断，回退到硬截断。

```python
COMPACTION_MAX_RETRIES = 3

async def run_context_pipeline(state: AgentState) -> AgentState:
    """
    5-stage context pipeline：
    1. toolResultBudget     — 截断单个工具结果
    2. historySnip          — 超出滑动窗口的历史裁剪
    3. microcompact         — 旧工具结果替换为 [cleared]
    4. contextCollapse      — 合并相邻同角色消息
    5. autocompact          — fork 子 agent 摘要（最贵，最后执行）
    """
    pipeline = [
        tool_result_budget_stage,
        history_snip_stage,
        microcompact_stage,
        context_collapse_stage,
        autocompact_stage,  # 唯一可能失败的阶段
    ]

    messages = state.messages
    budget = state.context_budget

    for stage in pipeline:
        result = await stage.process(messages, budget)
        messages = result.messages
        budget = result.remaining_budget
        if result.signal == "sufficient":
            break

    return {**state, "messages": messages}


async def autocompact_stage(messages, budget) -> StageResult:
    """
    Autocompact via forked agent：
    - fork 子 agent 生成 9-section 结构化摘要
    - 若子 agent 触发 context overflow → 重试（丢弃最老 20% rounds）
    - 3 次 PTL 失败后熔断 → 硬截断
    """
    if estimate_tokens(messages) < budget.compact_threshold:
        return {"messages": messages, "signal": "continue"}

    attempt = 0
    while attempt < COMPACTION_MAX_RETRIES:
        try:
            summary = await fork_summarization_agent(messages)
            return {"messages": replace_with_summary(messages, summary), "signal": "done"}
        except PromptTooLong:
            attempt += 1
            messages = drop_oldest_rounds(messages, 0.2)  # 丢弃最老 20%
            if attempt >= COMPACTION_MAX_RETRIES:
                # 熔断：硬截断
                return {"messages": truncate_at_budget(messages, budget), "signal": "done"}
    return {"messages": messages, "signal": "done"}
```

### 8.4 流式处理（Streaming SSE）

**实现方案**：使用 SSE（Server-Sent Events）通过 FastAPI 的 `StreamingResponse`。

```typescript
// 流式响应接口
interface StreamEvent {
  type: "text_delta" | "tool_call_start" | "tool_call_end" | "tool_result" | "error" | "done";
  delta?: string;           // text_delta 时
  tool_call?: {
    name: string;
    arguments: Record<string, any>;
  };
  tool_result?: any;        // tool_call_end 时
  error?: string;           // error 时
}

// SSE endpoint
// GET /api/agent/stream
// 返回：text/event-stream
```

**CopilotKit 集成**：CopilotKit 前端通过 `renderToolCalls` 接收工具调用结果并渲染卡片，需要：
- 工具返回格式：`摘要\n<!--COPILOTKIT_DATA-->JSON<--/COPILOTKIT_DATA-->`
- 前端正则提取 JSON 渲染，LLM 只读摘要（避免双份输出）

### 8.3 取消机制（Cancel）

**客户端取消**：用户点击「取消」或关闭页面时，前端 AbortController 触发 `signal.aborted = true`。

```typescript
// 前端
const controller = new AbortController();
const response = await fetch('/api/agent/stream', {
  signal: controller.signal,
  ...
});
// 用户取消
controller.abort();
```

**服务端处理**：

```typescript
// 中间件检测 abort
async def abort_check():
    if request.signal.aborted:
        # 标记当前 tool_call 状态为 cancelled
        # 不写入 audit log（已取消的操作不计入审计）
        raise ClientDisconnect()

// 工具执行层
async def tool_execute(tool_name, args, signal):
    for step in tool.steps:
        if signal.aborted:
            return {"status": "cancelled", "completed_steps": step - 1}
        await step.execute()
    return {"status": "completed"}
```

### 8.4 背压策略（Backpressure）

**问题**：工具调用慢（门店查询、LLM 推理）或失败时，循环如何不阻塞？

**策略 1：并发限制**

```typescript
const SEMAPHORE_LIMIT = 5;  // 最多 5 个并发工具调用
const semaphore = new Semaphore(SEMAPHORE_LIMIT);

async function toolCall(tool, args) {
  const permit = await semaphore.acquire();
  try {
    return await tool.execute(args);
  } finally {
    permit.release();
  }
}
```

**策略 2：超时控制**

```typescript
const TOOL_TIMEOUT_MS = 30_000;  // 单工具调用超时 30s

async function toolCall(tool, args) {
  return Promise.race([
    tool.execute(args),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Tool timeout')), TOOL_TIMEOUT_MS)
    )
  ]);
}
```

**策略 3：降级熔断**

```typescript
interface CircuitBreaker {
  failures: number;
  last_failure: number;
  state: "closed" | "open" | "half_open";
  threshold: 5;           // 连续失败 5 次后熔断
  reset_ms: 60_000;       // 1 分钟后尝试半开
}

async function toolCallWithBreaker(tool, breaker) {
  if (breaker.state === "open") {
    if (Date.now() - breaker.last_failure > breaker.reset_ms) {
      breaker.state = "half_open";
    } else {
      return { status: "degraded", fallback: "cached_result" };
    }
  }
  try {
    const result = await tool.execute();
    if (breaker.state === "half_open") breaker.state = "closed";
    return result;
  } catch (e) {
    breaker.failures++;
    breaker.last_failure = Date.now();
    if (breaker.failures >= breaker.threshold) breaker.state = "open";
    throw e;
  }
}
```

### 8.5 错误恢复

```typescript
interface LoopErrorRecovery {
  max_retries: 3;
  retry_delay_ms: [1000, 2000, 4000];  // 指数退避

  strategy: {
    "LLM_TIMEOUT": "retry_with_longer_timeout",
    "TOOL_NOT_FOUND": "log_and_skip",
    "TOOL_EXECUTION_ERROR": "retry_with_same_args",
    "PERMISSION_DENIED": "fail_immediately_and_notify",
    "CONTEXT_OVERFLOW": "compress_and_retry"
  };
}
```

---

## 9. Tool System

> 外部工具（业务逻辑）与内置工具（LLM 原生能力）统一 pipeline，统一定义、发现、执行。

### 9.1 工具分类

```
┌──────────────────────────────────────────────────────────────┐
│                      Tool Pipeline                           │
│                                                               │
│  ┌────────────┐                                             │
│  │ Built-in   │  date / time / calendar / math / web_search │
│  │ Tools      │  (LLM 原生能力，绕过权限检查)                │
│  └─────┬──────┘                                             │
│        │                                                     │
│  ┌─────┴──────┐                                             │
│  │ External    │  ontology查询 / 门店查询 / 品类查询          │
│  │ Tools       │  权限求值 / 审计写入 / 指标查询              │
│  └─────┬──────┘                                             │
│        │                                                     │
│        ▼                                                     │
│  ┌────────────────┐                                          │
│  │ Permission     │ ← 工具执行前必须通过                       │
│  │ Gate            │                                          │
│  └────────────────┘                                          │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 三层工具接口（Three-Tier Tool Interface）

按可选项分层，越往下越可选。**Tier 2 的安全字段必须设默认值，且默认 fail-closed**（省略=安全）。

```typescript
interface Tool<Input, Output, Progress = void> {
  // ========== Tier 1：必须实现的行为契约 ==========
  name: string;                                   // 唯一标识，LLM 通过此名称调用
  call(input: Input, context: ToolContext): Promise<ToolResult<Output>>;
  checkPermissions(input: Input, context: PermContext): PermissionResult;
  mapResult(output: Output): ToolResponseContent;
  prompt: string;                                  // 工具描述，LLM 据此决定何时调用

  // ========== Tier 2：安全与验证（默认 fail-closed）==========
  validateInput?(input: Input): ValidationResult;
  isConcurrencySafe: boolean;   // default false（并发读=true，写=false）
  isReadOnly: boolean;         // default false（读操作=true，写操作=false）
  isDestructive: boolean;       // default false（删除/清空操作=true）
  preparePermissionMatcher?(input: Input): PermissionMatcher;

  // ========== Tier 3：UX（可选，增强体验）==========
  onProgress?(progress: Progress): void;
  renderResultSummary?(output: Output): string;
  groupKey?: string;          // 工具分组（如 "inventory", "pricing"）
  maxResultSizeChars?: number; // 结果上限，默认 10_000
}

// buildTool 工厂（TypeScript satisfies 保证类型安全 + 字面量推断）
function buildTool<S extends ZodSchema, O>(def: ToolDef<S, O>): Tool<z.infer<S>, O> {
  return {
    isConcurrencySafe: false,
    isReadOnly: false,
    isDestructive: false,
    maxResultSizeChars: 10_000,
    ...def,
  };
}

export const StoreQueryTool = buildTool({
  name: "ontology.store.query",
  schema: StoreQueryInputSchema,
  isConcurrencySafe: true,   // 读工具，可并发
  isReadOnly: true,
  call: async (input, ctx) => { /* ... */ },
} satisfies ToolDef<typeof StoreQueryInputSchema, StoreOutput>);

export const PriceAdjustTool = buildTool({
  name: "price.adjust",
  schema: PriceAdjustInputSchema,
  isConcurrencySafe: false,  // 写工具，串行
  isReadOnly: false,
  isDestructive: false,
  call: async (input, ctx) => { /* ... */ },
} satisfies ToolDef<typeof PriceAdjustInputSchema, PriceAdjustOutput>);
```

```typescript
interface ToolDefinition {
  name: string;                    // 工具唯一标识
  description: string;             // 业务描述（用于 LLM 决策）
  category: "ontology" | "business" | "system" | "builtin";

  // 参数 Schema（JSON Schema）
  input_schema: object;            // Pydantic model / JSON Schema
  output_schema: object;

  // 权限需求
  required_permissions: {
    resource_type: ResourceType;
    actions: string[];
  };

  // 执行约束
  constraints: {
    timeout_ms: number;           // 超时限制
    max_retries: number;          // 最大重试
    cacheable: boolean;            // 是否可缓存
    cache_ttl_seconds: number;
  };

  // 审计配置
  audit: {
    log_input: boolean;           // 是否记录输入参数
    log_output: boolean;          // 是否记录输出结果
    mask_sensitive_fields: string[]; // 脱敏字段
  };

  // 内置工具标志
  is_builtin: boolean;
  builtin_handler?: string;       // builtin 时指定处理函数名
}
```

### 9.3 工具注册与发现

```typescript
// tools/registry.ts
const toolRegistry = new Map<string, ToolExtension>();

// 装饰器注册
function registerTool(config: Partial<ToolDefinition>) {
  return function(target: any) {
    toolRegistry.set(config.name, {
      ...config,
      name: config.name,
      category: config.category ?? "business",
    });
  };
}

// 缓存稳定的工具排序（按名称字母序，不受注册顺序影响）
// 这保证了 LLM 收到的 tools 数组顺序稳定 → prompt cache 命中稳定
function getToolsSorted(): ToolExtension[] {
  return Array.from(toolRegistry.values()).sort((a, b) => a.name.localeCompare(b.name));
}

// 工具别名（重命名/废弃工具路由到新实现）
const TOOL_ALIASES: Record<string, string> = {
  "store.get":    "ontology.store.query",     // 旧名 → 新名
  "sku.search":   "ontology.sku.query",
};

// 废弃警告（LLM 会看到 deprecation notice）
const TOOL_DEPRECATIONS: Record<string, string> = {
  "ontology.store.query": "Use ontology.store.search instead (v2.0)",
};

function resolveToolName(name: string): { actual: string; alias: string | null; deprecated: boolean } {
  if (TOOL_ALIASES[name]) {
    return { actual: TOOL_ALIASES[name], alias: name, deprecated: !!TOOL_DEPRECATIONS[TOOL_ALIASES[name]] };
  }
  return { actual: name, alias: null, deprecated: !!TOOL_DEPRECATIONS[name] };
}
```

> **Cache-stable ordering**：工具池按名称字母序排序（稳定），而非按注册顺序。新工具只追加不插入，保证 prompt cache 命中稳定。废弃工具通过别名路由到新实现，并附带 deprecation notice。

### 9.4 七步工具生命周期（Seven-Step Lifecycle）

固定顺序，不可绕过。每步可短路返回结构化错误，保持 Agent Loop 控制权。

```
Step 1: Registration      — 工具注册到 registry，提取 schema，设置 deferred 标志
Step 2: Schema Validation — Zod parse → typed Input                [短路：parse error]
Step 3: validateInput()    — 业务逻辑校验（超越 schema）               [短路：validation error]
Step 4: backfillObservable — 浅拷贝 input + 派生字段，供 hooks/权限使用
Step 5: Pre-tool hooks    — onToolStart，传入 observable input        [短路：hook abort]
Step 6: Permission check   — allow | deny | ask-user                    [短路：deny]
Step 7a: call()           — 执行工具
Step 7b: mapResult()      — 映射结果格式
Step 7c: result truncation — 超过 maxResultSizeChars → 截断/落盘
Step 8: Post-tool hooks   — onToolEnd，写审计日志                     [不短路]
```

```python
async def execute_tool_pipeline(
    tool_name: str,
    args: dict,
    context: FrozenPermissionContext,
) -> ToolResult:
    # Step 1: 查找工具
    tool = tool_registry.get(tool_name)
    if not tool:
        raise ToolNotFoundError(tool_name)

    # Step 2: Schema validation（Zod parse）
    parsed_args = tool.input_schema.parse(args)  # 失败则抛出 ZodError

    # Step 3: validateInput（业务逻辑校验）
    validation = tool.validate_input(parsed_args)
    if not validation.passed:
        raise ValidationError(validation.reason)

    # Step 4: backfillObservable（派生字段，供 hooks 和权限使用）
    observable_input = {
        **parsed_args,
        "_derived": {
            "category_path": resolve_category_path(parsed_args.get("category_id")),
            "org_scope_resolved": resolve_org_scope(context),
            "user_role": context.role,
        }
    }

    # Step 5: Pre-tool hooks
    for hook in hooks_by_event["onToolStart"]:
        result = await hook.execute(tool_name, observable_input, context)
        if result.exit_code == 2:  # 阻塞错误
            raise HookBlockedError(result.stderr)

    # Step 6: Permission check（6 层 cascade，在权限章节）
    permission_result = await evaluate_permission_cascade(context, tool_name, parsed_args)
    if not permission_result.granted:
        raise PermissionDeniedError(tool_name)

    # Step 7a-c: call → mapResult → result truncation
    raw_result = await tool.call(observable_input, context)
    mapped = tool.map_result(raw_result)

    # 截断超过 maxResultSizeChars 的结果
    if len(str(mapped)) > tool.max_result_size_chars:
        persisted_path = write_persisted_result(str(mapped))
        mapped = f"<persisted-output path=\"{persisted_path}\">\n{truncate(mapped, 200)}\n...({len(mapped)} chars)\n</persisted-output>"

    # Step 8: Post-tool hooks（不短路，记录后继续）
    for hook in hooks_by_event["onToolEnd"]:
        await hook.execute(tool_name, observable_input, raw_result, context)

    return mapped
```

```typescript
async function executeTool(
  tool_name: string,
  args: Record<string, any>,
  context: PermissionContext
): Promise<ToolResult> {
  // 1. 查找工具定义
  const tool = toolRegistry.get(tool_name);
  if (!tool) throw new ToolNotFoundError(tool_name);

  // 2. 参数校验
  validate(tool.input_schema, args);

  // 3. 权限检查（内置工具跳过）
  if (!tool.is_builtin) {
    const permission = await evaluatePermission({
      ...context,
      action: tool.required_permissions.actions[0],
      resource_type: tool.required_permissions.resource_type,
    });
    if (!permission.granted) {
      await writeAuditLog({ ...context, outcome: "REJECTED", reason: "permission_denied" });
      throw new PermissionDeniedError(tool_name);
    }
  }

  // 4. 缓存查询
  if (tool.cacheable) {
    const cached = await cache.get(tool_name, args);
    if (cached) return cached;
  }

  // 5. 执行（内置 vs 外部）
  const result = tool.is_builtin
    ? await executeBuiltin(tool.builtin_handler, args)
    : await tool.execute(args);

  // 6. 写入审计
  await writeAuditLog({
    tool_name,
    input: tool.audit.log_input ? args : null,
    output: tool.audit.log_output ? result : null,
    duration_ms: result.duration_ms,
  });

  // 7. 写入缓存
  if (tool.cacheable) {
    await cache.set(tool_name, args, result, tool.constraints.cache_ttl_seconds);
  }

  return result;
}
```

### 9.5 敏感字段脱敏

```typescript
// 审计日志中脱敏处理
function maskSensitiveFields(data: any, fields: string[]): any {
  if (!fields.length) return data;
  const masked = Array.isArray(data) ? [...data] : { ...data };
  for (const field of fields) {
    if (field in masked) {
      masked[field] = "***REDACTED***";
    }
  }
  return masked;
}

// 工具返回的敏感信息
const SENSITIVE_FIELDS = {
  "ontology.store.query": ["manager_phone", "address"],
  "ontology.employee.query": ["salary", "bank_account"],
};
```

---

## 10. Hooks & Extensibility

> 生命周期钩子 + 快照冻结，确保权限检查结果在执行期间不被篡改（防 TOCTOU / 防 Prompt 注入）。

### 10.1 26 个生命周期事件（Typed Frozen Payloads）

闭合事件集，26 个事件覆盖完整 Agent 生命周期。**每个事件的 payload 是 `Readonly`（不可变）**，Hook 不能修改 payload，只能通过返回值传递决策。

```
Session:       SessionStart, SessionEnd, Stop
Loop:          PreToolUse, PostToolUse, PreCompact, PostCompact
Permission:    PermissionRequest
Subagent:      SubagentStart, SubagentStop
Config:        ConfigChange, SettingsLoaded
Filesystem:    FileChanged, FileRead, FileWritten
Notification:  Notification, TaskComplete, TaskFailed
User:          UserMessage, AssistantMessage
Context:       ContextOverflow, ContextCompacted
Model:         ModelSwitch, ModelError, ModelRetry
System:        Heartbeat, Shutdown
```

```typescript
// 事件定义（TypeScript 类型，所有 payload = Readonly）
type LifecycleEvent =
  // Session
  | { event: "SessionStart";    payload: Readonly<{ sessionId: string; userId: string; mode: PermissionMode }> }
  | { event: "SessionEnd";      payload: Readonly<{ sessionId: string; durationMs: number; reason: string }> }
  | { event: "Stop";            payload: Readonly<{ reason: string; source: "user" | "system" }> }
  // Loop
  | { event: "PreToolUse";      payload: Readonly<{ toolName: string; args: Record<string, unknown>; frozenContext: FrozenPermissionContext }> }
  | { event: "PostToolUse";     payload: Readonly<{ toolName: string; args: Record<string, unknown>; result: ToolResult; durationMs: number }> }
  | { event: "PreCompact";      payload: Readonly<{ reason: string; currentTokens: number; budget: number }> }
  | { event: "PostCompact";     payload: Readonly<{ oldTokens: number; newTokens: number; method: "summary" | "truncate" }> }
  // Permission
  | { event: "PermissionRequest"; payload: Readonly<{ toolName: string; args: Record<string, unknown>; context: FrozenPermissionContext }> }
  // Subagent
  | { event: "SubagentStart";   payload: Readonly<{ agentId: string; model: string; prompt: string }> }
  | { event: "SubagentStop";    payload: Readonly<{ agentId: string; exitCode: number; durationMs: number }> }
  // Config
  | { event: "ConfigChange";    payload: Readonly<{ key: string; oldValue: unknown; newValue: unknown }> }
  | { event: "SettingsLoaded";  payload: Readonly<{ settings: SettingsSnapshot }> }
  // Filesystem
  | { event: "FileChanged";     payload: Readonly<{ path: string; kind: "created" | "modified" | "deleted" }> }
  | { event: "FileRead";        payload: Readonly<{ path: string; size: number }> }
  | { event: "FileWritten";     payload: Readonly<{ path: string; size: number; mode: "atomic" | "direct" }> }
  // Notification
  | { event: "Notification";    payload: Readonly<{ type: string; message: string; priority: "low" | "medium" | "high" }> }
  | { event: "TaskComplete";    payload: Readonly<{ taskId: string; result: unknown }> }
  | { event: "TaskFailed";      payload: Readonly<{ taskId: string; error: string }> }
  // User
  | { event: "UserMessage";     payload: Readonly<{ content: string; sessionId: string }> }
  | { event: "AssistantMessage"; payload: Readonly<{ content: string; toolCalls: string[]; sessionId: string }> }
  // Context
  | { event: "ContextOverflow";  payload: Readonly<{ currentTokens: number; maxTokens: number }> }
  | { event: "ContextCompacted"; payload: Readonly<{ oldMessages: number; newMessages: number; summaryLength: number }> }
  // Model
  | { event: "ModelSwitch";     payload: Readonly<{ from: string; to: string; reason: string }> }
  | { event: "ModelError";      payload: Readonly<{ model: string; error: string; recoverable: boolean }> }
  | { event: "ModelRetry";      payload: Readonly<{ attempt: number; maxRetries: number; delayMs: number }> }
  // System
  | { event: "Heartbeat";       payload: Readonly<{ uptime: number; activeSessions: number }> }
  | { event: "Shutdown";        payload: Readonly<{ graceful: boolean; reason: string }> };
```

```python
# Hook 注册表（Python 实现）
class HookRegistry:
    """
    事件名 → 钩子列表，触发时过滤匹配项并行执行。
    钩子 payload 均为 Readonly，禁止在钩子内修改。
    """
    _hooks: dict[str, list[Hook]] = defaultdict(list)

    def register(self, event: str, hook: Hook) -> None:
        self._hooks[event].append(hook)

    async def emit(self, event: LifecycleEvent) -> list[HookResult]:
        hook_list = self._hooks.get(event.event, [])
        results = await asyncio.gather(*[
            hook.execute(event.payload) for hook in hook_list
        ], return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]
```

### 10.2 六种钩子执行类型（Six Hook Types）

| 类型 | 执行方式 | 超时 | 适用场景 |
|------|---------|------|---------|
| `command` | Shell 子进程（沙箱） | 30s | Linter、格式化、Git hooks |
| `prompt` | 单次 LLM 调用 | 60s | 内容校验、改写 |
| `agent` | 子 agent 返回 `{ok, reason}` | 120s | 多步校验 |
| `http` | POST 到 URL + payload | 10s | CI webhook、外部集成 |
| `callback` | 内部函数引用 | 5s | 内置扩展 |
| `function` | 会话级内部函数 | 30s | 用户定义进程内逻辑 |

```python
# Exit code 作为契约（三种语义）
# exit 0 = 成功，继续
# exit 2 = 阻塞错误，工具调用被阻止
# exit 其他 = 非关键警告，继续执行，向用户显示警告

async def execute_hook(config: HookConfig, event: LifecycleEvent) -> HookResult:
    match config.type:
        case "command":
            proc = await asyncio.create_subprocess_exec(
                "sh", "-c", config.command,
                env={**os.environ, "HOOK_EVENT": json.dumps(event.payload)},
                timeout=config.timeout,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=config.timeout)
            return HookResult(exit_code=proc.returncode, stdout=stdout, stderr=stderr)

        case "agent":
            result = await subagent.query(
                config.prompt + f"\n\nEvent: {event.payload}",
                allowed_tools=["Read", "Grep"],
            )
            return HookResult(exit_code=0 if result.ok else 2, stdout=result.reason, stderr="")

        case "http":
            async with httpx.AsyncClient() as client:
                resp = await client.post(config.url, json=event.payload, timeout=config.timeout)
                return HookResult(exit_code=0 if resp.status_code < 400 else 2, stdout="", stderr=str(resp.status_code))
```

### 10.3 启动快照隔离（Startup Snapshot Isolation）

见 3.1.3 章节。钩子配置在启动时快照冻结，运行时读取快照而非实时配置，防止 mid-session 文件注入。

### 10.4 异步钩子协议（Async Hook Protocol）

长时运行钩子（部署验证、审批流）使用异步而不阻塞主循环。

```python
async def execute_hook_async(config: HookConfig, event: LifecycleEvent) -> None:
    """
    钩子 stdout 首行写 {"async": true} → Harness 检测到后立即返回成功。
    进程后台运行，exit code 2 时通过 asyncRewake 唤醒模型。
    """
    proc = await asyncio.create_subprocess_exec(
        "sh", "-c", config.command,
        stdout=asyncio.subprocess.PIPE,
    )
    first_line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)

    if json.loads(first_line).get("async"):
        register_exit_handler(proc, config)
        return  # 立即返回，不阻塞主循环

async def exit_handler(proc, config):
    exit_code = await proc.wait()
    if exit_code == 2:  # 阻塞错误
        enqueue_notification({
            "type": "hook_async_failure",
            "message": proc.stderr,
            "priority": "in_band",
        })  # 唤醒模型，传入 stderr 作为上下文



### 10.5 快照冻结机制（TOCTOU 防护）

**问题**：权限检查（Time-of-Check）和工具执行（Time-of-Use）之间，组织数据可能被修改。

**解决方案**：在 `on_before_tool_call` 钩子中，将当前权限检查结果和组织状态快照绑定到本次执行上下文，后续执行只能读快照，不能读实时数据。

```typescript
interface FrozenPermissionContext {
  // 快照：不可篡改
  readonly permission_result: PermissionResult;
  readonly org_snapshot: OrgSnapshot;      // 组织快照
  readonly category_snapshot: CategorySnapshot;  // 品类快照
  readonly timestamp: string;              // 快照时间

  // 令牌：校验用
  readonly context_token: string;          // HMAC(context_data, secret)
}

class PermissionSnapshotGate {
  private frozenContexts = new Map<string, FrozenPermissionContext>();

  // 钩子：工具调用前冻结
  async onBeforeToolCall(
    tool_name: string,
    args: Record<string, any>,
    context: PermissionContext
  ): Promise<FrozenPermissionContext> {
    // 1. 求值权限
    const result = await evaluatePermission(context, tool_name);

    // 2. 收集快照
    const org_snapshot = await collectOrgSnapshot(context.org_scope);
    const category_snapshot = await collectCategorySnapshot(context.category_scope);

    // 3. 生成上下文令牌（防篡改）
    const snapshot_data = JSON.stringify({ result, org_snapshot, category_snapshot });
    const context_token = hmacSha256(snapshot_data, process.env.SNAPSHOT_SECRET);

    const frozen: FrozenPermissionContext = {
      permission_result: result,
      org_snapshot,
      category_snapshot,
      timestamp: new Date().toISOString(),
      context_token,
    };

    // 4. 存入上下文表（后续执行只读此快照）
    this.frozenContexts.set(context.request_id, frozen);
    return frozen;
  }

  // 钩子：工具执行时校验
  async validateFrozenContext(request_id: string, tool_name: string): Promise<void> {
    const frozen = this.frozenContexts.get(request_id);
    if (!frozen) throw new Error("No permission context found");

    // 校验令牌完整性
    const snapshot_data = JSON.stringify({
      frozen.permission_result,
      frozen.org_snapshot,
      frozen.category_snapshot,
    });
    const expected_token = hmacSha256(snapshot_data, process.env.SNAPSHOT_SECRET);
    if (expected_token !== frozen.context_token) {
      throw new SecurityError("Permission context tampered");
    }

    // 校验快照未过期（5分钟窗口）
    const age_ms = Date.now() - new Date(frozen.timestamp).getTime();
    if (age_ms > 5 * 60 * 1000) {
      throw new SecurityError("Permission context expired");
    }
  }
}
```

### 10.3 Prompt 注入防护

**问题**：恶意用户通过在对话中注入 prompt（"Ignore previous instructions, ..."），尝试绕过权限检查。

**防护措施**：

```typescript
// 1. 输入清洗（去除可疑注入模式）
function sanitizeUserInput(input: string): string {
  const SUSPICIOUS_PATTERNS = [
    /ignore (all )?previous (instructions?|commands?)/gi,
    /disregard (your )?system prompt/gi,
    /you are now a different (AI|model|assistant)/gi,
    /\\[SYSTEM\\]|\\{SYSTEM\\}/gi,
  ];

  let sanitized = input;
  for (const pattern of SUSPICIOUS_PATTERNS) {
    sanitized = sanitized.replace(pattern, "[FILTERED]");
  }
  return sanitized;
}

// 2. 权限检查结果隔离（不受 LLM 输出影响）
// 工具调用的权限结果由服务端独立计算，不经过 LLM 传播
// CopilotKit 的 renderToolCalls 结果直接写入 DOM，不回传 LLM

// 3. 权限规则只读（服务端存储，不暴露给 LLM 的 system prompt）
// SYSTEM_PROMPT 中只包含"如何调用工具"，不包含"权限规则具体内容"
```

### 10.4 扩展点定义

```typescript
interface HookPoints {
  // 生命周期钩子
  "on_request_start": (context: RequestContext) => Promise<void>;
  "on_before_llm_inference": (context: RequestContext, prompt: string) => Promise<string>;
  "on_before_tool_call": (tool: ToolCall, frozen: FrozenPermissionContext) => Promise<void>;
  "on_after_tool_call": (tool: ToolCall, result: any, frozen: FrozenPermissionContext) => Promise<void>;
  "on_after_llm_inference": (context: RequestContext, response: LLMResponse) => Promise<void>;
  "on_before_response": (context: RequestContext) => Promise<void>;
  "on_response_complete": (context: RequestContext) => Promise<void>;

  // 错误处理钩子
  "on_tool_error": (tool: ToolCall, error: Error) => Promise<ErrorResult>;
  "on_llm_error": (error: Error) => Promise<ErrorResult>;
}

// 扩展点注册
const hooks: Partial<HookPoints> = {
  on_before_tool_call: async (tool, frozen) => {
    // 例：记录权限快照到审计
    await auditLogger.snapshot(frozen);
  },
  on_tool_error: async (tool, error) => {
    // 例：发送告警
    await alertService.send({ tool: tool.name, error: error.message });
    return { retry: error.retryable };
  },
};
```

---

## 11. Orchestration

> 多租户隔离 + 多 Agent 协调，确保不同门店/区域数据互不干扰，支持多 Agent 并行。

### 11.1 多租户隔离模型

**租户维度**：按 `store_id` 或 `org_group_id` 隔离。

```
Tenant Context（请求级注入）：

  request.headers["x-tenant-id"] = "STORE-S101"
  request.headers["x-tenant-type"] = "store"  // store | org_group | brand

  → 中间件自动注入 tenant_context
  → 所有数据库查询自动追加 WHERE tenant_id = ?
  → 权限范围自动限定在 tenant 边界内
```

```typescript
interface TenantContext {
  tenant_id: string;       // STORE-S101 / ORGGRP-华南区
  tenant_type: "store" | "org_group" | "brand";
  tenant_path: string[];   // ["集团", "华南区", "直营", "S101"]（完整路径）
}

// 中间件：自动注入租户上下文
async function tenantMiddleware(request: Request, next: Handler) {
  const tenant_id = request.headers["x-tenant-id"];
  const tenant_type = request.headers["x-tenant-type"] ?? "store";

  if (!tenant_id) {
    throw new UnauthorizedError("Missing tenant context");
  }

  const tenant_context = await resolveTenantContext(tenant_id, tenant_type);

  // 挂载到请求上下文
  request.tenant = tenant_context;

  return next(request);
}
```

**数据隔离策略**：

```typescript
// 数据文件按租户分离
data/
  tenant/
    {tenant_id}/
      inventory.json
      tasks.json
      near_expiry.json
      audit/
        {date}.jsonl

// 跨租户查询（仅系统管理员）
async function crossTenantQuery(query: Query, context: TenantContext) {
  if (context.tenant_type !== "brand" && context.role !== "system_admin") {
    throw new PermissionDeniedError("Cross-tenant query not allowed");
  }
  return executeQueryAcrossAllTenants(query);
}
```

### 11.2 多 Agent 协调

**Agent 类型**：

```typescript
interface AgentConfig {
  name: string;                    // "deep-agent" | "copilot-agent"
  model: string;                   // "MiniMax-M2.7-highspeed"
  tools: string[];                 // 可用工具列表
  max_iterations: number;          // 最大迭代次数
  streaming: boolean;              // 是否支持流式
}

const AGENTS: Record<string, AgentConfig> = {
  "deep-agent": {
    name: "deep-agent",
    model: "MiniMax-M2.7-highspeed",
    tools: ["ontology.*", "permission.*", "audit.*", "metrics.*"],
    max_iterations: 10,
    streaming: true,
  },
  "simple-agent": {
    name: "simple-agent",
    model: "MiniMax-M2.7-highspeed",
    tools: ["builtin.*"],
    max_iterations: 3,
    streaming: true,
  },
};
```

**Agent 选择策略**：

```typescript
function selectAgent(request: UserRequest): AgentConfig {
  // 简单请求 → simple-agent
  if (isSimpleQuery(request.text)) {
    return AGENTS["simple-agent"];
  }
  // 复杂业务请求 → deep-agent
  if (requiresBusinessTools(request)) {
    return AGENTS["deep-agent"];
  }
  // 默认 deep-agent
  return AGENTS["deep-agent"];
}
```

**多 Agent 协调（并行执行）**：

```typescript
// 例：区域经理请求"华南区所有门店今日销售+临期商品"
// 需要两个并行任务：销售汇总 + 临期查询

interface OrchestrationTask {
  task_id: string;
  agent: AgentConfig;
  input: UserRequest;
  dependencies: string[];  // 依赖的其他 task_id
}

async function orchestrate(request: UserRequest): Promise<AggregatedResult> {
  // 1. 分解任务
  const tasks = decomposeRequest(request);
  // task_1: { agent: deep-agent, tools: [sales_summary], deps: [] }
  // task_2: { agent: deep-agent, tools: [near_expiry_query], deps: [] }
  // task_3: { agent: deep-agent, tools: [merge_and_summarize], deps: [task_1, task_2] }

  // 2. 执行无依赖任务（并行）
  const readyTasks = tasks.filter(t => t.deps.length === 0);
  const results = await Promise.all(readyTasks.map(executeTask));

  // 3. 执行有依赖任务（等待依赖完成）
  for (const task of tasks.filter(t => t.deps.length > 0)) {
    const depsResults = getTaskResults(task.deps);
    const taskResult = await executeTaskWithDeps(task, depsResults);
    results.push(taskResult);
  }

  // 4. 聚合结果
  return aggregateResults(results);
}
```

### 11.3 Tenant × Agent 绑定

```typescript
// 每个 Tenant 只允许访问自己的 Agent 实例
function getAgentForTenant(tenant_id: string, agent_name: string): AgentConfig {
  const baseAgent = AGENTS[agent_name];

  // 注入租户上下文到 Agent 的 system prompt
  return {
    ...baseAgent,
    system_prompt_suffix: `
      [Tenant Context]
      tenant_id: ${tenant_id}
      tenant_path: ${resolveTenantPath(tenant_id)}
      所有数据查询必须附加 tenant_id 过滤
    `,
  };
}
```

### 11.3 并发 Agent 队列上限（50-Message Queue Cap）

并发 agent 过多导致 OOM。**硬上限 + 队列拒绝策略**。

```python
MAX_CONCURRENT_AGENTS = 50  # 超过此数量，新请求排队或拒绝

_agent_semaphore: asyncio.Semaphore = None

def init_agent_pool(max_concurrent: int = 50) -> None:
    global _agent_semaphore
    _agent_semaphore = asyncio.Semaphore(max_concurrent)

async def spawn_agent(config: AgentConfig) -> AgentHandle:
    """获取信号量许可，超限则拒绝而非无限排队"""
    if not _agent_semaphore.try_acquire():
        raise AgentPoolExhaustedError(
            f"Agent pool at capacity ({MAX_CONCURRENT_AGENTS}). "
            "Request queued or rejected."
        )
    agent = AgentHandle(config)
    return agent

class AgentHandle:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        _agent_semaphore.release()  # 释放许可，回调池
```

---

## 12. Context Management

> 上下文窗口管理、滑动窗口压缩、Prompt 审计，解决 CopilotKit 全量历史发送导致的 context 膨胀问题。

### 12.1 问题背景

CopilotKit 的已知问题：**每次请求发送全量对话历史**，随着对话进行：
- 历史消息累积 → context 膨胀 → 最终触发 `BadRequestError`（模型 context 超限）
- MiniMax API 单次请求 token 上限已知，超限即报错

### 12.2 滑动窗口策略

**按 HumanMessage 计数**，保留最近 N 个用户消息对应的上下文。

```typescript
interface ContextWindowConfig {
  max_human_messages: 3;       // 保留最近 3 个用户消息
  max_total_messages: 10;       // 最多保留 10 条消息（用户+AI+工具）
  preserve_system_prompt: true;  // system prompt 始终保留
  preserve_tools_schema: true;  // tools schema 始终保留
}

async function getContextForRequest(
  conversation_history: Message[],
  config: ContextWindowConfig
): Promise<ContextResult> {
  // 1. 提取所有 HumanMessage
  const humanMessages = conversation_history.filter(m => m.role === "human");
  const recentHumanMessages = humanMessages.slice(-config.max_human_messages);

  // 2. 保留从第 1 个 recent human message 开始的所有消息
  const firstRecentHumanIdx = conversation_history.findIndex(
    m => m.role === "human" && m.id === recentHumanMessages[0].id
  );
  const preservedMessages = conversation_history.slice(firstRecentHumanIdx);

  // 3. 如果仍然超限，截断工具调用详情
  const tokenCount = await countTokens(preservedMessages);
  if (tokenCount > MAX_TOKENS) {
    const truncated = truncateToolCalls(preservedMessages, MAX_TOKENS);
    return { messages: truncated, truncated: true };
  }

  return { messages: preservedMessages, truncated: false };
}
```

### 12.3 摘要压缩

当滑动窗口仍超限时，对早期消息进行摘要。

```typescript
interface CompressedMessage {
  id: string;
  role: "human" | "assistant";
  summary: string;           // 摘要内容
  original_token_count: number;
  compressed_token_count: number;
  type: "compressed";
}

async function compressContext(
  messages: Message[],
  target_token_budget: number
): Promise<CompressedMessage[]> {
  const currentTokens = await countTokens(messages);
  const excessTokens = currentTokens - target_token_budget;

  if (excessTokens <= 0) return messages.map(m => ({ ...m, type: "original" }));

  // 对最早的用户+AI对话对进行摘要
  const toCompress = extractOldestDialoguePairs(messages, excessTokens);
  const summaries = await Promise.all(
    toCompress.map(pair => summarizeWithLLM(pair))  // 调用 LLM 摘要
  );

  // 重组消息序列
  return replaceWithSummaries(messages, toCompress, summaries);
}
```

### 12.4 Prompt 审计

**记录每次请求的 prompt 内容**（用于排查 bad case 和合规审查）。

```typescript
interface PromptAuditEntry {
  audit_id: string;
  timestamp: string;
  user_id: string;
  conversation_id: string;

  // Prompt 各部分 token 统计
  token_breakdown: {
    system_prompt: number;
    tools_schema: number;
    conversation_history: number;
    current_turn: number;
    total: number;
  };

  // 实际发送的 prompt 内容（前 2000 字符截断）
  system_prompt_preview: string;
  tools_schema_preview: string;

  // 元数据
  model: string;
  truncation_count: number;     // 压缩了几段历史
  context_overflow_count: number;  // 历史溢出次数

  // 安全标记
  injection_suspicion: boolean;
  flagged_patterns: string[];
}
```

### 12.5 Token Budget 分配

```typescript
const TOKEN_BUDGET = {
  // MiniMax-M2.7-highspeed context window（需确认实际值，暂按 32K 估算）
  max_context: 32000,

  // 固定开销
  reserved: {
    system_prompt: 2000,    // system prompt（含权限上下文）
    tools_schema: 1500,     // tools schema（随工具数量增长）
    response_buffer: 2000,  // 留 2K 给回复
  },

  // 可变部分
  available_for_context(): number {
    return this.max_context - this.reserved.system_prompt
                              - this.reserved.tools_schema
                              - this.reserved.response_buffer;
  },
};
```

---

## 13. LLM Integration

> Prompt 版本化管理、模型配置、Cache 控制、多模型路由。

### 13.1 Prompt 版本化

**问题**：业务规则变更时 system prompt 需要更新，如何追踪变更历史并支持回滚？

```typescript
interface PromptVersion {
  version_id: string;         // "v1.0.0"
  template: string;           // 模板内容（支持 {{变量}} 占位）
  variables: string[];       // 变量列表
  created_at: string;
  created_by: string;
  changelog: string;
  active: boolean;           // 是否为当前活跃版本
}

interface PromptConfig {
  name: string;             // "store_agent_system_prompt"
  current_version: string;
  versions: PromptVersion[];
}

// prompts/store_agent.yaml
prompts:
  store_agent_system_prompt:
    current_version: "v1.2.0"
    versions:
      - version_id: "v1.2.0"
        created_at: "2026-05-01"
        created_by: "admin"
        changelog: "新增损耗上报权限说明"
        active: true
        template: |
          你是一个超市门店管理 AI 助手。用户属于 {{domain}} 域，
          权限范围：{{org_scope_description}}。
          可用工具：{{available_tools}}。
      - version_id: "v1.1.0"
        created_at: "2026-04-01"
        created_by: "admin"
        changelog: "初始版本"
        active: false
        template: |
          你是一个超市门店管理 AI 助手...
```

**版本切换**：

```typescript
// 热更新（不重启服务）
async function activatePromptVersion(name: string, version_id: string): Promise<void> {
  const config = await loadPromptConfig(name);
  const version = config.versions.find(v => v.version_id === version_id);
  if (!version) throw new Error(`Version ${version_id} not found`);

  // 更新运行时缓存
  promptCache.set(name, renderPrompt(version, getCurrentVariables()));

  // 记录审计
  await auditLogger.log({
    action: "prompt_version_activate",
    prompt_name: name,
    version_id,
    activated_by: getCurrentUser(),
  });
}
```

#### 13.1.1 六层 Prompt 组装流水线（System Prompt Assembly Pipeline）

**目的**：Prompt 从多个来源组装，必须保证**缓存稳定性**——任何变量变化不能破坏全局缓存命中。

```
Layer 1: Base Sections        → 固定：Agent 身份、行为规则
Layer 2: User Context         → 用户偏好、自定义指令
Layer 3: System Context       → 环境信息、项目状态
Layer 4: Attribution Header    → 模型/版本 ID（★ 层 1-4 = 可全局缓存前缀 ★）
     ── SYSTEM_PROMPT_DYNAMIC_BOUNDARY（分隔符）────────────────
Layer 5: Cache Markers        → 战略块标记 cache_control: { type: "ephemeral" }
Layer 6: Dynamic Injection     → 会话特定数据（每次不同）
```

```python
SYSTEM_PROMPT_DYNAMIC_BOUNDARY = "<!-- DYNAMIC_BOUNDARY -->"

def assemble_system_prompt(config: PromptRenderConfig) -> list[dict]:
    """
    6 层组装流水线，每层独立可测试。
    边界分隔符使得缓存范围显式化：层 1-4 可全局缓存。
    """
    sections = []

    # Layer 1: Base Sections（Agent 身份 + 行为规则，固定不变）
    sections.extend(base_sections())       # 零售 AI 助手身份、核心原则

    # Layer 2: User Context（用户偏好、自定义指令）
    sections.extend(user_context(config.user_id))  # 权限域、常用操作

    # Layer 3: System Context（环境信息）
    sections.extend(system_context(config))  # 当前时间、DC 配置、品类树

    # Layer 4: Attribution Header（模型/版本 ID）
    sections.append(attribution_header(config.model_id))

    # Layer 5: Cache Markers（战略性块级缓存标记）
    # 某些块标记为 ephemeral：每次请求重新计算
    insert_cache_markers(sections)

    # Layer 6: Dynamic Boundary（分隔缓存前缀和动态后缀）
    sections.append({"type": "text", "content": SYSTEM_PROMPT_DYNAMIC_BOUNDARY})

    # Layer 7: Dynamic Injection（会话特定数据，每次都变）
    sections.extend(dynamic_injection(config))  # 门店 ID、会话历史摘要

    return sections


def insert_cache_markers(sections: list[dict]) -> None:
    """在战略性位置插入 cache_control 标记"""
    for section in sections:
        if section.get("type") == "tool_schema":
            # 工具 schema 块：全局缓存（工具定义不频繁变化）
            section["cache_control"] = {"type": "ephemeral"}  # 不缓存，频繁变化


# 缓存边界验证（测试用）
def test_cache_boundary():
    prompt = assemble_system_prompt(sample_config())
    boundary_idx = next(i for i, s in enumerate(prompt) if s.get("content") == SYSTEM_PROMPT_DYNAMIC_BOUNDARY)
    prefix = prompt[:boundary_idx]
    suffix = prompt[boundary_idx + 1:]

    # 前缀哈希稳定（改变 session 特定数据不应影响前缀）
    prefix_hash_1 = hash_prompt_section(prefix)
    config_2 = replace_session_data(sample_config())
    prompt_2 = assemble_system_prompt(config_2)
    prefix_hash_2 = hash_prompt_section(prompt_2[:boundary_idx])

    assert prefix_hash_1 == prefix_hash_2, "Cache boundary violated: session data leaks into prefix"
```

> **缓存稳定性原则**：层 1-4 的哈希值在相同 Agent 版本下恒定，可供 LLM provider 缓存。只要 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 后的数据变化（门店 ID、品类上下文），前缀不变，缓存命中。

### 13.2 模型配置

```typescript
interface LLMConfig {
  model: string;                    // "MiniMax-M2.7-highspeed"
  base_url: string;                 // "https://api.minimaxi.com/v1"
  api_key_env: string;              // 从环境变量读取，不硬编码

  // 推理参数
  temperature: number;              // 默认 0.7
  top_p: number;                    // 默认 0.9
  max_tokens: number;               // 默认 1024

  // 请求控制
  request_timeout_ms: number;       // 默认 60s
  max_retries: number;              // 默认 3

  // Cache（如果模型支持）
  cache_enabled: boolean;           // 是否启用 cache
  cache_prefix: string;             // "store-ontology-prod"
}

const DEFAULT_LLM_CONFIG: LLMConfig = {
  model: "MiniMax-M2.7-highspeed",  // 注意：必须带 MiniMax- 前缀
  base_url: "https://api.minimaxi.com/v1",
  temperature: 0.7,
  top_p: 0.9,
  max_tokens: 1024,
  request_timeout_ms: 60_000,
  max_retries: 3,
  cache_enabled: false,
  cache_prefix: "store-ontology",
};
```

### 13.2.1 Multi-Provider 客户端工厂

单一 `createClient(config)` 工厂，provider 在构造时选定，调用点无需分支。统一 `messages.create()` / `messages.stream()` 接口。

```python
def create_llm_client(config: LLMConfig) -> LLMClient:
    """
    工厂模式：provider 在构造时确定，调用点无分支。
    新增 provider = 新增一个 match arm。
    """
    match config.provider:
        case "minimax":
            client = ChatOpenAI(
                model=config.model,  # "MiniMax-M2.7-highspeed"（注意必须带前缀）
                base_url=config.base_url,
                api_key=os.environ[config.api_key_env],
                max_retries=0,  # 禁用 SDK retry，自建 withRetry generator
                timeout=config.request_timeout_ms / 1000,
            )
        case "openai":
            client = ChatOpenAI(
                model=config.model,
                base_url=config.base_url,
                api_key=os.environ[config.api_key_env],
                max_retries=0,
            )
        case _:
            raise ValueError(f"Unknown provider: {config.provider}")

    return LLMClient(
        client=client,
        config=config,
        fetch=instrumented_fetch,  # 单点注入 telemetry + correlation headers
    )


def instrumented_fetch(url: str, opts: dict) -> httpx.Response:
    """
    单点注入：telemetry + retry-budget headers + auth tokens。
    包装 platform fetch，不修改 SDK 内部。
    """
    headers = {
        **opts.get("headers", {}),
        "x-request-id": uuid4(),        # 请求级追踪
        "x-correlation-id": get_corr_id(),  # 跨服务链路追踪
    }
    opts["headers"] = headers
    return httpx.post(url, **opts)
```

> **调用点无分支原则**：所有 `client.messages.create()` 调用点不写 `if provider == "minimax"` 分支。provider 差异在工厂内消化，调用点永远调用统一接口。

### 13.3 多模型路由

```typescript
// 根据请求特征选择模型
function selectModel(request: UserRequest): LLMConfig {
  // 简单工具调用（date/time）→ 低成本模型
  if (isBuiltinOnlyRequest(request)) {
    return { ...DEFAULT_LLM_CONFIG, model: "MiniMax-M2.7-highspeed", temperature: 0.3 };
  }

  // 复杂推理请求 → 高配模型
  if (requiresComplexReasoning(request)) {
    return { ...DEFAULT_LLM_CONFIG, model: "MiniMax-M2.7-highspeed", temperature: 0.7 };
  }

  // 快速查询 → 降级模型（如果有）
  if (request.urgency === "high" && hasFallbackModel()) {
    return FALLBACK_LLM_CONFIG;
  }

  return DEFAULT_LLM_CONFIG;
}
```

### 13.4 Cache 控制

**Beta Header Latching**：Beta headers（provider 特定缓存控制头）在会话开始时 latch（锁定），会话期间保持不变，保证 prompt cache 命中稳定。

```python
class BetaHeaderManager:
    """
    Beta headers 在会话启动时 latch，之后不再改变。
    改变 beta header 会破坏 prompt cache 命中（重算整个前缀）。
    """
    _session_beta_headers: dict[str, str] = {}

    @classmethod
    def latch(cls, beta_headers: dict[str, str]) -> None:
        """会话启动时调用，之后不可修改"""
        cls._session_beta_headers = dict(beta_headers)  # 深度拷贝，冻结

    @classmethod
    def get(cls) -> dict[str, str]:
        return cls._session_beta_headers  # 返回冻结副本


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        # 会话启动时 latch beta headers
        BetaHeaderManager.latch(config.beta_headers or {})

    def build_request_headers(self) -> dict:
        """构建请求头，包含 latched beta headers"""
        return {
            **self.config.extra_headers,  # 业务 headers
            **BetaHeaderManager.get(),     # latch 的 beta headers
        }
```

```typescript
// 请求级 Cache（对话内重复问题）
const requestCache = new LRUCache<string, LLMResponse>({
  max: 100,  // 最多缓存 100 个请求
  ttl: 300_000,  // 5 分钟
});

function buildCacheKey(messages: Message[], model: string): string {
  const hash = crypto.createHash('sha256');
  hash.update(JSON.stringify(messages.map(m => ({ role: m.role, content: m.content }))));
  return `${model}:${hash.digest('hex')}`;
}

async function cachedLLMCall(messages: Message[]): Promise<LLMResponse> {
  const key = buildCacheKey(messages, CURRENT_MODEL);
  const cached = requestCache.get(key);
  if (cached) {
    return { ...cached, cached: true };
  }
  const result = await llmInference(messages);
  requestCache.set(key, result);
  return result;
}
```

---

## 14. Architecture

> 四层架构：apps（应用）/ configs（配置）/ agents（智能体）/ observability（可观测性）。

### 14.0 Bootstrap State 与 Two-Layer State

**Bootstrap State（启动状态）**：进程生命周期配置（API keys、模型、project root）。作为 import 图的叶子节点，**不导入本地模块**，避免循环依赖。

```python
# bootstrap/state.py — 不导入任何本地模块
_model: str = ""
_api_key: str = ""
_base_url: str = ""
_permission_config_path: str = ""

def set_model(m: str) -> None:
    global _model; _model = m

def get_model() -> str:
    return _model
# ... 字段数量保持在 ~15 以内
```

**Two-Layer State**：Bootstrap state（只读，一次设置）和 Reactive state（频繁变更，60fps 级别）分离，防止 bootstrap 写入触发 UI 重渲染。

```python
# state/store.py — 响应式 store（~34 行）
class AppState:
    messages: list[Message] = []
    current_tool_use: ToolUse | None = None
    is_streaming: bool = False
    permission_requests: list[PermissionRequest] = []

state = AppState()
_listeners: list[Callable[[AppState], None]] = []

def set_state(partial: Partial[AppState]) -> None:
    global state
    state = AppState(**{**state.__dict__, **partial})
    for fn in _listeners:
        fn(state)

def subscribe(fn: Callable[[AppState], None]) -> Callable[[], None]:
    _listeners.append(fn)
    return lambda: _listeners.remove(fn)
```

> **单向依赖原则**：Reactive store 不导入 bootstrap（反向依赖禁止）。流式 delta 更新只触发 Reactive store，不影响 bootstrap。

### 14.1 项目结构

```
store-ontology/
├── apps/                          # 应用层：API 端点、入口
│   ├── api/
│   │   ├── agent/
│   │   │   ├── stream.py         # SSE 流式响应
│   │   │   └── chat.py           # 普通对话
│   │   ├── org/
│   │   ├── category/
│   │   ├── permission/
│   │   ├── audit/
│   │   └── metrics/
│   ├── main.py                   # FastAPI 入口
│   └── middleware/
│       ├── tenant.py             # 多租户中间件
│       ├── audit.py             # 审计中间件
│       └── abort.py             # 取消检测中间件
│
├── agents/                       # 智能体层：LLM 推理、工具编排
│   ├── deep_agent/
│   │   ├── agent.py             # Deep Agents 主逻辑
│   │   ├── tool_executor.py      # 工具执行器（含 Pipeline）
│   │   └── loop.py              # Agentic Loop（流式/取消/背压）
│   ├── copilot/
│   │   └── copilot_adapter.py    # CopilotKit 适配器
│   └── shared/
│       ├── tool_registry.py     # 工具注册表
│       └── hooks.py             # 生命周期钩子实现
│
├── configs/                      # 配置层：Prompt/权限规则/数据 Schema
│   ├── prompts/
│   │   ├── store_agent.yaml      # Prompt 版本化配置
│   │   ├── admin_agent.yaml
│   │   └── templates/
│   │       ├── system_base.j2
│   │       └── tool_description.j2
│   ├── permission/
│   │   └── rules.yaml            # 权限规则库（初始配置）
│   ├── ontology/
│   │   ├── org_units.schema.json
│   │   ├── categories.schema.json
│   │   ├── distribution_centers.schema.json
│   │   ├── permission_rules.schema.json
│   │   └── audit_entry.schema.json
│   └── llm/
│       └── models.yaml          # 模型配置
│
├── observability/                # 可观测性层：日志/Trace/指标
│   ├── logging/
│   │   ├── structured.py        # 结构化日志（JSON）
│   │   └── audit_logger.py       # 审计日志写入
│   ├── tracing/
│   │   ├── otel_setup.py        # OpenTelemetry 初始化
│   │   └── spans.py             # Trace span 工具
│   └── metrics/
│       ├── collector.py         # 指标采集
│       └── exporters.py         # 指标导出（Prometheus / OTLP）
│
├── data/                         # 数据层：JSON 文件存储
│   ├── ontology/                # 本体数据
│   ├── audit/                   # 审计日志（JSON Lines）
│   ├── metrics/                 # 指标数据
│   └── tenant/                  # 多租户数据（隔离目录）
│
└── tests/                        # 测试
    ├── unit/
    ├── integration/
    └── harness/                  # Harness 专项测试
```

### 14.2 数据流（完整请求生命周期）

```
用户请求
    │
    ▼
apps/middleware/tenant.py        ←── 注入 TenantContext
    │
    ▼
apps/middleware/audit.py         ←── 记录请求开始
    │
    ▼
agents/deep_agent/loop.py         ←── Agentic Loop（流式/取消/背压）
    │
    ├──► agents/shared/tool_registry.py
    │         │
    │         ├──► Permission Gate（权限检查）
    │         │     │
    │         │     └──► agents/shared/hooks.py（快照冻结）
    │         │
    │         └──► 外部工具（ontology/tools.py）
    │
    ▼
observability/tracing/otel_setup.py  ←── Trace Span 记录
    │
    ▼
observability/logging/audit_logger.py ←── 审计日志写入（含快照）
    │
    ▼
响应给用户
```

### 14.3 核心依赖关系

```
apps/         → agents/          （调用 agent 处理请求）
apps/         → configs/         （读取配置）
agents/       → configs/         （读取 prompt 版本、权限规则）
agents/       → observability/   （写入 trace/log）
observability/→ data/            （指标/审计数据落地）
agents/       → tools/           （调用业务工具）
```

### 14.4 部署架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端（Next.js）                        │
│               localhost:3000 / 内部域名                    │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP/WebSocket
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Backend（FastAPI / Python）                   │
│        localhost:8000 / internal.store-ontology           │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ apps/            应用层（API 端点）               │    │
│  │ middleware/      租户 + 审计 + 取消 检测          │    │
│  └───────────────────────┬─────────────────────────┘    │
│  ┌───────────────────────┴─────────────────────────┐    │
│  │ agents/          智能体层（Deep Agents + Loop）  │    │
│  │ shared/          工具注册 + 钩子实现               │    │
│  └───────────────────────┬─────────────────────────┘    │
│  ┌───────────────────────┴─────────────────────────┐    │
│  │ observability/    可观测性（Trace/Log/Metrics）  │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     MiniMax API     JSON 文件        监控端点
   (LLM 推理)       (数据持久化)    (Prometheus)
```

---

## 8. 实施优先级

### Phase 1（核心基础设施）

1. **本体论更新**：OrgUnit（含5级）、DistributionCenter、Category（含5级）、PermissionRule Schema
2. **组织结构 API**：Org Tree、Region→Store、DC→Store 查询
3. **品类树 API**：Category Tree、品类路径查询
4. **权限求值引擎**：Permission Evaluator（含 org_scope 逻辑解析）
5. **审计日志中间件**：自动写入 AuditLogEntry（含快照）

### Phase 2（权限业务闭环）

6. **权限规则库初始化**：按业务角色配置初始规则集
7. **损耗上报流程**：门店+DC 损耗报损/报溢（含审批流）
8. **定价权限流程**：总部/区域/门店三级调价

### Phase 3（可观测性）

9. **指标采集**：品类×组织双维度指标计算
10. **Trace 集成**：OpenTelemetry 全链路追踪
11. **告警配置**：损耗率/缺货率/价格偏离告警

### Phase 4（前端界面）

12. **权限管理 UI**：规则配置、用户有效权限查询
13. **审计日志 UI**：审计查询、审计报表
14. **数据看板**：品类×组织双维度热力图

---

## 附录 B

> **2026-05-26 更新**：对照 `langchain-ai/deepagents`（23k stars，libs/deepagents + libs/code）逐项核实。

**评分标准**：`[x]` = 已实现，`[~]` = 部分实现，`[ ]` = 未实现，`[N/A]` = 不适用，`[deep]` = deepagents 已实现

---

### Architecture（8 项）

| # | 审计项 | 状态 | deepagents 实际 | store-ontology 实际 |
|---|--------|------|---------------|-----------------|
| 1 | Multiple execution modes | [deep] | libs/cli（CLI）、libs/code（终端）、libs/deepagents（SDK）| 仅 FastAPI HTTP |
| 2 | State layers separated | [~] | `StateBackend`（会话态）/ `FilesystemBackend`（持久态）/ `CompositeBackend`（组合）三层抽象清晰 | 仅 MemorySaver（内存），无显式三层 |
| 3 | Single composition primitive | [x] | LangGraph `create_agent` 统一封装，无 callback 混用 | 使用 deepagents，继承其封装 |
| 4 | Bootstrap isolation | [x] | `deepagents._models.resolve_model` 在 middleware 构造时解析模型，启动失败立即报错 | 使用 deepagents，继承其封装 |
| 5 | Entry point unification | [x] | `create_deep_agent()` 单一入口，内置 6 种 middleware | 同上 |
| 6 | Feature flag strategy | [x] | `ExcludedMiddleware` 配置类，简单字典 | 使用 deepagents 配置 |
| 7 | Extension model uses primary abstraction | [x] | MCP tools 通过 `mcp_tools.py` → `ToolRuntime` 接入，与内置工具同一 pipeline | 同上 |
| 8 | Import graph discipline | [x] | deepagents 内部模块化，无循环依赖 | 使用 deepagents，无循环依赖 |

**Architecture 得分：deepagents 8/8（我们继承实现）**

---

### Agentic Loop（8 项）

| # | 审计项 | 状态 | deepagents 实际 | store-ontology 实际 |
|---|--------|------|---------------|-----------------|
| 1 | Generator-based loop | [~] | LangGraph `CompiledStateGraph`，非显式 `async function*`，但 yield 事件流式 | 同上 |
| 2 | Context management pipeline | [x] | `SummarizationMiddleware`：5-stage（trigger → summarize → offload → compact → evict），有 circuit breaker | `SummarizationMiddleware` 已开启（MemorySaver），但 pipeline 未显式分阶段 |
| 3 | Autocompact strategy | [x] | `SummarizationMiddleware`，fork LLM 摘要，非主 agent 自己压缩 | 同上 |
| 4 | Token budget tracking | [~] | `token_state.py` 追踪，但**不是流式期间实时** | 无实时追踪 |
| 5 | Crash-resilient persistence | [x] | `FilesystemBackend`（会话文件持久化）+ `MemorySaver`（checkpointer） | 有 `MemorySaver`，无会话文件持久化 |
| 6 | Streaming tool execution | [ ] | **未实现**：工具结果等全部完成再返回，无增量流式给 LLM | 同上 |
| 7 | Compaction circuit breaker | [x] | `SummarizationMiddleware` 有重试上限（未找到显式 3 次熔断代码，但有 `ContextOverflowError` fallback → `_clip_overflow_tail`） | 同上 |
| 8 | Session resume | [x] | `MemorySaver` + `thread_id` 可恢复；`Sessions` 类管理会话列表 | 同上 |

**Agentic Loop 得分：4/8（deepagents 提供）+ 0/8（store-ontology 独有）= 4/8**

> **关键发现**：`Streaming tool execution` 在 deepagents 中也**未实现**。这是跨 harness 的共同缺口。

---

### Tool System（8 项）

| # | 审计项 | 状态 | deepagents 实际 | store-ontology 实际 |
|---|--------|------|---------------|-----------------|
| 1 | Typed tool interface | [x] | `BaseTool` + `StructuredTool` + `ToolRuntime`，LangChain 统一抽象 | 同上（`@tool` 装饰器） |
| 2 | Lifecycle pipeline | [x] | `ToolNode`（LangGraph 内置）→ `invoke()` / `ainvoke()` → `ToolResult` | 同上 |
| 3 | Concurrent batching | [x] | `AsyncSubAgentMiddleware` 支持并发 subagent | 无并发 subagent |
| 4 | Result budget | [x] | `_overflow_clip.py`：工具结果超限 → `TOO_LARGE_TOOL_MSG` + 落盘 `/large_tool_results/{id}` | 无截断/落盘 |
| 5 | Deferred loading | [x] | `SkillsMiddleware` 延迟从 backend 加载 SKILL.md，按需注入 system prompt | 本体 TTL 延迟解析 |
| 6 | MCP integration | [x] | `mcp_providers/` + `mcp_tools.py`：`MCP Servers` → `ToolRuntime` 统一接入 | 无 MCP |
| 7 | Cache-stable ordering | [ ] | **未找到**：工具未按名称排序（注册顺序决定） | 无工具排序 |
| 8 | Alias and migration | [ ] | **未找到**：无工具别名/废弃路由机制 | 无 |

**Tool System 得分：5/8（deepagents）+ 1/8（store-ontology 扩展）= 6/8**

> **MCP 是 deepagents 已实现、store-ontology 缺失的**关键功能。

---

### Permission & Safety（8 项）

| # | 审计项 | 状态 | deepagents 实际 | store-ontology 实际 |
|---|--------|------|---------------|-----------------|
| 1 | Mode-based strategy | [~] | `FilesystemMiddleware` 有 `FilesystemPermission`（allow/deny），但仅限文件系统操作，无业务域权限 | 无权限引擎 |
| 2 | Rule cascade | [x] | `FilesystemPermission` 规则按声明顺序匹配（first-match wins） | 无 |
| 3 | Immutable permission context | [x] | `FilesystemMiddleware` 权限规则在 middleware 构造时冻结 | 无 |
| 4 | Hook-permission bridge | [ ] | **未找到**：钩子可调用任意工具，无权限桥接 | 无 |
| 5 | Sandbox integration | [x] | `SandboxBackend`（Daytona/Modal/QuickJS/Runloop providers）进程隔离 | 无 |
| 6 | Path security | [x] | `validate_path()` + `wcmatch.glob` 防路径遍历，`FilesystemBackend` 有 `virtual_mode` | 无 |
| 7 | Trust gate on external code | [x] | `MCP servers` 需 `mcp_auth.py` OAuth，`mcp_trust.py` trust 检查 | 无 |
| 8 | Enterprise policy layer | [ ] | **未找到**：无 Role × Domain RBAC/ABAC 业务权限 | 无 |

**Permission & Safety 得分：5/8（deepagents 仅限文件系统）+ 0/8（业务域权限缺失）= 5/8**

> **重要**：deepagents 的权限仅限**文件系统操作**，业务域权限（品类/组织/动作级别）**完全未实现**。这是 store-ontology 必须自己实现的部分。

---

### Extensibility（6 项）

| # | 审计项 | 状态 | deepagents 实际 |
|---|--------|------|---------------|
| 1 | Hook system with event contracts | [x] | `hooks.py`：`event_bus.py` 发布订阅，`EventBus` 类型化事件（`on_tool_use`/`on_message` 等）|
| 2 | Skill/plugin architecture | [x] | `SkillsMiddleware`：从 backend 加载 `SKILL.md`，支持多 source（base/user/project）|
| 3 | Conditional activation | [x] | `skills/invocation.py`：基于命令触发，非 always-on |
| 4 | Self-authoring mechanism | [ ] | **未找到**：无自动捕获工作流并编码为技能 |
| 5 | Multi-source priority | [x] | `skills.py`：多 source 列表，后面的覆盖前面的（last-wins）|
| 6 | Namespace collision prevention | [x] | `SkillsMiddleware` 按 source 隔离，无命名冲突 |

**Extensibility 得分：5/6（deepagents 提供）**

---

### LLM Integration（8 项）

| # | 审计项 | 状态 | deepagents 实际 |
|---|--------|------|---------------|
| 1 | Multi-provider client | [x] | `ChatOpenAI` / `ChatAnthropic` + `ConfigurableModel`，统一 `create_deep_agent` 接口 |
| 2 | Manual retry with backoff | [~] | LangChain SDK `max_retries`，无显式 `withRetry()` generator |
| 3 | Streaming state machine | [x] | `DeltaChannel`（O(N) 增长）+ `stream()` 事件流 |
| 4 | System prompt pipeline | [~] | `SkillsMiddleware`（分层注入）+ `MemoryMiddleware`（AGENTS.md），但无显式 6-layer 流水线 |
| 5 | Cache boundary design | [ ] | **未找到**：`SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 无实现 |
| 6 | Beta header management | [ ] | **未找到** |
| 7 | Cost tracking at stream time | [~] | `token_state.py` 在 `on_stream_end` 事件后统计，非流式期间 |
| 8 | Stale-while-revalidate | [ ] | **未找到** |

**LLM Integration 得分：3/8（deepagents 提供）**

---

### Infrastructure（6 项）

| # | 审计项 | 状态 | deepagents 实际 |
|---|--------|------|---------------|
| 1 | FS abstraction | [x] | `FilesystemBackend` / `StateBackend` / `StoreBackend` / `CompositeBackend` / `SandboxBackend` 多 backend 体系 |
| 2 | Config management | [x] | `model_config.py` + `config.py` 分层配置（CLI > env > file）|
| 3 | Git integration security | [x] | `_git.py`：`verify_clean_git_status()` + 路径安全检查 |
| 4 | Multi-tenancy isolation | [ ] | **未找到**：deepagents 无多租户概念（单用户工具）|
| 5 | Structured logging | [x] | LangSmith tracing + JSON 日志 |
| 6 | Graceful shutdown | [x] | `server.py` + `server_manager.py`：优雅关闭处理 |

**Infrastructure 得分：5/6（deepagents 提供）**

---

## 附录 C：最终对比结果

> 对照来源：`cauchyturing/agent-harness-engineering`（58 项审计清单）+ `langchain-ai/deepagents`（逐文件核实）

### 三方对照总表

| 审计模块 | harness 要求（项）| deepagents 实现 | store-ontology 实现 |
|---------|:---:|:---:|:---:|
| **Architecture** | 8 | ✅ 8/8 | ✅ 继承 deepagents |
| **Agentic Loop** | 8 | ⚠️ 5/8（缺 streaming tool exec）| ⚠️ 继承 + 0/8 独享 |
| **Tool System** | 8 | ✅ 6/8（缺 cache-stable/alias）| ⚠️ 1/8（TTL 解析）|
| **Permission & Safety** | 8 | ⚠️ 5/8（仅文件系统）| ❌ 0/8（业务域全缺）|
| **Extensibility** | 6 | ✅ 5/6 | ✅ 继承 deepagents |
| **LLM Integration** | 8 | ⚠️ 3/8（缺 cache boundary 等）| ❌ 0/8（无 pipeline）|
| **Infrastructure** | 6 | ✅ 5/6（缺多租户）| ⚠️ 继承部分 |
| **总分** | **52** | **37/52 ≈ 71%** | **≈ 25%** |

---

### store-ontology 能力分解

| 层级 | 覆盖范围 | 说明 |
|------|---------|------|
| **已继承** | Architecture / Extensibility / Infrastructure 大部 | `create_deep_agent` 内置 |
| **已继承但未启用** | Result budget / MCP / FilesystemBackend / Token 追踪 | deepagents 有代码，未接入 |
| **必须自研** | 业务权限引擎 / 品类权限边界 / 审计日志 / HITL 审批流 | 零售场景独有，deepagents 不覆盖 |
| **共同缺口** | Streaming tool execution / Multi-tenancy / 6-layer prompt | 整个行业都未解决 |

---

### 最终评分

```
deepagents 本体：          71%（37/52）
store-ontology 继承：      +15%（继承 deepagents 能力）
store-ontology 自研：       25%（业务权限/品类/审计/HITL 独享）
───────────────────────────────────────────────────────
store-ontology 最终系统：   约 65%（继承+自研综合）
```

---

### 优先实现路线图

```
P0（业务闭环必备）：
  1. [自研] 权限引擎基础（rule cascade + mode-based + org_scope 注入）
  2. [自研] 品类树权限边界（CategoryScope × Action）
  3. [自研] 审计日志中间件（调价/损耗/报溢）

P1（生产稳定性）：
  4. [共同] Streaming tool execution（deepagents 也缺）
  5. [继承] Result budget 截断（接入 deepagents _overflow_clip）
  6. [继承] MCP integration（接入 deepagents mcp_providers）
  7. [继承] 会话文件持久化（接入 deepagents FilesystemBackend）
  8. [共同] Multi-tenancy isolation（deepagents 无，store-ontology 需自研）

P2（功能完整）：
  9. [共同] Cache-stable tool ordering
  10. [共同] 6-layer system prompt pipeline
  11. [继承] Token 实时追踪（接入 deepagents token_state）
  12. [自研] HITL 业务审批流（三级：总部/区域/门店）
```

---

### A. 术语表

| 术语 | 说明 |
|------|------|
| OrgUnit | 组织单元实体的统称，含Brand/OrgGroup/Channel/Region/Store五级 |
| DC | Distribution Center，配送中心，含生鲜仓/杂货仓/中央仓 |
| Domain | 职能域：总部支持域/供应链域/超市运营域 |
| PermissionRule | 权限规则，定义 who × what × constraints |
| Permission Evaluator | 权限求值引擎，运行时解析 org_scope 逻辑引用 |
| AuditLogEntry | 审计日志条目，含操作快照 |
| CategoryScope | 品类范围，定义可操作的品类边界 |
| OrgScope | 组织范围，通过 scope_type 逻辑引用而非硬编码 |
| TOCTOU | Time-of-Check to Time-of-Use，审计快照防此问题 |
| Variety | 次小类，仅生鲜部门有的第5级品类 |

### B. 参考资料

- SAP S/4HANA 零售组织架构（Company Code / Plant / Sales Organization / Distribution Channel / Division）
- SAP IS-Retail Merchandise Hierarchy（部门/大类/中类/小类/商品）
- Agent Harness Engineering（Jiaaqiliu/Aweless-Harness / cauchyturing/agent-harness-engineering / cybernetix-lab/moss-harness）
- RBAC × ABAC 融合模型（ANSI INCITS 494-2021）
- OpenTelemetry Trace/Metrics/Logs 数据模型
