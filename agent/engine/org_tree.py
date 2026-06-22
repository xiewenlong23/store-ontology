"""OrgUnit 5 级组织树（v2 WP5）。

设计文档 §2.7/§5 WP5：从 workspace 的 ``data/org_units.json`` 加载完整 5 级树，
支持 descendants/ancestors/visible_units 查询。Repository.matches 用 visible_units
计算数据可见集合（取代精确字符串匹配）。

与 ``engine/workspace.py`` 的 ``OrgUnit.Tree``（只 id+parent）的区别：
- 本模块从 org_units.json 加载完整记录（含 level/parent_id/name/...）
- 提供 ``visible_units(unit_id)`` 返回该 unit 用户可见的所有 unit id（自身+子孙）
- ``"*"`` 语义（总部视角）显式处理
"""
import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set


@dataclass
class OrgUnitNode:
    """OrgUnit 树节点（org_units.json 一条记录的精简表示）。"""
    id: str
    parent_id: Optional[str]
    level: str = ""
    name: str = ""


class OrgTree:
    """5 级组织树（per-workspace）。"""

    def __init__(self, nodes: Iterable[OrgUnitNode]):
        self._by_id: Dict[str, OrgUnitNode] = {n.id: n for n in nodes}
        self._children: Dict[str, List[str]] = {}
        for n in self._by_id.values():
            parent_key = n.parent_id or "__root__"
            self._children.setdefault(parent_key, []).append(n.id)

    def get(self, unit_id: str) -> Optional[OrgUnitNode]:
        return self._by_id.get(unit_id)

    def ancestors(self, unit_id: str) -> List[str]:
        """从自身往上的祖先链（含自身）。unit_id 不存在返回空列表。"""
        chain: List[str] = []
        cur = self._by_id.get(unit_id)
        # 防环：访问集合
        seen: Set[str] = set()
        while cur and cur.id not in seen:
            seen.add(cur.id)
            chain.append(cur.id)
            if not cur.parent_id:
                break
            cur = self._by_id.get(cur.parent_id)
        return chain

    def descendants(self, unit_id: str) -> List[str]:
        """从自身往下的子孙集（含自身）。unit_id 不存在返回空列表。"""
        if unit_id not in self._by_id:
            return []
        result: List[str] = [unit_id]
        for child_id in self._children.get(unit_id, []):
            result.extend(self.descendants(child_id))
        return result

    def visible_units(self, unit_id: str) -> Set[str]:
        """某 OrgUnit 用户可见的单元集 = 自身 + 所有子孙。

        unit_id 不存在 → 返回只含 unit_id 的集合（保守：只见自身）。
        """
        return set(self.descendants(unit_id)) or {unit_id}

    def all_unit_ids(self) -> Set[str]:
        return set(self._by_id.keys())


def load_org_tree_from_data_dir(data_dir: str) -> Optional[OrgTree]:
    """从 workspace 的 data/org_units.json 加载 OrgTree。

    文件不存在或为空返回 None（调用方回落到精确字符串匹配）。
    """
    path = os.path.join(data_dir, "org_units.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, list) or not data:
        return None
    nodes = []
    for row in data:
        if not isinstance(row, dict) or "id" not in row:
            continue
        nodes.append(OrgUnitNode(
            id=row["id"],
            parent_id=row.get("parent_id"),
            level=row.get("level", ""),
            name=row.get("name", ""),
        ))
    if not nodes:
        return None
    return OrgTree(nodes)


def resolve_visible_units(org_unit_id: str, org_tree: Optional[OrgTree]) -> Set[str]:
    """统一入口：根据 org_unit_id + OrgTree 计算可见集合。

    - ``"*"`` → 空集合表示"全部可见"（调用方应特殊处理；返回 set() 配合 ``sees_all`` 语义）
    - org_tree 为 None → 回落精确匹配（返回只含 org_unit_id 的集合）
    - 正常 org_unit_id → 自身 + 子孙
    """
    if org_unit_id == "*":
        return set()   # 总部视角；调用方判断 "*" 即全部可见
    if org_tree is None:
        return {org_unit_id} if org_unit_id else set()
    return org_tree.visible_units(org_unit_id)
