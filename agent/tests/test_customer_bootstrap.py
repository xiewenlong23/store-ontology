"""测试 bootstrap_customer 按客户构建隔离实例（P1）。"""
import pytest
from engine.customer_bootstrap import bootstrap_customer, get_customer_agent_instance, reset_instances


@pytest.fixture(autouse=True)
def _clean():
    reset_instances()
    yield
    reset_instances()


def test_bootstrap_default_customer():
    """bootstrap 默认客户，得到一个 CustomerAgentInstance。"""
    inst = bootstrap_customer("customer_default")
    assert inst is not None
    assert inst.customer_id == "customer_default"
    assert inst.registry is not None
    assert inst.repository is not None


def test_instance_cached_per_customer():
    """同 customer 多次 bootstrap 返回缓存实例。"""
    inst1 = bootstrap_customer("customer_default")
    inst2 = bootstrap_customer("customer_default")
    assert inst1 is inst2


def test_two_customers_isolated():
    """两个客户的 registry/repository 实例不同，数据目录不同。"""
    import tempfile
    d1 = tempfile.mkdtemp()
    d2 = tempfile.mkdtemp()
    from engine.customer import CustomerConfig, register_customer, clear_customers
    clear_customers()
    register_customer(CustomerConfig(customer_id="ca", name="A", storage_type="json_files", data_dir=d1))
    register_customer(CustomerConfig(customer_id="cb", name="B", storage_type="json_files", data_dir=d2))
    reset_instances()

    ia = bootstrap_customer("ca")
    ib = bootstrap_customer("cb")
    assert ia is not ib
    assert ia.repository is not ib.repository
    assert str(ia.repository.data_dir) != str(ib.repository.data_dir)
    clear_customers()


def test_get_customer_agent_instance():
    inst = bootstrap_customer("customer_default")
    assert get_customer_agent_instance("customer_default") is inst
    assert get_customer_agent_instance("nonexistent") is None
