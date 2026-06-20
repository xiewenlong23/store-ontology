from ontology.tools import query_entity, confirm_action, execute_action
from ontology import tools as T


def _setup(monkeypatch, data_dir):
    """把 tools 的 parser/repository/executor 指向临时数据目录。"""
    from ontology.parser import OntologyParser
    from ontology.action_loader import load_actions
    from ontology.repository import JSONFileRepository
    from ontology.executor import ActionExecutor
    parser = OntologyParser(ttl_path="ontology/store.ttl", data_dir=data_dir)
    parser.registry.action_types = load_actions("ontology/actions")
    repo = JSONFileRepository(data_dir=data_dir, registry=parser.registry)
    ex = ActionExecutor(repository=repo, actions=parser.registry.action_types,
                        registry=parser.registry)
    monkeypatch.setattr(T, "_get_repo", lambda tenant="tenant_default": repo)
    monkeypatch.setattr(T, "_get_executor", lambda: ex)


def test_query_entity_reads_store(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({"entity_type": "Store"})
    assert "store_001" in out


def test_execute_action_returns_preview_id(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = execute_action.invoke({
        "action_type": "create_clearance_task",
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50})
    assert "preview_id" in out


def test_confirm_requires_preview(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = confirm_action.invoke({"preview_id": "bogus"})
    assert "preview" in out.lower() or "失败" in out or "无效" in out
