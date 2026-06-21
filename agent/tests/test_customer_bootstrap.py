"""测试 bootstrap_customer 按客户构建隔离实例（P1）。"""
import pytest
from engine.workspace_bootstrap import bootstrap_workspace, get_workspace_agent_instance, reset_instances


@pytest.fixture(autouse=True)
def _clean():
    reset_instances()
    yield
    reset_instances()


def test_bootstrap_default_customer():
    """bootstrap 默认客户，得到一个 WorkspaceAgentInstance。"""
    inst = bootstrap_workspace("customer_default")
    assert inst is not None
    assert inst.workspace_name == "customer_default"
    assert inst.registry is not None
    assert inst.repository is not None


def test_instance_cached_per_customer():
    """同 customer 多次 bootstrap 返回缓存实例。"""
    inst1 = bootstrap_workspace("customer_default")
    inst2 = bootstrap_workspace("customer_default")
    assert inst1 is inst2


def test_two_customers_isolated():
    """两个客户的 registry/repository 实例不同，数据目录不同。"""
    import tempfile
    d1 = tempfile.mkdtemp()
    d2 = tempfile.mkdtemp()
    from engine.workspace import WorkspaceConfig, register_workspace, clear_workspaces
    clear_workspaces()
    register_workspace(WorkspaceConfig(workspace_name="ca", name="A", storage_type="json_files", data_dir=d1))
    register_workspace(WorkspaceConfig(workspace_name="cb", name="B", storage_type="json_files", data_dir=d2))
    reset_instances()

    ia = bootstrap_workspace("ca")
    ib = bootstrap_workspace("cb")
    assert ia is not ib
    assert ia.repository is not ib.repository
    assert str(ia.repository.data_dir) != str(ib.repository.data_dir)
    clear_workspaces()


def test_get_workspace_agent_instance():
    inst = bootstrap_workspace("customer_default")
    assert get_workspace_agent_instance("customer_default") is inst
    assert get_workspace_agent_instance("nonexistent") is None


def test_workspace_instance_has_executor():
    """bootstrap_workspace 返回的实例应已接通 executor（非 None，spec §5.3）。

    executor 的 config 取自该 workspace source_pack 的（第一个）价值链流程，
    用于状态机校验。
    """
    inst = bootstrap_workspace("customer_default")
    assert inst.executor is not None, "executor 应已接通，不再为 None"
    assert inst.executor.config is not None, "executor.config 应为价值链流程（非 None）"
