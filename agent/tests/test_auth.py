"""WP2 认证机制测试（agent 层 JWT + middleware + endpoints）。

验证设计文档 §5 WP2：
- engine/auth.py 的 JWT 工具（create_access_token/decode_token/issue_session_tokens）
- engine/auth.py 的 AuthContext（含跨 ws 越权防护）
- engine/auth_audit.py 的审计日志
- main.py 的 auth_middleware（WP2 只注入不强制）+ 4 个 endpoints

用 TestClient（FastAPI in-process）跑端到端，不依赖 LLM。
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


# ============ 单元：JWT 工具 ============

class TestJWTTools:

    def test_access_token_roundtrip(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "test_secret_xxx")
        # 重新 import 让 _get_secret 读到新 env（_get_secret 是函数内查 env，无需重 import）
        from engine.auth import create_access_token, decode_token
        token = create_access_token("u1", "s1", ["jjy", "customerA"])
        payload = decode_token(token, expected_typ="access")
        assert payload["sub"] == "u1"
        assert payload["sid"] == "s1"
        assert payload["ws"] == ["jjy", "customerA"]
        assert payload["typ"] == "access"
        assert "iat" in payload and "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_decode_expired_token_fails(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "test_secret_xxx")
        from engine.auth import create_access_token, decode_token, TokenError
        # 手工签一个已过期的 token
        import jwt
        now = int(time.time())
        expired = jwt.encode(
            {"sub": "u1", "sid": "s1", "ws": [], "typ": "access",
             "iat": now - 100, "exp": now - 10},
            "test_secret_xxx", algorithm="HS256")
        with pytest.raises(TokenError, match="过期"):
            decode_token(expired, expected_typ="access")

    def test_decode_wrong_secret_fails(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "real_secret")
        from engine.auth import create_access_token
        token = create_access_token("u1", "s1", ["jjy"])
        # 用错的 secret 解
        import jwt
        from engine.auth import TokenError
        try:
            jwt.decode(token, "wrong_secret", algorithms=["HS256"])
            assert False, "应抛 InvalidTokenError"
        except jwt.InvalidTokenError:
            pass  # 预期

    def test_decode_wrong_type_fails(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "test_secret")
        from engine.auth import create_refresh_token, decode_token, TokenError
        refresh = create_refresh_token("u1", "s1")
        with pytest.raises(TokenError, match="类型错误"):
            decode_token(refresh, expected_typ="access")

    def test_issue_session_tokens_returns_pair(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "test_secret")
        from engine.auth import issue_session_tokens, decode_token
        result = issue_session_tokens("u1", ["jjy", "customerA"])
        assert "access_token" in result
        assert "refresh_token" in result
        assert "session_id" in result
        assert result["expires_in"] > 0
        # 两 token session_id 一致
        access_payload = decode_token(result["access_token"], expected_typ="access")
        refresh_payload = decode_token(result["refresh_token"], expected_typ="refresh")
        assert access_payload["sid"] == refresh_payload["sid"]
        assert access_payload["sid"] == result["session_id"]
        # access 含 ws 白名单，refresh 不含
        assert access_payload["ws"] == ["jjy", "customerA"]
        assert "ws" not in refresh_payload


# ============ 单元：AuthContext ============

class TestAuthContext:

    def test_anonymous_unauthenticated(self):
        from engine.auth import AuthContext
        a = AuthContext.anonymous()
        assert not a.is_authenticated()
        assert not a.can_access_workspace("any")

    def test_authenticated_user(self):
        from engine.auth import AuthContext
        a = AuthContext(user_id="u1", session_id="s1",
                        workspace_names=("jjy", "customerA"))
        assert a.is_authenticated()
        assert a.can_access_workspace("jjy")
        assert a.can_access_workspace("customerA")
        assert not a.can_access_workspace("other")   # 跨 ws 越权防护

    def test_workspace_whitelist_enforced(self):
        from engine.auth import AuthContext
        a = AuthContext(user_id="u1", session_id="s1", workspace_names=("jjy",))
        assert a.can_access_workspace("jjy")
        assert not a.can_access_workspace("customerA")


# ============ 单元：auth_audit ============

class TestAuthAudit:

    def test_log_event_creates_file(self, tmp_path, monkeypatch):
        """审计事件写入文件。"""
        from engine import auth_audit as aa
        # 重定向 _audit_path 到 tmp_path
        monkeypatch.setattr(aa, "_audit_path", lambda: str(tmp_path / "auth_audit.json"))
        aa.log_auth_event("login", username="alice", user_id="u1", outcome="success")
        data = json.loads((tmp_path / "auth_audit.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["event"] == "login"
        assert data[0]["username"] == "alice"
        assert data[0]["outcome"] == "success"

    def test_multiple_events_append(self, tmp_path, monkeypatch):
        from engine import auth_audit as aa
        monkeypatch.setattr(aa, "_audit_path", lambda: str(tmp_path / "auth_audit.json"))
        for i in range(5):
            aa.log_auth_event("login", username=f"u{i}", outcome="success")
        data = json.loads((tmp_path / "auth_audit.json").read_text(encoding="utf-8"))
        assert len(data) == 5

    def test_log_failure_doesnt_raise(self, tmp_path, monkeypatch):
        """审计写入失败不应抛（用不可写路径模拟）。"""
        from engine import auth_audit as aa
        # 用一个不可写的目录（不存在且无法创建）
        monkeypatch.setattr(aa, "_audit_path",
                            lambda: "/nonexistent_root_dir/auth_audit.json")
        # 不应抛
        aa.log_auth_event("login", username="x", outcome="success")


# ============ 集成：FastAPI endpoints ============

@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """提供一个隔离的 FastAPI TestClient + 临时 workspace 注册。

    - JWT_SECRET 用固定值（避免用 env 默认）
    - INITIAL_ADMIN_PASSWORD 给真实 workspace 的 seed admin 一个不同密码，
      避免与 _test_ws 的 admin123 冲突
    - 临时 _test_ws 注册，data_dir 在 tmp_path，避免污染真实 workspace/*/data/
    """
    # 必须在 import main 前 set env（main.py 启动时执行 seed_all_workspaces）
    monkeypatch.setenv("JWT_SECRET", "test_secret_fixed_32bytes_long_enough!")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "real_ws_different_pw_456")
    # 用临时 data_dir 注册一个测试 workspace，避免污染真实 workspace/*/data/
    from engine import pack as pack_mod
    pack_mod.clear_workspace_dirs()
    test_data = tmp_path / "ws_data"
    test_data.mkdir()
    (test_data / "users.json").write_text(json.dumps([{
        "id": "user_test_admin", "username": "admin", "status": "active",
        "display_name": "测试管理员",
        "password_hash": _hash_pw("admin123")}], ensure_ascii=False), encoding="utf-8")
    pack_mod.register_workspace_dir(pack_mod.WorkspaceDef(
        name="_test_ws", display_name="测试", domains=[], processes=[],
        data_dir=str(test_data)))

    import main as main_mod
    client = TestClient(main_mod.app)
    yield client

    pack_mod.clear_workspace_dirs()
    # 恢复真实 workspace 注册（避免污染后续测试依赖真实 workspace 的）。
    # 注意：bootstrap() 通过 importlib.import_module 触发自注册，但 Python module
    # cache 会让已 import 的 workspace.*.workspace 不再重跑顶层 register_workspace_dir。
    # 故用 importlib.reload 强制重跑。
    import importlib
    for ws_name in ["retail", "jjy", "customerA"]:
        mod_name = f"workspace.{ws_name}.workspace"
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


def _hash_pw(p: str) -> str:
    from engine.auth import hash_password
    return hash_password(p)


class TestLoginEndpoint:

    def test_login_success(self, app_client):
        """正确凭证 → 返回 token + memberships（至少含 _test_ws）。"""
        r = app_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "token" in body
        assert "refresh_token" in body
        assert "session_id" in body
        # 至少含 _test_ws（真实 workspace 用不同密码，不该匹配 admin123）
        ws_names = {m["workspace_name"] for m in body["memberships"]}
        assert "_test_ws" in ws_names
        test_m = next(m for m in body["memberships"]
                      if m["workspace_name"] == "_test_ws")
        assert test_m["username"] == "admin"

    def test_login_wrong_password(self, app_client):
        r = app_client.post("/api/auth/login", json={
            "username": "admin", "password": "wrong"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert "token" not in body

    def test_login_unknown_user(self, app_client):
        r = app_client.post("/api/auth/login", json={
            "username": "nobody", "password": "any"})
        assert r.status_code == 200
        assert r.json()["success"] is False


class TestMeEndpoint:

    def test_me_with_valid_token(self, app_client):
        """带 token 调 /me → 返回认证信息。"""
        login = app_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"}).json()
        token = login["token"]
        r = app_client.get("/api/auth/me",
                           headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["authenticated"] is True
        assert "user_id" in body
        assert "_test_ws" in body["workspace_names"]

    def test_me_without_token(self, app_client):
        """无 token 调 /me（WP2 阶段不强制）→ authenticated=False。"""
        r = app_client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["authenticated"] is False

    def test_me_with_invalid_token(self, app_client):
        """无效 token → authenticated=False（WP2 阶段不阻断）。"""
        r = app_client.get("/api/auth/me",
                           headers={"Authorization": "Bearer invalid_token_xxx"})
        assert r.status_code == 200
        assert r.json()["authenticated"] is False


class TestAuthMiddleware:

    def test_middleware_injects_auth_ctx_for_valid_token(self, app_client):
        """middleware 注入 auth_ctx（通过 /me 反映）。"""
        login = app_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"}).json()
        # /me 应反映认证态
        r = app_client.get("/api/auth/me",
                           headers={"Authorization": f"Bearer {login['token']}"})
        body = r.json()
        assert body["authenticated"] is True
        assert body["user_id"] == login["memberships"][0]["user_id"]

    def test_exempt_path_works_without_token(self, app_client):
        """豁免路径 /health 无 token 也通过。"""
        r = app_client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_other_endpoints_still_work_without_token_in_wp2(self, app_client):
        """WP2 阶段 middleware 不强制，无 token 也能访问业务端点（向后兼容）。"""
        # /api/auth/me 在无 token 时返回 authenticated=False（不 401）
        r = app_client.get("/api/auth/me")
        assert r.status_code == 200


class TestLogoutEndpoint:

    def test_logout_returns_success(self, app_client):
        r = app_client.post("/api/auth/logout")
        assert r.status_code == 200
        assert r.json()["success"] is True


class TestRefreshEndpoint:

    def test_refresh_returns_unsupported_in_mvp(self, app_client):
        """MVP 阶段 refresh 端点要求重新 login。"""
        login = app_client.post("/api/auth/login", json={
            "username": "admin", "password": "admin123"}).json()
        r = app_client.post("/api/auth/refresh",
                            json={"refresh_token": login["refresh_token"]})
        assert r.status_code == 200
        # MVP 简化：refresh 失败，提示重新登录
        body = r.json()
        assert body["success"] is False

    def test_refresh_with_invalid_token(self, app_client):
        r = app_client.post("/api/auth/refresh",
                            json={"refresh_token": "invalid_xxx"})
        assert r.status_code == 200
        assert r.json()["success"] is False
