#!/usr/bin/env python3
"""
SPARQL 本体查询服务
封装 RDFLib 图查询，提供语义层查询能力
"""

from pathlib import Path
from typing import Optional
import logging

from rdflib import Graph, Namespace

logger = logging.getLogger(__name__)

SO = Namespace("https://store-ontology.example.com/retail#")

ONTOLOGY_FILE = Path(__file__).parent.parent.parent / "modules" / "module1-worktask" / "WORKTASK-MODULE.ttl"

# 模块级 graph 缓存（进程内单例，避免每次实例化重解析 TTL）
_cached_graph: Optional[Graph] = None


def _get_cached_graph() -> Graph:
    """获取缓存的 graph，首次调用时解析 TTL，之后复用。"""
    global _cached_graph
    if _cached_graph is None:
        _cached_graph = Graph()
        _cached_graph.parse(str(ONTOLOGY_FILE), format="turtle")
        _cached_graph.bind("so", SO)
        logger.info(f"[SPARQL] Loaded ontology: {len(_cached_graph)} triples")
    return _cached_graph


class SPARQLService:
    def __init__(self, ontology_file: Optional[Path] = None):
        self.ontology_file = ontology_file or ONTOLOGY_FILE

    @property
    def graph(self) -> Graph:
        # 统一使用模块级缓存，支持多实例但共享同一 graph
        return _get_cached_graph()

    def query(self, sparql: str) -> list:
        """执行 SPARQL 查询，返回结果列表"""
        try:
            results = self.graph.query(sparql)
            return list(results)
        except Exception as e:
            logger.error(f"[SPARQL] Query failed: {e}")
            return []

    def query_pending_clearance_skus(self) -> list:
        """查询所有待出清 SKU"""
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
            FILTER(LANG(?catName) = 'zh-CN' || LANG(?catName) = '')
            FILTER(?clearanceStatus = so:ClearanceStatusPending)
        }
        GROUP BY ?sku ?name ?code ?qty ?exp ?cat ?catName ?clearanceStatus ?eventType
        """
        return self.query(query)

    def query_clearance_rules(self, category_uri: str) -> list:
        """查询品类对应的出清规则"""
        query = f"""
        PREFIX so: <https://store-ontology.example.com/retail#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?rule ?urgency ?tier ?tierMin ?tierMax
               ?recDiscount ?minDiscount ?maxDiscount
        WHERE {{
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
        return self.query(query)

    def get_task_by_id(self, task_id: str) -> list:
        """根据任务ID查询 WorkTask"""
        query = f"""
        PREFIX so: <https://store-ontology.example.com/retail#>

        SELECT ?task ?taskId ?taskType ?taskStatus ?taskPriority
               ?createdAt ?dueTime ?completedAt
        WHERE {{
            ?task a so:WorkTask ;
                  so:taskId ?taskId ;
                  so:taskType ?taskType ;
                  so:taskStatus ?taskStatus .
            OPTIONAL {{ ?task so:taskPriority ?taskPriority }}
            OPTIONAL {{ ?task so:createdAt ?createdAt }}
            OPTIONAL {{ ?task so:dueTime ?dueTime }}
            OPTIONAL {{ ?task so:completedAt ?completedAt }}
            FILTER(?taskId = "{task_id}")
        }}
        """
        return self.query(query)

    def get_all_tasks(self, limit: int = 50) -> list:
        """查询所有 WorkTask（上限 limit 条）"""
        query = f"""
        PREFIX so: <https://store-ontology.example.com/retail#>

        SELECT ?task ?taskId ?taskType ?taskStatus ?taskPriority
               ?createdAt ?dueTime
        WHERE {{
            ?task a so:WorkTask ;
                  so:taskId ?taskId ;
                  so:taskType ?taskType ;
                  so:taskStatus ?taskStatus .
            OPTIONAL {{ ?task so:taskPriority ?taskPriority }}
            OPTIONAL {{ ?task so:createdAt ?createdAt }}
            OPTIONAL {{ ?task so:dueTime ?dueTime }}
        }}
        LIMIT {limit}
        """
        return self.query(query)

    def query_exemption_rules(self, category_uri: Optional[str] = None) -> list:
        """
        查询豁免规则

        Args:
            category_uri: 可选，限定品类URI

        Returns:
            豁免规则列表，每条包含 exemption_type, exemption_reason, rule_source
        """
        if category_uri:
            query = f"""
            PREFIX so: <https://store-ontology.example.com/retail#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?exemptionType ?exemptionReason ?ruleSource ?ruleStatus
            WHERE {{
                ?rule a ?exemptionType .
                ?exemptionType rdfs:subClassOf so:ExemptionType .
                OPTIONAL {{ ?rule so:exemptionReason ?exemptionReason }}
                OPTIONAL {{ ?rule so:ruleSource ?ruleSource }}
                OPTIONAL {{ ?rule so:ruleStatus ?ruleStatus }}
                FILTER(STRSTARTS(STR(?exemptionType), "https://store-ontology.example.com/retail#Exemption"))
            }}
            """
        else:
            query = """
            PREFIX so: <https://store-ontology.example.com/retail#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?rule ?exemptionType ?exemptionReason ?ruleSource ?ruleStatus
            WHERE {
                ?rule a ?exemptionClass .
                ?exemptionClass rdfs:subClassOf so:ExemptionType .
                BIND(REPLACE(STR(?exemptionClass), "https://store-ontology.example.com/retail#", "") AS ?exemptionType)
                OPTIONAL { ?rule so:exemptionReason ?exemptionReason }
                OPTIONAL { ?rule so:ruleSource ?ruleSource }
                OPTIONAL { ?rule so:ruleStatus ?ruleStatus }
            }
            """
        return self.query(query)

    def check_product_exemption(
        self,
        product_id: str,
        category_uri: str,
        is_imported: bool = False,
        is_organic: bool = False,
        is_promoted: bool = False,
        arrival_days: Optional[int] = None,
    ) -> Optional[dict]:
        """
        检查商品是否有豁免资格

        Args:
            product_id: 商品ID
            category_uri: 商品品类URI
            is_imported: 是否进口
            is_organic: 是否有机
            is_promoted: 是否已参与促销
            arrival_days: 到货天数（可选）

        Returns:
            豁免信息dict或None（无豁免）
        """
        exemptions = self.query_exemption_rules(category_uri)

        exemption_map = {
            "Imported": ("imported", "进口商品不参与临期打折"),
            "Organic": ("organic", "有机绿色食品不参与临期打折"),
            "AlreadyPromoted": ("already_promoted", "已参与促销不叠加折扣"),
            "NewArrival": ("new_arrival", f"新上架商品(到货{arrival_days}天)不参与"),
            "HeadquartersBan": ("hq_ban", "总部禁止打折"),
            "StoreLocal": ("store_local", "门店本地豁免"),
        }

        for rule in exemptions:
            exemption_name = str(rule.exemptionType).split("#")[-1]
            if exemption_name in exemption_map:
                exempt_type, reason = exemption_map[exemption_name]
                # 新到货需要检查到达天数
                if exemption_name == "NewArrival" and arrival_days is not None:
                    if arrival_days <= 7:
                        return {
                            "exemption_type": exempt_type,
                            "exemption_reason": f"{reason}, 到达{arrival_days}天",
                            "rule_source": str(rule.ruleSource).split("#")[-1] if rule.ruleSource else "headquarters",
                        }
                else:
                    return {
                        "exemption_type": exempt_type,
                        "exemption_reason": reason,
                        "rule_source": str(rule.ruleSource).split("#")[-1] if rule.ruleSource else "headquarters",
                    }

        # 简化兜底逻辑：如果TTL没有返回，基于参数判断
        if is_imported:
            return {"exemption_type": "imported", "exemption_reason": "进口商品不参与临期打折", "rule_source": "headquarters"}
        if is_organic:
            return {"exemption_type": "organic", "exemption_reason": "有机绿色食品不参与临期打折", "rule_source": "headquarters"}
        if is_promoted:
            return {"exemption_type": "already_promoted", "exemption_reason": "已参与促销不叠加折扣", "rule_source": "headquarters"}
        if arrival_days is not None and arrival_days <= 7:
            return {"exemption_type": "new_arrival", "exemption_reason": f"新上架商品(到货{arrival_days}天)不参与", "rule_source": "headquarters"}

        return None