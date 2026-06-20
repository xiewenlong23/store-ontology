import pytest
from ontology.state_machine import is_valid_transition, TASK_TRANSITIONS


def test_created_to_pending():
    assert is_valid_transition("created", "pending_approval") is True


def test_in_progress_to_completed():
    assert is_valid_transition("in_progress", "completed") is True


def test_invalid_skip():
    assert is_valid_transition("created", "in_progress") is False


def test_terminal_cannot_transition():
    assert is_valid_transition("completed", "scrapped") is False
    assert is_valid_transition("scrapped", "completed") is False


def test_all_in_progress_targets():
    assert set(TASK_TRANSITIONS["in_progress"]) == {"completed", "scrapped"}
