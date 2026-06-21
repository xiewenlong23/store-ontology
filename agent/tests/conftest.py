import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

import pytest

# 以 backend/ 为 sys.path 根，使 from engine... / from models... 可用
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def tmp_data_dir(tmp_path):
    """提供一个空数据目录 + 基础 stores.json，供 Repository 测试用。"""
    stores = [{
        "id": "store_001", "name": "测试门店", "region_id": "region_001",
        "address": "测试地址", "manager_id": "emp_001",
        "created_at": "2024-01-01T00:00:00",
    }]
    (tmp_path / "stores.json").write_text(json.dumps(stores, ensure_ascii=False), encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def clearance_data_dir(tmp_path):
    """完整出清场景种子数据：1 门店/员工/商品/临期商品。"""
    (tmp_path / "stores.json").write_text(json.dumps([{
        "id": "store_001", "name": "测试门店", "region_id": "region_001",
        "address": "x", "manager_id": "emp_001",
        "created_at": "2024-01-01T00:00:00"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "employees.json").write_text(json.dumps([{
        "id": "emp_001", "name": "张店长", "store_id": "store_001",
        "role": "manager", "phone": "1"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "products.json").write_text(json.dumps([{
        "id": "prod_001", "name": "酸奶", "category": "乳", "brand": "蒙牛",
        "unit": "盒", "cost_price": 4.5, "retail_price": 6.0}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "near_expiry_products.json").write_text(json.dumps([{
        "id": "ne_001", "product_id": "prod_001", "store_id": "store_001",
        "batch_no": "B1", "production_date": "2026-06-01", "expiry_date": "2026-06-10",
        "stock_quantity": 50, "days_left": 5, "discount_tier": "T2",
        "status": "expiring"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "tasks.json").write_text("[]", encoding="utf-8")
    (tmp_path / "loss_reports.json").write_text("[]", encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def automation_data_dir(tmp_path):
    """自动化测试种子：含 in_progress Task（关联过期 NEP）+ 各状态 NEP，供 job 测试。

    场景：
    - nep_exp：已过期（days_left=-1，status=clearance）—— expiry_check 应报损
    - nep_sold：售罄待完成（Task sold>=planned）—— inventory_check 应完成
    - task_exp：in_progress，关联 nep_exp，planned=10 sold=3（报损 loss_quantity=7）
    - task_sold：in_progress，关联 nep_sold，planned=5 sold=5（应完成）
    """
    import json as _json
    data = {
        "stores.json": [{"id": "store_001", "name": "测试门店", "region_id": "r",
                         "address": "x", "manager_id": "emp_001",
                         "created_at": "2024-01-01T00:00:00"}],
        "employees.json": [{"id": "emp_001", "name": "张店长", "store_id": "store_001",
                            "role": "manager", "phone": "1"}],
        "products.json": [{"id": "prod_001", "name": "酸奶", "category": "乳", "brand": "蒙牛",
                           "unit": "盒", "cost_price": 4.5, "retail_price": 6.0}],
        "near_expiry_products.json": [
            {"id": "nep_exp", "product_id": "prod_001", "store_id": "store_001",
             "batch_no": "B1", "production_date": "2026-05-01", "expiry_date": "2026-06-19",
             "stock_quantity": 7, "days_left": -1, "discount_tier": "T1",
             "status": "clearance"},
            {"id": "nep_sold", "product_id": "prod_001", "store_id": "store_001",
             "batch_no": "B2", "production_date": "2026-06-01", "expiry_date": "2026-06-25",
             "stock_quantity": 0, "days_left": 5, "discount_tier": "T2",
             "status": "clearance"},
        ],
        "tasks.json": [
            {"id": "task_exp", "task_type": "clearance", "target_id": "nep_exp",
             "store_id": "store_001", "assignee_id": "emp_001", "status": "in_progress",
             "discount_percent": 50, "planned_quantity": 10, "sold_quantity": 3,
             "params_json": {}, "result_json": {}, "priority": "high", "notes": "到期报损测",
             "created_at": "2026-06-15T09:00:00", "started_at": "2026-06-15T14:00:00",
             "completed_at": None},
            {"id": "task_sold", "task_type": "clearance", "target_id": "nep_sold",
             "store_id": "store_001", "assignee_id": "emp_001", "status": "in_progress",
             "discount_percent": 30, "planned_quantity": 5, "sold_quantity": 5,
             "params_json": {}, "result_json": {}, "priority": "medium", "notes": "售罄完成测",
             "created_at": "2026-06-15T09:00:00", "started_at": "2026-06-15T14:00:00",
             "completed_at": None},
        ],
        "loss_reports.json": [],
        "regions.json": [],
    }
    for fn, rows in data.items():
        (tmp_path / fn).write_text(_json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def repair_data_dir(tmp_path):
    """设备维修 vertical 种子数据副本（隔离，不污染真实 data/customerA/）。"""
    import shutil
    src = Path(__file__).resolve().parent.parent.parent / "workspace" / "customerA" / "data"
    if src.is_dir():
        shutil.copytree(src, tmp_path, dirs_exist_ok=True)
    else:
        for f in ["equipments.json", "repair_tickets.json", "technicians.json", "vendors.json"]:
            (tmp_path / f).write_text("[]", encoding="utf-8")
    return str(tmp_path)
