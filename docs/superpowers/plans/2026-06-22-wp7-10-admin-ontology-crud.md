# WP7–WP10：管理员本体 Schema CRUD 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已存在的 PG 本体仓储写方法之上，接通 HTTP POST/PUT/DELETE 端点（WP7），编辑后自动失效缓存（WP8），前端提供全字段编辑 UI（WP9），补文档（WP10）。

**Architecture:** `agent/engine/admin_ontology_api.py` 新模块承载 JSON↔dataclass 转换 + 鉴权辅助；`main.py` 加 9 个写端点（3 collections × POST/PUT/DELETE），每个端点成功后调 `invalidate_workspace(ws)`；前端 BFF 补 `PUT`/`DELETE` export，admin 页加"本体编辑" tab；文档三处。

**Tech Stack:** Python 3.11 / FastAPI / psycopg2 (PG) / pytest (TestClient) / Next.js (TypeScript, 内联样式)。

**Spec:** `docs/superpowers/specs/2026-06-22-wp7-10-admin-ontology-crud-design.md`

**前置：** `docker compose up -d` + `python agent/scripts/import_to_pg.py` 已完成（PG 5433 上有 jjy/retail/customerA 三个 workspace 的 schema）。

**全局约定：**
- 所有 shell 命令从项目根 `/Users/xiewenlong/Documents/code/store-ontology` 执行。
- Python 解释器：`/opt/miniconda3/envs/store-ontology/bin/python`（下记 `PY`）。
- `DATABASE_URL` 始终 `postgresql://ontology:ontology@localhost:5433/ontology`。
- 测试 workspace 名约定：`_test_admin_ws`（与本仓 `test_pg_ontology_repo.py` 用的 `_test_ont_ws` 区分，互不污染）。
- 代码与注释风格：跟随周边文件（中文 docstring，模块头 docstring 解释"设计/用途"）。

---

## File Structure

**新建：**
- `agent/engine/admin_ontology_api.py` — JSON↔dataclass 转换器（`_json_to_object_type` / `_json_to_link_type` / `_json_to_action_def`）+ 鉴权辅助 `require_admin(request, ws_name)`。纯函数 + 一个返回 `None|JSONResponse` 的鉴权检查；不持状态。
- `agent/tests/test_admin_ontology_api.py` — TestClient 端到端测试 6 case + 转换器单元测试。

**修改：**
- `agent/main.py`（约 line 559-600 区域，紧跟现有 3 只读 ontology GET 端点之后）— 加 9 个写端点；在 `/data/{entity_type}` 端点把现有鉴权 inline 逻辑替换为调用 `require_admin`（一处就地去重，直接服务本次"统一鉴权入口"目标）。
- `frontend/app/api/admin/[...path]/route.ts` — 加 `PUT` / `DELETE` export。
- `frontend/app/admin/page.tsx` — 改造为 tab 结构，加"本体编辑"编辑器。
- `docs/design/20-api-data-contract.md` — 加九端点 + 失效说明。
- `docs/design/00-architecture.md` — 加一段 admin 本体 CRUD PG 化说明。
- `README.md` — 若已有 admin 段落补一行（无则跳过）。

---

## Task 1: 创建 `admin_ontology_api.py` 转换器模块（TDD）

**Files:**
- Create: `agent/engine/admin_ontology_api.py`
- Test: `agent/tests/test_admin_ontology_api.py`

本任务只做 **3 个转换器纯函数**（JSON dict → dataclass），不做鉴权（Task 2）、不做端点（Task 3）。先把"业务核心"独立可测。

- [ ] **Step 1: 写失败测试 — 转换器 round-trip**

创建 `agent/tests/test_admin_ontology_api.py`：

```python
"""WP7 admin_ontology_api 测试。

JSON dict → dataclass 转换器 round-trip：与 pg_ontology_repo.list_* 的输出结构对称，
保证前端 GET 拿到的对象 POST/PUT 回去能复原（spec §3.2）。
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.admin_ontology_api import (
    json_to_object_type, json_to_link_type, json_to_action_def,
)
from engine.parser import ObjectType, LinkType, PropertyDef
from engine.action_loader import ActionDefinition


class TestJsonObjectConv:
    def test_full_object_type(self):
        body = {
            "id": "Task", "label": "任务 (Task)", "label_zh": "任务",
            "comment": "工单", "storage_file": "tasks.json", "status": "active",
            "visibility": "normal", "edits_only_via_actions": True,
            "read_roles": "store_manager,regional_mgr",
            "read_except": "clerk",
            "write_roles": "",
            "write_except": "",
            "properties": [
                {"name": "id", "type": "string",
                 "read_roles": "", "read_except": "", "write_roles": "", "write_except": ""},
                {"name": "assignee", "type": "ref:Employee",
                 "read_roles": "store_manager", "read_except": "",
                 "write_roles": "store_manager", "write_except": ""},
            ],
        }
        ot = json_to_object_type(body)
        assert isinstance(ot, ObjectType)
        assert ot.id == "Task"
        assert ot.label == "任务 (Task)"
        assert ot.edits_only_via_actions is True
        assert ot.read_roles == "store_manager,regional_mgr"
        assert len(ot.properties) == 2
        assert ot.properties[1].name == "assignee"
        assert ot.properties[1].read_roles == "store_manager"

    def test_missing_required_raises(self):
        """body 缺 id 主键 → ValueError（端点层映射 422）。"""
        with pytest.raises(ValueError, match="id"):
            json_to_object_type({"label": "x"})

    def test_empty_properties_ok(self):
        ot = json_to_object_type({"id": "X", "label": "X", "properties": []})
        assert ot.properties == []

    def test_property_defaults(self):
        """property 子项只给 name+type，roles 字段缺省为 ""。"""
        ot = json_to_object_type({
            "id": "X", "label": "X",
            "properties": [{"name": "id", "type": "string"}],
        })
        p = ot.properties[0]
        assert p.read_roles == "" and p.write_except == ""


class TestJsonLinkConv:
    def test_full_link(self):
        body = {
            "id": "assignedTo", "label": "指派给 (assignedTo)",
            "label_zh": "指派给", "comment": "task→employee",
            "domain": "Task", "range": "Employee", "via": "assignee",
            "use_roles": "store_manager", "use_except": "",
        }
        lt = json_to_link_type(body)
        assert isinstance(lt, LinkType)
        assert lt.id == "assignedTo"
        assert lt.range == "Employee"
        assert lt.use_roles == "store_manager"

    def test_link_missing_id(self):
        with pytest.raises(ValueError, match="id"):
            json_to_link_type({"domain": "Task"})


class TestJsonActionConv:
    def test_full_action(self):
        body = {
            "api_name": "create_task", "display_name": "建工单",
            "description": "创建", "status": "active",
            "target_object_type": "Task",
            "edits_object_types": ["Task"],
            "locator_field": "task_id",
            "parameters": [{"name": "title", "type": "string"}],
            "submission_criteria": {"require_approval_from": "store_manager"},
            "side_effects": [{"kind": "audit_log"}],
        }
        ad = json_to_action_def(body)
        assert isinstance(ad, ActionDefinition)
        assert ad.api_name == "create_task"
        assert ad.parameters[0]["name"] == "title"
        assert ad.submission_criteria["require_approval_from"] == "store_manager"
        assert ad.side_effects[0]["kind"] == "audit_log"

    def test_action_missing_api_name(self):
        with pytest.raises(ValueError, match="api_name"):
            json_to_action_def({"display_name": "x"})

    def test_action_optional_fields_default(self):
        ad = json_to_action_def({"api_name": "noop"})
        assert ad.parameters == [] and ad.side_effects == []
        assert ad.submission_criteria == {}
        assert ad.target_object_type == ""
```

- [ ] **Step 2: 跑测试确认失败**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.admin_ontology_api'`。

- [ ] **Step 3: 创建 `agent/engine/admin_ontology_api.py`（转换器部分）**

```python
"""WP7 admin 本体 CRUD API 辅助 —— JSON↔dataclass 转换 + 鉴权。

设计（spec §3.2/§3.3）：
- ``json_to_object_type`` / ``json_to_link_type`` / ``json_to_action_def``：
  body dict → parser/action_loader 的 dataclass。字段结构与现有 GET 端点
  （``pg_ontology_repo.list_*``）输出对称，故前端 GET 拿到的对象原样 PUT/POST 回去
  能复原（round-trip）。
- ``require_admin``：统一鉴权入口（spec §3.3）。system_admin 角色或 bootstrap 初始
  admin 账号放行；其余返回 403 JSONResponse。供 main.py 的写端点统一调用。

仅纯函数 + 一个鉴权检查；不持状态。
"""
from typing import Optional

from fastapi.responses import JSONResponse

from engine.parser import ObjectType, LinkType, PropertyDef
from engine.action_loader import ActionDefinition


# ============ JSON → dataclass ============

def json_to_object_type(body: dict) -> ObjectType:
    """body dict → ObjectType。

    body 字段（与 pg_ontology_repo.list_object_types 输出对称）：
    id, label, label_zh, comment, storage_file, status, visibility,
    edits_only_via_actions, read_roles, read_except, write_roles, write_except,
    properties: [{name, type, read_roles, read_except, write_roles, write_except}, ...]
    """
    name = body.get("id")
    if not name:
        raise ValueError("Object Type body 缺 id 主键")
    props = [_json_to_property(p) for p in (body.get("properties") or [])]
    return ObjectType(
        id=name,
        label=body.get("label") or "",
        comment=body.get("comment") or "",
        properties=props,
        storage_file=body.get("storage_file") or f"{name.lower()}s.json",
        label_zh=body.get("label_zh") or "",
        status=body.get("status") or "active",
        visibility=body.get("visibility") or "normal",
        edits_only_via_actions=bool(body.get("edits_only_via_actions")),
        read_roles=body.get("read_roles") or "",
        read_except=body.get("read_except") or "",
        write_roles=body.get("write_roles") or "",
        write_except=body.get("write_except") or "",
    )


def _json_to_property(p: dict) -> PropertyDef:
    pname = p.get("name")
    if not pname:
        raise ValueError("property 项缺 name")
    return PropertyDef(
        name=pname,
        type=p.get("type") or "string",
        read_roles=p.get("read_roles") or "",
        read_except=p.get("read_except") or "",
        write_roles=p.get("write_roles") or "",
        write_except=p.get("write_except") or "",
    )


def json_to_link_type(body: dict) -> LinkType:
    """body dict → LinkType（字段与 list_link_types 输出对称）。"""
    name = body.get("id")
    if not name:
        raise ValueError("Link Type body 缺 id 主键")
    return LinkType(
        id=name,
        label=body.get("label") or "",
        domain=body.get("domain") or "",
        range=body.get("range") or "",
        via=body.get("via") or "",
        label_zh=body.get("label_zh") or "",
        comment=body.get("comment") or "",
        use_roles=body.get("use_roles") or "",
        use_except=body.get("use_except") or "",
    )


def json_to_action_def(body: dict) -> ActionDefinition:
    """body dict → ActionDefinition（字段与 list_action_types 输出对称）。

    parameters / side_effects 接受 list；submission_criteria 接受 dict。
    """
    api_name = body.get("api_name")
    if not api_name:
        raise ValueError("Action body 缺 api_name 主键")
    return ActionDefinition(
        api_name=api_name,
        display_name=body.get("display_name") or "",
        description=body.get("description") or "",
        status=body.get("status") or "active",
        target_object_type=body.get("target_object_type") or "",
        edits_object_types=list(body.get("edits_object_types") or []),
        locator_field=body.get("locator_field") or "",
        parameters=list(body.get("parameters") or []),
        submission_criteria=dict(body.get("submission_criteria") or {}),
        side_effects=list(body.get("side_effects") or []),
    )


# ============ require_admin（Task 2 填充） ============
```

- [ ] **Step 4: 跑测试确认通过**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py -v
```
Expected: PASS（9 个测试全过）。

- [ ] **Step 5: 提交**

```bash
git add agent/engine/admin_ontology_api.py agent/tests/test_admin_ontology_api.py
git commit -m "feat(WP7): admin_ontology_api JSON→dataclass 转换器（TDD）"
```

---

## Task 2: `require_admin` 鉴权辅助

**Files:**
- Modify: `agent/engine/admin_ontology_api.py`（追加 `require_admin`）
- Test: `agent/tests/test_admin_ontology_api.py`（追加测试类）

- [ ] **Step 1: 读现有 `/data/{entity_type}` 鉴权逻辑作为参考**

Read `agent/main.py:614-640`（`admin_data_browse`），它内联了"system_admin 或 username=='admin'"判断。本 Task 把这段逻辑搬到 `require_admin` 并参数化。

- [ ] **Step 2: 写失败测试 — `require_admin`**

在 `agent/tests/test_admin_ontology_api.py` 末尾追加：

```python
class TestRequireAdmin:
    """require_admin 鉴权逻辑。

    actor 由 _get_actor() 从 auth_ctx contextvar 派生。测试用 monkeypatch 替换。
    """

    def test_system_admin_allowed(self, monkeypatch):
        import engine.admin_ontology_api as mod
        monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "system_admin",
                                                         "user_id": "u1"})
        # 不抛、不返回 JSONResponse（返回 None）
        result = mod.require_admin(ws_name="jjy", is_admin_account=False)
        assert result is None

    def test_other_role_denied(self, monkeypatch):
        import engine.admin_ontology_api as mod
        monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "clerk",
                                                         "user_id": "u1"})
        result = mod.require_admin(ws_name="jjy", is_admin_account=False)
        assert result is not None
        assert result.status_code == 403

    def test_bootstrap_admin_account_allowed(self, monkeypatch):
        """username=='admin' 的 bootstrap 初始账号即使 role 非 system_admin 也放行。"""
        import engine.admin_ontology_api as mod
        monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "store_manager",
                                                         "user_id": "u1"})
        result = mod.require_admin(ws_name="jjy", is_admin_account=True)
        assert result is None
```

- [ ] **Step 3: 跑测试确认失败**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py::TestRequireAdmin -v
```
Expected: FAIL — `AttributeError: module 'engine.admin_ontology_api' has no attribute 'require_admin'`。

- [ ] **Step 4: 在 `admin_ontology_api.py` 末尾追加实现**

把 Task 1 末尾的占位注释 `# ============ require_admin（Task 2 填充） ============` 替换为：

```python
# ============ require_admin：统一鉴权入口 ============

def _get_actor() -> dict:
    """从 auth_ctx contextvar 派生 actor（转发到 agent.tools.shared._get_actor）。

    单独包一层方便测试 monkeypatch（避免直接 patch shared 模块）。
    """
    from agent.tools.shared import _get_actor as _impl
    return _impl()


def _is_bootstrap_admin_account(ws_name: str, user_id: str) -> bool:
    """检查 user_id 是否为该 workspace 的 bootstrap 初始 admin 账号
    （username=='admin'）。与 main.py 旧 /data 端点判断一致。"""
    if not user_id:
        return False
    from engine.identity import _load_users
    from engine.pack import get_workspace_dir
    ws_def = get_workspace_dir(ws_name)
    if not ws_def or not ws_def.data_dir:
        return False
    for u in _load_users(ws_def.data_dir):
        if u.get("id") == user_id and u.get("username") == "admin":
            return True
    return False


def require_admin(ws_name: str, is_admin_account: Optional[bool] = None) -> Optional[JSONResponse]:
    """鉴权：system_admin 角色或 bootstrap admin 账号放行；其余返回 403。

    返回 None 表示放行；返回 JSONResponse(403) 表示拒绝（调用方直接 return 该对象）。

    is_admin_account：调用方可预算（复用判断结果）传 None 让本函数自查。
    """
    actor = _get_actor()
    role = actor.get("role", "")
    user_id = actor.get("user_id", "")
    if role == "system_admin":
        return None
    if is_admin_account is None:
        is_admin_account = _is_bootstrap_admin_account(ws_name, user_id)
    if is_admin_account:
        return None
    return JSONResponse(
        status_code=403,
        content={"detail": f"无权操作（需 system_admin）", "role": role},
    )
```

- [ ] **Step 5: 跑测试确认通过**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py -v
```
Expected: PASS（12 个测试全过：9 conv + 3 auth）。

- [ ] **Step 6: 提交**

```bash
git add agent/engine/admin_ontology_api.py agent/tests/test_admin_ontology_api.py
git commit -m "feat(WP7): require_admin 统一鉴权辅助"
```

---

## Task 3: 后端写端点（9 个，含 WP8 失效）

**Files:**
- Modify: `agent/main.py`（line ~559-600 区段后追加 9 端点；line ~614-640 替换 inline 鉴权为 `require_admin`）
- Test: `agent/tests/test_admin_ontology_api.py`（追加端点测试）

本 Task 是 WP7+WP8 合并提交（spec §8 允许：失效是写端点的内置一部分）。

- [ ] **Step 1: 写失败测试 — 端点 round-trip + 鉴权 + 失效**

在 `agent/tests/test_admin_ontology_api.py` 顶部 import 区追加，并新增 fixture + 测试类：

```python
# 顶部追加 import
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """启动 FastAPI app（main:app）+ 关强制认证 + actor=system_admin。

    AUTH_REQUIRED=false → auth middleware 放行；_get_actor 兜底返回 system_admin。
    """
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    # 重置 workspace 实例缓存，避免跨用例污染
    from engine.workspace_bootstrap import reset_instances
    reset_instances()
    import main
    with TestClient(main.app) as c:
        yield c
    reset_instances()


@pytest.fixture
def admin_ws(client, monkeypatch):
    """准备测试 workspace：清空 PG 中 _test_admin_ws 的 ontology 数据。"""
    from engine import db as db_mod
    monkeypatch.setenv("DATABASE_URL", "postgresql://ontology:ontology@localhost:5433/ontology")
    db_mod._reset_pg_state()
    if not db_mod.ping():
        pytest.skip("PG 不可用")
    db_mod.execute("DELETE FROM object_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM link_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM action_types WHERE workspace_name = %s", ("_test_admin_ws",))
    yield "_test_admin_ws"
    db_mod.execute("DELETE FROM object_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM link_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM action_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod._reset_pg_state()


@pytest.fixture
def deny_admin(monkeypatch):
    """让 require_admin 拒绝（actor=clerk）。"""
    import engine.admin_ontology_api as mod
    monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "clerk", "user_id": "u1"})


HEADERS = {"X-Workspace": "_test_admin_ws"}


class TestObjectEndpoints:
    def test_post_then_get(self, client, admin_ws):
        body = {
            "id": "Foo", "label": "Foo (x)", "label_zh": "Foo",
            "comment": "t", "storage_file": "foos.json", "status": "active",
            "visibility": "normal", "edits_only_via_actions": False,
            "read_roles": "", "read_except": "", "write_roles": "", "write_except": "",
            "properties": [{"name": "id", "type": "string"},
                           {"name": "n", "type": "string"}],
        }
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                        json=body, headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["created"]["id"] == "Foo"
        # GET 确认落库
        g = client.get(f"/api/admin/customers/{admin_ws}/ontology/objects",
                       headers=HEADERS)
        ids = [o["id"] for o in g.json()["objects"]]
        assert "Foo" in ids

    def test_put_replaces_properties(self, client, admin_ws):
        # 先 POST 2 props
        client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                    json={"id": "Bar", "label": "Bar", "properties": [
                        {"name": "id", "type": "string"},
                        {"name": "a", "type": "string"}]},
                    headers=HEADERS)
        # PUT 改成 3 props
        r = client.put(f"/api/admin/customers/{admin_ws}/ontology/objects/Bar",
                       json={"id": "Bar", "label": "Bar2", "properties": [
                           {"name": "id", "type": "string"},
                           {"name": "a", "type": "string"},
                           {"name": "b", "type": "string"}]},
                       headers=HEADERS)
        assert r.status_code == 200
        # GET 验证 3 props + label 更新
        g = client.get(f"/api/admin/customers/{admin_ws}/ontology/objects",
                       headers=HEADERS)
        bar = next(o for o in g.json()["objects"] if o["id"] == "Bar")
        assert bar["label"] == "Bar2"
        assert len(bar["properties"]) == 3

    def test_delete_then_404(self, client, admin_ws):
        client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                    json={"id": "Baz", "label": "Baz", "properties": []},
                    headers=HEADERS)
        d = client.delete(f"/api/admin/customers/{admin_ws}/ontology/objects/Baz",
                          headers=HEADERS)
        assert d.status_code == 200
        assert d.json()["deleted"] is True
        d2 = client.delete(f"/api/admin/customers/{admin_ws}/ontology/objects/Baz",
                           headers=HEADERS)
        assert d2.status_code == 404

    def test_post_denied_non_admin(self, client, admin_ws, deny_admin):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                        json={"id": "X", "label": "X", "properties": []},
                        headers=HEADERS)
        assert r.status_code == 403

    def test_invalid_body_422(self, client, admin_ws):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                        json={"label": "no id"}, headers=HEADERS)
        assert r.status_code == 422


class TestLinkActionEndpoints:
    def test_link_crud(self, client, admin_ws):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/links",
                        json={"id": "lk", "label": "lk", "domain": "A",
                              "range": "B", "via": "ref", "use_roles": "x"},
                        headers=HEADERS)
        assert r.status_code == 200
        d = client.delete(f"/api/admin/customers/{admin_ws}/ontology/links/lk",
                          headers=HEADERS)
        assert d.status_code == 200

    def test_action_crud(self, client, admin_ws):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/actions",
                        json={"api_name": "do_x", "display_name": "Do X",
                              "target_object_type": "Task",
                              "parameters": [{"name": "a", "type": "string"}]},
                        headers=HEADERS)
        assert r.status_code == 200
        d = client.delete(f"/api/admin/customers/{admin_ws}/ontology/actions/do_x",
                          headers=HEADERS)
        assert d.status_code == 200


class TestInvalidation:
    def test_post_invalidates_workspace_instance(self, client, admin_ws):
        """编辑后 bootstrap_workspace 重取应反映新对象（spec §7 test 6）。"""
        from engine.workspace_bootstrap import bootstrap_workspace, invalidate_workspace
        # 触发一次 bootstrap 缓存（此时 _test_admin_ws 的 registry 为空）
        invalidate_workspace(admin_ws)
        inst_before = bootstrap_workspace(admin_ws)
        assert "Foo" not in inst_before.registry.object_types
        # POST 新对象
        client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                    json={"id": "Foo", "label": "Foo", "properties": []},
                    headers=HEADERS)
        # 再取（端点内部应已 invalidate）
        inst_after = bootstrap_workspace(admin_ws)
        assert "Foo" in inst_after.registry.object_types
```

- [ ] **Step 2: 跑测试确认失败**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py::TestObjectEndpoints \
  agent/tests/test_admin_ontology_api.py::TestLinkActionEndpoints \
  agent/tests/test_admin_ontology_api.py::TestInvalidation -v
```
Expected: FAIL — 404 / 405（POST/PUT/DELETE 路由不存在）。

- [ ] **Step 3: 在 `main.py` 加 9 个写端点**

在 `main.py` 现有 `@app.get("/api/admin/customers/{cid}/ontology/links")` 端点（line ~589-599）**之后**、`# ============ v2 管理数据浏览 API`（line ~602）**之前**插入：

```python
# ============ v2 本体 CRUD 写端点（WP7 + WP8 失效，spec §3/§4）============

from engine.admin_ontology_api import (
    json_to_object_type, json_to_link_type, json_to_action_def,
    require_admin,
)
from engine.workspace_bootstrap import invalidate_workspace
from engine import pg_ontology_repo as _ont_repo


def _ontology_to_dict(ot) -> dict:
    """ObjectType → dict（与 list_object_types 输出对称，用于响应 body）。"""
    return {
        "id": ot.id, "label": ot.label, "label_zh": ot.label_zh,
        "comment": ot.comment, "storage_file": ot.storage_file,
        "status": ot.status, "visibility": ot.visibility,
        "edits_only_via_actions": ot.edits_only_via_actions,
        "read_roles": ot.read_roles, "read_except": ot.read_except,
        "write_roles": ot.write_roles, "write_except": ot.write_except,
        "properties": [{"name": p.name, "type": p.type,
                        "read_roles": p.read_roles, "read_except": p.read_except,
                        "write_roles": p.write_roles, "write_except": p.write_except}
                       for p in ot.properties],
    }


def _link_to_dict(lt) -> dict:
    return {
        "id": lt.id, "label": lt.label, "label_zh": lt.label_zh,
        "comment": lt.comment, "domain": lt.domain, "range": lt.range,
        "via": lt.via, "use_roles": lt.use_roles, "use_except": lt.use_except,
    }


def _action_to_dict(ad) -> dict:
    return {
        "api_name": ad.api_name, "display_name": ad.display_name,
        "description": ad.description, "status": ad.status,
        "target_object_type": ad.target_object_type,
        "edits_object_types": list(ad.edits_object_types or []),
        "locator_field": ad.locator_field,
        "parameters": list(ad.parameters or []),
        "submission_criteria": dict(ad.submission_criteria or {}),
        "side_effects": list(ad.side_effects or []),
    }


# ----- Object Types -----

@app.post("/api/admin/customers/{cid}/ontology/objects")
async def admin_create_object(request: Request, cid: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        ot = json_to_object_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_object_type(ws_name, ot)
    invalidate_workspace(ws_name)
    return {"created": _ontology_to_dict(ot)}


@app.put("/api/admin/customers/{cid}/ontology/objects/{name}")
async def admin_update_object(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["id"] = name  # 路径主键覆盖 body（spec §3.1）
    try:
        ot = json_to_object_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_object_type(ws_name, ot)
    invalidate_workspace(ws_name)
    return {"updated": _ontology_to_dict(ot)}


@app.delete("/api/admin/customers/{cid}/ontology/objects/{name}")
async def admin_delete_object(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_object_type(ws_name, name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- Link Types -----

@app.post("/api/admin/customers/{cid}/ontology/links")
async def admin_create_link(request: Request, cid: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        lt = json_to_link_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_link_type(ws_name, lt)
    invalidate_workspace(ws_name)
    return {"created": _link_to_dict(lt)}


@app.put("/api/admin/customers/{cid}/ontology/links/{name}")
async def admin_update_link(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["id"] = name
    try:
        lt = json_to_link_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_link_type(ws_name, lt)
    invalidate_workspace(ws_name)
    return {"updated": _link_to_dict(lt)}


@app.delete("/api/admin/customers/{cid}/ontology/links/{name}")
async def admin_delete_link(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_link_type(ws_name, name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- Action Types -----

@app.post("/api/admin/customers/{cid}/ontology/actions")
async def admin_create_action(request: Request, cid: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        ad = json_to_action_def(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_action_type(ws_name, ad)
    invalidate_workspace(ws_name)
    return {"created": _action_to_dict(ad)}


@app.put("/api/admin/customers/{cid}/ontology/actions/{api_name}")
async def admin_update_action(request: Request, cid: str, api_name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["api_name"] = api_name
    try:
        ad = json_to_action_def(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_action_type(ws_name, ad)
    invalidate_workspace(ws_name)
    return {"updated": _action_to_dict(ad)}


@app.delete("/api/admin/customers/{cid}/ontology/actions/{api_name}")
async def admin_delete_action(request: Request, cid: str, api_name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_action_type(ws_name, api_name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{api_name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}
```

**注意 import：** `JSONResponse` 已在 `main.py` 文件内其他端点 import（见 line 521 `from fastapi.responses import JSONResponse` 在函数内 lazy import）。本块也用 lazy import 形式——确保顶部已 import 或在函数内 import。检查：若顶部已有则直接用；否则在每个函数内加 `from fastapi.responses import JSONResponse`。实现时按现有风格统一（main.py 多处在函数内 lazy import，跟随）。

- [ ] **Step 4: 把 `/data/{entity_type}` 端点的 inline 鉴权替换为 `require_admin`**

精确替换 `main.py:614-640`（从 `inst = bootstrap_workspace(...)` 那行，到 `content={"detail": f"无权浏览 {entity_type}", "role": role})` 那行的 if 块结束）。**保留 line 642 起的 `tc = TenantContext(...)` 及之后**——只换鉴权块。

把 line 614-640 替换为：

```python
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
    ws_name = _resolve_workspace_name(request, cid)
    from agent.tools.shared import _get_actor as _ga, _get_evaluator
    from fastapi.responses import JSONResponse
    denied = require_admin(ws_name)
    if denied:
        # data 浏览对非 admin 但 PermissionEvaluator 允许 read 的角色仍放行（保留旧语义）
        actor = _ga()
        role = actor.get("role", "")
        evaluator = _get_evaluator()
        if not evaluator.can_read_object(role, entity_type).granted:
            return denied
```

**校验替换边界：** 替换后下一行必须是 `# 总部视角读全部（admin 数据不应受 org_unit 隔离）` + `tc = TenantContext(...)`（原 line 641-642）。若不是，说明替换范围错了，回滚重来。

这一处是 spec §3.3 明确允许的"被改行直接服务本次请求的统一鉴权"重构：原 `_load_users` / `get_workspace_dir` / `is_admin_account` 内联判断被 `require_admin` 封装；PermissionEvaluator 兜底分支保留。

- [ ] **Step 5: 跑全部 admin_ontology_api 测试确认通过**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py -v
```
Expected: PASS（17 个测试全过）。

- [ ] **Step 6: 跑回归 — ontology repo 测试 + 一个 dashboard 测试不崩**

```bash
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_pg_ontology_repo.py \
  agent/tests/test_dashboard_api.py -v 2>&1 | tail -20
```
Expected: PASS（确认 §3 Step 4 的 `/data` 重构没破坏既有用例）。

- [ ] **Step 7: 提交**

```bash
git add agent/main.py agent/tests/test_admin_ontology_api.py
git commit -m "feat(WP7+WP8): admin 本体 9 写端点 + 编辑后 invalidate_workspace"
```

---

## Task 4: WP9 前端 — BFF 加 PUT/DELETE export

**Files:**
- Modify: `frontend/app/api/admin/[...path]/route.ts`

- [ ] **Step 1: 在文件末尾追加 PUT / DELETE export**

现有文件末尾是 `POST` export。在其后追加（`proxy()` 已通用，无需改动）：

```typescript
export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(req, "PUT", params);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(req, "DELETE", params);
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -10
```
Expected: 无新增错误（可能存在与本次无关的 pre-existing 错误，仅看是否本次改动引入）。

- [ ] **Step 3: 提交**

```bash
git add frontend/app/api/admin/[...path]/route.ts
git commit -m "feat(WP9): admin BFF 加 PUT/DELETE export"
```

---

## Task 5: WP9 前端 — admin 页改造为 tab + 本体编辑器

**Files:**
- Modify: `frontend/app/admin/page.tsx`

本 Task 较大但单文件。分步：先加 tab 框架迁移现有数据浏览，再加本体编辑子组件。

- [ ] **Step 1: 重写 `admin/page.tsx`（tab 框架 + 现有数据浏览移入 + 本体编辑占位）**

完全替换 `frontend/app/admin/page.tsx` 内容为：

```tsx
'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useWorkspace } from '../workspace-context'
import { useAuth } from '../auth-context'
import { OntologyEditor } from './ontology-editor'
import { DataBrowser } from './data-browser'

/**
 * v2 管理员页（WP7-WP9）。
 *
 * 两个 tab：
 * - 数据浏览（只读，原 admin/page.tsx 逻辑，搬到 data-browser.tsx）
 * - 本体编辑（CRUD：Object/Link/Action Type，全字段表单，WP9 新增）
 */

export default function AdminPage() {
  const { isAuthenticated } = useAuth()
  const [tab, setTab] = useState<'data' | 'ontology'>('data')

  if (!isAuthenticated) {
    return (
      <main style={{ padding: 24, color: '#666' }}>未登录，正在跳转登录页...</main>
    )
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, fontFamily: 'system-ui' }}>
      <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>🛠️ 管理员控制台</h1>
          <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>
            数据浏览（只读）· 本体编辑（Object/Link/Action Type CRUD）
          </p>
        </div>
        <Link href="/" style={{
          padding: '8px 16px', borderRadius: 6, background: '#3b82f6',
          color: '#fff', textDecoration: 'none', fontSize: 14, fontWeight: 500,
        }}>← 返回首页</Link>
      </header>

      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        {(['data', 'ontology'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 18px', borderRadius: 6,
            border: `1px solid ${tab === t ? '#2563eb' : '#d1d5db'}`,
            background: tab === t ? '#2563eb' : '#fff',
            color: tab === t ? '#fff' : '#374151',
            cursor: 'pointer', fontSize: 14, fontWeight: 500,
          }}>
            {t === 'data' ? '📊 数据浏览' : '🧱 本体编辑'}
          </button>
        ))}
      </div>

      {tab === 'data' ? <DataBrowser /> : <OntologyEditor />}
    </main>
  )
}
```

- [ ] **Step 2: 创建 `frontend/app/admin/data-browser.tsx`**

把现有 `admin/page.tsx` 的数据浏览逻辑（`ADMIN_ENTITIES` + `DataTable` + `formatValue` + fetch effect）原样搬到独立组件，props 改为内部用 hook：

```tsx
'use client'

import { useState, useEffect } from 'react'
import { useWorkspace } from '../workspace-context'
import { useAuth } from '../auth-context'

const ADMIN_ENTITIES = [
  { type: 'User', label: '用户', domain: 'identity' },
  { type: 'Role', label: '角色', domain: 'identity' },
  { type: 'PermissionGrant', label: '权限授予', domain: 'identity' },
  { type: 'OrgUnit', label: '组织单元', domain: 'organization' },
  { type: 'Category', label: '品类', domain: 'category' },
  { type: 'Employee', label: '员工', domain: 'personnel' },
] as const

interface DataResponse { entity_type: string; total: number; items: any[] }

export function DataBrowser() {
  const { selectedWorkspace } = useWorkspace()
  const { token, isAuthenticated } = useAuth()
  const [selected, setSelected] = useState<string>('User')
  const [data, setData] = useState<DataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated || !selectedWorkspace || !token) return
    setLoading(true); setError(null)
    fetch(`/api/admin/customers/${selectedWorkspace}/data/${selected}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async r => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(`${r.status}: ${body.detail || r.statusText}`)
        }
        return r.json()
      })
      .then(d => setData(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected, selectedWorkspace, token, isAuthenticated])

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {ADMIN_ENTITIES.map(e => (
          <button key={e.type} onClick={() => setSelected(e.type)} style={{
            padding: '6px 14px', borderRadius: 6,
            border: `1px solid ${selected === e.type ? '#2563eb' : '#d1d5db'}`,
            background: selected === e.type ? '#2563eb' : '#fff',
            color: selected === e.type ? '#fff' : '#374151',
            cursor: 'pointer', fontSize: 13,
          }}>{e.label} <span style={{ opacity: 0.6, fontSize: 11 }}>({e.domain})</span></button>
        ))}
      </div>
      {loading && <div style={{ padding: 12, color: '#666' }}>加载中...</div>}
      {error && (
        <div style={{
          padding: 12, background: '#fef2f2', border: '1px solid #ef4444',
          borderRadius: 6, color: '#dc2626', marginBottom: 12,
        }}>⚠️ {error}
          {error.includes('403') && (
            <div style={{ marginTop: 6, fontSize: 13 }}>需 system_admin 角色。</div>
          )}
        </div>
      )}
      {data && !loading && !error && <DataTable items={data.items} entityType={selected} />}
    </div>
  )
}

function DataTable({ items, entityType }: { items: any[]; entityType: string }) {
  if (items.length === 0) return <div style={{ padding: 12, color: '#999' }}>无数据</div>
  const allKeys = new Set<string>()
  items.forEach(it => Object.keys(it).forEach(k => allKeys.add(k)))
  const keys = Array.from(allKeys).slice(0, 8)
  return (
    <div>
      <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>共 {items.length} 条 {entityType}</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse', background: '#fff',
          border: '1px solid #e5e7eb', fontSize: 13,
        }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              {keys.map(k => (
                <th key={k} style={{
                  padding: '8px 12px', textAlign: 'left',
                  borderBottom: '1px solid #e5e7eb', fontWeight: 600, color: '#374151',
                }}>{k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 50).map((item, i) => (
              <tr key={item.id || i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                {keys.map(k => (
                  <td key={k} style={{ padding: '8px 12px', color: '#4b5563' }}>
                    {formatValue(item[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length > 50 && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
          只显示前 50 条（共 {items.length}）
        </div>
      )}
    </div>
  )
}

function formatValue(v: any): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v).slice(0, 60)
  if (typeof v === 'string' && v.length > 80) return v.slice(0, 80) + '...'
  return String(v)
}
```

- [ ] **Step 3: 创建 `frontend/app/admin/ontology-editor.tsx`（本体 CRUD 编辑器）**

```tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useWorkspace } from '../workspace-context'
import { useAuth } from '../auth-context'

/**
 * v2 本体编辑器（WP9）。
 *
 * 三个子 tab：Objects / Links / Actions。
 * 每个：表格 + 行级编辑/删除 + 顶部新建。全字段表单（spec §5.3）。
 * 写操作走 POST/PUT/DELETE /api/admin/customers/{ws}/ontology/{type}。
 */

type Kind = 'objects' | 'links' | 'actions'

export function OntologyEditor() {
  const { selectedWorkspace } = useWorkspace()
  const [kind, setKind] = useState<Kind>('objects')
  if (!selectedWorkspace) return <div style={{ padding: 12, color: '#999' }}>未选 workspace</div>
  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        {(['objects', 'links', 'actions'] as const).map(k => (
          <button key={k} onClick={() => setKind(k)} style={{
            padding: '6px 14px', borderRadius: 6,
            border: `1px solid ${kind === k ? '#2563eb' : '#d1d5db'}`,
            background: kind === k ? '#2563eb' : '#fff',
            color: kind === k ? '#fff' : '#374151', cursor: 'pointer', fontSize: 13,
          }}>{k}</button>
        ))}
      </div>
      {kind === 'objects' && <ObjectCrud ws={selectedWorkspace} />}
      {kind === 'links' && <LinkCrud ws={selectedWorkspace} />}
      {kind === 'actions' && <ActionCrud ws={selectedWorkspace} />}
    </div>
  )
}

// ============ 通用 fetch hook ============

function useOntologyFetch(ws: string, kind: Kind) {
  const { token } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reload = useCallback(() => {
    setLoading(true); setError(null)
    const key = kind === 'objects' ? 'objects' : kind
    fetch(`/api/admin/customers/${ws}/ontology/${key}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async r => {
        if (!r.ok) throw new Error(`${r.status}: ${(await r.json().catch(() => ({}))).detail || r.statusText}`)
        return r.json()
      })
      .then(d => setItems(d[kind] || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [ws, kind, token])
  useEffect(() => { reload() }, [reload])
  return { items, loading, error, reload, token }
}

// ============ Objects ============

const EMPTY_OBJECT = {
  id: '', label: '', label_zh: '', comment: '', storage_file: '',
  status: 'active', visibility: 'normal', edits_only_via_actions: false,
  read_roles: '', read_except: '', write_roles: '', write_except: '',
  properties: [] as any[],
}

function ObjectCrud({ ws }: { ws: string }) {
  const { items, loading, error, reload, token } = useOntologyFetch(ws, 'objects')
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)

  async function save(body: any, isNew: boolean) {
    setSaving(true)
    const name = body.id
    const url = isNew
      ? `/api/admin/customers/${ws}/ontology/objects`
      : `/api/admin/customers/${ws}/ontology/objects/${name}`
    const method = isNew ? 'POST' : 'PUT'
    const r = await fetch(url, {
      method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setSaving(false)
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      alert(`保存失败：${r.status} ${d.detail || r.statusText}`)
      return
    }
    setEditing(null)
    reload()
  }

  async function del(name: string) {
    if (!window.confirm(`删除 Object Type "${name}"？properties 子表会一并删除。`)) return
    const r = await fetch(`/api/admin/customers/${ws}/ontology/objects/${name}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      alert(`删除失败：${r.status} ${d.detail || r.statusText}`)
      return
    }
    reload()
  }

  if (loading) return <div style={{ padding: 12, color: '#666' }}>加载中...</div>
  if (error) return <div style={{ padding: 12, color: '#dc2626' }}>⚠️ {error}</div>

  return (
    <div>
      <button onClick={() => setEditing({ ...EMPTY_OBJECT })} style={btnNew}>+ 新建 Object</button>
      {editing && (
        <ObjectForm initial={editing} onSave={save} onCancel={() => setEditing(null)} saving={saving} isNew={!editing.id} />
      )}
      <div style={{ marginTop: 12 }}>
        {items.map((o: any) => (
          <div key={o.id} style={rowStyle}>
            <strong>{o.id}</strong> <span style={{ color: '#666' }}>{o.label_zh || o.label}</span>
            <span style={{ marginLeft: 8, fontSize: 11, color: '#999' }}>{o.properties?.length || 0} props</span>
            <span style={{ float: 'right' }}>
              <button onClick={() => setEditing(o)} style={btnEdit}>编辑</button>
              <button onClick={() => del(o.id)} style={btnDel}>删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ObjectForm({ initial, onSave, onCancel, saving, isNew }:
  { initial: any; onSave: (b: any, isNew: boolean) => void; onCancel: () => void; saving: boolean; isNew: boolean }) {
  const [f, setF] = useState<any>({ ...initial, properties: [...(initial.properties || [])] })
  const set = (k: string, v: any) => setF({ ...f, [k]: v })
  const setProp = (i: number, k: string, v: any) => {
    const props = [...f.properties]; props[i] = { ...props[i], [k]: v }; setF({ ...f, properties: props })
  }
  const addProp = () => setF({ ...f, properties: [...f.properties, { name: '', type: 'string', read_roles: '', read_except: '', write_roles: '', write_except: '' }] })
  const delProp = (i: number) => setF({ ...f, properties: f.properties.filter((_: any, j: number) => j !== i) })

  return (
    <div style={formBox}>
      <h3 style={{ marginTop: 0 }}>{isNew ? '新建' : '编辑'} Object Type</h3>
      <Row label="id (主键)" disabled={!isNew}>
        <input value={f.id} onChange={e => set('id', e.target.value)} style={input} disabled={!isNew} />
      </Row>
      <Row label="label"><input value={f.label} onChange={e => set('label', e.target.value)} style={input} /></Row>
      <Row label="label_zh"><input value={f.label_zh} onChange={e => set('label_zh', e.target.value)} style={input} /></Row>
      <Row label="comment"><input value={f.comment} onChange={e => set('comment', e.target.value)} style={input} /></Row>
      <Row label="storage_file"><input value={f.storage_file} onChange={e => set('storage_file', e.target.value)} style={input} /></Row>
      <Row label="status">
        <select value={f.status} onChange={e => set('status', e.target.value)} style={input}>
          <option value="active">active</option><option value="deprecated">deprecated</option>
        </select>
      </Row>
      <Row label="visibility">
        <select value={f.visibility} onChange={e => set('visibility', e.target.value)} style={input}>
          <option value="normal">normal</option><option value="hidden">hidden</option>
        </select>
      </Row>
      <Row label="edits_only_via_actions">
        <input type="checkbox" checked={!!f.edits_only_via_actions} onChange={e => set('edits_only_via_actions', e.target.checked)} />
      </Row>
      <Row label="read_roles"><input value={f.read_roles} onChange={e => set('read_roles', e.target.value)} style={input} /></Row>
      <Row label="read_except"><input value={f.read_except} onChange={e => set('read_except', e.target.value)} style={input} /></Row>
      <Row label="write_roles"><input value={f.write_roles} onChange={e => set('write_roles', e.target.value)} style={input} /></Row>
      <Row label="write_except"><input value={f.write_except} onChange={e => set('write_except', e.target.value)} style={input} /></Row>

      <h4>Properties</h4>
      {f.properties.map((p: any, i: number) => (
        <div key={i} style={{ marginBottom: 8, padding: 8, background: '#f9fafb', borderRadius: 4 }}>
          <input placeholder="name" value={p.name} onChange={e => setProp(i, 'name', e.target.value)} style={{ ...input, width: 120 }} />
          <input placeholder="type" value={p.type} onChange={e => setProp(i, 'type', e.target.value)} style={{ ...input, width: 140, marginLeft: 4 }} />
          <input placeholder="read_roles" value={p.read_roles} onChange={e => setProp(i, 'read_roles', e.target.value)} style={{ ...input, width: 140, marginLeft: 4 }} />
          <input placeholder="read_except" value={p.read_except} onChange={e => setProp(i, 'read_except', e.target.value)} style={{ ...input, width: 120, marginLeft: 4 }} />
          <input placeholder="write_roles" value={p.write_roles} onChange={e => setProp(i, 'write_roles', e.target.value)} style={{ ...input, width: 140, marginLeft: 4 }} />
          <input placeholder="write_except" value={p.write_except} onChange={e => setProp(i, 'write_except', e.target.value)} style={{ ...input, width: 120, marginLeft: 4 }} />
          <button onClick={() => delProp(i)} style={{ ...btnDel, marginLeft: 4 }}>−</button>
        </div>
      ))}
      <button onClick={addProp} style={btnNew}>+ 添加 Property</button>

      <div style={{ marginTop: 12 }}>
        <button onClick={() => onSave(f, isNew)} disabled={saving} style={btnSave}>{saving ? '保存中...' : '保存'}</button>
        <button onClick={onCancel} style={{ ...btnEdit, marginLeft: 8 }}>取消</button>
      </div>
    </div>
  )
}

// ============ Links ============

const EMPTY_LINK = { id: '', label: '', label_zh: '', comment: '', domain: '', range: '', via: '', use_roles: '', use_except: '' }

function LinkCrud({ ws }: { ws: string }) {
  const { items, loading, error, reload, token } = useOntologyFetch(ws, 'links')
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)

  async function save(body: any, isNew: boolean) {
    setSaving(true)
    const url = isNew ? `/api/admin/customers/${ws}/ontology/links`
      : `/api/admin/customers/${ws}/ontology/links/${body.id}`
    const r = await fetch(url, {
      method: isNew ? 'POST' : 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setSaving(false)
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail || r.statusText}`); return }
    setEditing(null); reload()
  }
  async function del(name: string) {
    if (!window.confirm(`删除 Link "${name}"？`)) return
    const r = await fetch(`/api/admin/customers/${ws}/ontology/links/${name}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail}`); return }
    reload()
  }

  if (loading) return <div style={{ padding: 12, color: '#666' }}>加载中...</div>
  if (error) return <div style={{ padding: 12, color: '#dc2626' }}>⚠️ {error}</div>
  return (
    <div>
      <button onClick={() => setEditing({ ...EMPTY_LINK })} style={btnNew}>+ 新建 Link</button>
      {editing && <SimpleForm initial={editing} fields={['id', 'label', 'label_zh', 'comment', 'domain', 'range', 'via', 'use_roles', 'use_except']}
        onSave={save} onCancel={() => setEditing(null)} saving={saving} isNew={!editing.id} />}
      <div style={{ marginTop: 12 }}>
        {items.map((l: any) => (
          <div key={l.id} style={rowStyle}>
            <strong>{l.id}</strong> <span style={{ color: '#666' }}>{l.domain} → {l.range}</span>
            <span style={{ float: 'right' }}>
              <button onClick={() => setEditing(l)} style={btnEdit}>编辑</button>
              <button onClick={() => del(l.id)} style={btnDel}>删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============ Actions ============

const EMPTY_ACTION = {
  api_name: '', display_name: '', description: '', status: 'active',
  target_object_type: '', edits_object_types: '', locator_field: '',
  parameters: '[]', submission_criteria: '{}', side_effects: '[]',
}

function ActionCrud({ ws }: { ws: string }) {
  const { items, loading, error, reload, token } = useOntologyFetch(ws, 'actions')
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)

  async function save(body: any, isNew: boolean) {
    setSaving(true)
    // edits_object_types 是逗号分隔字符串 → 数组；JSON 字段解析
    const payload: any = {
      ...body,
      edits_object_types: typeof body.edits_object_types === 'string'
        ? body.edits_object_types.split(',').map((s: string) => s.trim()).filter(Boolean) : body.edits_object_types,
      parameters: JSON.parse(body.parameters || '[]'),
      submission_criteria: JSON.parse(body.submission_criteria || '{}'),
      side_effects: JSON.parse(body.side_effects || '[]'),
    }
    const url = isNew ? `/api/admin/customers/${ws}/ontology/actions`
      : `/api/admin/customers/${ws}/ontology/actions/${payload.api_name}`
    const r = await fetch(url, {
      method: isNew ? 'POST' : 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    setSaving(false)
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail || r.statusText}`); return }
    setEditing(null); reload()
  }
  async function del(apiName: string) {
    if (!window.confirm(`删除 Action "${apiName}"？`)) return
    const r = await fetch(`/api/admin/customers/${ws}/ontology/actions/${apiName}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail}`); return }
    reload()
  }

  if (loading) return <div style={{ padding: 12, color: '#666' }}>加载中...</div>
  if (error) return <div style={{ padding: 12, color: '#dc2626' }}>⚠️ {error}</div>
  return (
    <div>
      <button onClick={() => setEditing({ ...EMPTY_ACTION })} style={btnNew}>+ 新建 Action</button>
      {editing && <ActionForm initial={editing} onSave={save} onCancel={() => setEditing(null)} saving={saving} isNew={!editing.api_name} />}
      <div style={{ marginTop: 12 }}>
        {items.map((a: any) => (
          <div key={a.api_name} style={rowStyle}>
            <strong>{a.api_name}</strong> <span style={{ color: '#666' }}>{a.display_name} → {a.target_object_type}</span>
            <span style={{ float: 'right' }}>
              <button onClick={() => setEditing({
                ...a,
                edits_object_types: (a.edits_object_types || []).join(', '),
                parameters: JSON.stringify(a.parameters || [], null, 2),
                submission_criteria: JSON.stringify(a.submission_criteria || {}, null, 2),
                side_effects: JSON.stringify(a.side_effects || [], null, 2),
              })} style={btnEdit}>编辑</button>
              <button onClick={() => del(a.api_name)} style={btnDel}>删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ActionForm({ initial, onSave, onCancel, saving, isNew }: any) {
  const [f, setF] = useState<any>({ ...initial })
  const set = (k: string, v: any) => setF({ ...f, [k]: v })
  return (
    <div style={formBox}>
      <h3 style={{ marginTop: 0 }}>{isNew ? '新建' : '编辑'} Action</h3>
      <Row label="api_name (主键)" disabled={!isNew}>
        <input value={f.api_name} onChange={e => set('api_name', e.target.value)} style={input} disabled={!isNew} />
      </Row>
      <Row label="display_name"><input value={f.display_name} onChange={e => set('display_name', e.target.value)} style={input} /></Row>
      <Row label="description"><input value={f.description} onChange={e => set('description', e.target.value)} style={input} /></Row>
      <Row label="status">
        <select value={f.status} onChange={e => set('status', e.target.value)} style={input}>
          <option value="active">active</option><option value="deprecated">deprecated</option>
        </select>
      </Row>
      <Row label="target_object_type"><input value={f.target_object_type} onChange={e => set('target_object_type', e.target.value)} style={input} /></Row>
      <Row label="edits_object_types (逗号分隔)"><input value={f.edits_object_types} onChange={e => set('edits_object_types', e.target.value)} style={input} /></Row>
      <Row label="locator_field"><input value={f.locator_field} onChange={e => set('locator_field', e.target.value)} style={input} /></Row>
      <Row label="parameters (JSON)">
        <textarea value={f.parameters} onChange={e => set('parameters', e.target.value)} style={{ ...input, height: 80, fontFamily: 'monospace' }} />
      </Row>
      <Row label="submission_criteria (JSON)">
        <textarea value={f.submission_criteria} onChange={e => set('submission_criteria', e.target.value)} style={{ ...input, height: 80, fontFamily: 'monospace' }} />
      </Row>
      <Row label="side_effects (JSON)">
        <textarea value={f.side_effects} onChange={e => set('side_effects', e.target.value)} style={{ ...input, height: 80, fontFamily: 'monospace' }} />
      </Row>
      <div style={{ marginTop: 12 }}>
        <button onClick={() => onSave(f, isNew)} disabled={saving} style={btnSave}>{saving ? '保存中...' : '保存'}</button>
        <button onClick={onCancel} style={{ ...btnEdit, marginLeft: 8 }}>取消</button>
      </div>
    </div>
  )
}

// ============ 通用 Simple 表单（Link 用）============

function SimpleForm({ initial, fields, onSave, onCancel, saving, isNew }: any) {
  const [f, setF] = useState<any>({ ...initial })
  const set = (k: string, v: any) => setF({ ...f, [k]: v })
  const idField = fields[0]
  return (
    <div style={formBox}>
      <h3 style={{ marginTop: 0 }}>{isNew ? '新建' : '编辑'}</h3>
      {fields.map((k: string) => (
        <Row key={k} label={k} disabled={!isNew && k === idField}>
          <input value={f[k] || ''} onChange={e => set(k, e.target.value)} style={input}
            disabled={!isNew && k === idField} />
        </Row>
      ))}
      <div style={{ marginTop: 12 }}>
        <button onClick={() => onSave(f, isNew)} disabled={saving} style={btnSave}>{saving ? '保存中...' : '保存'}</button>
        <button onClick={onCancel} style={{ ...btnEdit, marginLeft: 8 }}>取消</button>
      </div>
    </div>
  )
}

// ============ 小组件 + 样式 ============

function Row({ label, children, disabled }: { label: string; children: React.ReactNode; disabled?: boolean }) {
  return (
    <div style={{ marginBottom: 6, display: 'flex', alignItems: 'center' }}>
      <label style={{ width: 200, color: disabled ? '#999' : '#374151', fontSize: 13 }}>{label}</label>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  )
}

const input: React.CSSProperties = {
  padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 4, width: '100%', fontSize: 13,
}
const formBox: React.CSSProperties = {
  marginTop: 12, padding: 16, background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6,
}
const rowStyle: React.CSSProperties = {
  padding: '10px 12px', background: '#fff', border: '1px solid #e5e7eb', borderRadius: 4, marginBottom: 4,
}
const btnNew: React.CSSProperties = {
  padding: '6px 14px', borderRadius: 6, border: '1px solid #16a34a', background: '#16a34a', color: '#fff', cursor: 'pointer', fontSize: 13,
}
const btnEdit: React.CSSProperties = {
  padding: '4px 10px', borderRadius: 4, border: '1px solid #d1d5db', background: '#fff', color: '#374151', cursor: 'pointer', fontSize: 12, marginLeft: 4,
}
const btnDel: React.CSSProperties = {
  padding: '4px 10px', borderRadius: 4, border: '1px solid #ef4444', background: '#fff', color: '#dc2626', cursor: 'pointer', fontSize: 12, marginLeft: 4,
}
const btnSave: React.CSSProperties = {
  padding: '6px 18px', borderRadius: 6, border: '1px solid #2563eb', background: '#2563eb', color: '#fff', cursor: 'pointer', fontSize: 13,
}
```

- [ ] **Step 4: 类型检查 + 构建**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -15
```
Expected: 无与本次改动相关的错误。

- [ ] **Step 5: 手动冒烟（人工，记录结果）**

启动后端 + 前端：
- 后端：`/opt/miniconda3/envs/store-ontology/bin/python -m uvicorn agent.main:app --port 8123`（如未在跑）
- 前端：`cd frontend && npm run dev`

浏览器打开 `/admin`，登录 admin 账号：
1. 切"本体编辑" → Objects → 看到列表
2. 点"+ 新建 Object" → 填 `id=TestX, label=测试` → 保存 → 列表出现
3. 点"编辑" → 加一个 property → 保存 → 列表 props 数量更新
4. 点"删除" → 确认 → 列表消失
5. Links / Actions 各走一遍

记录：是否每步都成功；如有失败，记 status + detail。

- [ ] **Step 6: 提交**

```bash
git add frontend/app/admin/page.tsx frontend/app/admin/data-browser.tsx frontend/app/admin/ontology-editor.tsx
git commit -m "feat(WP9): admin 页 tab 化 + 本体 CRUD 编辑器（全字段表单）"
```

---

## Task 6: WP10 文档

**Files:**
- Modify: `docs/design/20-api-data-contract.md`
- Modify: `docs/design/00-architecture.md`
- Modify: `README.md`（条件性）

- [ ] **Step 1: 在 `docs/design/20-api-data-contract.md` 追加 admin 本体 CRUD 章节**

先 `Read docs/design/20-api-data-contract.md` 找合适插入位置（通常 admin 章节附近）。追加：

```markdown
## Admin 本体 CRUD（WP7+WP8）

九个写端点（鉴权：system_admin 角色，或 bootstrap 初始 `admin` 账号；其余 403）：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/admin/customers/{cid}/ontology/objects` | 新建/覆盖 Object Type（upsert） |
| PUT | `/api/admin/customers/{cid}/ontology/objects/{name}` | 更新 Object Type（路径 name 覆盖 body id） |
| DELETE | `/api/admin/customers/{cid}/ontology/objects/{name}` | 删除 Object Type（不存在返回 404） |
| POST/PUT/DELETE | `/api/admin/customers/{cid}/ontology/links[/{name}]` | 同上，主键 `name` |
| POST/PUT/DELETE | `/api/admin/customers/{cid}/ontology/actions[/{api_name}]` | 同上，主键 `api_name` |

**Body**：与 GET 端点返回结构对称（round-trip）。Object Type body 含 `properties: [...]` 子表；POST/PUT 会**全量替换** properties。

**响应**：`{created: <obj>}` / `{updated: <obj>}` / `{deleted: true}`。

**失效**：每个写端点成功后调用 `invalidate_workspace(ws)` —— 下次 `bootstrap_workspace(ws)` 从 PG 重载，新 schema 立即可见（运行时无过期数据）。进程内缓存（单进程 uvicorn 部署够用；多副本部署需扩展，见 spec §10）。

**错误**：404 不存在 / 422 body 缺主键或字段非法 / 403 非 admin。
```

- [ ] **Step 2: 在 `docs/design/00-architecture.md` 加一段 admin 本体 PG 化说明**

先 `Read docs/design/00-architecture.md` 找 admin 或存储章节。追加段落：

```markdown
### Admin 本体 CRUD（WP7-WP8）

管理员可在 admin UI 直接编辑本体 schema（Object/Link/Action Type），不再需要改 TTL/YAML
文件 + 重启。写端点走 `PgOntologyRepository.upsert_*` / `delete_*`（WP3），编辑后通过
`invalidate_workspace(ws)` 失效进程内的 `WorkspaceAgentInstance` 缓存，下次读取从 PG 重载。

业务数据（User/Role/Task 等）的 CRUD 仍走对话/Action，保留 `edits-only-via-actions` 治理
与 Action 审计——HTTP 层只暴露本体 schema 的写。
```

- [ ] **Step 3: 检查 `README.md` 是否有 admin 段落**

`Read README.md`。若已有"admin"或"管理"相关段落，补一行写操作说明；若无则跳过本步（spec §6 允许跳过）。

- [ ] **Step 4: 提交**

```bash
git add docs/design/20-api-data-contract.md docs/design/00-architecture.md README.md
git commit -m "docs(WP10): admin 本体 CRUD API + 失效说明"
```

（若 README 未改动，从 `git add` 去掉它。）

---

## Self-Review（写完后自查，非执行步骤）

执行人在完成所有 Task 后回头核对：

- [ ] Spec §3.1 九端点全部实现？→ Task 3
- [ ] Spec §3.2 转换器 round-trip？→ Task 1
- [ ] Spec §3.3 `require_admin` 鉴权？→ Task 2 + Task 3 Step 4
- [ ] Spec §4.2 失效接入？→ Task 3 每个端点都有 `invalidate_workspace(ws_name)`
- [ ] Spec §5.1 BFF PUT/DELETE？→ Task 4
- [ ] Spec §5.2/5.3 tab + 全字段表单？→ Task 5
- [ ] Spec §6 三处文档？→ Task 6
- [ ] Spec §7 六个测试 case？→ Task 3（鉴权、round-trip、PUT replace、DELETE+404、失效、+422 invalid body、link/action crud）
- [ ] 无 TODO/TBD/占位符？全文 Ctrl-F 检查
- [ ] 命名一致：`require_admin` / `invalidate_workspace` / `json_to_*` / `_ontology_to_dict` 全文统一

---

## Verification（最终验收）

```bash
# 1. 全套 admin 测试
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_admin_ontology_api.py -v

# 2. 回归（PG ontology + dashboard）
DATABASE_URL=postgresql://ontology:ontology@localhost:5433/ontology \
  /opt/miniconda3/envs/store-ontology/bin/python -m pytest \
  agent/tests/test_pg_ontology_repo.py agent/tests/test_dashboard_api.py -v

# 3. 前端类型
cd frontend && npx tsc --noEmit
```

全部通过 + 手动冒烟（Task 5 Step 5）通过 = WP7-WP10 完成。
