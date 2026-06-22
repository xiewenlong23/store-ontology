# v2 认证 + 完整 RBAC×ABAC（本体资源全覆盖）+ 组织/品类 5 级

> **状态**：设计已确认，待实施
> **日期**：2026-06-22
> **性质**：架构扩展。引入用户认证、完整 RBAC×ABAC 权限体系（覆盖 Tool/Object/属性/Action/Link 5 类资源）、5 级组织/品类树。落地 roadmap 的 v2-权限 + v2-本体。
> **关联**：[`docs/design/roadmap.md`](../../design/roadmap.md) §2/§3、[`docs/design/00-architecture.md`](../../design/00-architecture.md) §3.3/§3.4、[`docs/design/archive/legacy-Harness-Design.md`](../../design/archive/legacy-Harness-Design.md) §1/§2/§3

---

## 0. 问题陈述（现状地基）

四类缺口（探查已证实）：

1. **认证完全空白**：全仓 0 行 auth 代码、0 个 auth 依赖、0 个登录页。`actor_role` 是 `execute_action` 工具的字符串参数（默认 `"store_manager"`，`agent/tools/action_tools.py:16`），LLM/调用方自报、零校验。`agent/tools/crud_tools.py:72` 的 update_task 更是硬编码 `actor={"role":"store_manager"}`。同一函数内信任级别自相矛盾：`workspace_name`/`org_unit_id` 走可信的 `tenant_ctx` contextvar，`actor_role` 走不可信的 LLM 参数。
2. **组织/品类严重缺位**：组织只有 2 级（Region→Store），Brand/OrgGroup/Channel 不存在；品类是 `Product.category` 扁平字符串；`OrgUnit.Tree`（`agent/engine/workspace.py:11-47`）实现了 ancestors/descendants/visible_units 但**零业务调用**，Repository 用精确字符串匹配不过树。
3. **人员域不独立 + RBAC 断链**：Employee 寄生在 organization domain；`Employee.role`(clerk/manager/admin，`agent/engine/schemas.py:11-14`) 与 `submission_criteria.roles`(store_manager/region_cat_mgr/...，见各 action YAML) 词汇表几乎不重叠。
4. **权限模型零基础**：没有 User/Role/Permission 本体；除 submission_criteria 的 `is`/`is_not` 外，Object/属性/Link/Tool 级权限完全不存在；`WorkspaceDef`（`agent/engine/pack.py:42-48`）无强制 domain 校验；customerA 干脆没有 organization domain。

---

## 1. 核心边界：agent 职能 vs workspace 职能

```
┌──────────────────────────────────────────────────────────────────┐
│ agent 层（内核，纯通用机制，零身份数据）                          │
│   • 认证机制代码：JWT 签发/校验、bcrypt wrap（纯工具函数）        │
│   • auth_middleware：验 token 签名 → auth_ctx（user_id+ws 校验）  │
│   • /api/auth/login 端点：编排（遍历 workspace 调 verify）+ 签 JWT│
│   • PermissionEvaluator：通用求值引擎，读 workspace 的权限数据    │
│   • JWT_SECRET（.env）—— 机制配置，非身份数据                    │
│   • agent 层 audit：login/logout/token_fail 等认证事件            │
├──────────────────────────────────────────────────────────────────┤
│ workspace 层（每个 workspace 自管，声明式建模即接入）            │
│   • identity domain（新增必备）：                                 │
│       - 本体：User(含 password_hash) / Role / PermissionGrant     │
│       - 数据：users.json / roles.json / permission_grants.json     │
│       - verify_credentials(username, password) 函数               │
│   • organization domain：5 级 OrgUnit 树 + 数据                   │
│   • personnel domain：Employee（user_id 反向引用 User）           │
│   • category domain：5 级 Category 树 + 数据                      │
│   • business domains：原有本体（clearance/repair/...）+ 权限元数据│
│   • tool_manifest.yaml：本 workspace 工具的权限声明               │
│   • workspace 层 audit：tool/action/permission 事件               │
├──────────────────────────────────────────────────────────────────┤
│ LLM agent 实例 —— 只读消费身份（从 contextvar）                   │
│   • actor/权限对它必须是只读输入，绝不让它自报                    │
└──────────────────────────────────────────────────────────────────┘
```

**协议面**：agent 求值引擎只懂通用原语（`user_id` / `role` / `resource_type` / `resource_id` / `action` / `effect`）；具体角色字符串、组织树、品类树、TTL 权限声明都由 workspace 提供，agent 不硬编码任何业务词。

---

## 2. 设计决策（8 条）

### 2.1 身份存储

- User/credentials 存 workspace（`workspace/<ws>/data/users.json`），agent 层**零身份数据**。
- 一个 User 在多 workspace 可有对应 Employee（实名制：跨 workspace username 一致，password_hash 各自独立）。

### 2.2 登录流程（agent 编排 + workspace 验证）

1. 前端 `/login`：输入 username + password（不选 workspace——agent 来发现）。
2. `POST /api/auth/login`（agent 层）：遍历 `all_workspace_dirs()` → 调每个 ws 的 `verify_credentials(username, password)` → 收集认成功的 ws → `memberships: [{workspace_name, user_id, role, org_unit_id, display_name}]`。
3. 签 JWT（含 `user_id` + `session_id` + `ws_list`，**不锚定具体 ws**）→ 返回 `{token, memberships}`。
4. 前端选 ws → 后续请求带 `Authorization: Bearer <token>` + `X-Workspace: <ws>`。
5. auth_middleware：验签 + **校验 user 确在该 ws 的 users.json**（防跨 ws 越权）→ `auth_ctx`。

### 2.3 权限模型本体化

- identity domain 是第 4 类必备 capability domain（含 User/Role/PermissionGrant）。
- 角色字符串词汇表（store_manager/region_cat_mgr/...）由各 workspace 自定义。
- `system_admin` role：workspace 自管，有特殊 PermissionGrant（全 allow 或 eval bypass）；首次初始化引导种入。

### 2.4 权限声明位置：本体 TTL 元数据

权限规则放本体 TTL 里作为资源元数据。每个 Object Type / 属性 / Action Type / Link Type 可声明：

```turtle
:NearExpiryProduct a :Class ;
    :read_roles "store_manager, region_cat_mgr, store_clerk" ;   # 正向：谁能读此 Object
    :read_except "" ;                                             # 反向：除此外都可读
    :write_roles "store_manager" ;                                # 正向：谁能经 Action 写
    :write_except "" ;
    :property [
        :name "cost_price" ;
        :read_except "store_clerk" ;                              # 反向：店员不可读此属性
        :write_roles "procurement"                                # 正向：只有采购能改
    ] .
```

- Link/Action/Tool 同样支持 `use_roles` / `use_except` / `execute_roles` / `execute_except`。
- PermissionGrant 实例数据（`permission_grants.json`）作为 runtime override，优先级高于 TTL 默认。

### 2.5 正反向 + allow-by-default 求值语义

```
1. 无 TTL 元数据 + 无 PermissionGrant → ALLOW（allow-by-default）
2. read_roles="A,B,C"（正向）→ 只有 A/B/C 可读
3. read_except="X,Y"（反向）→ 除 X/Y 外都可读
4. 同时声明 → read_roles 基础上排除 read_except（read_roles="A,B,C" + read_except="B" → A,C）
5. PermissionGrant 显式 allow/deny → 覆盖 TTL（runtime override）
6. deny 永远赢过 allow（安全优先，无论来自 TTL except 还是 Grant deny）
7. system_admin role → 全 allow（绕过 TTL 检查）
```

### 2.6 属性级权限求值：Tool 层校验 + 提示

- Repository 不自动 mask。query_entity 等 tool 在返回时按 actor 权限处理：
  - **不可读属性**：从返回中隐去 + 在响应文本里明确告知 `"以下字段无权访问已隐去：salary, cost_price"`（LLM 能理解、不幻觉）。
  - **完全无权读的 Object Type**：返回 `"无权访问 NearExpiryProduct"`。
- execute_action：参数校验时检查 actor 是否有权写每个参数对应的属性。

### 2.7 组织 5 级 + 品类 5 级

- **Organization**：`Brand → OrgGroup → Channel → Region → Store`（生鲜部门特有第 6 级 `Dept`）。OrgUnit 字段含 `company_code` / `profit_center_code` / `cost_center_code`。
- **Category**：`Department → CategoryGroup → Category → SubCategory → Variety`。Product 加 `category_id` 引用 Category.id（保留旧 category 字符串做 deprecated 兼容）。
- 两树都自引用 `parent_of` Link（via=parent_id）。
- `OrgUnit.Tree` 接入 Repository：`TenantContext.matches(record)` 用 descendants 计算可见集合，取代精确字符串匹配。

### 2.8 Tool 权限声明机制

Tool 是 Python 代码不在 TTL，用 workspace 的 `tool_manifest.yaml` 声明：

```yaml
# workspace/retail/tool_manifest.yaml
tools:
  - name: query_near_expiry
    use_roles: "store_manager, store_clerk, region_cat_mgr"
    use_except: ""
  - name: execute_action
    use_roles: "*"   # 所有角色可用（具体 action 由 Action 级权限再校验）
  - name: create_entity
    use_roles: "system_admin"   # 通用 CRUD 锁为 admin
```

内核 8 个工具的 manifest 放 agent 层（`agent/tools/manifest.yaml`），workspace 专属工具放各 workspace。PermissionEvaluator 合并两者求值。

---

## 3. 数据模型

### 3.1 identity domain 本体（3 个新 Object Type + 1 可选）

```turtle
:User a :Class ;
    :labelZH "用户"@zh ;
    :properties "id, username, password_hash, display_name, status:UserStatus, created_at:datetime" ;
    :storage "users.json" ;
    :edits_only_via_actions "true" ;
    :read_roles "system_admin" ;                       # 只有 admin 可读用户列表
    :property [:name "password_hash" :read_roles ""] . # 任何角色都不可读（正向空=无人）

:Role a :Class ;
    :labelZH "角色"@zh ;
    :properties "id, name, display_name, description" ;
    :storage "roles.json" .

:PermissionGrant a :Class ;
    :labelZH "权限授予"@zh ;
    :properties "id, role_id, resource_type, resource_id, action, effect, scope_json" ;
    :storage "permission_grants.json" ;
    :edits_only_via_actions "true" .
    # resource_type: object_type | property | action | link | tool
    # resource_id: NearExpiryProduct / NearExpiryProduct.cost_price / create_clearance_task / has_employee / query_entity
    # action: read | write | execute | traverse | use
    # effect: allow | deny
    # scope_json: {"org_unit_id": "region_east"} 或 "*"（叠加 org/category 范围）

:Session a :Class ;   # 可选：refresh token 管理
    :properties "id, user_id, refresh_token_hash, expires_at, ..."
```

### 3.2 organization domain 扩展（5 级）

```turtle
:OrgUnit a :Class ;
    :labelZH "组织单元"@zh ;
    :properties "id, parent_id, level:OrgUnitLevel, name, code, company_code, profit_center_code, cost_center_code" ;
    :storage "org_units.json" .

:parent_of a rdfs:Property ;   # 自引用
    :domain :OrgUnit ; :range :OrgUnit ; :via "parent_id" .
```

`OrgUnitLevel` enum: `brand / org_group / channel / region / store / dept`。

### 3.3 category domain（新建）

```turtle
:Category a :Class ;
    :properties "id, parent_id, level:CategoryLevel, name, code" ;
    :storage "categories.json" .

:parent_of a rdfs:Property ;
    :domain :Category ; :range :Category ; :via "parent_id" .
```

`CategoryLevel` enum: `department / category_group / category / sub_category / variety`。Product 加 `category_id` 字段。

### 3.4 personnel domain（从 organization 拆出）

Employee 加 `user_id` 字段（反向引用 User.id）+ `department_id`。`EmployeeRole` enum 扩展对齐 submission_criteria.roles 词汇表（store_manager/store_clerk/region_cat_mgr/system_admin/...）。

---

## 4. PermissionEvaluator API

```python
class PermissionEvaluator:
    """通用权限求值引擎。读 workspace 的 TTL 元数据 + PermissionGrant 数据。

    求值顺序：system_admin 短路 → PermissionGrant runtime → TTL 元数据 → allow-by-default。
    """
    def can_use_tool(self, actor, tool_name, tc) -> PermissionResult
    def can_read_object(self, actor, obj_type, tc) -> PermissionResult
    def can_write_object(self, actor, obj_type, tc) -> PermissionResult
    def can_execute_action(self, actor, action_type, params, tc) -> PermissionResult
    def can_traverse_link(self, actor, link_type, tc) -> PermissionResult
    def readable_properties(self, actor, obj_type, tc) -> set[str]   # 返回可读属性名集合
    def writable_properties(self, actor, obj_type, tc) -> set[str]

    # 内部 helper：
    def _eval_roles(self, ttl_meta, actor_role) -> bool   # 处理 roles/except 正反向
    def _eval_grant(self, grants, actor, resource, action) -> Optional[bool]
    def _in_org_scope(self, actor, record_org, tc) -> bool   # OrgUnit.Tree descendants
```

每个方法内部：
1. `actor.role == system_admin` → allow 短路
2. 查 PermissionGrant（runtime，deny 优先）→ 有命中返回
3. 查 TTL 元数据（read_roles/read_except，正反向逻辑）→ 有声明按声明
4. 都无 → allow-by-default
5. org/category scope 叠加（用 OrgUnit/Category 树求 visible 集合）

失败抛 `PermissionDenied`（新增 error），审计日志写入。

---

## 5. 工作包分解（WP0-WP8，递进，每 WP 独立 commit + 验证）

### WP0：设计文档定稿（本文档）

### WP1：identity domain 本体 + 数据（workspace 层）
- 标准 TTL 模板（写入 `docs/design/manual/templates/`）：`identity_domain.ttl.template`。
- 三家 workspace 各建 `ontology/domains/identity/domain.ttl` + `actions/`（user CRUD actions）。
- 数据：`workspace/<ws>/data/users.json`（种子用户 + bcrypt hash）+ `roles.json`（标准角色枚举）+ `permission_grants.json`（初始基本为空）。
- workspace identity helper：`workspace/<ws>/identity.py` 导出 `verify_credentials(username, password) -> Optional[User]`、`get_employee_by_user(user_id)`。
- 首次初始化引导：种入 system_admin role + 一个 admin User（bootstrap 时检测 users.json 为空则创建）。
- `agent/engine/schemas.py`：加 `UserStatus` / `ResourceType` / `PermissionAction` / `PermissionEffect` 枚举。
- **验证**：pytest；`verify_credentials("EMP-001", "...")` 在 jjy 返回 User；密码错返回 None。

### WP2：认证机制（agent 层）
- 新增 `agent/engine/auth.py`：`hash_password` / `verify_password`（bcrypt wrap）、`create_access_token` / `create_refresh_token` / `decode_token`（pyjwt）、`AuthContext` dataclass。
- 新增 `agent/main.py` 端点：`POST /api/auth/login`、`POST /api/auth/refresh`、`GET /api/auth/me`、`POST /api/auth/logout`。
- 新增 `@app.middleware("http") async def auth_middleware`：验 Authorization Bearer → auth_ctx；**校验 user 确在 X-Workspace 指向的 ws 的 users.json**（跨 ws 越权防护）；豁免 `/api/auth/login` + `/health`。
- `agent/pyproject.toml`：加 `pyjwt`、`passlib[bcrypt]`。
- `.env.example`：加 `JWT_SECRET=`、`JWT_ACCESS_TTL=7200`、`JWT_REFRESH_TTL=604800`。
- agent 层认证审计：`agent/data/auth_audit.json`。
- **关键约束**：auth_middleware 在 WP2 只注入 auth_ctx，**不强制**（豁免所有路径）；强制切换在 WP6。
- **验证**：新增 `agent/tests/test_auth.py`；现有 pytest 全绿。

### WP3：权限元数据扩展（TTL + parser）
- `agent/engine/parser.py`：解析新 TTL 元数据 `:read_roles / :read_except / :write_roles / :write_except / :use_roles / :use_except / :execute_roles / :execute_except` 到对应 dataclass 字段。
- `agent/engine/parser.py` dataclass 扩展：ObjectType 加 `read_roles/read_except/write_roles/write_except`；Property 加同样字段；ActionType/LinkType 加 use/execute 对应字段。
- 现有 retail/customerA 本体补充权限元数据。
- tool_manifest 机制：`workspace/<ws>/tool_manifest.yaml` + `agent/tools/manifest.yaml` + parser/loader。
- **验证**：pytest（parser 测试覆盖新元数据）；启动确认本体解析无错；TTL 元数据可经 admin API 查询返回。

### WP4：5 级组织/品类 + 强制 domain（含数据迁移）
- `agent/engine/pack.py`：
  - `CapabilityDomain` 加 `kind: str = "business"`（值：organization/personnel/category/identity/business）。
  - `WorkspaceDef.required_domain_kinds = ["organization","personnel","category","identity"]`。
  - `register_workspace_dir` 加校验：4 类必备 domain 存在 + 含必需 Object Type。
- 标准 TTL 模板：`organization_domain.ttl.template` / `category_domain.ttl.template` / `personnel_domain.ttl.template`。
- 三家 workspace 数据迁移（最大单块）：
  - retail/jjy：扩 organization 到 5 级；新建 category domain；personnel 从 organization 拆出。
  - customerA：新建 organization/personnel/category/identity 四个 domain + 数据。
- `agent/engine/schemas.py`：加 `OrgUnitLevel` / `CategoryLevel` 枚举；扩 `EmployeeRole` 对齐词汇表。
- `agent/engine/parser.py`：支持 `:domainKind "organization"` TTL 元数据。
- **验证**：pytest；`bootstrap()` 启动确认三家 workspace 注册过校验；`query_entity("OrgUnit")`/`query_entity("Category")` 返回树数据。
- **注**：本 WP 可拆 WP4a（pack 校验 + 模板）/ WP4b（retail/jjy 迁移）/ WP4c（customerA 迁移）。

### WP5：PermissionEvaluator 求值引擎（agent 层）
- 新增 `agent/engine/permission.py`：`PermissionEvaluator`、`PermissionResult`、求值方法（§4 API）。
- 新增 `agent/engine/org_tree.py`：把现有 `OrgUnit.Tree`（workspace.py dead code）抽成独立模块 + descendants/ancestors/visible_units + 接入 Repository。
- `agent/engine/tenant.py:matches`：改用 OrgUnit.Tree.descendants(user_org_unit) 计算可见集合；`"*"` 保留总部语义。
- `agent/engine/executor.py:_check_submission`：扩展操作符（gte/lte/matches/includes/value_ref，5 个）+ 接入 PermissionEvaluator.can_execute_action。
- Tool 拦截层：`agent/tools/shared.py` 包装所有 tool 调用前过 `PermissionEvaluator.can_use_tool`。
- query_entity 等 tool 加 Object 级读权限 + 属性级 mask + 不可读字段提示（§2.6）。
- execute_action / confirm_action 加参数属性写权限校验。
- workspace 层 audit：`workspace/<ws>/data/audit_logs.json` + `agent/engine/audit.py`。
- **验证**：新增 `agent/tests/test_permission.py`（角色矩阵 / 正反向 TTL / 属性级 / org-scope / Grant override）；playwright e2e。

### WP6：信任修复（堵 actor 漏洞 + dashboard 越权）
- `agent/engine/errors.py`：加 `PermissionDenied(OntologyError)`。
- `agent/tools/action_tools.py`：删 `actor_role` 形参；execute_action/confirm_action 内部从 auth_ctx → Employee → actor 派生。
- `agent/tools/crud_tools.py:72`：删硬编码，同上。
- `agent/tools/shared.py`：新增 `_get_actor()` helper。
- `agent/main.py:dashboard_metrics` + `dashboard_*` 全部端点：改用请求级 `tenant_ctx` + auth_ctx；删 `inst.tenant_context`（org_unit_id="*" 越权 bug）。
- auth_middleware 切换为**强制**（除豁免路径外，无 token → 401）。
- **验证**：新增 `agent/tests/test_actor_trust.py`；现有 pytest 全绿（部分测试补 mock auth_ctx fixture）。

### WP7：前端（登录 + 动态选择器 + 403 UI）
- 新增 `frontend/app/login/page.tsx`、`frontend/app/auth-context.tsx`。
- `frontend/app/layout.tsx`：包裹 AuthProvider；`headers()` 加 Authorization。
- `frontend/app/workspace-context.tsx`：默认 ws 从 memberships[0] 读；store 选择器改 `/api/workspaces/{ws}/org-units`。
- `frontend/app/home-page.tsx`：删硬编码 `STORES`；store/ws 选择器从 API 拉。
- 新增 `frontend/app/api/auth/[endpoint]/route.ts`（BFF 转发到后端 8123）。
- 403 UI：`renderToolCalls` 加 `permission_denied` 类型渲染 + chat 顶层 toast。
- 可选：权限管理 UI（admin 查看用户/角色/PermissionGrant），如工期紧延后。
- **验证**：playwright e2e（登录 → 选 ws → 对话 → 切 store → 数据变化 → 403）；TS 编译无错。

### WP8：文档同步
- `docs/design/00-architecture.md`：加认证层、PermissionEvaluator、4 类必备 domain、org/category 5 级章节。
- `docs/design/20-api-data-contract.md`：加 /api/auth/* 端点、User/Role/PermissionGrant/OrgUnit/Category 数据模型、Authorization header 链路、TTL 权限元数据语法。
- `docs/design/30-development-guide.md`：加权限开发规范、新增 workspace 必须建 4 类 domain 的步骤、tool_manifest 写法。
- `docs/design/40-ontology-modeling-spec.md`：加组织/品类建模硬规范、user_id 反向引用规范、role 词汇表统一、TTL 权限元数据规范。
- `docs/design/manual/01-onboarding.md`：Phase A 加 4 类必备 domain；新增 Phase G（权限配置）。
- `docs/design/manual/02-templates.md`：加新模板索引。
- `docs/design/roadmap.md`：v2-权限/v2-本体/组织5级/品类5级 标 ✅ 完成。

---

## 6. 执行顺序（强制）

```
WP0（设计评审通过）
  → WP1（identity 本体+数据，pytest 全绿）
  → WP2（认证机制，pytest 全绿）
  → WP3（权限元数据扩展，pytest 全绿）
  → WP4（4 类必备 domain + 数据迁移，pytest + bootstrap 通过）
  → WP5（PermissionEvaluator，pytest + permission 矩阵测试通过）
  → WP6（信任修复 + 强制 auth，pytest 全绿）
  → WP7（前端，playwright e2e 通过）
  → WP8（文档同步）
```

每 WP 独立 commit，前一个不绿不进下一个。WP4 / WP5 是大头，分别可拆子 commit。

---

## 7. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| WP4 数据迁移破坏现有 e2e（retail 数据大改） | 🔴 高 | 保留旧字段做 deprecated 兼容；pytest fixture 同步；逐 workspace 迁移；WP4 拆 a/b/c |
| WP6 强制 auth 后现有测试全挂 | 🔴 高 | WP2 auth_middleware 只注入不强制，强制切换放 WP6；测试加 mock auth_ctx fixture |
| 权限元数据铺到所有本体资源工程量大 | 🔴 高 | 渐进：先核心业务实体（Task/NearExpiryProduct/RepairTicket），次要实体后续补；allow-by-default 让"未声明=允许"过渡期可用 |
| JWT secret 泄漏 | 🟡 中 | secret 只在 .env 不进 git；token TTL 短（2h）；refresh 7d |
| OrgUnit.Tree 接入后性能 | 🟡 中 | request scope 缓存 visible_units per (workspace, user_root)；MVP 小数据量不卡 |
| 跨 ws 越权（token 在 A ws 签发用于访问 B ws） | 🟡 中 | auth_middleware 校验 user 确在 X-Workspace 指向 ws 的 users.json |
| 属性级 mask 导致 LLM 困惑 | 🟡 中 | 不可读字段在响应文本明确告知，不静默裁剪；LLM 测试覆盖 |
| PermissionGrant 与 TTL 元数据优先级混乱 | 🟡 中 | 文档明确：Grant > TTL > allow-by-default；deny > allow；测试覆盖 |
| 工期（WP3+WP4+WP5 都是大块） | 🔴 高 | 9 个 WP 递进；每 WP 独立 commit + 验证；allow-by-default 让中间态可用 |
| 前端登录/refresh 链路复杂度 | 🟡 中 | 不引入 next-auth；先 access token only，refresh 可后置 |

---

## 8. 成功标准（全局）

1. `POST /api/auth/login` 实名登录，返回 JWT + memberships。
2. 所有 `/api/copilotkit` 请求必带有效 Authorization Bearer；无 token/过期/跨 ws 越权 → 401。
3. `actor_role` 不再是 LLM 工具参数；actor 从 auth_ctx 派生，无法伪造。
4. 每个 workspace 注册时校验含 organization/personnel/category/identity 4 类 domain；缺则启动失败。
5. identity domain 含 User/Role/PermissionGrant 本体 + 数据；`verify_credentials` 可验密码。
6. OrgUnit 树 5 级 + Category 树 5 级在 retail/jjy/customerA 三家数据可查。
7. Repository.read 过滤走 OrgUnit.Tree.descendants；store_manager 只看本店，region_cat_mgr 看本 region。
8. PermissionEvaluator 支持 Tool/Object/属性/Action/Link 5 类资源权限求值；正反向语法都支持；allow-by-default；deny 优先；system_admin 短路。
9. 角色矩阵测试覆盖所有 role × 主要 tool/action 组合。
10. 属性级权限：clerk 查 Employee 不见 salary，响应文本明确告知。
11. dashboard 不再用 `org_unit_id="*"`；按请求用户 org_scope 过滤。
12. 前端 /login 登录 → 选 ws → 选 store → 对话；403 有 UI 反馈。
13. pytest 全套绿；playwright e2e（含 403 场景）绿。
14. roadmap.md / architecture.md 等文档同步更新。

---

## 9. 范围外（明确不做）

- HMAC 快照冻结、26 生命周期 hook、6 PermissionMode、6 层 cascade 瀑布、CategoryScope coverage_depth、RuleSource 优先级（legacy 重型机制全部留接口预留/TODO 注释）。
- 真实 IdP 集成（OAuth/OIDC、SSO、企业微信/钉钉）—— 本轮用户名密码 + JWT，IdP 留 v2.1。
- 多用户并发会话管理 / token 撤销列表 —— access token 短 TTL 即可，refresh 撤销留 v2.1。
- PostgreSQL 迁移（roadmap v2-存储独立工作包）。
- 组织架构 / 品类 / 权限管理 CRUD UI（本轮只做读取展示，admin CRUD UI 留后续）。
- 嵌套 AND/OR 权限逻辑（如 (role=A AND org=X) OR (role=B AND category=Y)）—— 留 v3。
- DC（配送中心）维度、职能域 Domain 维度（legacy 三维 scope 之一）—— 留 v2.2。
