import pytest
from pydantic import ValidationError
from models.schemas import (
    Task, NearExpiryProduct, LossReport,
    TaskStatus, NearExpiryProductStatus, TaskType, LossReportStatus,
)


def test_task_uses_task_type_not_type():
    t = Task(id="t1", task_type=TaskType.CLEARANCE, target_id="ne_1",
             store_id="s1", assignee_id="e1")
    assert t.task_type == TaskType.CLEARANCE
    assert t.status == TaskStatus.CREATED
    assert "type" not in type(t).model_fields


def test_task_default_quantities_zero():
    t = Task(id="t1", task_type=TaskType.CLEARANCE, target_id="ne_1",
             store_id="s1", assignee_id="e1", discount_percent=30, planned_quantity=10)
    assert t.sold_quantity == 0


def test_discount_percent_range():
    with pytest.raises(ValidationError):
        Task(id="t1", task_type=TaskType.CLEARANCE, target_id="ne_1",
             store_id="s1", assignee_id="e1", discount_percent=150, planned_quantity=10)


def test_near_expiry_status_enum():
    ne = NearExpiryProduct(
        id="ne_1", product_id="p1", store_id="s1", batch_no="b1",
        production_date="2026-06-01", expiry_date="2026-06-10",
        stock_quantity=10, days_left=5, discount_tier="T2",
        status=NearExpiryProductStatus.EXPIRING)
    assert ne.status == NearExpiryProductStatus.EXPIRING


def test_loss_report_requires_task_link():
    lr = LossReport(id="lr_1", task_id="t1", target_id="ne_1",
                    loss_quantity=3, loss_value=13.5, loss_reason="过期")
    assert lr.status == LossReportStatus.PENDING
