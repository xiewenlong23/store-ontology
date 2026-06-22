"""WP6 信任修复测试。

验证设计文档 §5 WP6：
- actor_role 不再是 execute_action 工具参数（签名检查）
- actor 从 _get_actor 派生（auth_ctx → Employee → role）
- crud_tools 的 update_task 不再硬编码 actor
- auth_middleware 强制模式：AUTH_REQUIRED=true + 无 token → 401
- auth_middleware 强制模式：跨 ws 越权 → 401
- 豁免路径（/health、/api/auth/login）无 token 仍可访问
"""
import inspect
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


# ============ 签名级信任修复 ============

class TestSignatureFix:

    def _get_underlying_func(self, tool_obj):
        """@tool 装饰后变成 StructuredTool，取原函数验签名。"""
        return getattr(tool_obj, "func", tool_obj)

    def test_execute_action_no_actor_role_param(self):
        """execute_action 工具签名不再含 actor_role 参数（LLM 不能自报）。"""
        from agent.tools.action_tools import execute_action
        func = self._get_underlying_func(execute_action)
        params = inspect.signature(func).parameters
        assert "actor_role" not in params, \
            "execute_action 不应再有 actor_role 参数（WP6 信任修复）"

    def test_execute_action_params_only_action_type_params_workspace(self):
        """execute_action 只暴露 action_type/params/workspace_name/org_unit_id。"""
        from agent.tools.action_tools import execute_action
        func = self._get_underlying_func(execute_action)
        params = inspect.signature(func).parameters
        expected = {"action_type", "params", "workspace_name", "org_unit_id"}
        assert set(params.keys()) == expected

    def test_crud_tools_update_task_no_hardcoded_actor(self):
        """crud_tools.py 源码不再含 actor={'role': 'store_manager'} 硬编码。"""
        src = Path(BACKEND_DIR / "tools" / "crud_tools.py").read_text(encoding="utf-8")
        assert "actor={\"role\": \"store_manager\"}" not in src, \
            "crud_tools 不应再硬编码 actor role（应从 _get_actor 派生）"
        assert "_get_actor" in src


# ============ _get_actor 派生逻辑 ============

class TestGetActor:

    def test_no_auth_ctx_returns_system_admin(self, monkeypatch):
        """无 main.auth_ctx contextvar（离线/旧测试）→ 兜底 system_admin。"""
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "main":
                raise ImportError("模拟 main 不可用")
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", fake_import)

        from agent.tools.shared import _get_actor
        actor = _get_actor()
        assert actor["role"] == "system_admin"

    def test_anonymous_with_auth_required_off_returns_admin(self, monkeypatch):
        """AUTH_REQUIRED=false + auth_ctx anonymous → 兜底 admin（测试模式）。"""
        monkeypatch.setenv("AUTH_REQUIRED", "false")

        # 模拟 main.auth_ctx 存在但 anonymous
        class FakeMain:
            class _CtxMgr:
                def get(self):
                    from engine.auth import AuthContext
                    return AuthContext.anonymous()
            auth_ctx = _CtxMgr()
            tenant_ctx = _CtxMgr()

        sys.modules["main"] = FakeMain()
        try:
            # reload shared 让它读到 fake main
            import importlib
            import agent.tools.shared as shared_mod
            importlib.reload(shared_mod)
            actor = shared_mod._get_actor()
            assert actor["role"] == "system_admin"
        finally:
            del sys.modules["main"]
            importlib.reload(shared_mod)

    def test_anonymous_with_auth_required_on_returns_anonymous(self, monkeypatch):
        """AUTH_REQUIRED=true + auth_ctx anonymous → anonymous（生产强制）。"""
        monkeypatch.setenv("AUTH_REQUIRED", "true")

        class FakeMain:
            class _CtxMgr:
                def get(self):
                    from engine.auth import AuthContext
                    return AuthContext.anonymous()
            auth_ctx = _CtxMgr()
            tenant_ctx = _CtxMgr()

        sys.modules["main"] = FakeMain()
        try:
            import importlib
            import agent.tools.shared as shared_mod
            importlib.reload(shared_mod)
            actor = shared_mod._get_actor()
            assert actor["role"] == "anonymous"
        finally:
            del sys.modules["main"]
            importlib.reload(shared_mod)


# ============ auth_middleware 强制模式（端到端）============

@pytest.fixture
def strict_auth_client(tmp_path, monkeypatch):
    """AUTH_REQUIRED=true 的 TestClient + 临时 workspace。"""
    monkeypatch.setenv("JWT_SECRET", "test_secret_strict_mode_32_bytes!")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "test_admin_strict_pw")

    from engine import pack as pack_mod
    pack_mod.clear_workspace_dirs()
    td = tmp_path / "ws_data"
    td.mkdir()
    (td / "users.json").write_text(json.dumps([{
        "id": "u_admin", "username": "admin", "status": "active",
        "display_name": "Admin",
        "password_hash": _hash_pw("admin123")}], ensure_ascii=False), encoding="utf-8")
    pack_mod.register_workspace_dir(pack_mod.WorkspaceDef(
        name="_strict_test_ws", display_name="Strict", domains=[], processes=[],
        data_dir=str(td), required_domain_kinds=[]))

    import main as main_mod
    client = TestClient(main_mod.app)
    yield client

    pack_mod.clear_workspace_dirs()


def _hash_pw(p: str) -> str:
    from engine.auth import hash_password
    return hash_password(p)


class TestStrictAuthMiddleware:

    def test_health_exempt_no_token(self, strict_auth_client):
        """/health 无 token 也能访问（豁免）。"""
        r = strict_auth_client.get("/health")
        assert r.status_code == 200

    def test_login_exempt_no_token(self, strict_auth_client):
        """/api/auth/login 无 token 也能访问（豁免）。"""
        r = strict_auth_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"})
        assert r.status_code == 200

    def test_me_without_token_returns_401(self, strict_auth_client):
        """AUTH_REQUIRED=true + /me 无 token → 401。"""
        r = strict_auth_client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_valid_token_passes(self, strict_auth_client):
        """有效 token → 通过。"""
        login = strict_auth_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"}).json()
        r = strict_auth_client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {login['token']}",
            "X-Workspace": "_strict_test_ws",
        })
        assert r.status_code == 200
        assert r.json()["authenticated"] is True

    def test_cross_workspace_denied(self, strict_auth_client):
        """token 不含 X-Workspace 指向的 ws → 401（跨 ws 越权防护）。"""
        login = strict_auth_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"}).json()
        # token ws=['_strict_test_ws']，但请求 X-Workspace=other_ws
        r = strict_auth_client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {login['token']}",
            "X-Workspace": "other_ws_not_in_token",
        })
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, strict_auth_client):
        """无效 token → 401。"""
        r = strict_auth_client.get("/api/auth/me", headers={
            "Authorization": "Bearer not_a_valid_token"})
        assert r.status_code == 401


# ============ dashboard 用请求级 tenant_ctx（不再 inst.tenant_context）============

class TestDashboardTenantContext:

    def test_dashboard_uses_request_tenant_ctx(self):
        """dashboard 端点代码用 tenant_ctx.get() 而非 inst.tenant_context。

        用 AST 解析（避免注释里的字样误伤）。
        """
        import ast
        # P5：dashboard 端点已从 main.py 拆到 agent/routers/dashboard.py。
        dashboard_path = BACKEND_DIR / "routers" / "dashboard.py"
        tree = ast.parse(dashboard_path.read_text(encoding="utf-8"))

        # 找所有 dashboard_xxx 函数定义（含 async）
        dashboard_funcs = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("dashboard_")
        ]
        assert dashboard_funcs, "应至少有一个 dashboard_* 端点"

        for fn in dashboard_funcs:
            # 遍历函数体里的 Attribute 访问，检测 inst.tenant_context
            for node in ast.walk(fn):
                if isinstance(node, ast.Attribute):
                    if node.attr == "tenant_context" and \
                       isinstance(node.value, ast.Name) and \
                       node.value.id == "inst":
                        pytest.fail(
                            f"dashboard 端点 {fn.name} 仍用 inst.tenant_context "
                            f"（应改用 tenant_ctx.get() 反映请求级 org_unit）")
            # 确认至少调用了 tenant_ctx.get()
            src_seg = ast.get_source_segment(dashboard_path.read_text(encoding="utf-8"), fn)
            assert "tenant_ctx.get()" in src_seg, \
                f"dashboard 端点 {fn.name} 应调用 tenant_ctx.get()"
