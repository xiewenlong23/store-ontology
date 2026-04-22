"""
inventory_service 单元测试
"""

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.inventory_service import (
    query_pending_clearance_skus,
    get_product_by_sku,
    check_product_exemption_from_json,
    PRODUCTS_FILE,
    _load_products,
)


class TestQueryPendingClearanceSkus:
    """query_pending_clearance_skus 测试"""

    def test_no_products(self, tmp_path, monkeypatch):
        """空商品列表返回空"""
        fake = tmp_path / "products.json"
        fake.write_text("[]")
        monkeypatch.setattr("app.services.inventory_service.PRODUCTS_FILE", fake)
        # 强制重新加载
        import app.services.inventory_service as inv
        inv._cached_products = None
        inv.PRODUCTS_FILE = fake
        result = inv.query_pending_clearance_skus(days_threshold=2)
        assert result == []

    def test_expired_product_filtered(self, tmp_path, monkeypatch):
        """已过期（days_left < 0）不返回"""
        fake = tmp_path / "products.json"
        fake.write_text(json.dumps([{
            "product_id": "P999",
            "name": "过期测试",
            "category": "fresh",
            "store_id": "STORE-001",
            "production_date": "2026-03-01",
            "expiry_date": "2026-03-15",
            "stock": 10,
            "price": 5.0,
            "original_price": 10.0,
            "is_imported": False,
            "is_organic": False,
            "is_promoted": False,
            "arrival_days": 30,
            "in_reduction": False,
        }]))
        import app.services.inventory_service as inv
        inv._cached_products = None
        inv.PRODUCTS_FILE = fake
        result = inv.query_pending_clearance_skus(days_threshold=2)
        assert len(result) == 0

    def test_in_reduction_filtered(self, tmp_path, monkeypatch):
        """已在折扣中的商品不返回"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        fake = tmp_path / "products.json"
        fake.write_text(json.dumps([{
            "product_id": "P888",
            "name": "折扣中商品",
            "category": "fresh",
            "store_id": "STORE-001",
            "production_date": "2026-04-19",
            "expiry_date": tomorrow,
            "stock": 20,
            "price": 5.0,
            "original_price": 10.0,
            "is_imported": False,
            "is_organic": False,
            "is_promoted": False,
            "arrival_days": 30,
            "in_reduction": True,
        }]))
        import app.services.inventory_service as inv
        inv._cached_products = None
        inv.PRODUCTS_FILE = fake
        result = inv.query_pending_clearance_skus(days_threshold=2)
        assert len(result) == 0

    def test_within_threshold_returned(self, tmp_path, monkeypatch):
        """剩余天数在阈值内且未在折扣中则返回"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        fake = tmp_path / "products.json"
        fake.write_text(json.dumps([{
            "product_id": "P777",
            "name": "临期测试",
            "category": "dairy",
            "store_id": "STORE-001",
            "production_date": "2026-04-19",
            "expiry_date": tomorrow,
            "stock": 50,
            "price": 8.0,
            "original_price": 15.0,
            "is_imported": False,
            "is_organic": False,
            "is_promoted": False,
            "arrival_days": 10,
            "in_reduction": False,
        }]))
        import app.services.inventory_service as inv
        inv._cached_products = None
        inv.PRODUCTS_FILE = fake
        result = inv.query_pending_clearance_skus(days_threshold=2)
        assert len(result) == 1
        assert result[0]["sku"] == "P777"
        assert result[0]["days_left"] == 1
        assert result[0]["category"] == "dairy"


class TestGetProductBySku:
    """get_product_by_sku 测试"""

    def test_found(self, tmp_path, monkeypatch):
        """能根据 SKU 查到商品"""
        fake = tmp_path / "products.json"
        fake.write_text(json.dumps([
            {"product_id": "P001", "name": "香蕉", "category": "fresh"},
            {"product_id": "P002", "name": "苹果", "category": "fresh"},
        ]))
        import app.services.inventory_service as inv
        inv._cached_products = None
        inv.PRODUCTS_FILE = fake
        p = inv.get_product_by_sku("P002")
        assert p is not None
        assert p["name"] == "苹果"

    def test_not_found(self, tmp_path, monkeypatch):
        """不存在的 SKU 返回 None"""
        fake = tmp_path / "products.json"
        fake.write_text(json.dumps([{"product_id": "P001", "name": "香蕉"}]))
        import app.services.inventory_service as inv
        inv._cached_products = None
        inv.PRODUCTS_FILE = fake
        p = inv.get_product_by_sku("P999")
        assert p is None


class TestCheckProductExemptionFromJson:
    """check_product_exemption_from_json 测试"""

    def test_imported(self):
        """进口商品返回 imported 豁免"""
        product = {"is_imported": True, "is_organic": False, "is_promoted": False, "arrival_days": 30}
        result = check_product_exemption_from_json(product)
        assert result is not None
        assert result["exemption_type"] == "imported"

    def test_organic(self):
        """有机商品返回 organic 豁免"""
        product = {"is_imported": False, "is_organic": True, "is_promoted": False, "arrival_days": 30}
        result = check_product_exemption_from_json(product)
        assert result is not None
        assert result["exemption_type"] == "organic"

    def test_promoted(self):
        """已促销商品返回 already_promoted 豁免"""
        product = {"is_imported": False, "is_organic": False, "is_promoted": True, "arrival_days": 30}
        result = check_product_exemption_from_json(product)
        assert result is not None
        assert result["exemption_type"] == "already_promoted"

    def test_new_arrival(self):
        """到货 ≤7 天返回 new_arrival 豁免"""
        product = {"is_imported": False, "is_organic": False, "is_promoted": False, "arrival_days": 5}
        result = check_product_exemption_from_json(product)
        assert result is not None
        assert result["exemption_type"] == "new_arrival"

    def test_no_exemption(self):
        """无任何豁免条件返回 None"""
        product = {"is_imported": False, "is_organic": False, "is_promoted": False, "arrival_days": 30}
        result = check_product_exemption_from_json(product)
        assert result is None