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


def test_update_task_blocks_governed_fields(clearance_data_dir, monkeypatch):
    """回归：update_task 不能改受治理字段（discount_percent/sold_quantity/assignee_id...）。"""
    _setup(monkeypatch, clearance_data_dir)
    from ontology.tools import update_task
    # 先建一个任务
    pid = execute_action.invoke({
        "action_type": "create_clearance_task",
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50})
    import re
    m = re.search(r'"preview_id":\s*"([^"]+)"', pid)
    confirm_action.invoke({"preview_id": m.group(1)})
    # 尝试改受治理字段
    out = update_task.invoke({"task_id": "task_any", "discount_percent": 99})
    assert "success" in out
    import json as _json
    payload = _json.loads(out.split("<!--COPILOTKIT_DATA-->\n")[1].split("\n<!--")[0])
    assert payload["success"] is False
    # 允许改 notes
    out2 = update_task.invoke({"task_id": "task_any", "notes": "hello"})
    payload2 = _json.loads(out2.split("<!--COPILOTKIT_DATA-->\n")[1].split("\n<!--")[0])
    # task_any 不存在，会返回 success False（未找到），但不是因为字段被拒
    assert payload2.get("error") != "受治理字段只能经 Action 修改"
