from engine.discount_stub import set_discount_source
from workspace.retail.skills.clearance_workflow.discount import calculate_discount
import pytest


@pytest.fixture(autouse=True)
def _reset_source():
    set_discount_source(None)  # 每个测试前恢复磁盘源
    yield
    set_discount_source(None)  # 测试后也恢复，避免污染其它测试


def test_t1_is_50():
    set_discount_source([{"tier": "T1", "discount_percent": 50}])
    assert calculate_discount("T1") == 50


def test_t3_is_10():
    set_discount_source([
        {"tier": "T1", "discount_percent": 50},
        {"tier": "T2", "discount_percent": 30},
        {"tier": "T3", "discount_percent": 10},
    ])
    assert calculate_discount("T3") == 10


def test_unknown_tier_raises():
    set_discount_source([])
    import pytest
    with pytest.raises(KeyError):
        calculate_discount("T9")
