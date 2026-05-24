"""
验证脚本：Deep Agent Graph + ag_ui_langgraph 集成可行性

验证点：
1. create_deep_agent() 返回 CompiledStateGraph，可传给 LangGraphAgent
2. Deep Agents 内置工具可被 excluded_tools 排除
3. streaming 输出格式与 LangGraphAgent 兼容
4. 状态 schema 与 constant_schema_keys=['messages', 'tools'] 兼容
"""

import sys
import os

# 确保 backend 模块可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# ========== 验证 1: 类型兼容 ==========
print("=" * 60)
print("验证 1: 类型兼容 — create_deep_agent 返回 CompiledStateGraph")
print("=" * 60)

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
import inspect

api_key = os.getenv("QWEN_API_KEY")
base_url = os.getenv("QWEN_BASE_URL", "https://api.minimaxi.com/v1")
model = os.getenv("QWEN_MODEL", "MiniMax-M2.7-highspeed")

llm = ChatOpenAI(
    model=model,
    api_key=api_key,
    base_url=base_url,
    temperature=0.7,
)

# 创建 deep agent（暂不过滤工具，验证集成本身）
graph = create_deep_agent(
    model=llm,
    system_prompt="你是一个简单的助手。",
)

# 检查返回类型
print(f"返回类型: {type(graph)}")
# LangGraphAgent.graph 接受 CompiledStateGraph，检查类名
print(f"Graph 类型: {type(graph).__class__.__name__}")
print(f"Graph 模块: {type(graph).__module__}")

# 检查 graph 的 nodes
print(f"\nGraph nodes: {list(graph.nodes.keys())}")

# 检查 state schema
print(f"\nState channels: {list(graph.channels.keys())}")

# ========== 验证 2: 包装成 LangGraphAgent ==========
print("\n" + "=" * 60)
print("验证 2: LangGraphAgent 包装")
print("=" * 60)

from ag_ui_langgraph import LangGraphAgent

agent = LangGraphAgent(
    name="test-deep-agent",
    graph=graph,
    description="测试 Deep Agent 集成",
)

print(f"LangGraphAgent.name: {agent.name}")
print(f"LangGraphAgent.graph: {type(agent.graph)}")
print(f"LangGraphAgent.constant_schema_keys: {agent.constant_schema_keys}")

# ========== 验证 3: 挂载到 FastAPI ==========
print("\n" + "=" * 60)
print("验证 3: FastAPI 挂载")
print("=" * 60)

from fastapi import FastAPI
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

app = FastAPI(title="Deep Agent + AG-UI 验证")

add_langgraph_fastapi_endpoint(app, agent, "/agent")

# 检查路由
print("注册路由:")
for route in app.routes:
    if hasattr(route, "path") and hasattr(route, "methods"):
        print(f"  {route.methods} {route.path}")

# ========== 验证 4: 尝试单轮对话 ==========
print("\n" + "=" * 60)
print("验证 4: 单轮对话测试（不启动 server）")
print("=" * 60)

import asyncio
from langgraph.checkpoint.memory import MemorySaver

# 用 MemorySaver 做 checkpointer
checkpointer = MemorySaver()
graph_with_checkpointer = create_deep_agent(
    model=llm,
    system_prompt="你是门店助手，帮助店长管理门店。",
    checkpointer=checkpointer,
)

config = {"configurable": {"thread_id": "test-thread-1"}}

async def test_invoke():
    result = await graph_with_checkpointer.ainvoke(
        {"messages": [("human", "你好，门店 001 的店长是谁？")]},
        config=config,
    )
    print(f"\nLLM 响应类型: {type(result)}")
    if "messages" in result:
        last_msg = result["messages"][-1]
        print(f"最后一条消息类型: {type(last_msg)}")
        print(f"最后一条消息内容: {last_msg.content[:200] if hasattr(last_msg, 'content') else str(last_msg)[:200]}")

asyncio.run(test_invoke())

print("\n" + "=" * 60)
print("✅ 验证完成 — 如果看到 LLM 响应，说明集成可行")
print("=" * 60)
