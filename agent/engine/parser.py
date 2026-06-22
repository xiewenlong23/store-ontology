"""
本体解析器 —— 从 TTL 读取 Object/Link Type 定义，构建 EntityRegistry。
Action Type 不再在 TTL 定义，改由 ontology/actions/*.yaml 加载（见 action_loader.py）。
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def _to_bool(s: str) -> bool:
    return str(s).strip().lower() in ("true", "1", "yes")


@dataclass
class PropertyDef:
    name: str
    type: str
    # v2 权限元数据（WP3）——可选，未声明时为 ""（表示无限制，allow-by-default）
    # 含义见设计文档 §2.4/§2.5：roles 正向白名单 / except 反向除外
    read_roles: str = ""
    read_except: str = ""
    write_roles: str = ""
    write_except: str = ""


@dataclass
class ObjectType:
    id: str
    label: str
    comment: str
    properties: List[PropertyDef]
    storage_file: str
    label_zh: str = ""
    status: str = "active"
    visibility: str = "normal"
    edits_only_via_actions: bool = False
    # v2 权限元数据（WP3）——可选，allow-by-default
    read_roles: str = ""
    read_except: str = ""
    write_roles: str = ""
    write_except: str = ""


@dataclass
class LinkType:
    id: str
    label: str
    domain: str
    range: str
    via: str
    label_zh: str = ""
    comment: str = ""
    # v2 权限元数据（WP3）——Link 用 use（遍历）
    use_roles: str = ""
    use_except: str = ""


@dataclass
class EntityRegistry:
    object_types: Dict[str, ObjectType] = field(default_factory=dict)
    link_types: Dict[str, LinkType] = field(default_factory=dict)
    action_types: Dict[str, object] = field(default_factory=dict)  # 由 action_loader 填充


class OntologyParser:
    """解析 TTL 格式的本体定义文件（Object / Link Type）。

    prefix 从 TTL 文件的 @prefix 行动态读取（不再硬编码 "store:"），
    从而支持多个行业包/能力域各用自己的命名空间。
    """

    def __init__(self, ttl_path: str, data_dir: str, config=None):
        self.ttl_path = Path(ttl_path)
        self.data_dir = Path(data_dir)
        self.config = config  # Optional[WorkspaceDef/ValueChainProcess 上下文]（工作目录侧传入）
        self.PREFIX = self._read_prefix()
        self.registry = EntityRegistry()
        self._parse()

    def _read_prefix(self) -> str:
        """从 TTL 的 @prefix <name>: <...> . 行提取 'name:'，默认 'store:'。"""
        content = self.ttl_path.read_text(encoding="utf-8")
        m = re.search(r'@prefix\s+(\w+):\s*<[^>]+>\s*\.', content)
        return (m.group(1) + ":") if m else "store:"

    def _parse(self):
        content = self.ttl_path.read_text(encoding="utf-8")
        P = self.PREFIX

        # Object Types: <prefix>:X a rdfs:Class ; ... <line ending with " .">
        for m in re.finditer(
            rf'{P}(\w+)\s+a\s+rdfs:Class\s*;\s*(.*?)\s*\.\s*$',
            content, re.DOTALL | re.MULTILINE
        ):
            obj_id, body = m.group(1), m.group(2)
            props_str = self._first(r'properties\s+"([^"]*)"', body)
            if not props_str:
                continue
            label_zh = self._first(r'rdfs:label\s+"([^"]+)"@zh', body)
            label_en = self._first(r'rdfs:label\s+"[^"]+"@zh\s*,\s*"([^"]+)"@en', body)
            comment = self._first(r'rdfs:comment\s+"([^"]*)"@zh', body)
            storage = self._first(r'storage\s+"([^"]*)"', body)
            status = self._first(r'status\s+"([^"]*)"', body) or "active"
            visibility = self._first(r'visibility\s+"([^"]*)"', body) or "normal"
            edits = _to_bool(
                self._first(r'edits_only_via_actions\s+"([^"]*)"', body) or "false")
            # v2 权限元数据（WP3）：顶层字段解析前剥离 :property [ ... ] 嵌套块，
            # 避免嵌套块里的 read_roles/read_except 等被误当 Object 顶层字段。
            body_no_prop = re.sub(rf'{P}property\s*\[[^\]]*\]', '', body, flags=re.DOTALL)
            read_roles = self._first(r'read_roles\s+"([^"]*)"', body_no_prop) or ""
            read_except = self._first(r'read_except\s+"([^"]*)"', body_no_prop) or ""
            write_roles = self._first(r'write_roles\s+"([^"]*)"', body_no_prop) or ""
            write_except = self._first(r'write_except\s+"([^"]*)"', body_no_prop) or ""
            # 属性级权限元数据（嵌套 blank node）
            prop_perms = self._parse_property_permissions(body, P)
            props = self._parse_properties(props_str)
            for p in props:
                if p.name in prop_perms:
                    pp = prop_perms[p.name]
                    p.read_roles = pp.get("read_roles", "")
                    p.read_except = pp.get("read_except", "")
                    p.write_roles = pp.get("write_roles", "")
                    p.write_except = pp.get("write_except", "")
            self.registry.object_types[obj_id] = ObjectType(
                id=obj_id, label=f"{label_zh} ({label_en})", label_zh=label_zh,
                comment=comment, properties=props,
                storage_file=storage, status=status, visibility=visibility,
                edits_only_via_actions=edits,
                read_roles=read_roles, read_except=read_except,
                write_roles=write_roles, write_except=write_except,
            )

        # Link Types: store:X a rdfs:Property ; ... <line ending with " .">
        for m in re.finditer(
            rf'{P}(\w+)\s+a\s+rdfs:Property\s*;\s*(.*?)\s*\.\s*$',
            content, re.DOTALL | re.MULTILINE
        ):
            link_id, body = m.group(1), m.group(2)
            domain = self._first(r'domain\s+%s(\w+)' % P, body)
            if not domain:
                continue
            label_zh = self._first(r'rdfs:label\s+"([^"]+)"@zh', body)
            label_en = self._first(r'rdfs:label\s+"[^"]+"@zh\s*,\s*"([^"]+)"@en', body)
            comment = self._first(r'rdfs:comment\s+"([^"]*)"@zh', body)
            use_roles = self._first(r'use_roles\s+"([^"]*)"', body) or ""
            use_except = self._first(r'use_except\s+"([^"]*)"', body) or ""
            # `range` 是 Python 关键字，用 dict 展开绕开命名冲突
            self.registry.link_types[link_id] = LinkType(
                id=link_id, label=f"{label_zh} ({label_en})", label_zh=label_zh,
                comment=comment, domain=domain,
                **{"range": self._first(r'range\s+%s(\w+)' % P, body)},
                via=self._first(r'via\s+"([^"]*)"', body),
                use_roles=use_roles, use_except=use_except,
            )

    def _parse_property_permissions(self, body: str, prefix: str) -> Dict[str, dict]:
        """解析 ``:property [ :name "X" ; :read_roles "..." ]`` 嵌套结构。

        返回 ``{property_name: {read_roles, read_except, write_roles, write_except}}``。
        多个 :property 子句都解析；非法结构跳过。
        """
        result: Dict[str, dict] = {}
        # 单层 [ ... ]（不嵌套）。re.DOTALL 让 . 跨行。
        for blk in re.finditer(
            rf'{prefix}property\s*\[\s*(.*?)\s*\]',
            body, re.DOTALL
        ):
            inner = blk.group(1)
            name = self._first(r'name\s+"([^"]+)"', inner)
            if not name:
                continue
            result[name] = {
                "read_roles": self._first(r'read_roles\s+"([^"]*)"', inner) or "",
                "read_except": self._first(r'read_except\s+"([^"]*)"', inner) or "",
                "write_roles": self._first(r'write_roles\s+"([^"]*)"', inner) or "",
                "write_except": self._first(r'write_except\s+"([^"]*)"', inner) or "",
            }
        return result

    @staticmethod
    def _first(pattern: str, text: str) -> Optional[str]:
        m = re.search(pattern, text)
        return m.group(1) if m else None

    def _parse_properties(self, props_str: str) -> List[PropertyDef]:
        result = []
        for prop in props_str.split(","):
            prop = prop.strip()
            if ":" in prop:
                name, ptype = prop.split(":", 1)
                result.append(PropertyDef(name=name.strip(), type=ptype.strip()))
            elif prop:
                result.append(PropertyDef(name=prop, type="string"))
        return result

    def build_system_prompt(self, intro: str = "") -> str:
        """从本体定义生成精简系统提示。

        intro：开场白（来自 ValueChainProcess.system_prompt_intro），领域无关的通用表述，
        如 "你是门店运营助手。" 不传则用中性默认。
        """
        intro = intro or "你是业务运营助手。"
        lines = [f"{intro}\n"]
        lines.append("可用实体（用 query_entity 查询）: "
                     + ", ".join(ot.label_zh for ot in self.registry.object_types.values()))
        lines.append("\n关系（用 traverse_relation）: "
                     + ", ".join(f"{lt.label_zh}({lt.domain}->{lt.range})"
                                 for lt in self.registry.link_types.values()))
        lines.append("\n操作（用 execute_action/confirm_action）: "
                     + ", ".join(self.registry.action_types.keys()))
        lines.append("\n用中文回复。")
        return "\n".join(lines)


def get_ontology_parser(ttl_path: str = None, data_dir: str = None) -> "OntologyParser":
    """获取 OntologyParser（行业包/workspace 装配版，spec §5.3 决策1）。

    两种调用方式：
    1. get_ontology_parser(ttl_path=..., data_dir=...)  —— 显式路径（测试用）
    2. get_ontology_parser()                            —— 默认（all_workspace_dirs()[0]，回退空 registry）

    按 vertical name 取 parser 的旧方式已删除（vertical registry 已移除）。
    生产装配经 bootstrap_workspace / domains_to_registry，不经此函数。
    """
    # 方式 1：显式路径（不缓存，测试每次新建）
    if ttl_path is not None or data_dir is not None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # agent/
        root = os.path.dirname(base)                                          # 项目根
        ttl_path = ttl_path or os.path.join(base, "engine", "store.ttl")
        data_dir = data_dir or os.path.join(root, "data")
        actions_dir = os.path.join(os.path.dirname(ttl_path), "actions")
        p = OntologyParser(ttl_path, data_dir)
        from engine.action_loader import load_actions
        if os.path.isdir(actions_dir):
            p.registry.action_types = load_actions(actions_dir)
        return p

    # 方式 2：默认工作目录（all_workspace_dirs()[0]，回退空 registry）
    from engine.pack import all_workspace_dirs, domains_to_registry
    from engine.bootstrap import bootstrap
    bootstrap()
    ws_dirs = all_workspace_dirs()
    if ws_dirs:
        ws = ws_dirs[0]
        registry = domains_to_registry(ws, data_dir=ws.data_dir or ".")
        p = type('P', (), {'registry': registry, 'data_dir': __import__('pathlib').Path(ws.data_dir or "."),
                           'config': None})()
        return p
    # 无工作目录时返回空 registry
    registry = EntityRegistry()
    return type('P', (), {'registry': registry, 'data_dir': __import__('pathlib').Path("."),
                          'config': None})()


def reset_parser_cache() -> None:
    """空操作（保留仅为向后兼容；vertical 缓存已移除，spec §5.3 决策1）。"""
    return None
