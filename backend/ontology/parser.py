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


@dataclass
class LinkType:
    id: str
    label: str
    domain: str
    range: str
    via: str
    label_zh: str = ""
    comment: str = ""


@dataclass
class EntityRegistry:
    object_types: Dict[str, ObjectType] = field(default_factory=dict)
    link_types: Dict[str, LinkType] = field(default_factory=dict)
    action_types: Dict[str, object] = field(default_factory=dict)  # 由 action_loader 填充


class OntologyParser:
    """解析 TTL 格式的本体定义文件（Object / Link Type）。"""

    PREFIX = "store:"

    def __init__(self, ttl_path: str, data_dir: str):
        self.ttl_path = Path(ttl_path)
        self.data_dir = Path(data_dir)
        self.registry = EntityRegistry()
        self._parse()

    def _parse(self):
        content = self.ttl_path.read_text(encoding="utf-8")
        P = self.PREFIX

        # Object Types: store:X a rdfs:Class ; ... <line ending with " .">
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
            self.registry.object_types[obj_id] = ObjectType(
                id=obj_id, label=f"{label_zh} ({label_en})", label_zh=label_zh,
                comment=comment, properties=self._parse_properties(props_str),
                storage_file=storage, status=status, visibility=visibility,
                edits_only_via_actions=edits,
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
            # `range` 是 Python 关键字，用 dict 展开绕开命名冲突
            self.registry.link_types[link_id] = LinkType(
                id=link_id, label=f"{label_zh} ({label_en})", label_zh=label_zh,
                comment=comment, domain=domain,
                **{"range": self._first(r'range\s+%s(\w+)' % P, body)},
                via=self._first(r'via\s+"([^"]*)"', body),
            )

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

    def build_system_prompt(self) -> str:
        """从本体定义生成精简系统提示。"""
        lines = ["你是门店临期商品管理助手。\n"]
        lines.append("可用实体（用 query_entity 查询）: "
                     + ", ".join(ot.label_zh for ot in self.registry.object_types.values()))
        lines.append("\n关系（用 traverse_relation）: "
                     + ", ".join(f"{lt.label_zh}({lt.domain}->{lt.range})"
                                 for lt in self.registry.link_types.values()))
        lines.append("\n操作（用 execute_action/confirm_action）: "
                     + ", ".join(self.registry.action_types.keys()))
        lines.append("\n用 query_task 查询任务。用中文回复。")
        return "\n".join(lines)


# ============ 单例 ============
_parser_instance = None


def get_ontology_parser(ttl_path: str = None, data_dir: str = None) -> OntologyParser:
    """获取 OntologyParser 单例。"""
    global _parser_instance
    if _parser_instance is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend/
        root = os.path.dirname(base)                                          # 项目根
        ttl_path = ttl_path or os.path.join(base, "ontology", "store.ttl")
        data_dir = data_dir or os.path.join(root, "data")
        _parser_instance = OntologyParser(ttl_path, data_dir)
        from ontology.action_loader import load_actions
        _parser_instance.registry.action_types = load_actions(
            os.path.join(base, "ontology", "actions"))
    return _parser_instance
