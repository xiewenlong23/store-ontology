"""客户 onboarding 工具（P3）：ontocopy + ontoseed。

实现 APaaS spec §3.3 的 onboarding 五步中的代码自动化部分：
- copy_pack_to_customer: copy 行业包到客户目录（步骤①）
- seed_customer_data: 数据清洗/校验/初始化（步骤③）
步骤②④是客户手动编辑，步骤⑤是 bootstrap_customer（T3 升级）。
"""
import os
import json
import shutil
from typing import List

import yaml


def copy_pack_to_customer(pack_root: str, customer_root: str,
                          customer_id: str, customer_name: str,
                          pack_name: str) -> str:
    """Copy 行业包到客户目录（workspace 重构版）。

    pack_root: workspace/<pack_name>/ 的绝对路径
    customer_root: workspace/<customer_id>/ 的绝对路径
    生成：workspace/<id>/ontology/（TTL + Action，copy 自 pack 的 ontology/domains）
          + config.yaml + data/

    返回 customer_root。
    """
    ontology_dst = os.path.join(customer_root, "ontology")
    data_dst = os.path.join(customer_root, "data")
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

    # copy pack 的 data/（种子数据带入客户）
    pack_data_src = os.path.join(pack_root, "data")
    if os.path.isdir(pack_data_src):
        shutil.copytree(pack_data_src, data_dst, dirs_exist_ok=True)

    # 生成 config.yaml
    enabled_domains = _list_subdirs(os.path.join(ontology_dst, "domains"))
    config = {
        "customer_id": customer_id,
        "name": customer_name,
        "source_pack": pack_name,
        "storage": {"type": "json_files", "data_dir": "data"},
        "ontology_dir": "ontology",  # I-3: 显式声明（相对 customer_root）
        "enabled_domains": enabled_domains,
        "enabled_processes": [],
        "parameters": {},
        "org_tree": [],
    }
    config_path = os.path.join(customer_root, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

    return customer_root


def _list_subdirs(path: str) -> List[str]:
    """列出目录下的子目录名（排除 __pycache__）。"""
    if not os.path.isdir(path):
        return []
    return sorted(name for name in os.listdir(path)
                  if os.path.isdir(os.path.join(path, name))
                  and name != "__pycache__")


def seed_customer_data(customer_data_dir: str, source_file: str,
                       object_type: str, registry,
                       customer_id: str = "customer_default") -> str:
    """数据清洗/校验/初始化（步骤③）。

    读取 source_file（JSON 数组），按 Object Type 的 properties 校验：
    - id 字段必填
    - 强制盖 customer_id（防止无标记数据泄漏到默认客户，I-1 修复）
    校验通过后写入 customer_data_dir/<storage_file>。

    registry: EntityRegistry（含 object_types）
    customer_id: 灌入数据归属的客户 ID（强制盖上，不依赖源数据手填）
    返回写入的文件路径。
    """
    obj = registry.object_types.get(object_type)
    if not obj:
        raise ValueError(f"未知 Object Type: {object_type}")

    with open(source_file, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise ValueError("源数据必须是 JSON 数组")

    # 校验：每行必须有 id + 强制盖 customer_id（I-1：防止无标记数据泄漏）
    prop_names = {p.name for p in obj.properties}
    for i, row in enumerate(rows):
        if "id" not in row or not row["id"]:
            raise ValueError(f"第 {i+1} 行缺少必填字段: id")
        row["customer_id"] = customer_id  # 强制盖，不依赖源数据手填

    # 写入
    out_path = os.path.join(customer_data_dir, obj.storage_file)
    os.makedirs(customer_data_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return out_path
