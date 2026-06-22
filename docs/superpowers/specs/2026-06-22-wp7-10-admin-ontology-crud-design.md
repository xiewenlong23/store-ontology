# WP7–WP10：管理员本体 Schema CRUD + 失效 + 前端 UI + 文档

- 日期：2026-06-22
- 分支：`feat/v2-pg-storage`
- 起点：WP1–WP6（PG 实例 + `PgOntologyRepository` + `PgDataRepository` + 迁移脚本 + `bootstrap_workspace` 切 PG）
- 范围：在已存在的 PG 仓储写方法（`upsert_*` / `delete_*`）之上接通 HTTP 管理端点，编辑后让缓存失效，前端提供全字段编辑 UI，补文档。

## 1. 背景与现状

WP1–WP6 完成后：

- `agent/engine/pg_ontology_repo.py` 已实现 `upsert_object_type` / `upsert_link_type` / `upsert_action_type` / `delete_object_type` / `delete_link_type` / `delete_action_type`（事务内 upsert，properties 子表全量替换）。
- `agent/main.py` 已有 **三个只读 GET 端点**（`/api/admin/customers/{cid}/ontology/{objects|actions|links}`）和一个只读数据浏览端点 `/data/{entity_type}`。
- `agent/engine/workspace_bootstrap.py:207` 已有 `invalidate_workspace(ws_name)`，但**没有任何调用方**——编辑本体后内存里 `_instances[ws].registry` 会读到过期数据。
- 前端 `frontend/app/admin/page.tsx` 为只读数据浏览；BFF 代理 `frontend/app/api/admin/[...path]/route.ts` 只导出了 `GET`/`POST`，缺 `PUT`/`DELETE`。

缺口：把"写"从仓储层接到 HTTP；编辑后调用失效；前端提供编辑 UI；补文档。

## 2. 决策（已与用户确认）

| 议题 | 决策 |
|---|---|
| WP7 写端点覆盖层 | **仅本体 schema**（Object/Link/Action Type）。业务数据（User/Role/Task/NearExpiryProduct 等）保持只读浏览，CRUD 仍走对话/Action，保留 `edits-only-via-actions` 治理与 Action 审计。 |
| WP9 表单字段范围 | **全字段表单**（含 `roles`/`except`/`visibility`/`status`/`edits_only_via_actions` 等；Object 含 properties 子表编辑器）。 |
| 鉴权 | 与现有 GET 端点一致：`system_admin` 角色，或 bootstrap 初始 `username=='admin'` 账号；其他 → 403。 |
| REST 风格 | 资源式（POST 创建 / PUT 更新 / DELETE 删除）。POST/PUT 仓储层都是 upsert（幂等），区别仅在语义与 URL 是否含主键。 |

## 3. WP7 — 后端写端点

### 3.1 端点矩阵

在 `agent/main.py` 现有三只读端点旁追加九个处理函数：

| 方法 | 路径 | 仓储调用 | 响应 |
|---|---|---|---|
| POST | `/api/admin/customers/{cid}/ontology/objects` | `upsert_object_type(ws, body→ObjectType)` | `{created: <obj dict>}` |
| PUT | `/api/admin/customers/{cid}/ontology/objects/{name}` | 同上，路径 `name` 覆盖 body 的 `id` | `{updated: <obj dict>}` |
| DELETE | `/api/admin/customers/{cid}/ontology/objects/{name}` | `delete_object_type(ws, name)` | `{deleted: true}` / 404 |
| POST | `/api/admin/customers/{cid}/ontology/links` | `upsert_link_type` | `{created: ...}` |
| PUT | `/api/admin/customers/{cid}/ontology/links/{name}` | 同上 | `{updated: ...}` |
| DELETE | `/api/admin/customers/{cid}/ontology/links/{name}` | `delete_link_type` | `{deleted: true}` |
| POST | `/api/admin/customers/{cid}/ontology/actions` | `upsert_action_type` | `{created: ...}` |
| PUT | `/api/admin/customers/{cid}/ontology/actions/{api_name}` | 同上 | `{updated: ...}` |
| DELETE | `/api/admin/customers/{cid}/ontology/actions/{api_name}` | `delete_action_type` | `{deleted: true}` |

主键：`objects`/`links` 用 `name`；`actions` 用 `api_name`。

### 3.2 Body → dataclass 转换器

新建 `agent/engine/admin_ontology_api.py`，放三个纯函数：

- `_json_to_object_type(body: dict) -> ObjectType`
- `_json_to_link_type(body: dict) -> LinkType`
- `_json_to_action_def(body: dict) -> ActionDefinition`

字段映射与现有 GET 端点返回结构**完全对称**——GET 出什么，POST/PUT 就收什么（round-trip）。`properties` 子表从 body 的 `properties: [{name, type, read_roles, read_except, write_roles, write_except}, ...]` 列表直接构造 `PropertyDef`。`parameters` / `submission_criteria` / `side_effects` 接受 list/dict。

### 3.3 鉴权辅助

抽取 `_require_admin(request, cid, ws_name)`：

- 返回 `None`（放行）或 `JSONResponse(status_code=403, content={...})`。
- 逻辑复用现有 `/data/{entity_type}` 端点里的"system_admin 或 username=='admin'"判断（见 `main.py:614-640`）。
- 新写端点全部先调它；现有 `/data` 端点顺手也换成它（一处就地重构，CLAUDE.md "Surgical Changes" 允许：被改的行直接服务于本次请求的"统一鉴权"）。

现有三个只读 ontology GET 端点目前**未做**权限校验（任何登录用户都能读）。本 WP 不扩大该缺口——新写端点强制 admin；GET 端点的鉴权加严留作 follow-up（在 §6 follow-up 列出，不在本 spec 范围内实现）。

### 3.4 错误处理

- 404：DELETE 命中 0 行（仓储 `delete_*` 返回 False）。
- 422：body 缺主键（POST 无 `id`/`api_name`）或字段类型非法（转换器抛 ValueError）。
- 500：PG 异常透传（与 GET 端点一致，FastAPI 默认 handler）。

## 4. WP8 — 缓存失效

### 4.1 唯一相关缓存

全仓搜索结论（2026-06-22）：

- `agent/engine/workspace_bootstrap.py:29` `_instances: Dict[str, WorkspaceAgentInstance]` —— **唯一持有 runtime registry 的进程内缓存**。已提供 `invalidate_workspace(ws)`（line 207）。
- `agent/engine/preview_cache.py` —— Action confirm 的 record preview，与本 spec 的本体 schema 无关。
- `agent/engine/tool_manifest.py` —— 从 JSON 文件读，`bootstrap_workspace` 内每实例构建一次；随 `_instances` 失效自动重建。

### 4.2 接入

在 §3 九个写端点**成功返回前**调用：

```python
from engine.workspace_bootstrap import invalidate_workspace
invalidate_workspace(ws_name)
```

下次 `bootstrap_workspace(ws_name)` 会从 PG 重新 `load_registry`，新 schema 立即可见。**自动、同步、无新端点**（YAGNI：用户没要 manual `/invalidate` 接口，不建）。

## 5. WP9 — 前端 CRUD UI

### 5.1 BFF 代理补动词

`frontend/app/api/admin/[...path]/route.ts`：现有 `proxy(req, method, params)` 已通用；只缺 export。补 `PUT`、`DELETE` 两个 export，各 5 行，复用 `proxy()`。

### 5.2 页面结构

改造 `frontend/app/admin/page.tsx`：

- 顶层加 **Tab**：
  - **数据浏览**（现有 `DataTable`，搬进 tab，逻辑不动）
  - **本体编辑**（新增）—— 子 tab：`Objects` / `Links` / `Actions`
- 样式沿用现页（`system-ui` + 内联样式 + 蓝 `#2563eb` 强调色）。

### 5.3 本体编辑器

每个子 tab：

- **表格视图**：复用现有 `DataTable` 风格；每行尾部加 **编辑** / **删除** 按钮；表头加 **+ 新建** 按钮。
- **全字段表单**（模态或行内展开，实现时定）：
  - **Object**：`id, label, label_zh, comment, storage_file, status, visibility, edits_only_via_actions, read_roles, read_except, write_roles, write_except` + **properties 子编辑器**（每行 `name, type, read_roles, read_except, write_roles, write_except`，行级 +/− 按钮）。
  - **Link**：`id, label, label_zh, comment, domain, range, via, use_roles, use_except`。
  - **Action**：`api_name, display_name, description, status, target_object_type, edits_object_types, locator_field, parameters, submission_criteria, side_effects`（后三个 JSON 文本框）。
- **删除**：弹确认对话框（`window.confirm` 即可，YAGNI 不引第三方组件）。
- **保存**：新建→POST，编辑→PUT（带路径主键）；成功后用响应里的对象刷新该行。

### 5.4 鉴权 UX

- 调用返回 403：与现页一致的红色提示块（"需 system_admin 角色"）。
- 非 admin 账号进入"本体编辑" tab：表格 GET 当前不校验（见 §3.3 follow-up），可读；但**写按钮**（新建/编辑/删除）点击会 403。UI 不预隐藏按钮，让后端是唯一权限真相源。

## 6. WP10 — 文档

- `docs/design/20-api-data-contract.md`：追加九个写端点（method/path/body/response/鉴权），加一节"编辑后失效"说明 `invalidate_workspace`。
- `docs/design/00-architecture.md`：一段说明——admin 本体 CRUD 已 PG 化；编辑后 workspace 实例经 `invalidate_workspace` 失效，下次读取从 PG 重载。
- `README.md`：若已有 admin 段落，补一行写操作说明；无则跳过。

## 7. 测试

后端（`agent/tests/test_admin_ontology_api.py`，FastAPI `TestClient`）：

1. **鉴权**：非 admin → 403；admin/`system_admin` → 200。
2. **round-trip**：POST object → GET objects 包含该对象，字段一致。
3. **PUT 更新**：改 label → 再 GET 反映新值。
4. **properties 全量替换**：POST 含 2 props → PUT 改成 3 props → GET 返回 3 props（验证 §3.2 子表全量替换语义）。
5. **DELETE**：删 → GET 不再含；再 DELETE 同名 → 404。
6. **失效生效**：POST 一个新 object → 立即 `bootstrap_workspace(ws)` 重取（命中缓存会读旧 registry）→ 断言新对象出现在新实例的 `registry.object_types` 中（验证 §4.2 的 `invalidate_workspace` 确实被调用）。

前端：无测试框架，人工冒烟（建/改/删 Object 一轮）。

## 8. 实施顺序与提交粒度

对齐 WP1–WP6 节奏，每 WP 一次 commit：

1. **WP7**：`admin_ontology_api.py` + `main.py` 九端点 + `_require_admin` + 抽取。
2. **WP8**：在 WP7 端点里接 `invalidate_workspace`（与 WP7 同 commit 或紧随其后的小 commit，二选一——实现时定）。
3. **WP7/8 测试**：`test_admin_ontology_api.py` 六 case。
4. **WP9**：BFF `PUT`/`DELETE` export + `admin/page.tsx` tab + 编辑器。
5. **WP10**：三处文档。

## 9. 非目标（YAGNI）

- 业务数据（User/Role/Task 等）的 HTTP 写端点——保持只读 + Action 治理。
- 手动 `/invalidate` REST 端点——自动失效已足够。
- ontology GET 端点鉴权加严（follow-up，本 spec 不实现）。
- 前端测试框架引入。
- 批量导入/导出 ontology（已有 `import_to_pg.py` 迁移脚本覆盖初始导入）。
- 软删除/版本/审计日志（PG schema 未含，超出范围）。

## 10. 风险

- **POST/PUT 都是 upsert**：客户端传错主键会静默覆盖。缓解：PUT 强制路径主键覆盖 body；POST 缺主键 422。
- **properties 全量替换**：编辑时若前端漏传某 property，会被删。缓解：编辑表单预填当前值（round-trip 保证字段齐全）；文档注明语义。
- **失效只在本进程**：多进程/多副本部署下其他进程仍读旧 `_instances`。当前单进程部署（FastAPI uvicorn）够用；规模化需换 Redis/PG 通知，留 follow-up。
