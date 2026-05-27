"""FastAPI 主入口 — 本体驱动 AI 门店助手

架构：
- 本体语义定义: ontology/store.ttl
- 本体解析器: ontology/parser.py → EntityRegistry
- 通用工具: ontology/tools.py (query_entity, create_entity, traverse_relation)
- Agent: Deep Agents (create_deep_agent) + LangGraphAgent (ag_ui_langgraph)
- 前端: CopilotKit v1.57.4 via AG-UI 协议
"""

import os
import warnings
import sys
from dotenv import load_dotenv

load_dotenv()

# 确保 ontology 模块可导入
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

# ===== 导入本体驱动通用工具 =====
from ontology.tools import (
    query_entity, create_entity, update_entity, traverse_relation,
    execute_action, confirm_action, query_task, update_task,
    query_near_expiry, build_ontology_prompt,
)

# ============ LLM 配置 ============

api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    raise RuntimeError("QWEN_API_KEY 环境变量未设置")

base_url = os.getenv("QWEN_BASE_URL", "https://api.minimaxi.com/v1")
model_name = os.getenv("QWEN_MODEL", "MiniMax-M2.7-highspeed")

llm = ChatOpenAI(
    model=model_name,
    api_key=api_key,
    base_url=base_url,
    temperature=0.7,
)


# ============ LLM 配置 ============
tools = [
    query_entity,
    create_entity,
    update_entity,
    traverse_relation,
    execute_action,
    confirm_action,
    query_task,
    update_task,
    query_near_expiry,
]


# ============ Deep Agent Graph ============

# 动态生成本体系统提示
ontology_prompt = build_ontology_prompt()
store_context = """
当前用户选择的门店ID是: store_001。

**操作流程（Preview → Confirm 模式）：**
1. 用户要求出清/调拨/补货时，先调用 execute_action 获取预览
2. 展示预览结果，询问用户确认
3. 用户回复"确认"/"好的"/"可以"后，调用 confirm_action 完成执行
4. 用中文回复。
"""

system_prompt = ontology_prompt + store_context

# Skill 源路径（FilesystemBackend 从磁盘加载）
skills_backend = FilesystemBackend(root_dir=os.path.join(os.path.dirname(__file__), "skills"), virtual_mode=True)

# 创建 Deep Agent Graph
# - SummarizationMiddleware 默认开启，自动压缩长对话上下文（解决 BadRequestError）
# - DeltaChannel 内置，checkpoint 增长从 O(N²) 降到 O(N)
# - SkillsMiddleware 从 backend/skills/ 加载 SKILL.md（Progressive Disclosure）
# - checkpointer=MemorySaver 保持多轮会话状态
deep_agent_graph = create_deep_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
    checkpointer=MemorySaver(),
    backend=skills_backend,
    skills=["/store-ontology/"],
    # 排除 Deep Agents 内置的通用工具（文件系统、shell、子agent），只保留业务工具
)


# ============ FastAPI 应用 ============

app = FastAPI(
    title="门店临期商品管理 - 本体驱动 Agent",
    description="基于 CopilotKit + 本体语义 + Deep Agents 的 AI 助手",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAgent(
        name="default",
        description="门店临期商品管理助手（本体驱动 + Deep Agents）",
        graph=deep_agent_graph,
    ),
    path="/api/copilotkit",
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8123"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
