# 设计文档同步：把 v2 落地内容回填到 canonical 文档

> **状态**：设计稿（待评审）· **日期**：2026-06-22 · **作者**：brainstorming
> **来源**：用户反馈「设计文档落后于实现结果，spec 在 docs/superpowers/specs，实现完成后没回填 docs/design」
> **方案**：C（按文档角色差异化深度）—— 一次性补齐，不引入新流程

## 1. 背景与问题

`docs/design/` 是项目的「单一权威」文档家（README 明示），由 4 份 canonical 文档 + roadmap + manual + reference + archive 组成。每份顶部带状态徽章（✅ 当前 / 🔮 前瞻 / 🗄 归档 / 📚 参考）。

`docs/superpowers/specs/` 是 brainstorm→spec 的详细设计稿（4 份近期 spec：v2-tenant-dynamic、v2-agent-isolation、v2-auth-rbac、wp7-10-admin-ontology-crud），全部已实现（WP1–WP10 feat 提交可见）。

**漂移现象**：spec 实现完成后，落地内容没有实质回填到 canonical 文档。具体表现：

- 最近一次提交 `3ff3840` 已同步了 `roadmap.md` 和 `00-architecture.md §11`（v2 认证/RBAC + admin CRUD）。
- 但**同一份 architecture 前半部分仍把已落地能力标成「🔜 v2 / 未来」**，与 §11 自相矛盾。
- **两份规范文档完全没收录 v2 落地内容**：40-ontology-modeling-spec（缺 identity domain / personnel / 权限元数据 / admin CRUD 建模）、30-development-guide（缺 auth / PG 双后端 / PermissionEvaluator / require_admin / tool_manifest）。
- README 把 roadmap 标成「🔮 均未落地」，但 roadmap 内部已有多节 ✅ 已落地。

## 2. 目标与非目标

**目标**

1. docs/design 恢复「单一权威」地位，内部自洽、与 spec 一致。
2. modeler / developer 照 canonical 文档能干活，不必先翻 spec。
3. 不引入新的同步流程（用户明确选「先做一次性补齐」）。

**非目标**

- 不建立 PR checklist / 同步脚本 / 收尾 skill（防漂移流程留待以后）。
- 不重写 architecture §11（它已是权威 v2 章节）。
- 不复制 spec 全部细节到 canonical（避免双份维护、再次漂移）。
- 不动 roadmap.md（已同步）。
- 不动 archive / manual / reference / industry-packs。

## 3. 漂移清单（实施时的核对依据）

| 文件 | 漂移类型 | 具体位置/内容 |
|------|---------|--------------|
| `00-architecture.md` | 内部自相矛盾 | L33/39/57/61 架构图把 PG 存储 / 组织品类 5 级 / workspace 切换 UI 标「未来 v2」；L78/159 Interface Type 表；L178「未来实现 PostgresRepository」；L208-219 submission_criteria「留 v2」；L455 技术选型表「JSON 文件 / 未来 PG」；L469-470 生产部署「v2 预留 / 迁移到 PG」；L486 风险表「v2 换 PG」；L627 §11.8「PostgreSQL 迁移」范围外。以上均与 §11 / roadmap 已 ✅ 矛盾 |
| `40-ontology-modeling-spec.md` | 实质内容缺失 | 无 identity domain（第 4 类必备 domain）、无 personnel domain 独立、无 `Employee.user_id`/`EmployeeRole`、无 TTL 属性级权限元数据、无 admin 本体 CRUD 建模入口、无组织/品类 5 级基线。徽章却写「随内核演进同步更新」 |
| `30-development-guide.md` | 实质内容缺失 + 措辞过期 | L170「完整 RBAC 留 v2」、L181「完整操作符留 v2」（部分已落地）；L201「v2 换 PG」（已落地）；全篇无 auth/RBAC/PG 开发说明 |
| `README.md` | 徽章分类过期 | roadmap 行标「🔮 均未落地」，与 roadmap 内部 ✅ 节矛盾 |
| `20-api-data-contract.md` | 待核验 | 15:16 刚补过 admin 字段契约。实施时核验是否覆盖 `/api/auth/*` 端点、admin CRUD 9 端点、请求头 |

## 4. 方案设计（方案 C：按文档角色差异化）

核心原则：**canonical 写「稳定摘要 + 链接到 spec」，不复制 spec 全部细节。** canonical 答「是什么/怎么用」，spec 答「为什么这么设计」。

### 4.1 `00-architecture.md` — 去矛盾 + 交叉引用（不重写 §11）

§11 是权威 v2 章节，前半部分按它去矛盾：

- 架构图（L33/39/57/61）：「未来 v2」描述里，已落地的项（PG 存储、组织/品类 5 级、workspace 切换 UI）改标 ✅ + 指向 §11；仍属 v2 的（A2UI、多 Agent）保留 🔜。
- L78/159 Interface Type 表：保留「v2 元数据预留」（确实未实现）。
- L178「未来实现 PostgresRepository」：改「✅ 已实现 PgDataRepository/PgOntologyRepository（见 §1 / roadmap §1）；GraphRepository 仍 🔜 远期」。
- L208-219 submission_criteria：改「现状已落地 `roles` + `is/is_not`（见 §11.7）；复杂操作符（matches/includes/gte/value_ref）+ 嵌套 AND/OR 仍 🔜 v2」。
- L455 技术选型表 / L469-470 生产部署 / L486 风险表：按 PG+JSON 双后端现状改写（配 DATABASE_URL 走 PG，缺失回落 JSON）。
- L627 §11.8 范围外「PostgreSQL 迁移」：该条已在 WP1–WP5 落地，从「范围外」移除或标注「已于 WP1–WP5 落地」。

### 4.2 `40-ontology-modeling-spec.md` — 实质补 v2 本体深化

新增/补充内容（结论级，不复制 spec 全部细节）：

- **必备 capability domain 升至 4 类**：organization / personnel / category / **identity**（User / Role / PermissionGrant / Session）。每类列出必备 Object Type。缺则 workspace 注册失败。
- **personnel domain 独立**：Employee 从 organization 拆出；`Employee.user_id` 反向引用 identity User；`department_id` 指向 Category；`EmployeeRole` 词汇表（store_manager / store_clerk / region_cat_mgr / system_admin / ...）对齐 `submission_criteria.roles`。
- **TTL 属性级权限元数据**：ObjectType 属性上的 `:read_roles` / `:read_except` / `:write_roles` / `:write_except`（含嵌套 `:property [ ... ]`）；Link 的 `:use_roles` / `:use_except`。给一段建模示例 + 「详见 spec」收尾。
- **admin 本体 CRUD 建模入口**：admin 可在 admin UI 直接编辑 schema（Object / Link / Action Type），不必改 TTL/YAML + 重启。说明这是建模工作流的补充入口，TTL/YAML 仍是源码侧权威。
- **组织/品类 5 级作为已落地基线**写入建模基线节（Brand→OrgGroup→Channel→Region→Store；Department→CategoryGroup→Category→SubCategory→Variety）。
- 仍属 v2 的（Interface Type / Shared Property / Branching / 显式 Cardinality）保留现有标记。

### 4.3 `30-development-guide.md` — 实质补 v2 开发流

新增两节（结论级 + 链接到 spec）：

- **认证与权限开发**：
  - JWT + bcrypt + `/api/auth/{login,refresh,me,logout}` + `auth_middleware`（强制模式 `AUTH_REQUIRED=true`）。
  - `require_admin` 统一鉴权辅助用法。
  - `PermissionEvaluator` 5 类资源（tool/object/property/action/link）+ 正反向语法 + allow-by-default + system_admin 短路。
  - `tool_manifest.yaml` 声明 Tool（内核 8 + workspace 专属），替代「Tool 在 TTL」。
  - actor 从 auth_ctx → Employee.user_id 派生，**不可被 LLM 自报**（信任修复）。
- **存储后端**：
  - PG/JSON 双后端：配 `DATABASE_URL` 走 PG+JSONB，缺失或连不上自动回落 `JSONFileRepository`，Repository 接口不变。
  - 启用步骤：`.env` 加 `DATABASE_URL` → `docker compose up -d` 起 PG → 跑 `agent/scripts/import_to_pg.py` 迁移 → 重启后端看日志无「回落 JSON」。
- 修正 L170/L181/L201 的「留 v2」措辞为现状（已落地部分标 ✅，未落地部分保留 🔜）。

### 4.4 `README.md` — 徽章修正

roadmap 行从「🔮 均未落地」改 ✅ 当前；说明改「含已落地 + 前瞻，每节有 ✅/🔜 标注」（roadmap 内部 per-section 标记已够，不必拆行）。

### 4.5 `20-api-data-contract.md` — 核验补缺

实施时先读全文，确认覆盖：
- `/api/auth/{login,refresh,me,logout}` 端点。
- admin 本体 CRUD 9 端点（POST/PUT/DELETE × objects/links/actions）。
- `X-Workspace` / `X-Org-Unit-ID` 请求头透传链路。
缺则补，全则不动。

## 5. 仍属 v2 的内容（不动）

Interface Type / Shared Property / Ontology Branching / 多 Agent / BPM / submission_criteria 操作符全集（gte/matches/includes/value_ref + 嵌套 AND/OR）/ DC 维度 / 职能域 Domain / 6 PermissionMode / 6 cascade / HMAC 快照 / 26 hooks —— **确实未落地**，保留现有「🔜 v2」标记，不误改成 ✅。判定依据：每个 ✅ 必须能在某个 spec 或 roadmap 节找到落地证据；每个 🔜 必须确实未实现。

## 6. 验收闸

实施完跑 grep 巡检，确认无残留矛盾：
- 在 4 份 canonical 文档（00/20/30/40）搜 `v2` / `🔜` / `未实现` / `MVP 不实现` / `留 v2` / `未来`，逐条对照落地状态：落地的改 ✅，没落地的保留。
- 交叉核对：每条 ✅ 在 spec / roadmap 有对应落地证据；每条 🔜 确实未实现。
- README 徽章与文档内部状态一致。

## 7. 提交策略

按文档家族分 3 个提交，便于 review 和回滚：
1. `docs(design): architecture 去矛盾 + README 徽章修正`（00-architecture + README）
2. `docs(design): 本体建模规范补 v2 深化（identity/personnel/权限元数据/admin CRUD）`（40-ontology）
3. `docs(design): 开发规范补 v2 流（auth/RBAC + PG 双后端）+ 20-api 核验`（30-dev-guide + 20-api）

提交到当前分支 `docs/sync-v2-pg-storage-status`（不新建分支，用户已在 docs 同步分支上）。

## 8. 风险

- **风险**：实施时把仍属 v2 的内容误标成 ✅（扩大漂移）。**缓解**：§5 明列不动清单 + §6 验收闸逐条核对落地证据。
- **风险**：40/30 补太多细节导致 canonical 和 spec 双份维护。**缓解**：§4 原则——canonical 写结论级，spec 收尾链接，不复制细节。
- **风险**：20-api 实施时发现缺得多，改动超预期。**缓解**：实施时先读再定动作，缺则补、全则不动，不强制改动。
