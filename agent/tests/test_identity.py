"""WP1 identity domain 测试。

验证设计文档 §3.1/§5 WP1：
- agent/engine/auth.py 的 hash_password/verify_password（bcrypt）
- agent/engine/identity.py 的 verify_credentials / list_user_workspaces / seed_workspace_identity
- 三家 workspace 的 identity TTL 可被 parser 解析（含 4 个 Object Type）
- workspace.py 注册了 identity domain
- schemas.py 新增的 4 个枚举（UserStatus/ResourceType/PermissionAction/PermissionEffect）
"""
import json
import os
import sys
from pathlib import Path

import pytest

# 让 from engine... 可用
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.auth import hash_password, verify_password
from engine.identity import (
    verify_credentials, list_user_workspaces,
    seed_workspace_identity, seed_all_workspaces,
)
from engine.schemas import UserStatus, ResourceType, PermissionAction, PermissionEffect


# ============ auth.py: hash/verify ============

class TestPasswordHash:
    def test_hash_and_verify_roundtrip(self):
        h = hash_password("secret123")
        assert h and h != "secret123"
        assert verify_password("secret123", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("secret123")
        assert verify_password("wrong", h) is False

    def test_verify_empty_hash(self):
        assert verify_password("anything", "") is False

    def test_hash_is_unique_per_call(self):
        """bcrypt 每次生成不同 salt，相同密码两次 hash 不同。"""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
        assert verify_password("same", h1) and verify_password("same", h2)


# ============ identity.py: verify_credentials / list_user_workspaces ============

@pytest.fixture
def isolated_workspace(tmp_path, monkeypatch):
    """临时注册一个 workspace，data_dir 指向 tmp_path。

    避免 seed_all_workspaces 污染真实 workspace/*/data/users.json。
    """
    from engine import pack as pack_mod
    # 清空注册表，隔离本测试
    pack_mod.clear_workspace_dirs()

    fake_ws = pack_mod.WorkspaceDef(
        name="_test_ws", display_name="测试 workspace",
        domains=[], processes=[], data_dir=str(tmp_path),
        required_domain_kinds=[])   # 测试 fixture，关闭 4 类必备校验
    pack_mod.register_workspace_dir(fake_ws)
    yield fake_ws.name
    pack_mod.clear_workspace_dirs()


class TestVerifyCredentials:

    def test_no_users_returns_none(self, isolated_workspace, tmp_path):
        """空 users.json → verify_credentials 返回 None。"""
        (tmp_path / "users.json").write_text("[]", encoding="utf-8")
        assert verify_credentials(isolated_workspace, "admin", "any") is None

    def test_correct_credentials(self, isolated_workspace, tmp_path):
        """正确用户名密码 → 返回 user（剥离 password_hash）。"""
        (tmp_path / "users.json").write_text(json.dumps([{
            "id": "u1", "username": "alice", "display_name": "Alice",
            "status": "active",
            "password_hash": hash_password("s3cret"),
        }], ensure_ascii=False), encoding="utf-8")
        u = verify_credentials(isolated_workspace, "alice", "s3cret")
        assert u is not None
        assert u["id"] == "u1"
        assert u["username"] == "alice"
        # password_hash 必须被剥离
        assert "password_hash" not in u

    def test_wrong_password(self, isolated_workspace, tmp_path):
        (tmp_path / "users.json").write_text(json.dumps([{
            "id": "u1", "username": "alice", "status": "active",
            "password_hash": hash_password("s3cret"),
        }], ensure_ascii=False), encoding="utf-8")
        assert verify_credentials(isolated_workspace, "alice", "wrong") is None

    def test_unknown_user(self, isolated_workspace, tmp_path):
        (tmp_path / "users.json").write_text(json.dumps([{
            "id": "u1", "username": "alice", "status": "active",
            "password_hash": hash_password("s3cret"),
        }], ensure_ascii=False), encoding="utf-8")
        assert verify_credentials(isolated_workspace, "bob", "s3cret") is None

    def test_disabled_user_rejected(self, isolated_workspace, tmp_path):
        (tmp_path / "users.json").write_text(json.dumps([{
            "id": "u1", "username": "alice", "status": "disabled",
            "password_hash": hash_password("s3cret"),
        }], ensure_ascii=False), encoding="utf-8")
        assert verify_credentials(isolated_workspace, "alice", "s3cret") is None

    def test_unknown_workspace(self, isolated_workspace):
        """未注册 workspace → None。"""
        assert verify_credentials("does_not_exist", "any", "any") is None


class TestListUserWorkspaces:

    def test_scan_finds_matching_workspaces(self, monkeypatch, tmp_path):
        from engine import pack as pack_mod
        pack_mod.clear_workspace_dirs()
        try:
            # 两个 workspace 都注册 alice
            ws1_dir = tmp_path / "ws1" / "data"
            ws2_dir = tmp_path / "ws2" / "data"
            ws1_dir.mkdir(parents=True)
            ws2_dir.mkdir(parents=True)
            (ws1_dir / "users.json").write_text(json.dumps([{
                "id": "u1", "username": "alice", "status": "active",
                "display_name": "Alice",
                "password_hash": hash_password("s3cret")}], ensure_ascii=False), encoding="utf-8")
            (ws2_dir / "users.json").write_text(json.dumps([{
                "id": "u2", "username": "alice", "status": "active",
                "display_name": "Alice B",
                "password_hash": hash_password("s3cret")}], ensure_ascii=False), encoding="utf-8")
            (tmp_path / "ws3" / "data").mkdir(parents=True)
            (tmp_path / "ws3" / "data" / "users.json").write_text(json.dumps([{
                "id": "u3", "username": "bob", "status": "active",
                "display_name": "Bob",
                "password_hash": hash_password("s3cret")}], ensure_ascii=False), encoding="utf-8")

            for nm, dd in [("ws1", str(ws1_dir)), ("ws2", str(ws2_dir)), ("ws3", str(tmp_path/"ws3"/"data"))]:
                pack_mod.register_workspace_dir(pack_mod.WorkspaceDef(
                    name=nm, display_name=nm, domains=[], processes=[], data_dir=dd,
                    required_domain_kinds=[]))

            memberships = list_user_workspaces("alice", "s3cret")
            assert len(memberships) == 2
            ws_names = {m["workspace_name"] for m in memberships}
            assert ws_names == {"ws1", "ws2"}
            for m in memberships:
                assert m["username"] == "alice"
                assert m["user_id"].startswith("u")
        finally:
            pack_mod.clear_workspace_dirs()

    def test_wrong_password_finds_nothing(self, monkeypatch, tmp_path):
        from engine import pack as pack_mod
        pack_mod.clear_workspace_dirs()
        try:
            d = tmp_path / "data"
            d.mkdir()
            (d / "users.json").write_text(json.dumps([{
                "id": "u1", "username": "alice", "status": "active",
                "password_hash": hash_password("s3cret")}], ensure_ascii=False), encoding="utf-8")
            pack_mod.register_workspace_dir(pack_mod.WorkspaceDef(
                name="w", display_name="w", domains=[], processes=[], data_dir=str(d),
                required_domain_kinds=[]))
            assert list_user_workspaces("alice", "wrong") == []
        finally:
            pack_mod.clear_workspace_dirs()


# ============ identity.py: seed_workspace_identity ============

class TestSeedWorkspaceIdentity:

    def test_seeds_admin_when_empty(self, isolated_workspace, tmp_path):
        """空 users.json → 种入一个 admin。"""
        (tmp_path / "users.json").write_text("[]", encoding="utf-8")
        ok = seed_workspace_identity(isolated_workspace)
        assert ok is True
        users = json.loads((tmp_path / "users.json").read_text(encoding="utf-8"))
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["status"] == "active"
        assert "password_hash" in users[0]

    def test_idempotent_when_already_seeded(self, isolated_workspace, tmp_path):
        (tmp_path / "users.json").write_text(json.dumps([{
            "id": "existing", "username": "someone",
            "password_hash": "x", "status": "active"}], ensure_ascii=False), encoding="utf-8")
        ok = seed_workspace_identity(isolated_workspace)
        assert ok is False  # 已有用户，不重种
        users = json.loads((tmp_path / "users.json").read_text(encoding="utf-8"))
        assert len(users) == 1  # 没新增
        assert users[0]["username"] == "someone"

    def test_seeded_admin_can_login(self, isolated_workspace, tmp_path):
        """种入的 admin 用默认密码 admin123 能登录。"""
        (tmp_path / "users.json").write_text("[]", encoding="utf-8")
        seed_workspace_identity(isolated_workspace)
        u = verify_credentials(isolated_workspace, "admin", "admin123")
        assert u is not None
        assert u["username"] == "admin"

    def test_seeded_admin_uses_env_password(self, isolated_workspace, tmp_path, monkeypatch):
        """INITIAL_ADMIN_PASSWORD env 覆盖默认密码。"""
        monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "env_secret_456")
        (tmp_path / "users.json").write_text("[]", encoding="utf-8")
        seed_workspace_identity(isolated_workspace)
        # 默认密码应失败
        assert verify_credentials(isolated_workspace, "admin", "admin123") is None
        # env 密码应成功
        u = verify_credentials(isolated_workspace, "admin", "env_secret_456")
        assert u is not None

    def test_seed_all_workspaces_iterates(self, monkeypatch, tmp_path):
        """seed_all_workspaces 遍历所有注册 workspace。"""
        from engine import pack as pack_mod
        pack_mod.clear_workspace_dirs()
        try:
            d1 = tmp_path / "a" / "data"; d1.mkdir(parents=True)
            d2 = tmp_path / "b" / "data"; d2.mkdir(parents=True)
            (d1 / "users.json").write_text("[]", encoding="utf-8")
            (d2 / "users.json").write_text("[]", encoding="utf-8")
            pack_mod.register_workspace_dir(pack_mod.WorkspaceDef(
                name="a", display_name="A", domains=[], processes=[], data_dir=str(d1),
                required_domain_kinds=[]))
            pack_mod.register_workspace_dir(pack_mod.WorkspaceDef(
                name="b", display_name="B", domains=[], processes=[], data_dir=str(d2),
                required_domain_kinds=[]))
            seed_all_workspaces()
            for d in [d1, d2]:
                users = json.loads((d / "users.json").read_text(encoding="utf-8"))
                assert len(users) == 1
                assert users[0]["username"] == "admin"
        finally:
            pack_mod.clear_workspace_dirs()


# ============ schemas.py: 新增枚举 ============

class TestSchemasEnums:
    def test_user_status_values(self):
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.DISABLED.value == "disabled"
        assert UserStatus.PENDING.value == "pending"

    def test_resource_type_covers_5_kinds(self):
        """设计文档 §3.1：覆盖 5 类本体资源。"""
        values = {r.value for r in ResourceType}
        assert values == {"object_type", "property", "action", "link", "tool"}

    def test_permission_action_values(self):
        values = {a.value for a in PermissionAction}
        assert values == {"read", "write", "execute", "traverse", "use"}

    def test_permission_effect_values(self):
        assert PermissionEffect.ALLOW.value == "allow"
        assert PermissionEffect.DENY.value == "deny"


# ============ workspace 本体可解析 ============

class TestWorkspaceIdentityDomain:
    """验证三家 workspace 的 identity domain TTL 都能被 parser 解析。"""

    @pytest.fixture
    def three_ws_root(self):
        return Path(__file__).resolve().parent.parent.parent / "workspace"

    @pytest.mark.parametrize("ws,prefix", [
        ("retail", "store:"),
        ("jjy", "store:"),
        ("customerA", "repair:"),
    ])
    def test_identity_ttl_parseable(self, three_ws_root, ws, prefix):
        """identity domain TTL 可解析出至少 User/Role/PermissionGrant 三个 Object Type。"""
        from engine.parser import OntologyParser
        ttl = three_ws_root / ws / "ontology" / "domains" / "identity" / "domain.ttl"
        assert ttl.exists(), f"{ws} 缺 identity/domain.ttl"
        parser = OntologyParser(ttl_path=str(ttl), data_dir=str(three_ws_root / ws / "data"))
        assert parser.PREFIX == prefix
        obj_names = set(parser.registry.object_types.keys())
        # 必备三件套（Session 可选）
        assert "User" in obj_names, f"{ws} identity TTL 缺 User"
        assert "Role" in obj_names, f"{ws} identity TTL 缺 Role"
        assert "PermissionGrant" in obj_names, f"{ws} identity TTL 缺 PermissionGrant"

    @pytest.mark.parametrize("ws", ["retail", "jjy", "customerA"])
    def test_workspace_py_registers_identity(self, three_ws_root, ws):
        """workspace.py 的 WorkspaceDef.domains 含 identity domain。"""
        import importlib
        from engine import pack as pack_mod
        pack_mod.clear_workspace_dirs()
        try:
            # import 触发 register_workspace_dir
            mod_name = f"workspace.{ws}.workspace"
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            importlib.import_module(mod_name)
            registered = pack_mod.get_workspace_dir(ws)
            assert registered is not None, f"{ws} 未注册"
            domain_names = {d.name for d in registered.domains}
            assert "identity" in domain_names, f"{ws} workspace.py 未声明 identity domain"
        finally:
            pack_mod.clear_workspace_dirs()

    @pytest.mark.parametrize("ws", ["retail", "jjy", "customerA"])
    def test_data_files_exist(self, three_ws_root, ws):
        """三家 workspace 的 data/ 含 users.json（空）/roles.json/permission_grants.json。"""
        for fn in ["users.json", "roles.json", "permission_grants.json"]:
            path = three_ws_root / ws / "data" / fn
            assert path.exists(), f"{ws}/data/{fn} 缺失"
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, list), f"{ws}/data/{fn} 应是 JSON 数组"

    def test_roles_json_contains_system_admin(self, three_ws_root):
        """roles.json 含 system_admin（设计文档 §2.3）。"""
        for ws in ["retail", "jjy", "customerA"]:
            data = json.loads(
                (three_ws_root / ws / "data" / "roles.json").read_text(encoding="utf-8"))
            names = {r["name"] for r in data}
            assert "system_admin" in names, f"{ws}/roles.json 缺 system_admin"
