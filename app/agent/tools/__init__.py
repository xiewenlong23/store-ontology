# ============================================================
# 工具注册表 — Phase 2.3
# 按角色动态注册 allowed-tools（来自 config/skills.yaml）
# ============================================================
from typing import Callable, Any
from app.skills import get_allowed_tools, get_skill_roles


def _build_tool_list(skill_name: str, role: str) -> list[Callable]:
    """
    根据 Skill 名称和角色返回允许的工具列表

    逻辑：
    1. 从 config/skills.yaml 读取该 Skill 的 allowed-tools
    2. 检查 role 是否在 Skill 的 roles 列表中
    3. 返回对应工具函数
    """
    allowed_tool_names = get_allowed_tools(skill_name)
    allowed_roles = get_skill_roles(skill_name)

    # 角色检查
    if role not in allowed_roles and role != "headquarters":
        return []

    # 动态导入工具函数
    tools = []
    for tool_name in allowed_tool_names:
        func = _TOOL_REGISTRY.get(tool_name)
        if func:
            tools.append(func)

    return tools


def get_tools(skill_name: str, role: str, store_id: str = "") -> list[Callable]:
    """
    获取指定 Skill 的工具列表

    Args:
        skill_name: Skill 名称（如 "discount-skill"）
        role: 当前用户角色（clerk / store_manager / headquarters）
        store_id: 门店编号（注入到工具闭包）

    Returns:
        允许调用的工具函数列表
    """
    return _build_tool_list(skill_name, role)


def get_all_tools(role: str, store_id: str = "") -> dict[str, Any]:
    """
    获取所有 Skill 的全部可用工具（Python 函数 + MCP 工具）
    用于 Deep Agents 初始化时注册工具集
    """
    all_tools: dict[str, Any] = {}
    for skill_name in _SKILL_REGISTRY:
        # Python 函数工具
        tools = get_tools(skill_name, role, store_id)
        for tool in tools:
            all_tools[tool.__name__] = tool
        # MCP 工具（来自 langchain-mcp-adapters，BaseTool 实例）
        try:
            mcp_tools = get_mcp_tools_for_skill(skill_name)
            for t in mcp_tools:
                all_tools[t.name] = t
        except Exception:
            pass  # MCP 未初始化时跳过
    return all_tools


def get_mcp_tools_for_skill(skill_name: str) -> list[Any]:
    """
    获取指定 Skill 对应的 MCP 工具（来自 config/skills.yaml allowed-tools）
    同步调用：MCP 工具在 init_mcp_clients() 时已初始化到全局变量
    """
    # 动态导入避免循环依赖
    from app.agent.tools import mcp_tools as _mcp_module
    allowed_names = get_allowed_tools(skill_name)
    all_mcp = _mcp_module.get_mcp_tools()
    return [t for t in all_mcp if t.name in allowed_names]


# ============================================================
# 工具注册（实际工具函数在各自模块中定义）
# 此处只做名称→函数的映射，供 registry 动态查找
# ============================================================
from app.agent.tools import sparql_tools, discount_tools

_TOOL_REGISTRY: dict[str, Callable] = {
    # SPARQL 工具
    "sparql_query": sparql_tools.sparql_query,
    "query_expiring_products": sparql_tools.query_expiring_products,
    "query_product_info": sparql_tools.query_product_info,

    # 折扣工具
    "calculate_discount_tier": discount_tools.calculate_discount_tier,
    "create_discount_task": discount_tools.create_discount_task,
    "approve_discount": discount_tools.approve_discount,
    "reject_discount": discount_tools.reject_discount,
    "query_discount_task": discount_tools.query_discount_task,
    "query_pending_approvals": discount_tools.query_pending_approvals,
}

_SKILL_REGISTRY = ["discount-skill", "task-skill", "product-skill", "inventory-skill", "display-skill"]
