"""E2E 测试夹具 —— 构造指向临时数据的 agent + 脚本化 LLM + ask() 辅助。

设计要点：
- 用临时数据目录（复制 clearance 种子），不污染真实 data/
- 用 ScriptedLLM（按轮次返回预设工具调用），确定性、不依赖真实 LLM
- ask() 调 graph.ainvoke，从最终 messages 提取 tool_calls 与文本
"""
import os
import sys
import json
import shutil
from pathlib import Path
from collections import namedtuple

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))


# ============ E2E 调用结果 ============

E2EResult = namedtuple("E2EResult", ["text", "tool_calls", "tool_outputs"])


class E2EAgent:
    """封装 graph + ScriptedLLM，提供 ask() 入口。"""

    def __init__(self, graph, scripted_llm, tenant_id="tenant_default"):
        self.graph = graph
        self.scripted_llm = scripted_llm
        self.tenant_id = tenant_id
        self._hist_lens = {}  # thread_id -> 消息历史长度（跨轮追踪用）

    async def ask(self, message: str, thread_id: str = "default") -> E2EResult:
        config = {"configurable": {"thread_id": thread_id}}
        # 记录调用前的消息数，以便只提取本轮新增的 tool_calls
        before_count = self._history_len(thread_id)
        result = await self.graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]}, config)
        messages = result.get("messages", [])
        # 缓存最新历史长度，供下一轮判断
        self._set_history_len(thread_id, len(messages))
        # 只看本轮新增的消息（index >= before_count）
        new_messages = messages[before_count:]
        tool_calls = []
        tool_outputs = []  # 工具返回的内容（ToolMessage.content）
        last_text = ""
        for msg in new_messages:
            tcs = getattr(msg, "tool_calls", None) or []
            for tc in tcs:
                tool_calls.append(tc.get("name", "") if isinstance(tc, dict)
                                  else getattr(tc, "name", ""))
            # ToolMessage 的 content 是工具返回值
            msg_type = type(msg).__name__
            if msg_type == "ToolMessage":
                tool_outputs.append(getattr(msg, "content", ""))
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                last_text = content
        return E2EResult(text=last_text, tool_calls=tool_calls,
                         tool_outputs=tool_outputs)

    def _history_len(self, thread_id: str) -> int:
        return self._hist_lens.get(thread_id, 0)

    def _set_history_len(self, thread_id: str, n: int) -> None:
        self._hist_lens[thread_id] = n


# ============ 脚本化 LLM ============

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedLLM(BaseChatModel):
    """按轮次返回预设响应的假 LLM（BaseChatModel 子类，满足 deepagents 要求）。

    每个预设 = (tool_calls, text)：tool_calls 是 [{"name","args"}]。
    agent 工具循环每调一次 LLM 取下一个预设。预设用尽返回空文本结束。

    用法：llm.script(([], "回复"))  —— 注入预设并重置消费计数。
    """

    responses: list = []
    _consumed: int = 0  # pydantic PrivateAttr

    def script(self, *responses):
        """注入预设响应并重置消费计数。每个 response = (tool_calls_list, text)。"""
        # pydantic v2 私有属性赋值
        object.__setattr__(self, "responses", list(responses))
        object.__setattr__(self, "_consumed", 0)
        return self

    def _respond(self) -> AIMessage:
        consumed = object.__getattribute__(self, "_consumed")
        responses = object.__getattribute__(self, "responses")
        if consumed >= len(responses):
            return AIMessage(content="(已完成)")
        tool_calls, text = responses[consumed]
        object.__setattr__(self, "_consumed", consumed + 1)
        tcs = [{"name": tc["name"], "args": tc.get("args", {}),
                "id": f"call_{consumed+1}", "type": "tool_call"}
               for tc in tool_calls]
        return AIMessage(content=text, tool_calls=tcs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        msg = self._respond()
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        msg = self._respond()
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def _identifying_params(self) -> dict:
        return {"responses_count": len(self.responses)}

    def bind_tools(self, tools, **kwargs):
        # 深度 agent 会调；脚本化 LLM 无视绑定，按预设返回
        return self


# ============ 夹具 ============

@pytest.fixture
def e2e_data_dir(tmp_path):
    """复制 clearance 种子到临时目录，供 E2E agent 读写。"""
    src = BACKEND_DIR.parent / "workspace" / "retail" / "data"
    if src.is_dir():
        shutil.copytree(src, tmp_path, dirs_exist_ok=True)
    return str(tmp_path)


@pytest.fixture
def scripted_llm():
    """默认空预设；测试用 .script(...) 注入。返回 ScriptedLLM（带 script 方法）。"""
    return ScriptedLLM(responses=[])


@pytest.fixture
def e2e_agent(e2e_data_dir, scripted_llm, monkeypatch):
    """构造指向临时数据、用 ScriptedLLM 的 clearance agent。

    用 pack helper 构建完整 registry（3 domain TTL 合并），指向临时数据。
    """
    from tests._clearance_helper import build_clearance_executor, CLEARANCE_TEST_CONFIG
    ex, repo = build_clearance_executor(e2e_data_dir)
    reg = repo.registry

    # monkeypatch tools 层的依赖装配
    import engine.tools as T
    monkeypatch.setattr(T, "_parser", lambda vertical=None: type('P',(),{'registry':reg})())
    monkeypatch.setattr(T, "_get_repo", lambda tenant=None, vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)

    # 构造 agent（用 deepagents create_deep_agent + ScriptedLLM）
    from langgraph.checkpoint.memory import MemorySaver
    from deepagents import create_deep_agent
    from deepagents.backends.filesystem import FilesystemBackend

    prompt_intro = CLEARANCE_TEST_CONFIG.system_prompt_intro
    # 从 registry 构建提示词
    lines = [f"{prompt_intro}\n"]
    lines.append("可用实体: " + ", ".join(ot.label_zh for ot in reg.object_types.values()))
    lines.append("\n操作: " + ", ".join(reg.action_types.keys()))
    prompt = "\n".join(lines)

    BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
    from engine.tools import query_entity, create_entity, update_entity, traverse_relation, \
        execute_action, confirm_action, query_task, update_task
    from workspace.retail.skills.clearance_workflow.tools import query_near_expiry
    tools = [query_entity, create_entity, update_entity, traverse_relation,
             execute_action, confirm_action, query_task, update_task, query_near_expiry]

    skills_backend = FilesystemBackend(
        root_dir=str(BACKEND_DIR.parent / "workspace" / "retail" / "skills"),
        virtual_mode=True)

    graph = create_deep_agent(
        model=scripted_llm,
        tools=tools,
        system_prompt=prompt,
        checkpointer=MemorySaver(),
        backend=skills_backend,
        skills=["/store-ontology/", "/clearance-workflow/"],
    )

    yield E2EAgent(graph=graph, scripted_llm=scripted_llm)

    # 清理
    reset_parser_cache() if False else None  # 不再需要 reset（用 monkeypatch）
