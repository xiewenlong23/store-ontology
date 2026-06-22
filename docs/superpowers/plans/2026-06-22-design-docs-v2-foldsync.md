# Canonical 文档 v2 落地内容回填 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已落地的 v2 能力（PG 双后端 / 认证+RBAC×ABAC / 组织品类 5 级 / identity+personnel domain / admin 本体 CRUD / tool_manifest / 动态 workspace header）从 docs/superpowers/specs 回填到 docs/design 的 canonical 文档，消除内部自相矛盾与内容缺失。

**Architecture:** 方案 C——按文档角色差异化深度。architecture 前半部分去矛盾 + 交叉引用到 §11（不重写 §11）；40-ontology-modeling-spec 与 30-development-guide 实质补 v2 章节（结论级 + 链接到 spec）；README 修徽章；20-api-data-contract 核验（实测已基本覆盖，仅一处小修）。canonical 答「是什么/怎么用」，spec 答「为什么」——不复制 spec 细节，避免再次漂移。

**Tech Stack:** 纯文档（Markdown）。无代码、无测试。验收靠 grep 巡检 + 人工通读。

**Spec:** [`docs/superpowers/specs/2026-06-22-design-docs-v2-foldsync-design.md`](../specs/2026-06-22-design-docs-v2-foldsync-design.md)

---

## 编辑约定（所有 task 通用）

1. 每个 step 给出**精确** old_string → new_string。若 Edit 报「old_string 不唯一」，用更长的上下文使其唯一（不要用 replace_all，除非 step 明确说全替换）。
2. 每次编辑后**不必 re-read 验证**（Edit 成功即生效）；但每个 task 末尾的「通读验收」step 要 Read 改动段落确认上下文连贯。
3. **绝对不改仍属 v2 的内容**（spec §5 清单）：Interface Type / Shared Property / Ontology Branching / 多 Agent / BPM / submission_criteria 嵌套 AND/OR / DC 维度 / 职能域 Domain / 6 PermissionMode / 6 cascade / HMAC 快照 / 26 hooks / token 撤销列表 / OAuth-SSO / 多副本缓存失效通知。这些保留「🔜 v2」。
4. 中文标点与原文件保持一致（全角括号 `（）`、顿号 `、`、破折号 `——`）。
5. 提交信息走 conventional commits 中文描述，与近期 `docs:` 提交风格一致。

---

## Task 1: architecture 去矛盾 + README 徽章修正

**Files:**
- Modify: `docs/design/00-architecture.md`（多处：L33/57/61/178/219/455/469-470/486/627）
- Modify: `docs/design/README.md:29`

本 task 只做「去矛盾 + 交叉引用」，**不重写 §11**（§11 已是权威 v2 章节）。原则：已落地的「🔜 v2 / 未来」改 ✅ + 指向 §11 或 roadmap；仍 v2 的保留。

- [ ] **Step 1.1: 五层架构图第 5 层（L33）——workspace 切换 UI 已落地**

old_string:
```
│  现状：CopilotKit v1.57（9 个 renderToolCalls，clearance 专用）           │
│  未来（v2）：A2UI 标准渲染、多工作目录切换 UI、定时自动化作业 UI              │
```
new_string:
```
│  现状：CopilotKit v1.57 + 多工作目录切换 UI（✅ 已落地，见 §11）            │
│  🔜 v2：A2UI 标准渲染、定时自动化作业 UI、权限/审计管理 UI                    │
```

- [ ] **Step 1.2: 五层架构图第 2 层（L57）——组织/品类 5 级已落地**

old_string:
```
│  未来（v2）：组织5级 / 品类5级 / DC / 职能域（零售工作目录深化）              │
```
new_string:
```
│  ✅ 已落地：组织5级 / 品类5级 / 4 类必备 domain（见 §11.4/§11.5）           │
│  🔜 v2：DC 维度 / 职能域 Domain（三维 scope 之一）                          │
```

- [ ] **Step 1.3: 五层架构图第 1 层（L61）——PG 存储已落地**

old_string:
```
│  存储：JSON 文件（现状）via Repository 抽象 → PostgreSQL+JSONB（v2）        │
```
new_string:
```
│  存储：JSON / PostgreSQL+JSONB 双后端（✅ 已落地，见 roadmap §1）           │
│        配 DATABASE_URL 走 PG，缺失回落 JSON，Repository 接口不变             │
```

- [ ] **Step 1.4: 四概念分工表 Interface Type 行（L78）——保留 v2（确实未落地）**

本 step **不改**。Interface Type 确实还是 v2 元数据预留。仅在此记录「已核对，不动」。

- [ ] **Step 1.5: §3.1 资源类型 Interface Type（L159）——保留 v2（确实未落地）**

本 step **不改**。同上理由。

- [ ] **Step 1.6: §3.3 Repository 实现树（L178）——PG 已落地**

old_string:
```
    └── 未来实现（🔜 v2）：PostgresRepository（JSONB）、GraphRepository
```
new_string:
```
    ├── ✅ 已实现：PgDataRepository / PgOntologyRepository（PostgreSQL+JSONB）
    └── 🔜 远期：GraphRepository（复杂关系遍历，见 roadmap §1）
```

- [ ] **Step 1.7: §3.4 Action Type 契约的 submission_criteria 现状（L219）——操作符全集已落地**

old_string:
```
**现状**（`agent/engine/executor.py`）：submission_criteria 做 `roles` 白名单 + 条件（`is`/`is_not` 操作符）。🔜 复杂操作符（matches/includes/gte/value_ref）与嵌套逻辑留 v2。
```
new_string:
```
**现状**（`agent/engine/executor.py`）：submission_criteria 做 `roles` 白名单 + 条件，操作符已落地全集 `is`/`is_not`/`gte`/`lte`/`gt`/`lt`/`matches`/`includes`/`value_ref`（见 §11.7）。🔜 嵌套 AND/OR 逻辑留 v2。
```

- [ ] **Step 1.8: §9 技术选型表数据存储行（L455）——PG 已落地**

old_string:
```
| 数据存储 | JSON 文件 | MVP 零依赖，未来通过 Repository 抽象迁移到 PostgreSQL+JSONB |
```
new_string:
```
| 数据存储 | JSON / PostgreSQL+JSONB 双后端 | 配 `DATABASE_URL` 走 PG（JSONB + GIN 索引），缺失自动回落 JSON；Repository 接口不变（roadmap §1） |
```

- [ ] **Step 1.9: §10 生产部署节标题 + 正文（L469-470）——PG 已落地，标题不再「v2 预留」**

old_string:
```
### 生产部署（v2 预留）
前端 `next build` → Nginx 托管；后端 `uvicorn main:app --workers N`；Nginx 反向代理 `/api/copilotkit` → 后端。数据存储 v2 从 JSON 迁移到 PostgreSQL+JSONB（换 Repository 实现，上层接口不变）。
```
new_string:
```
### 生产部署
前端 `next build` → Nginx 托管；后端 `uvicorn main:app --workers N`；Nginx 反向代理 `/api/copilotkit` → 后端。数据存储走 PostgreSQL+JSONB（生产配 `DATABASE_URL`）；Repository 接口不变，缺失或连不上自动回落 JSON（roadmap §1）。
```

- [ ] **Step 1.10: 附录 A 数据一致性表 JSON 并发行（L486）——PG 已落地，补充双后端表述**

old_string:
```
| JSON 文件并发写入损坏 | Repository 层 `fcntl.flock` 文件锁（MVP，仅 Unix）；v2 换 PG 后由数据库事务保证 |
```
new_string:
```
| JSON 文件并发写入损坏 | JSON 后端：Repository 层 `fcntl.flock` 文件锁（Unix）+ 原子写；PG 后端：由数据库事务保证（已落地，roadmap §1） |
```

- [ ] **Step 1.11: §11.8 范围外清单——删「PostgreSQL 迁移」（WP1–WP5 已落地）**

old_string:
```
- token 撤销列表 / 多设备会话
- PostgreSQL 迁移
- 组织/品类/权限管理 CRUD UI
```
new_string:
```
- token 撤销列表 / 多设备会话
- 组织/品类/权限管理 CRUD UI
```

（`PostgreSQL 迁移` 已于 WP1–WP5 落地，不应再列在「范围外」。其余条目确实未落地，保留。）

- [ ] **Step 1.12: README roadmap 行徽章（L29）**

old_string:
```
| **演进路线** | [`roadmap.md`](./roadmap.md) | v2 方向：存储/权限/本体深化/自动化/多 Agent/UI。**均未落地**，仅供方向参考 |
```
new_string:
```
| **演进路线** | [`roadmap.md`](./roadmap.md) | v2 方向：存储/权限/本体深化/自动化/多 Agent/UI。每节带 ✅/🔜 标注，部分已落地、部分前瞻 |
```

- [ ] **Step 1.13: README 顶部「前瞻（🔮 未实现）」分组标题——roadmap 不再全前瞻**

old_string:
```
### 前瞻（🔮 未实现）

| 文档 | 路径 | 一句话说明 |
|------|------|-----------|
| **演进路线** | [`roadmap.md`](./roadmap.md) | v2 方向：存储/权限/本体深化/自动化/多 Agent/UI。每节带 ✅/🔜 标注，部分已落地、部分前瞻 |
```
new_string:
```
### 演进路线（部分已落地）

| 文档 | 路径 | 一句话说明 |
|------|------|-----------|
| **演进路线** | [`roadmap.md`](./roadmap.md) | v2 方向：存储/权限/本体深化/自动化/多 Agent/UI。每节带 ✅/🔜 标注，部分已落地、部分前瞻 |
```

- [ ] **Step 1.14: 验收——grep 巡检 00-architecture 无残留矛盾**

Run（在 repo 根）:
```bash
rg -n "MVP 零依赖|未来通过 Repository|（v2 预留）|未来实现（🔜 v2）：PostgresRepository|未来（v2）：组织5级|未来（v2）：A2UI 标准渲染、多工作目录切换" docs/design/00-architecture.md
```
Expected: **无输出**（所有已落地项的旧措辞都已改）。

再 Run（确认仍 v2 的措辞保留，这是**应当**存在的）:
```bash
rg -n "🔜 v2|（v2，MVP 不实现|列为 v2|留 v2" docs/design/00-architecture.md
```
Expected: 仍有输出（Interface Type / 多 Agent / Branching / BPM / Redis preview 升级 / 嵌套逻辑 等确实未落地）。

- [ ] **Step 1.15: 验收——通读 00-architecture §1/§2/§3/§9/§10/附录A + README**

Read `docs/design/00-architecture.md` 行 27-65（五层图）、169-180（Repository 树）、442-490（技术选型/部署/一致性）、510-640（§11 不改，只确认未被前面编辑波及）。Read `docs/design/README.md` 全文。确认：上下文连贯、无半句残留、交叉引用指向正确。

- [ ] **Step 1.16: 提交**

```bash
git add docs/design/00-architecture.md docs/design/README.md
git commit -m "docs(design): architecture 去矛盾 + README 徽章修正（v2 落地回填 1/3）

五层图/技术选型/部署/一致性表里把已落地的 PG 双后端、组织品类 5 级、
workspace 切换 UI、submission_criteria 操作符全集从「🔜 v2」改为 ✅，
交叉引用 §11 / roadmap §1。仍属 v2 的（Interface Type / 多 Agent /
Branching / BPM / 嵌套逻辑）保留。§11.8 范围外删「PostgreSQL 迁移」
（WP1-WP5 已落地）。README roadmap 徽章从 🔮 改为「部分已落地」。"
```

---

## Task 2: 40-ontology-modeling-spec 实质补 v2 本体深化

**Files:**
- Modify: `docs/design/40-ontology-modeling-spec.md`（§5.4 措辞修正 + §6.3 存储补 PG + §7.3 单一事实源补 admin 入口 + 新增 §12 v2 本体深化节）

本 task 实质补 modeler 日常需要、目前完全缺失的 v2 建模内容。结论级 + 链接到 spec，不复制细节。

- [ ] **Step 2.1: §5.4 submission_criteria 操作符全集已落地（L273）**

old_string:
```
MVP `submission_criteria` 只实现 `roles` 白名单 + 简单参数条件（`is`/`is_not`/`equals`）；Palantir 式操作符全集与嵌套逻辑留 v2。
```
new_string:
```
`submission_criteria` 现已落地 `roles` 白名单 + 条件操作符全集 `is`/`is_not`/`gte`/`lte`/`gt`/`lt`/`matches`/`includes`/`value_ref`（详见架构文档 §11.7）；未知操作符保守返回 False（不抛）。🔜 嵌套 AND/OR 逻辑留 v2。
```

- [ ] **Step 2.2: §6.3 存储与多租户——补 PG 双后端（L319-324 整段替换）**

old_string:
```
### 6.3 存储与多租户

- 存储文件名 = 对应 Object Type 的 `{snake_case 复数}.json`，一一对应。
- 路径：`workspace/<pack>/data/{storage_file}`。租户隔离由路径承载（架构文档 §3.3）。
- 同一 Object Type 的所有实例存在同一个文件里（JSON 数组）。
- **禁止** 直接读写文件；**必须** 经 Repository 接口（`repository.read/write`），由它负责租户过滤、文件锁、edits-only-via-actions 检查。
```
new_string:
```
### 6.3 存储与多租户

**双后端**（✅ 已落地，详见 roadmap §1）：配 `DATABASE_URL` 走 PostgreSQL+JSONB（`object_types`/`object_type_properties`/`link_type`/`action_types`/`entities` 五表，关系列存核心查询字段 + JSONB 存复杂结构 + TenantContext 过滤索引 + JSONB GIN 索引）；缺失或连不上自动回落 JSON 文件，Repository 接口不变。

- **JSON 后端**：存储文件名 = 对应 Object Type 的 `{snake_case 复数}.json`，一一对应；路径 `workspace/<pack>/data/{storage_file}`；同一 Object Type 的所有实例存在同一个文件里（JSON 数组）。租户隔离由路径承载。
- **PG 后端**：所有 workspace 共享一套表，租户隔离由 `workspace_name + org_unit_id` 列 + 过滤索引承载（架构文档 §3.3）。
- **迁移**：`agent/scripts/import_to_pg.py` 把 TTL/YAML/JSON 幂等 upsert 进 PG，支持 `--workspace` / `--skip-data` / `--skip-schema` / `--dry-run`。
- **禁止** 直接读写文件或表；**必须** 经 Repository 接口（`repository.read/write`），由它负责租户过滤、文件锁/事务、edits-only-via-actions 检查。
```

- [ ] **Step 2.3: §7.3 单一事实源——补 admin CRUD 入口（L348-352 整段替换）**

old_string:
```
### 7.3 单一事实源一致性

- Object/Link Type 的权威定义在 **TTL**（`workspace/<pack>/ontology/domains/<域>/domain.ttl`）。代码侧（`agent/engine/schemas.py`）的 Pydantic 模型如镜像 Object 形状，**必须** 与 TTL 一致。Link Type 不再在代码里维护常量类（早期 `LinkTypes` 常量已删除，以 TTL 为唯一事实源）。
- Action Type 权威定义在 **YAML**，代码里的 `ActionType` 枚举 **必须** 与 YAML 一致。
- 发现两处定义冲突时，以本体定义文件（TTL/YAML）为准，修代码，**禁止** 反过来。
```
new_string:
```
### 7.3 单一事实源一致性

- Object/Link Type 的权威定义在 **TTL**（`workspace/<pack>/ontology/domains/<域>/domain.ttl`）。代码侧（`agent/engine/schemas.py`）的 Pydantic 模型如镜像 Object 形状，**必须** 与 TTL 一致。Link Type 不再在代码里维护常量类（早期 `LinkTypes` 常量已删除，以 TTL 为唯一事实源）。
- Action Type 权威定义在 **YAML**，代码里的 `ActionType` 枚举 **必须** 与 YAML 一致。
- 发现两处定义冲突时，以本体定义文件（TTL/YAML）为准，修代码，**禁止** 反过来。
- **Admin 本体 CRUD 入口**（✅ 已落地，§12.4）：`system_admin` 可在 admin UI 直接编辑本体 schema（Object/Link/Action Type），不必改 TTL/YAML + 重启；写端点经 `PgOntologyRepository` 落 PG，写后 `invalidate_workspace(ws)` 失效缓存。**源码侧 TTL/YAML 仍是权威定义**——admin 编辑是运行时建模补充入口，不取代源码事实源地位；新建工作目录 / 重建 PG 仍以 TTL/YAML 为准（详见 §12.4）。
```

- [ ] **Step 2.4: 新增 §12「v2 本体深化（已落地）」——插入到 §11 建模创建顺序之后、附录之前**

先 Read 确认 §11 末尾与附录开头的精确文本（用于 Edit 的锚点）。

锚点 old_string（§11 末尾的 Palantir 注释 + 附录标题）:
```
> Palantir 第 4 步 Interface（抽象形状）和第 6 步 Function（复杂计算）本规范列为 v2：Interface 留待有跨类型共享需求时引入，Function 不引入（计算经 Tool 暴露，§1.3）。

---

## 附录：与参考文档的对应关系
```

new_string（在中间插入 §12）:
```
> Palantir 第 4 步 Interface（抽象形状）和第 6 步 Function（复杂计算）本规范列为 v2：Interface 留待有跨类型共享需求时引入，Function 不引入（计算经 Tool 暴露，§1.3）。

---

## 12. v2 本体深化（✅ 已落地）

> **状态**：✅ 当前（2026-06-22 落地）。本节汇总已落地的 v2 本体建模要素。完整设计见 [`docs/superpowers/specs/2026-06-22-v2-auth-rbac-design.md`](../superpowers/specs/2026-06-22-v2-auth-rbac-design.md)。

### 12.1 必备 capability domain 升至 4 类

`register_workspace_dir` 校验 workspace 含**四类必备 domain**，缺则启动失败：

| domain | 必备 Object Type | 职责 |
|--------|-----------------|------|
| `organization` | `OrgUnit` | 组织树（5 级）+ 财务核算字段 |
| `personnel` | `Employee` | 员工，`user_id` 反向引用 identity User |
| `category` | `Category` | 品类树（5 级） |
| `identity` | `User` + `Role` + `PermissionGrant` | 认证身份与运行时权限覆盖 |

测试 fixture 用 `required_domain_kinds=[]` 关闭校验。

### 12.2 personnel domain 独立 + EmployeeRole 词汇表

- `Employee` 从 organization 拆出（独立 personnel domain），新增：
  - `user_id`：反向引用 identity domain 的 `User`（actor 由此派生）。
  - `department_id`：指向 `Category`（员工归属品类部门）。
- `EmployeeRole` 词汇表（store_manager / store_clerk / region_cat_mgr / system_admin / ...）**必须** 与 `submission_criteria.roles` 对齐——两者是同一套角色字符串，分叉会导致权限门控失效。

### 12.3 TTL 属性级权限元数据

ObjectType 属性 / Link 上声明正反向权限角色，PermissionEvaluator 据此求值（架构文档 §11.3）：

```turtle
# ObjectType 属性级（含嵌套 :property [ ... ]）
NearExpiryProduct :read_roles "store_manager, region_cat_mgr" ;
                 :read_except "system_admin" ;
                 :property [
                   :name "cost_price" ;
                   :read_roles "region_cat_mgr" ;   # 仅 region 及以上可见成本价
                   :read_except "*"
                 ] .

# Link 级遍历权限
has_employee :use_roles "store_manager, region_cat_mgr" ;
             :use_except "" .
```

- 正反向语法：`roles="A,B,C"`（正向）+ `except="X,Y"`（反向）+ `roles="*"` 通配 + `except="*"` 全员除外（敏感字段如 password_hash 用）。
- 求值顺序（详见 spec §2.5）：`system_admin` 短路 → PermissionGrant runtime override（deny 优先）→ TTL 元数据 → allow-by-default。
- **禁止** 在 Skill / Tool 里手写属性可见性判断——声明在 TTL，由 PermissionEvaluator 统一求值。

### 12.4 Admin 本体 Schema CRUD（建模补充入口）

`system_admin` 可在 `/admin` 页直接编辑本体 schema（Object / Link / Action Type），写后实时生效（无需重启）：

- **端点**：`POST/PUT/DELETE /api/admin/customers/{cid}/ontology/{objects|links|actions}[/{key}]`（9 个写端点，API 契约见 `20-api-data-contract.md` §1.5）。
- **落库**：经 `PgOntologyRepository.upsert_*` / `delete_*` 写 PG；HTTP 层只暴露本体 schema 的写（业务数据 CRUD 仍走对话/Action，保持 `edits-only-via-actions` 治理）。
- **失效**：每个写端点成功后 `invalidate_workspace(ws)` 丢弃进程内 `WorkspaceAgentInstance` 缓存，下次读取从 PG 重载。
- **事实源定位**：admin 编辑是**运行时建模补充入口**，不取代源码侧 TTL/YAML 的权威地位（§7.3）。新建工作目录 / 全量重建 PG 仍以 TTL/YAML 为准。

### 12.5 仍属 v2（未落地，不动现有标记）

Interface Type / Shared Property / Ontology Branching / 显式 Cardinality（1:1/1:N 声明）/ DC 维度 / 职能域 Domain 维度 / transfer·restock Action 契约 —— 保留 §1.3 / §3.3 / §4.4 的「v2」标记。

---

## 附录：与参考文档的对应关系
```

- [ ] **Step 2.5: 验收——grep 巡检 40-ontology 无残留过期措辞**

Run:
```bash
rg -n "MVP .submission_criteria. 只实现|未来通过 Repository|完整操作符（gte/matches/value_ref）留 v2" docs/design/40-ontology-modeling-spec.md
```
Expected: **无输出**。

再确认仍 v2 的保留:
```bash
rg -n "列为 .v2|留 v2|v2，MVP 不实现" docs/design/40-ontology-modeling-spec.md
```
Expected: 有输出（Interface Type / Shared Property / Branching / Cardinality 等确实未落地）。

- [ ] **Step 2.6: 验收——通读 40-ontology §5.4 / §6.3 / §7.3 / §12**

Read 上述四节，确认上下文连贯、§12 与 §11 不重复（§12 引用 §11.3/§11.7 而非复制）、附录锚点未断。

- [ ] **Step 2.7: 提交**

```bash
git add docs/design/40-ontology-modeling-spec.md
git commit -m "docs(design): 本体建模规范补 v2 深化（v2 落地回填 2/3）

§5.4 submission_criteria 操作符全集改 ✅；§6.3 存储补 PG 双后端 + 迁移脚本；
§7.3 单一事实源补 admin CRUD 入口（运行时补充，不取代 TTL/YAML 权威）；
新增 §12 v2 本体深化：4 类必备 domain / personnel 独立 + EmployeeRole /
TTL 属性级权限元数据 / admin schema CRUD / 仍 v2 清单。"
```

---

## Task 3: 30-development-guide 实质补 v2 开发流 + 20-api 核验

**Files:**
- Modify: `docs/design/30-development-guide.md`（§4 现状说明重写 + §4.2 措辞 + §5.2 措辞 + 新增 §4.3 auth/RBAC 开发 + 新增 §5.3 存储后端开发）
- Modify: `docs/design/20-api-data-contract.md:391`（一处小修：workspace header 静态→动态）

本 task 实质补 developer 日常需要、目前完全缺失的 auth/RBAC 与 PG 开发说明。

- [ ] **Step 3.1: §4 权限开发规范现状说明重写（L170）——完整 RBAC 已落地**

old_string:
```
> **现状说明**：当前已落地的只有 Action 级 `submission_criteria`（角色白名单 + 条件）和 Repository 的 workspace 隔离。完整 RBAC 引擎、审计日志留 v2（见 [`roadmap.md`](./roadmap.md)）。
```
new_string:
```
> **现状说明**：✅ 认证 + 完整 RBAC×ABAC 权限引擎已落地（2026-06-22，详见架构文档 §11）。本节先讲既有两项（edits-only / submission_criteria），再讲 v2 权限开发（§4.3）。审计日志仍 🔜 v2。
```

- [ ] **Step 3.2: §4.2 submission_criteria 措辞修正（L181）——操作符全集已落地**

old_string:
```
`submission_criteria` 独立于（未来的）粗粒度 RBAC：粗粒度答"谁能用 execute_action"，submission_criteria 答"给定 user+参数，这个 action 实例能否提交"。MVP 支持 `roles` 白名单 + `is`/`is_not` 条件。完整操作符（gte/matches/value_ref）留 v2。
```
new_string:
```
`submission_criteria` 独立于粗粒度 RBAC（§4.3）：粗粒度答"谁能用 execute_action"，submission_criteria 答"给定 user+参数，这个 action 实例能否提交"。现已支持 `roles` 白名单 + 操作符全集 `is`/`is_not`/`gte`/`lte`/`gt`/`lt`/`matches`/`includes`/`value_ref`（架构文档 §11.7）。🔜 嵌套 AND/OR 逻辑留 v2。
```

- [ ] **Step 3.3: §5.2 原子写入措辞修正（L201）——PG 已落地**

old_string:
```
已实现在 `agent/engine/repository.py`：`fcntl.flock` 文件锁（Unix）+ 临时文件 `os.replace` 原子替换 + 写入前 `.bak` 备份。v2 换 PG 后由数据库事务保证。
```
new_string:
```
- **JSON 后端**（`agent/engine/repository.py`）：`fcntl.flock` 文件锁（Unix）+ 临时文件 `os.replace` 原子替换 + 写入前 `.bak` 备份。
- **PG 后端**（`agent/engine/pg_data_repo.py`）：由数据库事务保证原子性（已落地，见 §5.3 / roadmap §1）。后端选择由 `is_pg_enabled() and ping()` 决定，缺失回落 JSON。
```

- [ ] **Step 3.4: 新增 §4.3「认证与权限开发（v2，✅ 已落地）」——插入到 §4.2 之后、§5 之前**

锚点 old_string（§4.2 末尾 + §5 标题）:
```
`submission_criteria` 独立于粗粒度 RBAC（§4.3）：粗粒度答"谁能用 execute_action"，submission_criteria 答"给定 user+参数，这个 action 实例能否提交"。现已支持 `roles` 白名单 + 操作符全集 `is`/`is_not`/`gte`/`lte`/`gt`/`lt`/`matches`/`includes`/`value_ref`（架构文档 §11.7）。🔜 嵌套 AND/OR 逻辑留 v2。

---

## 5. 错误处理规范
```

new_string（在中间插入 §4.3）:
```
`submission_criteria` 独立于粗粒度 RBAC（§4.3）：粗粒度答"谁能用 execute_action"，submission_criteria 答"给定 user+参数，这个 action 实例能否提交"。现已支持 `roles` 白名单 + 操作符全集 `is`/`is_not`/`gte`/`lte`/`gt`/`lt`/`matches`/`includes`/`value_ref`（架构文档 §11.7）。🔜 嵌套 AND/OR 逻辑留 v2。

### 4.3 认证与权限开发（v2，✅ 已落地）

> 详见架构文档 §11 与 [`docs/superpowers/specs/2026-06-22-v2-auth-rbac-design.md`](../superpowers/specs/2026-06-22-v2-auth-rbac-design.md)。本节给开发者日常接入要点。

**认证接入**：
- JWT（HS256，access 2h + refresh 7d）+ bcrypt 密码 hash。端点 `/api/auth/{login,refresh,me,logout}`（API 契约见 `20-api-data-contract.md` §1.4）。
- `auth_middleware`（`agent/main.py`）：验签 + token.ws 白名单含 `X-Workspace`（跨 ws 越权防护）→ `auth_ctx` contextvar。
- **强制模式** `AUTH_REQUIRED=true`（默认）：无 token / 过期 / 跨 ws 越权 → 401；豁免 `/api/auth/login` + `/health`。开发兜底设 `=false`。
- **新增 admin 端点鉴权**：用 `require_admin(actor)` 统一辅助（`agent/engine/admin_ontology_api.py`），`system_admin` 角色或 bootstrap 初始 `admin` 账号放行，其余 403。**禁止** 在各端点手写角色判断。

**PermissionEvaluator 求值**（`agent/engine/permission.py`）：
- 5 类资源：`can_use_tool` / `can_read_object`+`can_write_object` / `readable_properties`+`denied_properties`+`can_write_property` / `can_execute_action` / `can_traverse_link`。
- 正反向语法 + `*` 通配；求值顺序：`system_admin` 短路 → PermissionGrant runtime override（deny 优先）→ TTL 元数据 → allow-by-default。
- **Tool 接入**：5 个内核工具已全部接入（query/query_task 读 + 属性 mask；traverse_relation 遍历校验；execute_action/confirm_action tool+action 级；create/update_entity 写校验）。新增 Tool 时**必须** 在 `tool_manifest.yaml` 声明权限（见下）。

**Tool 权限声明（tool_manifest.yaml）**：
- Tool 不在 TTL，用 YAML 声明（替代"Tool 在 TTL"）。内核 8 工具默认声明在 `agent/tools/manifest.yaml`；各 workspace 专属工具声明在 `workspace/<pack>/tool_manifest.yaml`。
- 未声明 = allow-by-default（开发友好，但生产前**应当** 显式声明受治理工具的 roles）。

**actor 派生（信任修复，WP6）**：
- actor 一律从 `shared._get_actor()` 派生：`auth_ctx` → `Employee.user_id` → role。**禁止** 让 LLM 自报 actor/role（`execute_action` 已删 `actor_role` 参数）。
- 兜底：contextvar 缺失 / `AUTH_REQUIRED=false` + anonymous → `system_admin`（开发/测试）；生产强制时 anonymous 拒。

**TTL 权限元数据**：建模侧（ObjectType 属性级 `:read_roles`/`:read_except`/`:write_*` + 嵌套 `:property[]`、Link 的 `:use_roles`/`:use_except`）的写法见 `40-ontology-modeling-spec.md` §12.3。

---

## 5. 错误处理规范
```

- [ ] **Step 3.5: 新增 §5.3「存储后端开发（v2，✅ 已落地）」——插入到 §5.2 之后、§6 之前**

锚点 old_string（§5.2 新末尾 + §6 标题，注意 §5.2 已在 Step 3.3 改过）:
```
- **JSON 后端**（`agent/engine/repository.py`）：`fcntl.flock` 文件锁（Unix）+ 临时文件 `os.replace` 原子替换 + 写入前 `.bak` 备份。
- **PG 后端**（`agent/engine/pg_data_repo.py`）：由数据库事务保证原子性（已落地，见 §5.3 / roadmap §1）。后端选择由 `is_pg_enabled() and ping()` 决定，缺失回落 JSON。

---

## 6. 多 workspace 开发规范
```

new_string:
```
- **JSON 后端**（`agent/engine/repository.py`）：`fcntl.flock` 文件锁（Unix）+ 临时文件 `os.replace` 原子替换 + 写入前 `.bak` 备份。
- **PG 后端**（`agent/engine/pg_data_repo.py`）：由数据库事务保证原子性（已落地，见 §5.3 / roadmap §1）。后端选择由 `is_pg_enabled() and ping()` 决定，缺失回落 JSON。

### 5.3 存储后端开发（v2，✅ 已落地）

> 详见 roadmap §1。本节给开发者启用 / 切换后端的要点。

**双后端架构**：
- Repository 接口不变；实现二选一：`JSONFileRepository`（默认）或 `PgDataRepository` + `PgOntologyRepository`（PG）。
- `workspace_bootstrap.py` 按 `is_pg_enabled() and ping()` 选实现；PG 加载失败回落 JSON 并打印告警（日志出现「回落 JSON」即未生效）。
- `agent/engine/db.py`：psycopg 3 + psycopg-pool 单例连接池（4–8 连接/进程）；`transaction()` 上下文自动 commit/rollback；`DATABASE_URL` 缺失抛 `PGNotConfigured` 让上层回落。

**启用 PG 步骤**：
1. `.env` 加 `DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology`。
2. `docker compose up -d` 起 PG（compose 已含 pgvector 扩展）。
3. 跑迁移：`python agent/scripts/import_to_pg.py`（TTL/YAML/JSON → PG 幂等 upsert；支持 `--workspace retail` / `--skip-data` / `--skip-schema` / `--dry-run`）。
4. 重启后端，日志不再出现「回落 JSON」即生效。

**多副本部署注意**：每进程一个连接池已就绪；进程内 `WorkspaceAgentInstance` 缓存经 `invalidate_workspace(ws)` 失效（admin 写后触发），但**跨进程缓存失效通知机制 defer**（roadmap §1）。单进程 uvicorn 部署够用。

**Schema（`agent/sql/schema.sql`）**：`object_types` / `object_type_properties` / `link_type` / `action_types` / `entities` 五表；关系列存核心查询字段，JSONB 存复杂结构（parameters/side_effects/properties）；含 TenantContext 过滤索引（`workspace_name + org_unit_id`）+ JSONB GIN 索引 + `updated_at` 触发器。pgvector 扩展已建（embedding 列预留，本轮注释掉）。

---

## 6. 多 workspace 开发规范
```

- [ ] **Step 3.6: 20-api-data-contract §6 workspace 传递链路——静态 header 改动态（L391）**

old_string:
```
    → route.ts 注入 HTTP header (X-Workspace)              [现状: 静态默认 header]
```
new_string:
```
    → route.ts 注入 HTTP header (X-Workspace)              [✅ 已落地: 前端 headers prop 动态注入]
```

（动态注入已于 v2-tenant-dynamic 落地，详见 roadmap §8。20-api 其余 auth/admin 章节（§1.4/§1.5）已完整覆盖，不动。）

- [ ] **Step 3.7: 验收——grep 巡检 30-development-guide 无残留过期措辞**

Run:
```bash
rg -n "完整 RBAC 引擎、审计日志留 v2|（未来的）粗粒度 RBAC|v2 换 PG 后由数据库事务保证" docs/design/30-development-guide.md
```
Expected: **无输出**。

确认仍 v2 的保留:
```bash
rg -n "留 v2|🔜 v2|审计日志" docs/design/30-development-guide.md
```
Expected: 有输出（§4 现状说明提到审计日志 🔜 v2、§4.2 嵌套逻辑 🔜 v2——确实未落地）。

- [ ] **Step 3.8: 验收——通读 30-development-guide §4/§5 + 20-api §6**

Read 30-dev-guide §4（含新增 §4.3）+ §5（含新增 §5.3），确认上下文连贯、新节与 §11 不重复（引用而非复制）。Read 20-api §6 确认 header 链路表述与 roadmap §8 一致。

- [ ] **Step 3.9: 提交**

```bash
git add docs/design/30-development-guide.md docs/design/20-api-data-contract.md
git commit -m "docs(design): 开发规范补 v2 流 + 20-api header 核验（v2 落地回填 3/3）

30-dev-guide：§4 现状说明重写（RBAC 已落地）；§4.2/§5.2 措辞修正；
新增 §4.3 认证与权限开发（JWT/auth_middleware/require_admin/
PermissionEvaluator/tool_manifest/actor 派生）；
新增 §5.3 存储后端开发（PG 启用步骤/双后端选择/多副本注意/schema）。
20-api：§6 workspace header 静态→动态（v2-tenant-dynamic 已落地）。
auth 端点（§1.4）与 admin CRUD（§1.5）已覆盖，不动。"
```

---

## 最终验收（全 task 完成后）

- [ ] **Step V1: 全局 grep 巡检——4 份 canonical 文档无残留过期 v2 措辞**

Run:
```bash
rg -n "MVP 零依赖|（v2 预留）|未来实现（🔜 v2）：PostgresRepository|未来（v2）：组织5级|未来（v2）：A2UI 标准渲染、多工作目录切换|完整 RBAC 引擎、审计日志留 v2|（未来的）粗粒度 RBAC|v2 换 PG 后由数据库事务保证|现状: 静态默认 header|MVP .submission_criteria. 只实现" docs/design/00-architecture.md docs/design/20-api-data-contract.md docs/design/30-development-guide.md docs/design/40-ontology-modeling-spec.md docs/design/README.md
```
Expected: **无输出**。

- [ ] **Step V2: 确认仍属 v2 的措辞保留（应当存在）**

Run:
```bash
rg -n "🔜 v2|列为 .v2|v2，MVP 不实现|留 v2|远期" docs/design/00-architecture.md docs/design/30-development-guide.md docs/design/40-ontology-modeling-spec.md | head -50
```
Expected: 有输出，且每条都对应确实未落地的能力（Interface Type / 多 Agent / Branching / BPM / 嵌套逻辑 / HMAC / 26 hooks / DC 维度 / GraphRepository / token 撤销列表 等）。人工逐条核对「这条确实没落地吗」。

- [ ] **Step V3: README 状态徽章与文档内部状态一致**

Read `docs/design/README.md` 全文，确认：roadmap 行不再标 🔮、其余 canonical 文档（00/20/30/40）仍标 ✅ 当前、archive 仍标 🗄。

- [ ] **Step V4: git log 确认 3 个提交**

Run:
```bash
git log --oneline -4
```
Expected: 看到 Task 1/2/3 的 3 个 `docs(design):` 提交 + 之前的 spec 提交 `86629cf`。

---

## 不做的事（明确排除）

- 不改 roadmap.md（已同步）。
- 不改 archive / manual / reference / industry-packs。
- 不重写 architecture §11（已是权威 v2 章节）。
- 不复制 spec 全部细节到 canonical（只写结论级 + 链接）。
- 不动仍属 v2 的内容（Interface Type / 多 Agent / BPM / 嵌套逻辑 / HMAC / hooks / DC / 职能域 / GraphRepository / token 撤销列表 / OAuth-SSO / 多副本失效通知）。
- 不引入新流程（PR checklist / 同步脚本 / 收尾 skill）——用户明确选「先做一次性补齐」。
