"""Task 工作流状态机（架构 spec §1.5）。迁移只能由 Action 触发。"""

TASK_TRANSITIONS = {
    "created":          ["pending_approval", "scrapped"],
    "pending_approval": ["approved", "rejected", "scrapped"],
    "approved":         ["accepted", "scrapped"],
    "accepted":         ["in_progress", "scrapped"],
    "in_progress":      ["completed", "scrapped"],
}

TERMINAL_STATES = {"completed", "rejected", "scrapped"}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    if from_status in TERMINAL_STATES:
        return False
    return to_status in TASK_TRANSITIONS.get(from_status, [])
