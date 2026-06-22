"""WP3 权限元数据扩展测试。

验证：
- parser.py 解析 :read_roles/:read_except/:write_roles/:write_except（ObjectType）
- parser.py 解析属性级嵌套 :property [:name "X" ; :read_roles "..."]
- parser.py 解析 Link 的 :use_roles/:use_except
- tool_manifest.py 加载内核 + workspace manifest
- 三家 workspace 现有 identity TTL 的权限元数据可被正确解析
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.parser import OntologyParser
from engine.tool_manifest import (
    load_tool_manifest, load_kernel_tool_manifest,
    load_workspace_tool_manifest, merge_manifests, ToolPerm,
)


# ============ TTL 元数据解析单元测试 ============

class TestObjectTypePermissions:

    def test_parse_object_level_roles(self, tmp_path):
        """ObjectType 上的 read_roles/read_except 等被正确解析。"""
        ttl = tmp_path / "test.ttl"
        ttl.write_text('''@prefix t: <http://example.org/t#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

t:Foo a rdfs:Class ;
    rdfs:label "Foo"@zh , "Foo"@en ;
    t:properties "id:string,name:string" ;
    t:storage "foos.json" ;
    t:read_roles "store_manager, region_cat_mgr" ;
    t:read_except "" ;
    t:write_roles "store_manager" ;
    t:write_except "store_clerk" .
''', encoding="utf-8")
        p = OntologyParser(ttl_path=str(ttl), data_dir=str(tmp_path))
        obj = p.registry.object_types["Foo"]
        assert obj.read_roles == "store_manager, region_cat_mgr"
        assert obj.read_except == ""
        assert obj.write_roles == "store_manager"
        assert obj.write_except == "store_clerk"

    def test_default_empty_when_not_declared(self, tmp_path):
        """未声明权限元数据 → 字段为 ''（allow-by-default）。"""
        ttl = tmp_path / "test.ttl"
        ttl.write_text('''@prefix t: <http://example.org/t#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

t:Foo a rdfs:Class ;
    rdfs:label "Foo"@zh , "Foo"@en ;
    t:properties "id:string" ;
    t:storage "foos.json" .
''', encoding="utf-8")
        p = OntologyParser(ttl_path=str(ttl), data_dir=str(tmp_path))
        obj = p.registry.object_types["Foo"]
        assert obj.read_roles == ""
        assert obj.read_except == ""
        assert obj.write_roles == ""
        assert obj.write_except == ""

    def test_backward_compat_existing_object_types(self, tmp_path):
        """现有 retail organization TTL 仍能正常解析（含新字段，向后兼容）。

        v2（WP4）：Employee 已移到 personnel domain；organization 含
        OrgUnit/Region/Store/Task。
        """
        ttl_path = BACKEND_DIR.parent / "workspace" / "retail" / "ontology" / "domains" / "organization" / "domain.ttl"
        if not ttl_path.exists():
            pytest.skip("retail organization TTL 不存在")
        p = OntologyParser(
            ttl_path=str(ttl_path),
            data_dir=str(BACKEND_DIR.parent / "workspace" / "retail" / "data"))
        # 业务实体应能解析（WP4 后 Employee 移到 personnel）
        assert "OrgUnit" in p.registry.object_types
        assert "Store" in p.registry.object_types
        assert "Task" in p.registry.object_types
        # 未声明权限 → 字段为 ''
        store = p.registry.object_types["Store"]
        assert store.read_roles == ""
        # Task 有 edits_only_via_actions（向后兼容）
        task = p.registry.object_types["Task"]
        assert task.edits_only_via_actions is True


class TestPropertyPermissions:

    def test_parse_property_level_roles(self, tmp_path):
        """属性级 :property [:name "X" ; :read_roles "..."] 嵌套结构解析。"""
        ttl = tmp_path / "test.ttl"
        ttl.write_text('''@prefix t: <http://example.org/t#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

t:Foo a rdfs:Class ;
    rdfs:label "Foo"@zh , "Foo"@en ;
    t:properties "id:string,name:string,salary:float" ;
    t:storage "foos.json" ;
    t:property [
        t:name "salary" ;
        t:read_except "store_clerk" ;
        t:write_roles "system_admin"
    ] .
''', encoding="utf-8")
        p = OntologyParser(ttl_path=str(ttl), data_dir=str(tmp_path))
        obj = p.registry.object_types["Foo"]
        # 属性字典
        prop_by_name = {pp.name: pp for pp in obj.properties}
        assert "salary" in prop_by_name
        salary = prop_by_name["salary"]
        assert salary.read_except == "store_clerk"
        assert salary.write_roles == "system_admin"
        # 未在 :property 块里声明的属性 → 字段为 ''
        assert prop_by_name["name"].read_roles == ""
        assert prop_by_name["name"].read_except == ""

    def test_parse_multiple_property_blocks(self, tmp_path):
        """多个 :property 子句都被解析。"""
        ttl = tmp_path / "test.ttl"
        ttl.write_text('''@prefix t: <http://example.org/t#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

t:Foo a rdfs:Class ;
    rdfs:label "Foo"@zh , "Foo"@en ;
    t:properties "id:string,a:string,b:string" ;
    t:storage "foos.json" ;
    t:property [ t:name "a" ; t:read_roles "X" ] ;
    t:property [ t:name "b" ; t:read_except "Y" ] .
''', encoding="utf-8")
        p = OntologyParser(ttl_path=str(ttl), data_dir=str(tmp_path))
        obj = p.registry.object_types["Foo"]
        prop_by_name = {pp.name: pp for pp in obj.properties}
        assert prop_by_name["a"].read_roles == "X"
        assert prop_by_name["b"].read_except == "Y"

    def test_identity_ttl_user_password_hash_property(self):
        """三家 workspace 的 identity TTL 里 User.password_hash 的 :read_roles "" 被正确解析。"""
        ws_root = BACKEND_DIR.parent / "workspace"
        for ws, prefix in [("retail", "store:"), ("jjy", "store:"), ("customerA", "repair:")]:
            ttl = ws_root / ws / "ontology" / "domains" / "identity" / "domain.ttl"
            assert ttl.exists(), f"{ws} 缺 identity TTL"
            p = OntologyParser(ttl_path=str(ttl),
                               data_dir=str(ws_root / ws / "data"))
            user = p.registry.object_types["User"]
            # User 级别 read_roles="system_admin"
            assert user.read_roles == "system_admin", f"{ws} User.read_roles 错"
            # password_hash 属性 read_roles=""（无人可读）
            prop_by_name = {pp.name: pp for pp in user.properties}
            assert "password_hash" in prop_by_name, f"{ws} User 缺 password_hash 属性"
            assert prop_by_name["password_hash"].read_roles == "", \
                f"{ws} password_hash.read_roles 应为 ''（正向空=无人）"


class TestLinkPermissions:

    def test_parse_link_use_roles(self, tmp_path):
        """Link 的 :use_roles/:use_except 解析。"""
        ttl = tmp_path / "test.ttl"
        ttl.write_text('''@prefix t: <http://example.org/t#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

t:Foo a rdfs:Class ;
    rdfs:label "Foo"@zh , "Foo"@en ;
    t:properties "id:string" ;
    t:storage "foos.json" .

t:Bar a rdfs:Class ;
    rdfs:label "Bar"@zh , "Bar"@en ;
    t:properties "id:string,foo_id:string" ;
    t:storage "bars.json" .

t:links_to a rdfs:Property ;
    rdfs:label "关联"@zh , "links to"@en ;
    rdfs:domain t:Foo ; rdfs:range t:Bar ; t:via "foo_id" ;
    t:use_roles "store_manager" ;
    t:use_except "store_clerk" .
''', encoding="utf-8")
        p = OntologyParser(ttl_path=str(ttl), data_dir=str(tmp_path))
        link = p.registry.link_types["links_to"]
        assert link.use_roles == "store_manager"
        assert link.use_except == "store_clerk"


# ============ tool_manifest 加载测试 ============

class TestToolManifest:

    def test_load_from_yaml(self, tmp_path):
        path = tmp_path / "manifest.yaml"
        path.write_text('''tools:
  - name: query_near_expiry
    use_roles: "store_manager, store_clerk"
    use_except: ""
  - name: execute_action
    use_roles: "*"
''', encoding="utf-8")
        m = load_tool_manifest(str(path))
        assert "query_near_expiry" in m
        assert m["query_near_expiry"].use_roles == "store_manager, store_clerk"
        assert "execute_action" in m
        assert m["execute_action"].use_roles == "*"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_tool_manifest(str(tmp_path / "no_such.yaml")) == {}

    def test_malformed_yaml_returns_empty(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("[: not yaml :]", encoding="utf-8")
        assert load_tool_manifest(str(path)) == {}

    def test_kernel_manifest_loads(self):
        """内核 manifest.yaml 加载 8 个工具。"""
        m = load_kernel_tool_manifest()
        assert len(m) == 8
        expected = {"query_entity", "create_entity", "update_entity",
                    "traverse_relation", "execute_action", "confirm_action",
                    "query_task", "update_task"}
        assert set(m.keys()) == expected
        # 通用 CRUD 锁 admin
        assert m["create_entity"].use_roles == "system_admin"
        # execute_action 开放（action 级再校验）
        assert m["execute_action"].use_roles == "*"

    def test_workspace_manifest_no_file_returns_empty(self, tmp_path):
        """workspace 无 manifest → 空 dict（allow-by-default 兜底）。"""
        assert load_workspace_tool_manifest(str(tmp_path)) == {}

    def test_workspace_manifest_loads_from_workspace_root(self, tmp_path):
        """workspace manifest 放在 workspace 根（与 workspace.py 同级），不在 data/。"""
        ws_root = tmp_path / "ws"
        data_dir = ws_root / "data"
        data_dir.mkdir(parents=True)
        (ws_root / "tool_manifest.yaml").write_text('''tools:
  - name: query_near_expiry
    use_roles: "store_manager"
''', encoding="utf-8")
        m = load_workspace_tool_manifest(str(data_dir))
        assert "query_near_expiry" in m

    def test_merge_manifests_workspace_overrides_kernel(self, tmp_path):
        """合并：workspace manifest 覆盖 kernel（同名 tool）。"""
        k = {"tool_a": ToolPerm(name="tool_a", use_roles="kernel")}
        ws = {"tool_a": ToolPerm(name="tool_a", use_roles="workspace"),
              "tool_b": ToolPerm(name="tool_b", use_roles="workspace")}
        merged = merge_manifests(k, ws)
        assert merged["tool_a"].use_roles == "workspace"   # 覆盖
        assert merged["tool_b"].use_roles == "workspace"   # 新增


# ============ 集成：admin API 暴露权限元数据 ============

class TestAdminAPIExposesPermissions:
    """admin API 的 ontology/objects 应返回 read_roles 等字段（便于前端展示）。"""

    def test_admin_objects_endpoint_returns_permission_meta(self, tmp_path, monkeypatch):
        """暂时跳过：admin API 的修改放 WP5（求值引擎）一起做。这里只验证 parser 能读。"""
        # 这个测试是占位——admin API 字段扩展放 WP5。
        # 这里仅断言 parser 读出的 ObjectType 含权限元数据字段。
        ttl = tmp_path / "test.ttl"
        ttl.write_text('''@prefix t: <http://example.org/t#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

t:Foo a rdfs:Class ;
    rdfs:label "Foo"@zh , "Foo"@en ;
    t:properties "id:string" ;
    t:storage "foos.json" ;
    t:read_roles "admin" .
''', encoding="utf-8")
        p = OntologyParser(ttl_path=str(ttl), data_dir=str(tmp_path))
        obj = p.registry.object_types["Foo"]
        assert hasattr(obj, "read_roles")
        assert obj.read_roles == "admin"
