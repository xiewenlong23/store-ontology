"""性能验证：OrgTree.visible_units 在 read 时只求一次（不在每条 record 重算）。

之前的 _matches_with_tree 对每条 record 都调 org_tree.visible_units（全树遍历），
O(N*M) 复杂度。优化后 _compute_visible_units 在 read 入口求一次，
_matches_with_tree 收预算的 set 做集合包含检查（O(1)）。

本测试不严格 benchmark（CI 不稳定），而是断言调用次数：
- 优化前：org_tree.visible_units 被调用 N 次（每条 record 一次）
- 优化后：org_tree.visible_units 只被调用 1 次（无论 N 条 record）
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.repository import JSONFileRepository, _compute_visible_units
from engine.tenant import TenantContext
from engine.org_tree import OrgTree, OrgUnitNode


@pytest.fixture
def repo_with_tree_and_many_records(tmp_path):
    """临时 workspace：OrgTree（3 级）+ 100 条 task。"""
    # OrgTree
    units = [{"id": "root", "parent_id": None, "level": "brand"}]
    for i in range(10):  # 10 region
        units.append({"id": f"region_{i}", "parent_id": "root", "level": "region"})
        for j in range(10):  # 每 region 10 store
            units.append({"id": f"store_{i}_{j}", "parent_id": f"region_{i}", "level": "store"})
    (tmp_path / "org_units.json").write_text(json.dumps(units, ensure_ascii=False), encoding="utf-8")

    # 100 条 task：分布在不同 store
    tasks = []
    for i in range(10):
        for j in range(10):
            tasks.append({
                "id": f"task_{i}_{j}",
                "store_id": f"store_{i}_{j}",
                "org_unit_id": f"store_{i}_{j}",
                "workspace_name": "jjy",
                "status": "created",
            })
    (tmp_path / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")

    from engine.parser import ObjectType
    class _Reg:
        object_types = {"Task": ObjectType(
            id="Task", label="Task", comment="",
            properties=[], storage_file="tasks.json")}
    return JSONFileRepository(data_dir=str(tmp_path), registry=_Reg())


class TestVisibleUnitsCallCount:

    def test_region_query_calls_visible_units_once(self, repo_with_tree_and_many_records):
        """region_0 上下文查 task：visible_units 应只被调用 1 次（不是 100 次）。

        优化前：每条 record 调一次 → 100 次（全树遍历）
        优化后：read 入口调一次 → 1 次
        """
        repo = repo_with_tree_and_many_records
        tc = TenantContext(workspace_name="jjy", org_unit_id="region_0")

        # spy：包装 visible_units 计数
        original_visible_units = repo._org_tree.visible_units
        call_count = {"n": 0}
        def counting_visible_units(unit_id):
            call_count["n"] += 1
            return original_visible_units(unit_id)
        repo._org_tree.visible_units = counting_visible_units

        rows = repo.read("Task", tc)

        # 应只调 1 次
        assert call_count["n"] == 1, \
            f"visible_units 应只被调用 1 次（优化后预算一次），实际 {call_count['n']} 次"
        # 结果正确：region_0 见自身 + 10 个子 store → 10 条 task
        assert len(rows) == 10

    def test_headquarters_query_no_visible_units_call(self, repo_with_tree_and_many_records):
        """总部视角（org=*)不调 visible_units（_matches_with_tree 内短路 sees_all）。"""
        repo = repo_with_tree_and_many_records
        tc = TenantContext(workspace_name="jjy", org_unit_id="*")

        original = repo._org_tree.visible_units
        call_count = {"n": 0}
        def counting(unit_id):
            call_count["n"] += 1
            return original(unit_id)
        repo._org_tree.visible_units = counting

        rows = repo.read("Task", tc)

        assert call_count["n"] == 0, \
            f"总部视角不该调 visible_units（短路），实际 {call_count['n']} 次"
        assert len(rows) == 100


class TestComputeVisibleUnits:

    def test_headquarters_returns_none(self):
        """总部视角 → None（_matches_with_tree 内 sees_all 短路）。"""
        tc = TenantContext(workspace_name="x", org_unit_id="*")
        tree = OrgTree([OrgUnitNode(id="a", parent_id=None)])
        assert _compute_visible_units(tc, tree) is None

    def test_no_tree_returns_none(self):
        """无 org_tree → None（_matches_with_tree 回落精确匹配）。"""
        tc = TenantContext(workspace_name="x", org_unit_id="store_1")
        assert _compute_visible_units(tc, None) is None

    def test_normal_returns_set(self):
        """正常路径 → 返回 set（自身 + 子孙）。"""
        tc = TenantContext(workspace_name="x", org_unit_id="root")
        tree = OrgTree([
            OrgUnitNode(id="root", parent_id=None),
            OrgUnitNode(id="a", parent_id="root"),
            OrgUnitNode(id="b", parent_id="root"),
        ])
        v = _compute_visible_units(tc, tree)
        assert v == {"root", "a", "b"}
