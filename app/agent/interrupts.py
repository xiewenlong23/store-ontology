# ============================================================
# interrupt_on 配置 — Phase 2.3
# 按角色粒度控制工具是否触发 HITL 中断
# 来自 TBOX 权限规则，不硬编码在 Skill 中
# ============================================================


def get_interrupt_config(role: str) -> dict:
    """
    根据角色返回 interrupt_on 配置

    规则：
    - 查询类工具：不需要审批，直接执行
    - 写入类工具（create_task / execute_discount）：店员需要店长审批
    - 店长：可审批本店折扣 ≤ 70%，> 70% 需总部审批
    - 总部：无限制

    返回格式：
        {
            "tool_name": False           # 不中断，直接执行
            "tool_name": {               # 中断，等待审批
                "allowed_decisions": [...],
                "max_rate": 0.70,       # 可选，金额/折扣率上限
            }
        }
    """
    base_config = {
        # ===== 查询类工具：不中断 =====
        "sparql_query": False,
        "query_expiring_products": False,
        "query_product_info": False,
        "query_discount_task": False,
        "query_pending_approvals": False,
        "query_tasks": False,
        "query_stock": False,
        "query_low_stock": False,
        "query_low_turnover_products": False,
        "query_high_demand_products": False,

        # ===== 任务创建：店员需审批，店长直接执行 =====
        "create_task": {
            "allowed_decisions": ["approve", "reject"],
        },

        # ===== 折扣执行 =====
        "execute_discount": {
            "allowed_decisions": ["approve", "edit", "reject"],
            "max_rate": 0.70,  # 店长最高批准 70% 折扣
        },
        "approve_discount": {
            "allowed_decisions": ["approve", "edit", "reject"],
        },
        "reject_discount": {
            "allowed_decisions": ["approve", "edit", "reject"],
        },
    }

    if role == "store_manager":
        # 店长：可以审批，execute_discount 不需要 HITL（直接执行）
        return {
            "execute_discount": False,  # 店长执行折扣不需要中断
            "approve_discount": False,  # 店长批准不需要中断
            **{k: v for k, v in base_config.items() if k not in ("execute_discount", "approve_discount")},
        }

    elif role == "headquarters":
        # 总部：无限制，折扣执行都不中断
        return {
            **{k: False for k in base_config},
            "execute_discount": False,
            "approve_discount": False,
            "reject_discount": False,
        }

    else:
        # 店员（clerk）：所有写入类工具都需要审批
        return base_config
