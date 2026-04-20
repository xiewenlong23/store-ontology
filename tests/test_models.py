from app.models import ReductionTask, Product, TaskStatus, ProductCategory
from datetime import date, datetime

def test_reduction_task_fields():
    task = ReductionTask(
        task_id="T001",
        store_id="S001",
        product_id="P001",
        product_name="嫩豆腐",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=date(2026, 4, 21),
        original_stock=50,
        created_by="store_manager"
    )
    assert task.task_id == "T001"
    assert task.status == TaskStatus.PENDING
    assert task.discount_rate is None

def test_product_category_enum():
    assert ProductCategory.DAILY_FRESH.value == "daily_fresh"
    assert ProductCategory.BAKERY.value == "bakery"
