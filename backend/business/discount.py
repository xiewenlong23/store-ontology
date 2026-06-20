"""折扣计算 —— 全系统唯一事实源（见建模规范 §6.2、§8 反模式 1/8/9）。
其它处（tools/SKILL）只调用本函数，禁止重复定义折扣数值。"""
from ontology.discount_stub import get_discount_source


def calculate_discount(discount_tier: str) -> int:
    """返回减扣百分比（0-100 int）。50 表示五折（减 50%）。"""
    rules = get_discount_source()
    for r in rules:
        if r["tier"] == discount_tier:
            return int(r["discount_percent"])
    raise KeyError(f"未知 discount_tier: {discount_tier}")
