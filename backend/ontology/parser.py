"""
本体解析器 — 从 TTL 文件读取对象类型/关系类型/动作类型的语义定义，
构建 EntityRegistry 供通用工具使用。
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PropertyDef:
    name: str
    type: str  # string, int, float, date, datetime, enum


@dataclass
class ObjectType:
    id: str          # 如 "Store"
    label: str       # 如 "门店"
    comment: str
    properties: List[PropertyDef]
    storage_file: str  # 如 "stores.json"
    label_zh: str = ""


@dataclass
class LinkType:
    id: str
    label: str
    domain: str       # 源实体
    range: str        # 目标实体
    via: str          # 通过哪个字段关联
    label_zh: str = ""


@dataclass
class ActionType:
    id: str
    label: str
    description: str
    input_fields: List[PropertyDef]
    output_type: str
    requires_approval: bool = False
    label_zh: str = ""


@dataclass
class EntityRegistry:
    object_types: Dict[str, ObjectType] = field(default_factory=dict)
    link_types: Dict[str, LinkType] = field(default_factory=dict)
    action_types: Dict[str, ActionType] = field(default_factory=dict)


class OntologyParser:
    """解析 TTL 格式的本体定义文件"""

    def __init__(self, ttl_path: str, data_dir: str):
        self.ttl_path = Path(ttl_path)
        self.data_dir = Path(data_dir)
        self.registry = EntityRegistry()
        self._parse()

    def _parse(self):
        content = self.ttl_path.read_text(encoding="utf-8")
        # 提取前缀
        prefix = "store:"
        base = "http://example.org/store-ontology#"

        # 解析 Object Types
        for match in re.finditer(
            rf'{prefix}(\w+)\s+a\s+rdfs:Class\s*;\s*'
            rf'rdfs:label\s+"([^"]+)"@zh\s*,\s*"([^"]+)"@en\s*;\s*'
            rf'rdfs:comment\s+"([^"]*)"@zh\s*;\s*'
            rf'{prefix}properties\s+"([^"]*)"\s*;\s*'
            rf'{prefix}storage\s+"([^"]*)"',
            content, re.DOTALL
        ):
            obj_id, label_zh, label_en, comment, props_str, storage = match.groups()
            properties = self._parse_properties(props_str)
            self.registry.object_types[obj_id] = ObjectType(
                id=obj_id,
                label=f"{label_zh} ({label_en})",
                label_zh=label_zh,
                comment=comment,
                properties=properties,
                storage_file=storage,
            )

        # 解析 Link Types
        for match in re.finditer(
            rf'{prefix}(\w+)\s+a\s+rdfs:Property\s*;\s*'
            rf'rdfs:label\s+"([^"]+)"@zh\s*,\s*"([^"]+)"@en\s*;\s*'
            rf'rdfs:domain\s+{prefix}(\w+)\s*;\s*'
            rf'rdfs:range\s+{prefix}(\w+)\s*;\s*'
            rf'{prefix}via\s+"([^"]*)"',
            content, re.DOTALL
        ):
            link_id, label_zh, label_en, domain, range_, via = match.groups()
            self.registry.link_types[link_id] = LinkType(
                id=link_id,
                label=f"{label_zh} ({label_en})",
                label_zh=label_zh,
                domain=domain,
                range=range_,
                via=via,
            )

        # 解析 Action Types (store:target + store:params 格式)
        for match in re.finditer(
            rf'{prefix}(\w+)\s+a\s+rdfs:Class\s*;\s*'
            rf'rdfs:label\s+"([^"]+)"@zh\s*,\s*"([^"]+)"@en\s*;\s*'
            rf'rdfs:comment\s+"([^"]*)"@zh\s*;\s*'
            rf'{prefix}target\s+{prefix}(\w+)\s*;\s*'
            rf'{prefix}params\s+"([^"]*)"',
            content, re.DOTALL
        ):
            action_id, label_zh, label_en, desc, target_type, params_str = match.groups()
            input_fields = self._parse_properties(params_str)
            self.registry.action_types[action_id] = ActionType(
                id=action_id,
                label=f"{label_zh} ({label_en})",
                label_zh=label_zh,
                description=desc,
                input_fields=input_fields,
                output_type=target_type,
                requires_approval=True,
            )

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
        """从本体定义生成精简系统提示"""
        lines = ["你是门店临期商品管理助手。\n"]
        lines.append("可用实体（用 query_entity 查询）: ")
        lines.append(", ".join(f"{ot.label_zh}" for ot in self.registry.object_types.values()))
        lines.append("\n")
        lines.append("关系（用 traverse_relation）: ")
        lines.append(", ".join(f"{lt.label_zh}({lt.domain}→{lt.range})" for lt in self.registry.link_types.values()))
        lines.append("\n")
        lines.append("操作类型（用 execute_action 执行）: ")
        for at in self.registry.action_types.values():
            params = ", ".join(f.name for f in at.input_fields)
            lines.append(f"- {at.label_zh}({at.id}): {params}")
        lines.append("用 query_task 查询任务，update_task 修改任务。用中文回复。")
        return "\n".join(lines)


# ============ 单例模式 ============

_parser_instance = None


def get_ontology_parser(ttl_path: str = None, data_dir: str = None) -> OntologyParser:
    """获取 OntologyParser 单例"""
    global _parser_instance
    if _parser_instance is None:
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        root = os.path.dirname(base)  # backend/ -> store-ontology/
        ttl_path = ttl_path or os.path.join(base, "ontology", "store.ttl")
        data_dir = data_dir or os.path.join(root, "data")
        _parser_instance = OntologyParser(ttl_path, data_dir)
    return _parser_instance
