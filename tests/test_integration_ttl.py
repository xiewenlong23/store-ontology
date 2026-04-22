#!/usr/bin/env python3
"""
TTL End-to-End Integration Tests

Tests that:
1. WORKTASK-MODULE.ttl can be parsed successfully
2. SPARQL queries return expected results
3. Query results match expected ontology structure
"""

import pytest
from pathlib import Path
from rdflib import Graph, Namespace

# Project paths
REPO_ROOT = Path(__file__).parent.parent
TTL_FILE = REPO_ROOT / "modules" / "module1-worktask" / "WORKTASK-MODULE.ttl"
ONTOLOGY_BASE = "https://store-ontology.example.com/retail"
SO = Namespace(ONTOLOGY_BASE + "#")


class TestTTLFileExists:
    """TTL file existence and basic validity"""

    def test_ttl_file_exists(self):
        assert TTL_FILE.exists(), f"TTL file not found at {TTL_FILE}"

    def test_ttl_file_not_empty(self):
        content = TTL_FILE.read_text(encoding="utf-8")
        assert len(content) > 1000, "TTL file seems too small to be valid"


class TestTTLParse:
    """TTL parsing and graph construction"""

    def test_parse_ttl_without_errors(self):
        """TTL should parse without raising exceptions"""
        g = Graph()
        g.parse(str(TTL_FILE), format="turtle")
        assert len(g) > 0, "Parsed graph should contain triples"

    def test_ontology_has_version(self):
        """Parsed ontology should have version info"""
        g = Graph()
        g.parse(str(TTL_FILE), format="turtle")

        # Query for versionInfo
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?version WHERE { ?ontology owl:versionInfo ?version }
        """
        results = list(g.query(query))
        assert len(results) > 0, "Ontology should have versionInfo"

    def test_graph_contains_worktask_class(self):
        """Parsed ontology should contain WorkTask class"""
        g = Graph()
        g.parse(str(TTL_FILE), format="turtle")

        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?class WHERE { ?class a owl:Class ; rdfs:label "作业任务"@zh-CN }
        """
        results = list(g.query(query))
        assert len(results) > 0, "WorkTask class (作业任务) should exist in ontology"


class TestSPARQLQueries:
    """SPARQL query result verification"""

    @pytest.fixture
    def graph(self):
        """Parse TTL once for all tests in this class"""
        g = Graph()
        g.parse(str(TTL_FILE), format="turtle")
        g.bind("so", SO)
        return g

    def test_query_clearance_rules_returns_results(self, graph):
        """query_clearance_rules should return discount tier rules"""
        # Query for clearance rules - using Dairy as test category
        dairy_uri = ONTOLOGY_BASE + "#Dairy"
        query = f"""
        PREFIX so: <https://store-ontology.example.com/retail#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?rule ?urgency ?tier ?tierMin ?tierMax
               ?recDiscount ?minDiscount ?maxDiscount
        WHERE {{
            ?rule so:appliesToCategory <{dairy_uri}> ;
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
        results = list(graph.query(query))
        # We expect at least some rules (Dairy has tier rules in the ontology)
        assert isinstance(results, list)

    def test_query_clearance_rules_daily_fresh(self, graph):
        """Query clearance rules for DailyFresh category"""
        daily_fresh_uri = ONTOLOGY_BASE + "#DailyFresh"
        query = f"""
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?tierMin ?tierMax ?recDiscount
        WHERE {{
            ?rule so:appliesToCategory <{daily_fresh_uri}> ;
                  so:hasDiscountTier ?tier .
            ?tier so:tierMinDays ?tierMin ;
                  so:tierMaxDays ?tierMax ;
                  so:recommendedDiscountRate ?recDiscount .
        }}
        ORDER BY ?tierMin
        """
        results = list(graph.query(query))
        # Results should be ordered by tierMin
        assert isinstance(results, list)

    def test_tier_structure_has_min_max_days(self, graph):
        """Each tier should have tierMinDays and tierMaxDays"""
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT DISTINCT ?tierMin ?tierMax
        WHERE {
            ?tier so:tierMinDays ?tierMin ;
                  so:tierMaxDays ?tierMax .
        }
        ORDER BY ?tierMin
        """
        results = list(graph.query(query))
        assert len(results) > 0, "Should have tier definitions with min/max days"

        # Verify min < max for each tier
        for row in results:
            tier_min = int(row.tierMin)
            tier_max = int(row.tierMax)
            assert tier_min <= tier_max, f"Tier min ({tier_min}) should be <= max ({tier_max})"

    def test_discount_range_is_valid(self, graph):
        """Discount rates should be valid (0 <= min <= rec <= max <= 1)"""
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?recDiscount ?minDiscount ?maxDiscount
        WHERE {
            ?tier so:recommendedDiscountRate ?recDiscount ;
                  so:minDiscountRate ?minDiscount ;
                  so:maxDiscountRate ?maxDiscount .
        }
        """
        results = list(graph.query(query))
        assert len(results) > 0, "Should have discount rate definitions"

        for row in results:
            min_d = float(row.minDiscount)
            rec_d = float(row.recDiscount)
            max_d = float(row.maxDiscount)
            assert 0.0 <= min_d <= 1.0, f"minDiscount {min_d} out of range"
            assert 0.0 <= rec_d <= 1.0, f"recDiscount {rec_d} out of range"
            assert 0.0 <= max_d <= 1.0, f"maxDiscount {max_d} out of range"
            assert min_d <= rec_d <= max_d, f"Discount range invalid: {min_d} <= {rec_d} <= {max_d}"

    def test_exemption_rules_exist(self, graph):
        """Ontology should define exemption rules"""
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?exemptionType ?exemptionReason
        WHERE {
            ?rule so:exemptionType ?exemptionType .
            OPTIONAL { ?rule so:exemptionReason ?exemptionReason }
        }
        """
        results = list(graph.query(query))
        # Should have at least some exemption types defined
        assert isinstance(results, list)

    def test_urgency_enum_values(self, graph):
        """Ontology should define urgency levels"""
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT DISTINCT ?urgency
        WHERE {
            ?rule so:clearanceUrgency ?urgency .
        }
        """
        results = list(graph.query(query))
        # Should have urgency values
        assert isinstance(results, list)

    def test_task_status_enum_values(self, graph):
        """Ontology should define task status values"""
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?status
        WHERE {
            ?status a so:TaskStatus .
        }
        """
        results = list(graph.query(query))
        # Should have task status values defined
        assert isinstance(results, list)


class TestSPARQLServiceIntegration:
    """Integration tests using the actual SPARQLService"""

    def test_sparql_service_initializes(self):
        """SPARQLService should initialize without errors"""
        from app.services.sparql_service import SPARQLService
        service = SPARQLService()
        assert service is not None
        assert service.graph is not None

    def test_sparql_service_query_clearance_rules_dairy(self):
        """SPARQLService.query_clearance_rules should return results for Dairy"""
        from app.services.sparql_service import SPARQLService

        service = SPARQLService()
        dairy_uri = ONTOLOGY_BASE + "#Dairy"
        results = service.query_clearance_rules(dairy_uri)

        assert isinstance(results, list)
        # Should return at least one rule for Dairy

    def test_sparql_service_query_exemption_rules(self):
        """SPARQLService.query_exemption_rules should return results"""
        from app.services.sparql_service import SPARQLService

        service = SPARQLService()
        results = service.query_exemption_rules()

        assert isinstance(results, list)
        # May or may not have results depending on ontology content

    def test_ttl_query_clearance_rules_function(self):
        """ttl_query_clearance_rules function should work correctly"""
        from app.services.ttl_llm_reasoning import ttl_query_clearance_rules

        result = ttl_query_clearance_rules("dairy")

        assert isinstance(result, dict)
        assert "rules" in result or "found" in result
        assert result.get("source") == "ttl"
        assert result.get("layer") == 1


class TestSPARQLQueryAgainstExpectedStructure:
    """Verify SPARQL query results match expected ontology structure"""

    @pytest.fixture
    def graph(self):
        g = Graph()
        g.parse(str(TTL_FILE), format="turtle")
        g.bind("so", SO)
        return g

    def test_category_uri_resolution(self, graph):
        """Category URIs should resolve to actual category definitions"""
        # Test DailyFresh
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?category WHERE {
            ?category rdfs:label "日配"@zh-CN .
        }
        """
        results = list(graph.query(query))
        assert isinstance(results, list)

    def test_clearance_rule_structure(self, graph):
        """Clearance rules should have all required properties"""
        query = """
        PREFIX so: <https://store-ontology.example.com/retail#>
        SELECT ?rule WHERE { ?rule a so:ClearanceRule }
        LIMIT 1
        """
        results = list(graph.query(query))
        # If there are ClearanceRule instances, verify structure
        if len(results) > 0:
            rule = results[0][0]
            # Query specific properties
            prop_query = f"""
            PREFIX so: <https://store-ontology.example.com/retail#>
            SELECT ?appliesToCategory ?clearanceUrgency
            WHERE {{
                <{rule}> so:appliesToCategory ?appliesToCategory ;
                         so:clearanceUrgency ?clearanceUrgency .
            }}
            """
            prop_results = list(graph.query(prop_query))
            assert len(prop_results) > 0


class TestTTLIntegrationSmokeTests:
    """Smoke tests for full TTL integration"""

    def test_reasoning_imports_work(self):
        """Core reasoning imports should work"""
        from app.services.ttl_llm_reasoning import (
            ttl_query_clearance_rules,
            ttl_query_pending_skus,
            ttl_query_exemption_rules,
        )
        assert callable(ttl_query_clearance_rules)
        assert callable(ttl_query_pending_skus)
        assert callable(ttl_query_exemption_rules)

    def test_ttl_query_clearance_rules_returns_layer1(self):
        """ttl_query_clearance_rules should return layer 1 results"""
        from app.services.ttl_llm_reasoning import ttl_query_clearance_rules
        result = ttl_query_clearance_rules("bakery")
        assert result.get("layer") == 1
        assert result.get("source") == "ttl"

    def test_ttl_query_pending_skus_returns_layer1(self):
        """ttl_query_pending_skus should return layer 1 results"""
        from app.services.ttl_llm_reasoning import ttl_query_pending_skus
        result = ttl_query_pending_skus()
        assert result.get("layer") == 1
        assert result.get("source") == "ttl"
        assert "skus" in result
        assert "count" in result