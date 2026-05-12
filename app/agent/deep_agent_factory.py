# ============================================================
# Deep Agent 工厂 — Phase 2.3
# create_deep_agent() — 基于 LangChain Deep Agents SDK
# ============================================================
from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from app.agent.state import AgentState
from app.agent.interrupts import get_interrupt_config
from app.agent.tools import get_all_tools
from app.config import settings
import structlog

logger = structlog.get_logger()

# 模型实例（复用）
_llm: BaseChatModel | None = None


def _get_llm() -> BaseChatModel:
    """延迟加载模型"""
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key or settings.dashscope_api_key,
            base_url=settings.openai_base_url or "https://api.deepseek.com",
            temperature=0.3,
        )
    return _llm


def create_store_brain_agent(
    user_id: str,
    store_id: str,
    role: str,
    employee_name: str = "",
    auth_token: str = "",
) -> create_deep_agent:
    """
    创建门店大脑 Deep Agent

    参数：
        user_id: 飞书 open_id
        store_id: 门店编号
        role: clerk / store_manager / headquarters
        employee_name: 员工姓名
        auth_token: 授权 token（可选）

    流程：
    1. 加载所有 Skill 的工具（按 role 过滤）
    2. 按 interrupt_on 配置工具中断策略
    3. 初始化 checkpointer（MemorySaver 本地会话）
    4. LangSmith tracing（已配置 API key 时启用）
    """
    logger.info(
        "create_store_brain_agent",
        user_id=user_id,
        store_id=store_id,
        role=role,
    )

    # 1. 加载工具（按角色过滤 allowed-tools）
    tools = get_all_tools(role=role, store_id=store_id)

    # 2. interrupt_on 配置
    interrupt_config = get_interrupt_config(role)

    # 3. LangSmith tracing（已配置 key 时启用）
    langsmith_config = {}
    if settings.langsmith_api_key:
        langsmith_config = {
            "langsmith_tracing": True,
            "langsmith_project": "store-ontology",
            "langsmith_api_key": settings.langsmith_api_key,
        }

    # 4. 创建 Deep Agent
    agent = create_deep_agent(
        model=_get_llm(),
        tools=list(tools.values()),
        interrupt_on=interrupt_config,
        checkpointer=MemorySaver(),
        state_schema=AgentState,
        **langsmith_config,
    )

    logger.info("deep_agent_created", role=role, num_tools=len(tools))
    return agent
