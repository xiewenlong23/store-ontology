"""折扣数据源的进程内可替换入口。默认从磁盘加载，测试可注入。"""
import json
import os

_source = None  # None 表示用磁盘文件


def set_discount_source(rules):
    """测试用：注入内存折扣规则列表。传 None 恢复磁盘读取。"""
    global _source
    _source = rules


def get_discount_source():
    if _source is not None:
        return _source
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(root, "data", "discount_rules.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
