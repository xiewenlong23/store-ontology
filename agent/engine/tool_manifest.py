"""tool_manifest 加载（设计文档 §2.8）。

Tool 是 Python 代码不在 TTL，权限声明用 YAML：
- 内核 8 个工具的 manifest 在 ``agent/tools/manifest.yaml``
- 各 workspace 专属工具的 manifest 在 ``workspace/<ws>/tool_manifest.yaml``

PermissionEvaluator 合并两者求值。未声明的工具默认 allow（设计文档 §2.5）。

YAML 格式：
    tools:
      - name: query_near_expiry
        use_roles: "store_manager, store_clerk, region_cat_mgr"
        use_except: ""
      - name: execute_action
        use_roles: "*"
"""
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml


@dataclass
class ToolPerm:
    """单个 tool 的权限声明。"""
    name: str
    use_roles: str = ""    # 正向：逗号分隔角色白名单；"*" 表示所有角色
    use_except: str = ""   # 反向：逗号分隔除外角色


def load_tool_manifest(path: str) -> Dict[str, ToolPerm]:
    """从 YAML 文件加载 tool manifest → ``{tool_name: ToolPerm}``。

    文件不存在或为空返回空 dict（求值时 fallthrough 到 allow-by-default）。
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}
    result: Dict[str, ToolPerm] = {}
    for entry in data.get("tools", []) or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        result[name] = ToolPerm(
            name=name,
            use_roles=str(entry.get("use_roles", "") or ""),
            use_except=str(entry.get("use_except", "") or ""),
        )
    return result


def load_kernel_tool_manifest() -> Dict[str, ToolPerm]:
    """加载内核 8 个工具的 manifest（``agent/tools/manifest.yaml``）。"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tools", "manifest.yaml")
    return load_tool_manifest(path)


def load_workspace_tool_manifest(workspace_data_dir: str) -> Dict[str, ToolPerm]:
    """加载 workspace 专属工具 manifest。

    workspace_data_dir: workspace 的 data/ 目录路径；manifest 放在其父目录
    （即 workspace 根），与 workspace.py 同级。
    """
    if not workspace_data_dir:
        return {}
    # manifest 在 workspace 根，不在 data/
    workspace_root = os.path.dirname(workspace_data_dir)
    return load_tool_manifest(os.path.join(workspace_root, "tool_manifest.yaml"))


def merge_manifests(*manifests: Dict[str, ToolPerm]) -> Dict[str, ToolPerm]:
    """合并多个 manifest。后出现的覆盖先出现的（workspace 覆盖 kernel）。"""
    merged: Dict[str, ToolPerm] = {}
    for m in manifests:
        merged.update(m)
    return merged
