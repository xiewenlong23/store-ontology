"""系统原子 Tool 包（架构 spec §3.1）。

三类系统 Tool，与业务无关，对所有 workspace 通用：
- query_tools: 通用查询（query_entity, traverse_relation, query_task）
- crud_tools:  通用 CRUD（create_entity, update_entity, update_task）
- action_tools: Action 治理管道（execute_action, confirm_action）

业务 Tool 在各 workspace 的 skills/<scene>/tools.py 中，由 main.py 聚合加载。
本包 re-export 全部符号，使 `from agent.tools import X` 与 `import agent.tools as T; T._get_repo(...)`
都可用（替代旧的 engine.tools）。
"""
from agent.tools.shared import (
    _preview_cache, _parser, _get_repo, _get_executor,
    build_ontology_prompt, _wrap, _tc,
)
from agent.tools.query_tools import (
    query_entity, traverse_relation, query_task,
)
from agent.tools.crud_tools import (
    create_entity, update_entity, update_task,
)
from agent.tools.action_tools import (
    execute_action, confirm_action,
)

# clearance 专属工具在 workspace/retail/skills/clearance_workflow/tools.py，
# 由 main.py 的 _aggregate_pack_tools 聚合加载。引擎不再直接 import workspace 代码。
query_near_expiry = None  # 占位（向后兼容引用）

# 聚合所有系统 Tool（main.py 与测试可直接用 TOOLS）
TOOLS = [
    query_entity, traverse_relation, query_task,
    create_entity, update_entity, update_task,
    execute_action, confirm_action,
]

__all__ = [
    # 系统 Tool
    "query_entity", "traverse_relation", "query_task",
    "create_entity", "update_entity", "update_task",
    "execute_action", "confirm_action",
    "query_near_expiry", "TOOLS",
    # 共享 helper（业务 Tool 与测试依赖）
    "_preview_cache", "_parser", "_get_repo", "_get_executor",
    "build_ontology_prompt", "_wrap", "_tc",
]
