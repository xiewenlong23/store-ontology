"""测试工具层按 customer/org_unit 过滤（P1）。"""
from ontology.tools import query_entity
from ontology import tools as T


def _setup(monkeypatch, data_dir):
    from ontology.parser import OntologyParser
    from ontology.action_loader import load_actions
    from ontology.repository import JSONFileRepository
    from ontology.executor import ActionExecutor
    from ontology.bootstrap import bootstrap
    from verticals.clearance.config import CLEARANCE_CONFIG
    bootstrap()
    p = OntologyParser(ttl_path=CLEARANCE_CONFIG.ttl_path, data_dir=data_dir,
                       config=CLEARANCE_CONFIG)
    p.registry.action_types = load_actions(CLEARANCE_CONFIG.actions_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=p.registry)
    ex = ActionExecutor(repository=repo, actions=p.registry.action_types,
                        registry=p.registry, config=CLEARANCE_CONFIG)
    monkeypatch.setattr(T, "_parser", lambda vertical=None: p)
    monkeypatch.setattr(T, "_get_repo", lambda tenant=None, vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)


def test_query_entity_accepts_customer_and_org_unit(clearance_data_dir, monkeypatch):
    """工具接受 customer_id + org_unit_id，按客户过滤。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({
        "entity_type": "Store",
        "customer_id": "customer_default",
        "org_unit_id": "*",
    })
    assert "store_001" in out


def test_query_entity_defaults_to_customer_default(clearance_data_dir, monkeypatch):
    """不传 customer_id 时默认 customer_default。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({"entity_type": "Store"})
    assert "store_001" in out  # 旧数据（无 customer_id）兼容可见


def test_query_entity_isolates_by_customer(clearance_data_dir, monkeypatch):
    """不同 customer_id 看不到彼此数据。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({
        "entity_type": "Store",
        "customer_id": "customer_other",
    })
    assert "store_001" not in out  # 属于 customer_default，不属于 customer_other
