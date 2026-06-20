"""E2E 测试 —— A 类查询场景。

驱动开发：用户发自然语言 → agent 推理 → 调对工具 → 返回正确数据。
入口：headless agent.ainvoke（绕过 SSE，测核心链路）。
LLM 用 ScriptedLLM（确定性），测接线和契约而非 LLM 智能。
"""
import pytest


@pytest.mark.asyncio
async def test_user_asks_near_expiry_agent_calls_query_near_expiry(e2e_agent, scripted_llm):
    """A1: 用户问"查 store_001 的临期商品" → agent 调 query_near_expiry → 返回数据。

    脚本化 LLM 第1轮：调 query_near_expiry(store_id=store_001)
    第2轮：把工具结果转述给用户（含 nep_001）

    断言三件事：
    - agent 调用了 query_near_expiry（工具选择正确）
    - 返回消息含临期商品数据（nep_001 / 蒙牛酸奶）
    - 未触发任何写工具（查询场景不应有副作用）
    """
    scripted_llm.script(
        # 第1轮：LLM 决定调 query_near_expiry
        ([{"name": "query_near_expiry", "args": {"store_id": "store_001"}}], ""),
        # 第2轮：LLM 把结果转述给用户
        ([], "查到 store_001 的临期商品：nep_001 蒙牛酸奶（T2，剩余5天）等。"),
    )

    result = await e2e_agent.ask("查一下 store_001 的临期商品", thread_id="t_a1")

    assert "query_near_expiry" in result.tool_calls, \
        f"应调 query_near_expiry，实际调了: {result.tool_calls}"
    assert ("nep_001" in result.text or "蒙牛酸奶" in result.text), \
        f"返回应含临期商品数据，实际: {result.text[:200]}"
    write_tools = {"create_entity", "update_entity", "execute_action",
                   "confirm_action", "update_task"}
    assert not (set(result.tool_calls) & write_tools), \
        f"查询场景不应触发写工具，实际触发: {set(result.tool_calls) & write_tools}"
