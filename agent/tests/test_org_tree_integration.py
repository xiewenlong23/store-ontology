"""WP5 接入：OrgTree 接入 Repository.matches 的测试。

验证设计文档 §2.7：region_cat_mgr 登录后能看到本 region 子树所有门店数据；
store_manager 只看本店；总部（"*"）看全部。

走真实 JSONFileRepository + 临时 org_units.json + 各 org_unit_id 数据。
"""
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.repository import JSONFileRepository, _matches_with_tree
from engine.tenant import TenantContext
from engine.org_tree import OrgTree, OrgUnitNode


# ============ _matches_with_tree 单元 ============

class TestMatchesWithTree:

    @pytest.fixture
    def tree(self):
        """3 级树：root → region_north → store_001/store_002。"""
        return OrgTree([
            OrgUnitNode(id="root", parent_id=None, level="brand"),
            OrgUnitNode(id="region_north", parent_id="root", level="region"),
            OrgUnitNode(id="store_001", parent_id="region_north", level="store"),
            OrgUnitNode(id="store_002", parent_id="region_north", level="store"),
        ])

    def test_headquarters_sees_all(self, tree):
        """org_unit_id='*' → 看全部（总部视角）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="*")
        for org in ["store_001", "store_002", "region_north", "root"]:
            assert _matches_with_tree(
                {"workspace_name": "jjy", "org_unit_id": org}, tc, tree)

    def test_workspace_hard_isolation(self, tree):
        """workspace_name 不匹配 → 不可见（硬隔离）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="*")
        assert not _matches_with_tree(
            {"workspace_name": "other_ws", "org_unit_id": "store_001"}, tc, tree)

    def test_region_sees_subtree(self, tree):
        """region_north 上下文 → 能见 region_north + store_001 + store_002（子树）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="region_north")
        # 子树全部可见
        assert _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "region_north"}, tc, tree)
        assert _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "store_001"}, tc, tree)
        assert _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "store_002"}, tc, tree)
        # 父级 / 兄弟不可见
        assert not _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "root"}, tc, tree)

    def test_store_sees_only_self(self, tree):
        """store_001 上下文 → 只见 store_001（叶子无子孙）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="store_001")
        assert _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "store_001"}, tc, tree)
        # 同级兄弟不可见
        assert not _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "store_002"}, tc, tree)
        # 父级不可见
        assert not _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "region_north"}, tc, tree)

    def test_wildcard_record_visible_to_all(self, tree):
        """record 自身 org_unit_id='*'（共享数据如品类）→ 任何上下文可见。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="store_001")
        assert _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "*"}, tc, tree)

    def test_no_tree_fallback_exact_match(self):
        """无 org_tree → 回落精确匹配（向后兼容）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="store_001")
        assert _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "store_001"}, tc, None)
        assert not _matches_with_tree(
            {"workspace_name": "jjy", "org_unit_id": "store_002"}, tc, None)

    def test_old_data_no_workspace_name(self, tree):
        """旧数据无 workspace_name → 视为 jjy（向后兼容）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="*")
        assert _matches_with_tree({"org_unit_id": "store_001"}, tc, tree)
        # 旧 customer_id 字段
        assert _matches_with_tree(
            {"customer_id": "jjy", "org_unit_id": "store_001"}, tc, tree)
        # 不同 workspace 的旧数据不可见
        tc2 = TenantContext(workspace_name="retail", org_unit_id="*")
        assert not _matches_with_tree(
            {"customer_id": "jjy", "org_unit_id": "store_001"}, tc2, tree)


# ============ JSONFileRepository 端到端 ============

class TestRepositoryWithOrgTree:

    @pytest.fixture
    def repo_with_tree(self, tmp_path):
        """临时 workspace 数据：含 OrgTree + 多门店数据。"""
        # org_units.json（3 级树）
        (tmp_path / "org_units.json").write_text(json.dumps([
            {"id": "root", "parent_id": None, "level": "brand"},
            {"id": "region_north", "parent_id": "root", "level": "region"},
            {"id": "store_001", "parent_id": "region_north", "level": "store"},
            {"id": "store_002", "parent_id": "region_north", "level": "store"},
        ], ensure_ascii=False), encoding="utf-8")
        # 多门店的 tasks.json
        (tmp_path / "tasks.json").write_text(json.dumps([
            {"id": "t1", "store_id": "store_001", "org_unit_id": "store_001",
             "workspace_name": "jjy", "status": "created"},
            {"id": "t2", "store_id": "store_002", "org_unit_id": "store_002",
             "workspace_name": "jjy", "status": "created"},
            {"id": "t3", "store_id": "store_001", "org_unit_id": "region_north",
             "workspace_name": "jjy", "status": "in_progress"},
        ], ensure_ascii=False), encoding="utf-8")
        # mock registry
        from engine.parser import ObjectType
        class _Reg:
            object_types = {
                "Task": ObjectType(
                    id="Task", label="Task", comment="",
                    properties=[], storage_file="tasks.json"),
            }
        return JSONFileRepository(data_dir=str(tmp_path), registry=_Reg())

    def test_headquarters_reads_all_tasks(self, repo_with_tree):
        """总部视角（org=*) → 读到所有 task。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="*")
        rows = repo_with_tree.read("Task", tc)
        assert len(rows) == 3

    def test_store_sees_only_own_tasks(self, repo_with_tree):
        """store_001 视角 → 只见 org_unit_id=store_001 的 task（t1）。

        注：t3 的 org_unit_id=region_north，对 store_001 上下文不可见
        （store_001 是 region_north 的子节点，反向不见父级）。
        """
        tc = TenantContext(workspace_name="jjy", org_unit_id="store_001")
        rows = repo_with_tree.read("Task", tc)
        ids = {r["id"] for r in rows}
        assert ids == {"t1"}, f"store_001 应只见 t1，实际：{ids}"

    def test_region_sees_all_subtree_tasks(self, repo_with_tree):
        """region_north 视角 → 见 t1（store_001）+ t2（store_002）+ t3（region_north 自身）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="region_north")
        rows = repo_with_tree.read("Task", tc)
        ids = {r["id"] for r in rows}
        assert ids == {"t1", "t2", "t3"}, f"region 应见全部 3 个，实际：{ids}"

    def test_workspace_isolation(self, repo_with_tree):
        """不同 workspace（如 customerA）看不到 jjy 的数据。"""
        tc = TenantContext(workspace_name="customerA", org_unit_id="*")
        rows = repo_with_tree.read("Task", tc)
        assert rows == []

    def test_write_with_region_tc_assigns_region_org(self, repo_with_tree):
        """write 时强制盖 org_unit_id（如 region 用户写数据 → org=region_north）。"""
        tc = TenantContext(workspace_name="jjy", org_unit_id="region_north")
        repo_with_tree.write("Task", tc, {"id": "t_new", "status": "created"},
                             create=True, bypass_action_check=True)
        # 读回验证 org_unit_id 被盖为 region_north
        rows = repo_with_tree.read("Task", TenantContext(workspace_name="jjy", org_unit_id="*"))
        new = [r for r in rows if r["id"] == "t_new"][0]
        assert new["org_unit_id"] == "region_north"

    def test_update_only_matches_visible(self, repo_with_tree):
        """update 按 _matches_with_tree 过滤，跨 org 不可改。"""
        # store_001 上下文改 t2（属于 store_002）→ 不应匹配，新增而非替换
        tc = TenantContext(workspace_name="jjy", org_unit_id="store_001")
        repo_with_tree.write("Task", tc,
                             {"id": "t2", "status": "modified"},
                             bypass_action_check=True)
        # 全部读回看 t2 状态
        all_rows = repo_with_tree.read(
            "Task", TenantContext(workspace_name="jjy", org_unit_id="*"))
        t2 = [r for r in all_rows if r["id"] == "t2"][0]
        # store_001 上下文改不到 t2（因 _matches_with_tree 不匹配 store_002 的记录）
        # → write 走 "未匹配则新增" 分支，t2 仍是 created
        assert t2["status"] == "created"


# ============ JSONFileRepository 无 OrgTree 回落 ============

class TestRepositoryNoTreeFallback:

    def test_no_org_units_json_falls_back_to_exact(self, tmp_path):
        """data_dir 无 org_units.json → _org_tree=None → 回落精确匹配。"""
        (tmp_path / "tasks.json").write_text(json.dumps([
            {"id": "t1", "org_unit_id": "store_001", "workspace_name": "jjy"},
            {"id": "t2", "org_unit_id": "store_002", "workspace_name": "jjy"},
        ], ensure_ascii=False), encoding="utf-8")
        from engine.parser import ObjectType
        class _Reg:
            object_types = {"Task": ObjectType(
                id="Task", label="Task", comment="",
                properties=[], storage_file="tasks.json")}
        repo = JSONFileRepository(data_dir=str(tmp_path), registry=_Reg())
        assert repo._org_tree is None  # 无 OrgTree
        # store_001 上下文只见 t1
        tc = TenantContext(workspace_name="jjy", org_unit_id="store_001")
        rows = repo.read("Task", tc)
        assert {r["id"] for r in rows} == {"t1"}
