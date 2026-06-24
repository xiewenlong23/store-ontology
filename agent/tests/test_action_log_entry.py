"""ActionLogEntry dataclass 单测：构造、成功/失败更新、affected_objects 提取、
失败分类、敏感字段掩码（spec §3.3/§3.4/§7.1）。

从 agent/ 跑：.venv/bin/pytest tests/test_action_log_entry.py -v
"""
import pytest

from engine.action_log import (
    ActionLogEntry,
    classify_failure,
    mask_sensitive_params,
)
from engine.errors import EntityNotFoundError, OntologyError, ValidationError


# ============ ActionLogEntry 构造 + 更新 ============

def test_init_sets_basic_fields_and_user_actor():
    entry = ActionLogEntry.init(
        action_type="create_clearance_task",
        actor={"user_id": "u1", "role": "store_manager"},
        workspace_name="retail",
        trigger_source="llm_session",
    )
    assert entry.action_type == "create_clearance_task"
    assert entry.outcome == ""  # pending until update
    assert entry.actor_id == "u1"
    assert entry.actor_role == "store_manager"
    assert entry.actor_type == "user"
    assert entry.trigger_source == "llm_session"
    assert entry.workspace_name == "retail"
    assert entry.affected_objects == {}
    assert entry.failure_type is None


def test_init_actor_id_compatible_with_legacy_id_key():
    """executor 实际传的 actor 可能用 'id' 而非 'user_id'（test_executor.py 风格）。"""
    entry = ActionLogEntry.init(
        "a", {"id": "emp_001", "role": "store_manager"}, "ws", "llm_session")
    assert entry.actor_id == "emp_001"
    assert entry.actor_type == "user"


def test_init_agent_actor_has_agent_type():
    entry = ActionLogEntry.init(
        action_type="expiry_check",
        actor={"role": "system_scheduler"},  # 无 user_id → agent
        workspace_name="retail",
        trigger_source="automation",
    )
    assert entry.actor_type == "agent"
    assert entry.actor_id == "agent:automation"


def test_update_success_extracts_affected_pks():
    entry = ActionLogEntry.init("create_clearance_task",
                                {"user_id": "u1", "role": "store_manager"},
                                "retail", "llm_session")
    changes = {
        "created": {"Task": [{"id": "task_001"}]},
        "updated": {"NearExpiryProduct": [{"id": "nep_001"}, {"id": "nep_002"}]},
    }
    entry.update_success(changes)
    assert entry.outcome == "success"
    assert entry.failure_type is None
    assert entry.affected_objects == {
        "Task": ["task_001"],
        "NearExpiryProduct": ["nep_001", "nep_002"],
    }


def test_update_failure_sets_classification():
    entry = ActionLogEntry.init("approve_clearance",
                                {"user_id": "u1", "role": "clerk"},
                                "retail", "llm_session")
    entry.update_failure("permission_denied", "角色 clerk 无权提交")
    assert entry.outcome == "failure"
    assert entry.failure_type == "permission_denied"
    assert entry.error_message == "角色 clerk 无权提交"


# ============ classify_failure（spec §3.3，8 类对齐 executor raise 点）============

@pytest.mark.parametrize("exc,expected", [
    (EntityNotFoundError("未找到 X"), "entity_not_found"),
    (ValidationError("未知 Action Type: foo"), "unknown_action"),
    (ValidationError("角色 clerk 无权提交 approve_clearance"), "permission_denied"),
    (ValidationError("非法状态迁移: a -> b"), "illegal_transition"),
    (ValidationError("缺少必填参数: qty"), "invalid_param"),
    (ValidationError("参数 qty 不满足约束 0..100"), "invalid_param"),
    (ValidationError("submission 条件不满足"), "submission_failed"),
    (OntologyError("some other ontology error"), "side_effect_error"),
    (RuntimeError("boom"), "unclassified"),
])
def test_classify_failure(exc, expected):
    assert classify_failure(exc) == expected


# ============ mask_sensitive_params（spec §7.1）============

def test_mask_sensitive_params_redacts_known_fields():
    out = mask_sensitive_params({"username": "admin", "password": "s3cr3t",
                                  "token": "abc", "quantity": 5})
    assert out == {"username": "admin", "password": "***",
                   "token": "***", "quantity": 5}


def test_mask_sensitive_params_none_passthrough():
    assert mask_sensitive_params(None) is None
    assert mask_sensitive_params({}) == {}
