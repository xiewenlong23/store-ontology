"""加载 ontology/actions/*.yaml → ActionDefinition。"""
import os
from dataclasses import dataclass, field
from typing import Dict, List

import yaml


@dataclass
class ActionDefinition:
    api_name: str
    display_name: str
    description: str
    status: str
    target_object_type: str
    edits_object_types: List[str]
    parameters: List[dict]
    side_effects: List[dict]
    submission_criteria: dict = field(default_factory=dict)


def load_actions(actions_dir: str) -> Dict[str, ActionDefinition]:
    actions = {}
    for fname in sorted(os.listdir(actions_dir)):
        if not (fname.endswith(".yaml") or fname.endswith(".yml")):
            continue
        path = os.path.join(actions_dir, fname)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        actions[data["api_name"]] = ActionDefinition(
            api_name=data["api_name"],
            display_name=data["display_name"],
            description=data.get("description", ""),
            status=data.get("status", "active"),
            target_object_type=data["target_object_type"],
            edits_object_types=data.get("edits_object_types", []),
            parameters=data.get("parameters", []),
            side_effects=data.get("side_effects", []),
            submission_criteria=data.get("submission_criteria", {}) or {},
        )
    return actions
