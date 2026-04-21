#!/usr/bin/env python3
"""
门店本体推理引擎 - 临期商品折扣推荐
=====================================
输入：TTL本体文件（WORKTASK-MODULE.ttl + DEMO-STORE-INVENTORY.ttl）
处理：
  1. 加载 TTL（RDFLib）
  2. 查询所有待出清 SKU（clearanceStatus = ClearanceStatusPending）
  3. 计算剩余保质期天数
  4. 查询品类 → 出清规则 → 适用折扣层级
  5. 匹配剩余天数 → 推荐折扣
  6. 生成 WorkTask 实例（TTL 格式）
输出：推荐结果 + WorkTask 实例 TTL
"""

import os
import sys
from datetime import date, datetime
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# 命名空间
SO = Namespace("https://store-ontology.example.com/retail#")
TTL_DIR = os.path.dirname(os.path.abspath(__file__)) or "."
SCHEMA_TTL = os.path.join(TTL_DIR, "../modules/module1-worktask/WORKTASK-MODULE.ttl")
DATA_TTL = os.path.join(TTL_DIR, "DEMO-STORE-INVENTORY.ttl")

# 全局图
g = Graph()

def load_ontology():
    """加载本体 + 实例数据"""
    g.parse(SCHEMA_TTL, format="turtle")
    g.parse(DATA_TTL, format="turtle")
    g.bind("so", SO)
    print(f"[INFO] 本体加载完成: {len(g)} triples")

def days_remaining(expiration_date_str: str, reference_date: date = None) -> int:
    """计算剩余保质期天数"""
    ref = reference_date or date.today()
    exp = date.fromisoformat(expiration_date_str)
    return (exp - ref).days

def query_pending_skus():
    """查询所有待出清 SKU（去重：同一 SKU 只取一条）"""
    query = """
    PREFIX so: <https://store-ontology.example.com/retail#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?sku ?name ?code ?qty ?exp ?cat ?catName
           ?clearanceStatus ?eventType
    WHERE {
        ?sku a so:SKU ;
             so:skuName ?name ;
             so:skuCode ?code ;
             so:currentQuantity ?qty ;
             so:expirationDate ?exp ;
             so:clearanceStatus ?clearanceStatus ;
             so:hasCategory ?cat .
        ?cat rdfs:label ?catName .
        # 只取中文标签，避免同一条 SKU 返回两次
        FILTER(LANG(?catName) = 'zh-CN' || LANG(?catName) = '')
        # 只取待出清状态
        FILTER(?clearanceStatus = so:ClearanceStatusPending)
    }
    GROUP BY ?sku ?name ?code ?qty ?exp ?cat ?catName ?clearanceStatus ?eventType
    """
    results = g.query(query)
    return list(results)

def query_clearance_rule_for_category(category_uri: str):
    """
    查询品类对应的出清规则。
    注：ClearanceRule 在本体中定义为 owl:Class（品类规则的类级别定义），
    而非 NamedIndividual。因此通过 appliesToCategory 属性反向查找。
    """
    query = f"""
    PREFIX so: <https://store-ontology.example.com/retail#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?rule ?urgency ?tier ?tierMin ?tierMax
           ?recDiscount ?minDiscount ?maxDiscount
    WHERE {{
        # 通过 appliesToCategory 找到对应品类的出清规则
        ?rule so:appliesToCategory <{category_uri}> ;
              so:clearanceUrgency ?urgency ;
              so:hasDiscountTier ?tier .
        ?tier so:tierMinDays ?tierMin ;
              so:tierMaxDays ?tierMax ;
              so:recommendedDiscountRate ?recDiscount ;
              so:minDiscountRate ?minDiscount ;
              so:maxDiscountRate ?maxDiscount .
    }}
    ORDER BY ?tierMin
    """
    results = g.query(query)
    return list(results)

def reason_discount(sku_data: dict) -> dict:
    """
    核心推理：
    给定 SKU + 品类 → 查规则 → 匹配剩余天数 → 推荐折扣
    """
    rule_results = query_clearance_rule_for_category(sku_data["cat"])

    if not rule_results:
        return {
            "reasoning": "未找到出清规则，跳过",
            "recommended_discount": None,
            "tier": None,
            "urgency": None,
        }

    # 找匹配的折扣层级（按紧迫度从高到低选第一个匹配的）
    days = sku_data["days_remaining"]
    matched_tier = None
    best_rec = None
    best_urgency = None

    tier_order = {"UrgencyCritical": 0, "UrgencyHigh": 1, "UrgencyMedium": 2,
                   "UrgencyLow": 3, "UrgencyPreventive": 4}

    for row in rule_results:
        tier_min = int(row.tierMin)
        tier_max = int(row.tierMax)
        if tier_min <= days <= tier_max:
            urgency_name = row.urgency.split("#")[1] if "#" in row.urgency else row.urgency
            priority = tier_order.get(urgency_name, 99)
            if matched_tier is None or priority < tier_order.get(best_urgency, 99):
                matched_tier = row
                best_urgency = urgency_name

    if matched_tier:
        tier_uri = matched_tier.tier
        tier_name = tier_uri.split("#")[1] if "#" in tier_uri else tier_uri
        rec = float(matched_tier.recDiscount)
        min_d = float(matched_tier.minDiscount)
        max_d = float(matched_tier.maxDiscount)

        return {
            "reasoning": (
                f"剩余保质期 {days} 天，匹配 [{tier_name}]，"
                f"规则允许折扣 {min_d*100:.0f}%-{max_d*100:.0f}%，推荐 {rec*100:.0f}%"
            ),
            "recommended_discount": rec,
            "tier": tier_name,
            "urgency": best_urgency,
            "min_discount": min_d,
            "max_discount": max_d,
            "tier_uri": str(tier_uri),
        }
    else:
        return {
            "reasoning": f"剩余保质期 {days} 天，超出所有折扣层级适用范围，跳过",
            "recommended_discount": None,
            "tier": None,
            "urgency": None,
        }

def generate_worktask_ttl(sku_data: dict, discount_data: dict, task_id: str) -> str:
    """生成 WorkTask 实例（TTL 格式）"""
    sku_uri = sku_data["sku"]
    sku_code = sku_data["code"]
    sku_name = sku_data["name"]
    qty = sku_data["qty"]
    exp = sku_data["exp"]
    days = sku_data["days_remaining"]
    cat_name = sku_data["catName"]
    urgency = discount_data.get("urgency", "UrgencyHigh")
    tier = discount_data.get("tier", "Unknown")
    rec_rate = discount_data.get("recommended_discount", 0.0)

    # 优先级映射
    priority_map = {
        "UrgencyCritical": "PriorityCritical",
        "UrgencyHigh": "PriorityHigh",
        "UrgencyMedium": "PriorityMedium",
        "UrgencyLow": "PriorityLow",
        "UrgencyPreventive": "PriorityLow",
    }
    priority = priority_map.get(urgency, "PriorityMedium")

    ttl = f"""
# ------------------------------------------------------------
# WorkTask 实例：临期打折任务
# 生成时间：{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}
# 触发商品：{sku_name}（{sku_code}）
# ------------------------------------------------------------
so:{task_id} a so:WorkTask ;
    so:taskId "{task_id}" ;
    so:taskType so:TaskTypeDiscountExecute ;
    so:taskStatus so:TaskStatusPending ;
    so:taskPriority so:{priority} ;
    so:createdAt "{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}"^^xsd:dateTime ;
    so:dueTime "{exp}T23:59:59"^^xsd:dateTime ;
    so:triggerReason "保质期临期"@zh-CN ;
    so:triggeredByInventoryEvent so:{sku_data["event_uri"]} ;
    so:hasSKU so:{sku_code} ;
    so:hasCategory so:{cat_name} ;
    so:originalInventoryQty {qty} ;
    so:recommendedDiscountRate {rec_rate} ;
    so:recommendedReason "剩余保质期 {days} 天（{exp}），品类【{cat_name}】规则适用 [{tier}]，推荐折扣 {rec_rate*100:.0f}%"@zh-CN ;
    so:hasActor so:Emp001 ;
    so:assignedTo so:Emp001 ;
    so:hasChecklist so:{task_id}_Checklist ;
    so:storeCode "S001" ;
    so:storeName "家家悦鲁东区域店" .

# 任务执行清单
so:{task_id}_Checklist a so:WorkTaskCheckItem ;
    so:itemOrder 1 ;
    so:itemDescription "确认打折标签，打印价签"@zh-CN ;
    so:itemStatus so:CheckItemStatusPending .

so:{task_id}_Checklist2 a so:WorkTaskCheckItem ;
    so:itemOrder 2 ;
    so:itemDescription "将商品移至临期商品销售区"@zh-CN ;
    so:itemStatus so:CheckItemStatusPending .

so:{task_id}_Checklist3 a so:WorkTaskCheckItem ;
    so:itemOrder 3 ;
    so:itemDescription "执行 POS 扫描出清"@zh-CN ;
    so:itemStatus so:CheckItemStatusPending .
"""
    return ttl

def main():
    print("=" * 60)
    print("门店本体推理引擎 - 临期折扣推荐")
    print("=" * 60)
    print()

    # 参考日期：默认今天，可通过环境变量覆写（用于回溯测试）
    _ref_date_env = os.environ.get("CLEARANCE_REF_DATE")
    REF_DATE = date.fromisoformat(_ref_date_env) if _ref_date_env else date.today()
    print(f"[INFO] 参考日期: {REF_DATE}")
    print()

    # Step 1：加载本体
    print("[Step 1] 加载本体...")
    load_ontology()
    print()

    # Step 2：查询待出清 SKU
    print("[Step 2] 查询待出清 SKU...")
    skus = query_pending_skus()
    print(f"[INFO] 找到 {len(skus)} 个待出清 SKU")
    print()

    worktask_ttls = []
    results = []

    for row in skus:
        sku_uri = str(row.sku)
        sku_code = str(row.code)
        sku_name = str(row.name)
        qty = int(row.qty)
        exp_str = str(row.exp)
        cat_uri = str(row.cat)
        cat_name = str(row.catName)
        event_uri = str(row.eventType).split("#")[1] if "#" in str(row.eventType) else str(row.eventType)

        days = days_remaining(exp_str, REF_DATE)

        sku_data = {
            "sku": sku_uri,
            "code": sku_code,
            "name": sku_name,
            "qty": qty,
            "exp": exp_str,
            "days_remaining": days,
            "cat": cat_uri,
            "catName": cat_name,
            "event_uri": event_uri,
        }

        print(f"  📦 {sku_name}（{sku_code}）")
        print(f"     品类：{cat_name} | 库存：{qty}件 | 到期：{exp_str} | 剩余：{days}天")

        # Step 3：推理折扣
        discount_data = reason_discount(sku_data)
        print(f"     推理：{discount_data['reasoning']}")

        if discount_data["recommended_discount"] is not None:
            rec = discount_data["recommended_discount"]
            print(f"     ✅ 推荐折扣：{rec*100:.0f}%")
            task_id = f"TASK-{REF_DATE.strftime('%Y%m%d')}-{sku_code[:8]}"
            ttl = generate_worktask_ttl(sku_data, discount_data, task_id)
            worktask_ttls.append(ttl)
            results.append({
                "sku": sku_name,
                "code": sku_code,
                "category": cat_name,
                "days_remaining": days,
                "qty": qty,
                "tier": discount_data["tier"],
                "urgency": discount_data["urgency"],
                "recommended_discount": f"{rec*100:.0f}%",
                "task_id": task_id,
            })
            print(f"     🏷️  生成任务：{task_id}")
        else:
            print(f"     ⏭️  跳过（无需出清）")

        print()

    # Step 4：汇总输出
    print("=" * 60)
    print("推理结果汇总")
    print("=" * 60)

    if results:
        print(f"\n{'商品':<30} {'品类':<8} {'剩余':<4} {'库存':<5} {'层级':<20} {'推荐折扣':<8} {'任务ID'}")
        print("-" * 100)
        for r in results:
            print(f"{r['sku']:<30} {r['category']:<8} {r['days_remaining']:<4} {r['qty']:<5} {r['tier']:<20} {r['recommended_discount']:<8} {r['task_id']}")
    else:
        print("  无需生成任务")

    # Step 5：输出 WorkTask TTL
    if worktask_ttls:
        output_path = os.path.join(TTL_DIR, "DEMO-WORKTASK-RESULTS.ttl")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# ============================================================\n")
            f.write("# WorkTask 推理结果（由 clearance_engine.py 自动生成）\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n")
            f.write("# ============================================================\n\n")
            f.write("@prefix so: <https://store-ontology.example.com/retail#> .\n")
            f.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n")
            f.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n")
            for ttl in worktask_ttls:
                f.write(ttl)

        print(f"\n[INFO] WorkTask 实例已写入: {output_path}")

    print()
    print("[INFO] 推理完成")

if __name__ == "__main__":
    main()
