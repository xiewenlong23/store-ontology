"""equipment_repair vertical 的工作流状态机。

RepairTicket 状态机：reported → diagnosed → assigned → repairing → resolved
旁路：任何非终态 → cancelled
"""

REPAIR_TICKET_TRANSITIONS = {
    "reported":  ["diagnosed", "cancelled"],
    "diagnosed": ["assigned", "cancelled"],
    "assigned":  ["repairing", "cancelled"],
    "repairing": ["resolved", "cancelled"],
}

TERMINAL_STATES = {"resolved", "cancelled"}
