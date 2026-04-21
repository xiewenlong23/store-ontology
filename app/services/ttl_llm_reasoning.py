#!/usr/bin/env python3
"""
TTL + LLM 协同推理引擎

分层架构：
- Layer 1 (TTL Only, <50ms): 简单结构化查询
- Layer 2 (TTL + LLM, 500ms-2s): 复杂推理

核心原则：
- TTL 本体作为可信规则源（Business Logic Source of Truth）
- LLM 作为推理引擎和自然语言接口
- 所有推理结果必须可回溯到 TTL 规则
"""

import json
import logging
from datetime import date
from typing import Optional, Any

from app.models import ProductCategory, RiskLevel
from app.services.sparql_service import SPARQLService
from app.services.llm_service import get_minimax_llm

logger = logging.getLogger(__name__)


# ============================================================
# Layer 1: TTL Only (Simple Queries)
# ============================================================

def ttl_query_pending_skus() -> dict:
    """
    Layer 1: 查询所有待出清 SKU（纯 TTL 查询）
    """
    sparql = SPARQLService()
    results = sparql.query_pending_clearance_skus()
    if not results:
        return {"skus": [], "count": 0, "source": "ttl", "layer": 1}

    skus = []
    for row in results:
        skus.append({
            "sku_uri": str(row.sku),
            "name": str(row.name),
            "code": str(row.code),
            "quantity": int(row.qty),
            "expiry_date": str(row.exp),
            "category_uri": str(row.cat),
            "category_name": str(row.catName),
            "clearance_status": str(row.clearanceStatus).split("#")[-1],
        })
    return {"skus": skus, "count": len(skus), "source": "ttl", "layer": 1}


def ttl_query_clearance_rules(category: str) -> dict:
    """
    Layer 1: 查询品类折扣规则（纯 TTL 查询）
    """
    from app.routers.reasoning import CATEGORY_URI_MAP

    category_uri = CATEGORY_URI_MAP.get(category)
    if not category_uri:
        return {"rules": [], "found": False, "source": "ttl", "layer": 1}

    sparql = SPARQLService()
    results = sparql.query_clearance_rules(category_uri)
    if not results:
        return {"rules": [], "found": False, "source": "ttl", "layer": 1}

    rules = []
    for row in results:
        rules.append({
            "urgency": str(row.urgency).split("#")[-1],
            "tier": str(row.tier).split("#")[-1],
            "tier_min_days": int(row.tierMin),
            "tier_max_days": int(row.tierMax),
            "recommended_discount": float(row.recDiscount),
            "min_discount": float(row.minDiscount),
            "max_discount": float(row.maxDiscount),
        })
    return {"rules": rules, "found": True, "source": "ttl", "layer": 1}


def ttl_query_exemption_rules(category: str = None) -> dict:
    """
    Layer 1: 查询豁免规则（纯 TTL 查询）
    """
    sparql = SPARQLService()
    results = sparql.query_exemption_rules(category)
    if not results:
        return {"exemptions": [], "found": False, "source": "ttl", "layer": 1}

    exemptions = []
    for row in results:
        exemptions.append({
            "exemption_type": str(row.exemptionType).split("#")[-1] if hasattr(row, "exemptionType") else None,
            "exemption_reason": str(row.exemptionReason) if hasattr(row, "exemptionReason") else None,
            "rule_source": str(row.ruleSource).split("#")[-1] if hasattr(row, "ruleSource") else None,
        })
    return {"exemptions": exemptions, "found": True, "source": "ttl", "layer": 1}


def ttl_query_tasks(status: str = None) -> dict:
    """
    Layer 1: 查询任务列表（纯 TTL 查询）
    """
    sparql = SPARQLService()
    results = sparql.get_all_tasks(limit=50)
    if not results:
        return {"tasks": [], "count": 0, "source": "ttl", "layer": 1}

    tasks = []
    for row in results:
        task_status = str(row.taskStatus).split("#")[-1] if "#" in str(row.taskStatus) else str(row.taskStatus)
        # 状态过滤
        if status and task_status.lower() != status.lower():
            continue
        tasks.append({
            "task_uri": str(row.task),
            "task_id": str(row.taskId),
            "task_type": str(row.taskType).split("#")[-1] if "#" in str(row.taskType) else str(row.taskType),
            "task_status": task_status,
            "task_priority": str(row.taskPriority).split("#")[-1] if hasattr(row, "taskPriority") and row.taskPriority else None,
            "created_at": str(row.createdAt) if hasattr(row, "createdAt") and row.createdAt else None,
            "due_time": str(row.dueTime) if hasattr(row, "dueTime") and row.dueTime else None,
        })
    return {"tasks": tasks, "count": len(tasks), "source": "ttl", "layer": 1}


# ============================================================
# Layer 2: TTL + LLM 协同推理
# ============================================================

def _build_ttl_context_for_discount(
    category: str,
    days_left: int,
    stock: int,
    product_name: str,
) -> str:
    """
    构建 TTL 本体上下文，供 LLM 参考

    返回结构化的 TTL 规则文本，LLM 可据此推理
    """
    rules_data = ttl_query_clearance_rules(category)
    exemptions_data = ttl_query_exemption_rules()

    context_parts = [
        f"【商品信息】{product_name}",
        f"  品类: {category}",
        f"  剩余保质期: {days_left} 天",
        f"  当前库存: {stock}",
    ]

    if rules_data.get("found"):
        context_parts.append("\n【本体折扣规则】")
        for rule in rules_data["rules"]:
            context_parts.append(
                f"  - {rule['tier']}: "
                f"剩余 {rule['tier_min_days']}-{rule['tier_max_days']} 天，"
                f"折扣区间 {rule['min_discount']*100:.0f}%-{rule['max_discount']*100:.0f}%，"
                f"推荐 {rule['recommended_discount']*100:.0f}%，"
                f"紧迫度 {rule['urgency']}"
            )
    else:
        context_parts.append("\n【本体折扣规则】未找到该品类规则，使用标准分级")

    if exemptions_data.get("found"):
        context_parts.append("\n【本体豁免规则】")
        for ex in exemptions_data["exemptions"][:5]:  # 最多5条
            if ex.get("exemption_reason"):
                context_parts.append(
                    f"  - {ex['exemption_type']}: {ex['exemption_reason']}"
                )

    # 添加库存调整提示
    if stock > 100 and days_left <= 2:
        context_parts.append(
            f"\n【库存调整】高库存({stock}) + 短有效期({days_left}天) → 建议更激进折扣"
        )

    return "\n".join(context_parts)


def reason_discount_llm(
    product_id: str,
    product_name: str,
    category: ProductCategory,
    expiry_date: date,
    stock: int,
    use_llm: bool = True,
) -> dict:
    """
    Layer 2: TTL + LLM 协同折扣推理

    流程：
    1. TTL 查折扣规则（规则源）
    2. TTL 查豁免规则（约束源）
    3. LLM 综合推理 → 折扣建议 + 自然语言解释

    Args:
        product_id: 商品ID
        product_name: 商品名称
        category: 品类
        expiry_date: 过期日期
        stock: 库存
        use_llm: 是否使用 LLM（False 则降级到纯 TTL）

    Returns:
        {
            "product_id": ...,
            "recommended_discount": 0.2,
            "discount_range": [0.1, 0.5],
            "tier": 1,
            "reasoning": "...",
            "explanation": "...",  # LLM 生成的自然语言解释
            "is_exempted": False,
            "exemption_type": None,
            "exemption_reason": None,
            "source": "ttl+llm" or "ttl",
            "layer": 2,
        }
    """
    today = date.today()
    days_left = (expiry_date - today).days

    if days_left < 0:
        return {
            "product_id": product_id,
            "recommended_discount": None,
            "discount_range": [0.0, 0.0],
            "tier": 0,
            "reasoning": f"商品已过期 {abs(days_left)} 天",
            "explanation": f"⚠️ 商品已过期 {abs(days_left)} 天，无法进行折扣处理。",
            "is_exempted": False,
            "source": "ttl",
            "layer": 1 if not use_llm else 2,
        }

    # Step 1: TTL 查询
    ttl_context = _build_ttl_context_for_discount(
        category=category.value,
        days_left=days_left,
        stock=stock,
        product_name=product_name,
    )

    # Step 2: 查豁免规则
    from app.services.sparql_service import SPARQLService
    sparql = SPARQLService()
    exemption = sparql.check_product_exemption(
        product_id=product_id,
        category_uri="",
        is_imported=False,
        is_organic=False,
        is_promoted=False,
        arrival_days=None,
    )

    is_exempted = exemption is not None
    exemption_type = exemption["exemption_type"] if is_exempted else None
    exemption_reason = exemption["exemption_reason"] if is_exempted else None

    # Step 3: TTL 匹配 tier（确定性部分，LLM 不可覆盖）
    rules_data = ttl_query_clearance_rules(category.value)
    matched_tier = None
    rec_discount = None
    discount_range = [0.0, 1.0]
    tier_name = None

    if rules_data.get("found"):
        for rule in rules_data["rules"]:
            if rule["tier_min_days"] <= days_left <= rule["tier_max_days"]:
                matched_tier = rule
                rec_discount = rule["recommended_discount"]
                discount_range = [rule["min_discount"], rule["max_discount"]]
                tier_name = rule["tier"]
                break

    # Step 4: TTL 降级 fallback
    if matched_tier is None:
        # 使用标准分级
        if days_left <= 1:
            tier_num, rec_discount = 1, 0.20
            discount_range = [0.10, 0.50]
        elif days_left <= 3:
            tier_num, rec_discount = 2, 0.40
            discount_range = [0.30, 0.60]
        elif days_left <= 7:
            tier_num, rec_discount = 3, 0.70
            discount_range = [0.50, 0.80]
        elif days_left <= 14:
            tier_num, rec_discount = 4, 0.85
            discount_range = [0.70, 0.90]
        else:
            tier_num, rec_discount = 5, 0.95
            discount_range = [0.90, 1.00]
        tier_name = f"Tier{tier_num}"
        matched_tier = {"tier": tier_name, "urgency": "Medium"}

    # Step 5: 库存调整（确定性规则）
    adjusted_discount = rec_discount
    if stock > 100 and days_left <= 2:
        adjusted_discount = min(rec_discount * 0.8, 0.30)
        ttl_context += f"\n【库存调整】高库存+短有效期，折扣下调至 {adjusted_discount*100:.0f}%"

    # Step 6: LLM 生成自然语言解释
    explanation = None
    if use_llm and not is_exempted:
        try:
            llm = get_minimax_llm()
            prompt = f"""你是门店运营折扣推理专家。根据以下 TTL 本体数据和商品信息，给出折扣建议和解释。

{ttl_context}

【TTL 推理结果】
- 匹配 Tier: {tier_name}
- 推荐折扣: {rec_discount*100:.0f}%
- 折扣区间: {discount_range[0]*100:.0f}%-{discount_range[1]*100:.0f}%
- 库存调整后折扣: {adjusted_discount*100:.0f}%
- 豁免状态: {"是" if is_exempted else "否"}

请用自然语言（50-100字）向店长解释：
1. 为什么建议这个折扣
2. 有什么需要注意的
3. 是否需要人工确认

格式：
折扣建议: X%
原因: ...
行动建议: ..."""

            response = llm.chat([
                {"role": "system", "content": "你是一个专业的门店运营助手，擅长用简单易懂的语言解释复杂的规则。"},
                {"role": "user", "content": prompt},
            ])
            explanation = response.strip()
        except Exception as e:
            logger.warning(f"[TTL+LLM] LLM explanation failed: {e}")
            explanation = f"建议折扣 {adjusted_discount*100:.0f}%，请店长确认。"

    # Step 7: 构建推理说明（可回溯到 TTL）
    reasoning_parts = [
        f"剩余保质期 {days_left} 天",
        f"匹配 {tier_name}",
        f"推荐折扣 {adjusted_discount*100:.0f}%",
    ]
    if stock > 100 and days_left <= 2:
        reasoning_parts.append("高库存+短有效期已调整")
    if is_exempted:
        reasoning_parts.append(f"豁免: {exemption_type}")

    return {
        "product_id": product_id,
        "product_name": product_name,
        "category": category.value,
        "days_left": days_left,
        "recommended_discount": adjusted_discount,
        "discount_range": discount_range,
        "tier": 1 if "TierShelfLife1Day" in tier_name
            else 2 if "TierShelfLife2to3Days" in tier_name
            else 3 if "TierShelfLife4to7Days" in tier_name
            else 4 if "TierShelfLife8to14Days" in tier_name
            else 5 if "TierShelfLife15to30Days" in tier_name
            else 1,
        "tier_name": tier_name,
        "reasoning": " → ".join(reasoning_parts),
        "explanation": explanation or f"建议折扣 {adjusted_discount*100:.0f}%，请店长确认。",
        "is_exempted": is_exempted,
        "exemption_type": exemption_type,
        "exemption_reason": exemption_reason,
        "auto_create_task": days_left <= 1 and not is_exempted,
        "source": "ttl+llm" if use_llm else "ttl",
        "layer": 2 if use_llm else 1,
    }


def assess_risk_llm(
    discount_rate: float,
    stock: int,
    days_left: int,
    category: ProductCategory,
    use_llm: bool = True,
) -> dict:
    """
    Layer 2: TTL + LLM 协同风险评估

    流程：
    1. TTL 查品类风险规则
    2. LLM 综合评估风险等级 + 自动确认建议

    Returns:
        {
            "risk_level": "low",
            "risk_score": 0.2,
            "auto_confirm": True,
            "reason": "...",
            "explanation": "...",  # LLM 生成的解释
            "source": "ttl+llm",
        }
    """
    from app.services.sparql_service import SPARQLService
    from app.services.auto_confirm_service import assess_risk

    # Step 1: TTL 快速风险评估（兜底）
    ttl_risk = assess_risk(discount_rate, stock, days_left, category)

    # Step 2: LLM 综合评估（可选）
    explanation = None
    if use_llm:
        try:
            llm = get_minimax_llm()
            from app.routers.reasoning import CATEGORY_URI_MAP
            category_uri = CATEGORY_URI_MAP.get(category.value, "")
            category_name = category.value

            prompt = f"""你是门店运营风险评估专家。根据以下信息，评估风险等级和是否应该自动确认。

【商品信息】
- 品类: {category_name}
- 推荐折扣: {discount_rate*100:.0f}%
- 当前库存: {stock}
- 剩余保质期: {days_left} 天

【TTL 风险评估结果】
- 风险评分: {ttl_risk.score:.2f}
- 风险等级: {ttl_risk.risk_level.value}
- 是否建议自动确认: {"是" if ttl_risk.auto_confirm else "否"}
- 评估理由: {ttl_risk.reason}

【风险因素】
- 折扣幅度: {"高" if discount_rate > 0.5 else "中" if discount_rate > 0.3 else "低"}
- 库存: {"高" if stock > 100 else "中" if stock > 50 else "低"}
- 保质期: {"极短" if days_left <= 1 else "短" if days_left <= 3 else "正常"}

请用 2-3 句话向店长解释：
1. 这个风险评估的核心原因
2. 是否建议自动确认，还是需要人工复核

格式：
风险解读: ...
确认建议: ..."""

            response = llm.chat([
                {"role": "system", "content": "你是一个专业的门店运营助手，擅长用简单易懂的语言解释风险评估结果。"},
                {"role": "user", "content": prompt},
            ])
            explanation = response.strip()
        except Exception as e:
            logger.warning(f"[TTL+LLM] Risk LLM assessment failed: {e}")
            explanation = f"风险评估: {ttl_risk.risk_level.value}，{'建议自动确认' if ttl_risk.auto_confirm else '建议人工确认'}。"

    return {
        "risk_level": ttl_risk.risk_level.value,
        "risk_score": ttl_risk.score,
        "auto_confirm": ttl_risk.auto_confirm,
        "reason": ttl_risk.reason,
        "explanation": explanation,
        "source": "ttl+llm" if use_llm else "ttl",
    }


def explain_discount_reasoning(
    product_id: str,
    product_name: str,
    category: str = None,
    expiry_date=None,
    stock: int = None,
    discount_rate: float = None,
) -> dict:
    """
    解释为什么某商品当前是某个折扣（Layer 2）。

    结合 TTL 规则和 LLM 生成自然语言解释。

    Args:
        product_id: 商品ID
        product_name: 商品名称
        category: 品类
        expiry_date: 到期日期
        stock: 库存量
        discount_rate: 当前折扣率

    Returns:
        {
            "success": True,
            "product_name": str,
            "discount_rate": float,
            "explanation": str,  # 自然语言解释
            "tier": int,
            "tier_name": str,
            "reasoning": str,
        }
    """
    from app.models import ProductCategory

    cat = ProductCategory(category) if category else ProductCategory.DAILY_FRESH

    # 查 TTL 规则（ttl_query_clearance_rules 只接受 category 参数）
    rules = ttl_query_clearance_rules(category=category or "daily_fresh")
    rec_discount = 0.4
    disc_range = [0.1, 0.5]
    tier_name = "Unknown"
    tier = 0
    days_left = 0
    matched_rule = None  # 初始化，避免 if matched_rule 报错

    if rules and isinstance(rules, list) and len(rules) > 0:
        matched_rule = rules[0]
        tier_name = matched_rule.get("tier_name", "TierShelfLife1Day")
        rec_discount = matched_rule.get("recommended_discount", 0.4)
        disc_range = matched_rule.get("discount_range", [0.1, 0.5])
        tier = matched_rule.get("tier", 0)

        # 解析 tier 数字
        if "1Day" in tier_name:
            tier = 1
        elif "2Day" in tier_name:
            tier = 2
        elif "3Day" in tier_name:
            tier = 3

    # 生成自然语言解释
    if discount_rate:
        explanation = (
            f"这件 {product_name} 当前标价是原价的 {discount_rate*100:.0f}%。"
        )
        if matched_rule:
            explanation += (
                f"根据系统规则，该商品属于「{tier_name}」，"
                f"建议折扣率是 {rec_discount*100:.0f}%（合理范围 {disc_range[0]*100:.0f}%-{disc_range[1]*100:.0f}%。"
            )
            if days_left > 0:
                explanation += f"剩余保质期还有 {days_left} 天。"
            if stock and stock > 100:
                explanation += f"当前库存 {stock} 件，属于高库存，折扣偏高有利于加快出清。"
            explanation += "这是系统根据临期规则和库存情况综合计算的结果。"
        else:
            explanation += "该品类暂无明确的TTL规则，系统给出了一个建议折扣。"
    else:
        explanation = f"抱歉，未提供当前折扣率，无法生成解释。"

    return {
        "success": True,
        "product_name": product_name,
        "discount_rate": discount_rate,
        "days_left": days_left,
        "tier": tier,
        "tier_name": tier_name,
        "discount_range": disc_range,
        "recommended_discount": rec_discount,
        "explanation": explanation,
        "reasoning": explanation,
    }


def generate_chat_response(
    user_input: str,
    intent: str,
    ttl_result: Optional[dict],
    llm_result: Optional[dict],
    layer: int,
) -> str:
    """
    Layer 2: 生成自然语言回复

    将 TTL 查询结果和 LLM 推理结果综合，生成面向店长的自然语言回复。
    """
    if layer == 1:
        # Layer 1: 简单查询，直接格式化 TTL 结果
        return _format_ttl_result(user_input, intent, ttl_result)
    else:
        # Layer 2: 复杂查询，用 LLM 解释
        return _format_llm_result(user_input, intent, ttl_result, llm_result)


def _format_ttl_result(user_input: str, intent: str, result: Optional[dict]) -> str:
    """格式化 Layer 1 简单查询结果"""
    if result is None:
        return "抱歉，暂时无法查询到相关信息，请稍后重试。"

    if intent == "query_pending":
        skus = result.get("skus", [])
        if not skus:
            return "目前没有待出清的临期商品，库存状态良好 👍"
        lines = [f"目前有 {len(skus)} 个待出清商品：\n"]
        for sku in skus[:10]:  # 最多显示10条
            lines.append(
                f"• {sku['name']} | 库存 {sku['quantity']} | "
                f"到期 {sku['expiry_date']} | {sku.get('category_name', '未知品类')}"
            )
        if len(skus) > 10:
            lines.append(f"\n... 还有 {len(skus) - 10} 个商品，扫描全部查看")
        return "\n".join(lines)

    elif intent == "query_tasks":
        tasks = result.get("tasks", [])
        if not tasks:
            return "当前没有任务"
        lines = [f"当前有 {len(tasks)} 个任务：\n"]
        for t in tasks[:10]:
            lines.append(
                f"• {t['task_id']} | {t['task_type']} | 状态: {t['task_status']}"
            )
        return "\n".join(lines)

    elif intent == "query_discount":
        rules = result.get("rules", [])
        if not rules:
            return "未找到该品类的折扣规则"
        lines = [f"该品类折扣规则：\n"]
        for r in rules:
            lines.append(
                f"• {r['tier']}: {r['tier_min_days']}-{r['tier_max_days']}天 "
                f"→ 折扣 {r['recommended_discount']*100:.0f}% "
                f"({r['min_discount']*100:.0f}%-{r['max_discount']*100:.0f}%)"
            )
        return "\n".join(lines)

    return f"查询结果：共 {result.get('count', result.get('count', len(result.get('skus', []))))} 条记录"


def _format_llm_result(
    user_input: str,
    intent: str,
    ttl_result: Optional[dict],
    llm_result: Optional[dict],
) -> str:
    """格式化 Layer 2 复杂推理结果"""
    if llm_result and llm_result.get("explanation"):
        return llm_result["explanation"]

    if intent == "query_discount" and llm_result:
        disc = llm_result.get("recommended_discount", 0)
        tier = llm_result.get("tier_name", "T1")
        days = llm_result.get("days_left", "?")
        is_exempted = llm_result.get("is_exempted", False)

        if is_exempted:
            return f"该商品属于豁免品类，不参与临期折扣。如有疑问请联系总部。"

        return (
            f"📋 折扣建议\n"
            f"商品：{llm_result.get('product_name', '未知')}\n"
            f"剩余保质期：{days} 天\n"
            f"匹配规则：{tier}\n"
            f"推荐折扣：{disc*100:.0f}%\n"
            f"折扣区间：{llm_result.get('discount_range', [0, 1])[0]*100:.0f}%-"
            f"{llm_result.get('discount_range', [0, 1])[1]*100:.0f}%\n\n"
            f"💡 {llm_result.get('reasoning', '')}"
        )

    if intent == "assess_risk" and llm_result:
        return (
            f"⚠️ 风险评估\n"
            f"风险等级：{llm_result.get('risk_level', '?').upper()}\n"
            f"风险评分：{llm_result.get('risk_score', 0):.2f}\n"
            f"自动确认：{'✅ 是' if llm_result.get('auto_confirm') else '❌ 否，需人工确认'}\n\n"
            f"💡 {llm_result.get('reason', '')}"
        )

    return "抱歉，暂时无法处理您的请求，请稍后重试。"
