"""折扣数据源的进程内可替换入口（M-2 升级：支持客户级规则路径）。

查找顺序：
1. 进程内注入源（测试用 set_discount_source）
2. 客户级规则文件（customers/<cid>/data/discount_rules.json 或 ontology 参数指定）
3. pack 默认（packs/retail/domains/marketing/rules/discount_rules.json）
4. 全局回退（data/discount_rules.json）
"""
import json
import os

_source = None  # None 表示用磁盘文件


def set_discount_source(rules):
    """测试用：注入内存折扣规则列表。传 None 恢复磁盘读取。"""
    global _source
    _source = rules


def _find_rules_file():
    """按优先级查找 discount_rules.json（M-2：客户级 > pack > 全局）。"""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates = [
        # pack 默认
        os.path.join(root, "backend", "packs", "retail", "domains", "marketing",
                     "rules", "discount_rules.json"),
        # 全局回退
        os.path.join(root, "data", "discount_rules.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[-1]  # 回退到最后一个（即使不存在，让 open 报错清晰）


def get_discount_source():
    if _source is not None:
        return _source
    path = _find_rules_file()
    with open(path, encoding="utf-8") as f:
        return json.load(f)
