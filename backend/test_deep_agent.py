"""
Deep Agent 对话测试（不走 CopilotKit 前端，直接调 agent）
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# 加载 .env
from dotenv import load_dotenv
load_dotenv(".env")

api_key = os.getenv("QWEN_API_KEY")
base_url = os.getenv("QWEN_BASE_URL", "https://api.minimaxi.com/v1")
model_name = os.getenv("QWEN_MODEL", "MiniMax-M2.7-highspeed")

llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url, temperature=0.7)

@tool
def get_store_summary(store_id: str = None) -> str:
    """获取门店摘要。"""
    if not store_id:
        return "请指定门店ID"
    return f"门店 {store_id} 店长是 张三，共有 5 名员工。"

tools = [get_store_summary]
checkpointer = MemorySaver()

graph = create_deep_agent(
    model=llm,
    tools=tools,
    system_prompt="你是一个门店管理助手，用中文回复。",
    checkpointer=checkpointer,
)

config = {"configurable": {"thread_id": "test-thread-1"}}

async def test_single():
    print("=== 单轮对话测试 ===")
    result = await graph.ainvoke(
        {"messages": [("human", "门店 001 的店长是谁？")]},
        config=config,
    )
    last_msg = result["messages"][-1]
    print(f"回复: {last_msg.content[:300]}")
    print()

async def test_multi():
    print("=== 多轮对话测试（5轮） ===")
    config = {"configurable": {"thread_id": "test-thread-2"}}
    questions = [
        "门店 001 的店长是谁？",
        "他手下有几个员工？",
        "最近有没有临期商品？",
        "帮我创建一个出清任务",
        "确认创建",
    ]
    for q in questions:
        result = await graph.ainvoke(
            {"messages": [("human", q)]},
            config=config,
        )
        last_msg = result["messages"][-1]
        print(f"Q: {q}")
        print(f"A: {last_msg.content[:200] if hasattr(last_msg, 'content') else str(last_msg)[:200]}")
        print()

async def test_context_compression():
    print("=== Context 压缩测试（10轮，验证 BadRequestError 不再出现） ===")
    config = {"configurable": {"thread_id": "test-thread-3"}}
    for i in range(10):
        result = await graph.ainvoke(
            {"messages": [("human", f"这是第{i+1}轮对话，请重复说：我收到了第{i+1}轮消息")]},
            config=config,
        )
        last_msg = result["messages"][-1]
        print(f"轮次 {i+1}: {last_msg.content[:100] if hasattr(last_msg, 'content') else '...'}")
    print("10轮对话完成，未报错 ✓")

asyncio.run(test_single())
asyncio.run(test_multi())
asyncio.run(test_context_compression())
print("=== 全部测试通过 ===")
