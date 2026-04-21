#!/usr/bin/env python3
"""
AI 自动确认阈值服务

基于风险评估决定哪些任务可以AI自动确认，无需人工干预。
风险评估维度：
1. 折扣幅度（高折扣风险高）
2. 库存数量（高库存风险高）
3. 剩余保质期（越短风险越高）
4. 商品品类（部分品类不允许自动确认）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.models import ProductCategory, RiskLevel

logger = logging.getLogger(__name__)

# 自动确认风险阈值配置
AUTO_CONFIRM_CONFIG = {
    # 低风险：折扣 <= 50% 且 库存 <= 50 且 剩余保质期 >= 1天
    "max_discount_rate": 0.50,
    "max_stock": 50,
    "min_days_left": 1,
    # 品类黑名单：这些品类不允许自动确认
    "excluded_categories": {
        ProductCategory.MEAT_POULTRY,  # 肉禽
        ProductCategory.SEAFOOD,       # 水产
        ProductCategory.DAIRY,         # 乳品（品质敏感）
    },
}


@dataclass
class RiskAssessment:
    """风险评估结果"""
    risk_level: RiskLevel
    auto_confirm: bool
    reason: str
    score: float  # 0.0 ~ 1.0，越高风险越高


def assess_risk(
    discount_rate: float,
    stock: int,
    days_left: int,
    category: ProductCategory,
) -> RiskAssessment:
    """
    评估任务风险等级和是否可自动确认

    Args:
        discount_rate: 推荐折扣幅度（0.0 ~ 1.0）
        stock: 当前库存
        days_left: 剩余保质期天数
        category: 商品品类

    Returns:
        RiskAssessment: 包含风险等级、自动确认建议和理由
    """
    score = 0.0
    reasons = []

    # 1. 折扣幅度评分（权重 40%）
    if discount_rate > 0.70:
        score += 0.40
        reasons.append(f"高折扣({discount_rate*100:.0f}%)")
    elif discount_rate > 0.50:
        score += 0.20
        reasons.append(f"中高折扣({discount_rate*100:.0f}%)")
    elif discount_rate > 0.30:
        score += 0.10
        reasons.append(f"中等折扣({discount_rate*100:.0f}%)")
    else:
        reasons.append(f"低折扣({discount_rate*100:.0f}%)")

    # 2. 库存评分（权重 30%）
    if stock > 100:
        score += 0.30
        reasons.append(f"高库存({stock})")
    elif stock > 50:
        score += 0.15
        reasons.append(f"中高库存({stock})")
    else:
        reasons.append(f"正常库存({stock})")

    # 3. 保质期评分（权重 20%）
    if days_left <= 1:
        score += 0.20
        reasons.append(f"临界保质期({days_left}天)")
    elif days_left <= 2:
        score += 0.10
        reasons.append(f"短保质期({days_left}天)")
    else:
        reasons.append(f"正常保质期({days_left}天)")

    # 4. 品类敏感度评分（权重 10%）
    excluded = AUTO_CONFIRM_CONFIG["excluded_categories"]
    if category in excluded:
        score += 0.10
        reasons.append(f"敏感品类({category.value})")

    # 判断风险等级
    if score >= 0.60:
        risk_level = RiskLevel.HIGH
        auto_confirm = False
    elif score >= 0.30:
        risk_level = RiskLevel.MEDIUM
        auto_confirm = False
    else:
        risk_level = RiskLevel.LOW
        auto_confirm = True

    # 额外安全检查：品类黑名单直接禁止自动确认
    if category in AUTO_CONFIRM_CONFIG["excluded_categories"]:
        auto_confirm = False
        risk_level = RiskLevel.MEDIUM
        reasons.append("品类禁止自动确认")

    reason_str = "; ".join(reasons) if reasons else "低风险"

    logger.info(
        f"[AutoConfirm] product assessment: score={score:.2f}, "
        f"risk={risk_level.value}, auto_confirm={auto_confirm}, reason={reason_str}"
    )

    return RiskAssessment(
        risk_level=risk_level,
        auto_confirm=auto_confirm,
        reason=reason_str,
        score=score,
    )


def should_auto_confirm(
    discount_rate: float,
    stock: int,
    days_left: int,
    category: ProductCategory,
) -> tuple[bool, RiskLevel, str]:
    """
    判断任务是否应该自动确认（便捷方法）

    Returns:
        (should_auto_confirm, risk_level, reason)
    """
    assessment = assess_risk(discount_rate, stock, days_left, category)
    return assessment.auto_confirm, assessment.risk_level, assessment.reason
