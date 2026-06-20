"""工作流状态机（架构 spec §1.5）。迁移只能由 Action 触发。

多 vertical 改造后：状态迁移表来自 VerticalConfig（per-vertical），不再全局硬编码。
clearance 的迁移表作为默认保留（向后兼容 + 作 VerticalConfig.state_transitions 的范例）。
"""

# clearance vertical 的状态迁移表（向后兼容 + VerticalConfig 范例）
TASK_TRANSITIONS = {
    "created":          ["pending_approval", "scrapped"],
    "pending_approval": ["approved", "rejected", "scrapped"],
    "approved":         ["accepted", "scrapped"],
    "accepted":         ["in_progress", "scrapped"],
    "in_progress":      ["completed", "scrapped"],
}

TERMINAL_STATES = {"completed", "rejected", "scrapped"}


def is_valid_transition(from_status: str, to_status: str,
                        transitions: dict = None, terminals: set = None) -> bool:
    """校验状态迁移是否合法。

    transitions/terminals 不传则用 clearance 默认表（向后兼容）。
    多 vertical 场景从 VerticalConfig 传入该 vertical 自己的表。
    """
    trans = transitions if transitions is not None else TASK_TRANSITIONS
    term = terminals if terminals is not None else TERMINAL_STATES
    if from_status in term:
        return False
    return to_status in trans.get(from_status, [])
