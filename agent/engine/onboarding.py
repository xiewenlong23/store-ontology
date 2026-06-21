"""workspace onboarding 工具：ontocopy + ontoseed（架构 spec §3.3）。

实现 onboarding 五步中的代码自动化部分：
- copy_pack_to_workspace: copy 行业包到 workspace 目录（步骤①）
- seed_workspace_data: 数据清洗/校验/初始化（步骤③）
步骤②④是手动编辑，步骤⑤是 bootstrap_workspace。
"""
import os
import json
import shutil
from typing import List

import yaml


def copy_pack_to_workspace(pack_root: str, workspace_root: str,
                           workspace_name: str, workspace_label: str,
                           pack_name: str) -> str:
    """Copy 行业包到 workspace 目录（架构 spec §3.3 onboarding 步骤①）。

    pack_root: workspace/<pack_name>/ 的绝对路径
    workspace_root: workspace/<workspace_name>/ 的绝对路径
    生成：workspace/<name>/ontology/（TTL + Action，copy 自 pack 的 ontology/domains）
          + config.yaml + data/

    返回 workspace_root。
    """
    ontology_dst = os.path.join(workspace_root, "ontology")
    data_dst = os.path.join(workspace_root, "data")
    os.makedirs(ontology_dst, exist_ok=True)
    os.makedirs(data_dst, exist_ok=True)

    # copy pack 的 ontology/domains/（workspace 结构）
    domains_src = os.path.join(pack_root, "ontology", "domains")
    if os.path.isdir(domains_src):
        for domain_name in os.listdir(domains_src):
            src = os.path.join(domains_src, domain_name)
            if not os.path.isdir(src):
                continue
            dst = os.path.join(ontology_dst, "domains", domain_name)
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # copy pack 的 data/（种子数据带入 workspace）
    pack_data_src = os.path.join(pack_root, "data")
    if os.path.isdir(pack_data_src):
        shutil.copytree(pack_data_src, data_dst, dirs_exist_ok=True)

    # 生成 config.yaml
    enabled_domains = _list_subdirs(os.path.join(ontology_dst, "domains"))
    config = {
        "workspace_name": workspace_name,
        "name": workspace_label,
        "source_pack": pack_name,
        "storage": {"type": "json_files", "data_dir": "data"},
        "ontology_dir": "ontology",  # I-3: 显式声明（相对 workspace_root）
        "enabled_domains": enabled_domains,
        "enabled_processes": [],
        "parameters": {},
        "org_tree": [],
    }
    config_path = os.path.join(workspace_root, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

    return workspace_root


def _list_subdirs(path: str) -> List[str]:
    """列出目录下的子目录名（排除 __pycache__）。"""
    if not os.path.isdir(path):
        return []
    return sorted(name for name in os.listdir(path)
                  if os.path.isdir(os.path.join(path, name))
                  and name != "__pycache__")


def seed_workspace_data(workspace_data_dir: str, source_file: str,
                        object_type: str, registry,
                        workspace_name: str = "customer_default") -> str:
    """数据清洗/校验/初始化（onboarding 步骤③）。

    读取 source_file（JSON 数组），按 Object Type 的 properties 校验：
    - id 字段必填
    - 强制盖 workspace_name（防止无标记数据泄漏到默认 workspace，I-1 修复）
    校验通过后写入 workspace_data_dir/<storage_file>。

    registry: EntityRegistry（含 object_types）
    workspace_name: 灌入数据归属的 workspace（强制盖上，不依赖源数据手填）
    返回写入的文件路径。
    """
    obj = registry.object_types.get(object_type)
    if not obj:
        raise ValueError(f"未知 Object Type: {object_type}")

    with open(source_file, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise ValueError("源数据必须是 JSON 数组")

    # 校验：每行必须有 id + 强制盖 workspace_name（I-1：防止无标记数据泄漏）
    for i, row in enumerate(rows):
        if "id" not in row or not row["id"]:
            raise ValueError(f"第 {i+1} 行缺少必填字段: id")
        row["workspace_name"] = workspace_name  # 强制盖，不依赖源数据手填

    # 写入
    out_path = os.path.join(workspace_data_dir, obj.storage_file)
    os.makedirs(workspace_data_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return out_path
