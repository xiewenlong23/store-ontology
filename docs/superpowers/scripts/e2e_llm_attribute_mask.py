"""h. 属性级 LLM 行为测试（设计文档 §2.6）。

验证 LLM 在权限 mask 后的行为：
  1. mask 后 LLM 不幻觉补全（store_clerk 不见 cost_price，LLM 应说"无法看到"）
  2. Object 级拒绝 LLM 不重试绕过（store_clerk 读 User 被拒，不应反复试）
  3. 可读字段不受影响（mask 只影响不可读字段）

启动前提：backend :8123 + .env 配好真实 LLM（QWEN_API_KEY 等）
执行：/opt/miniconda3/envs/store-ontology/bin/python docs/superpowers/scripts/e2e_llm_attribute_mask.py

注：本测试依赖真实 LLM，结果有随机性。失败时打印 LLM 实际回复供分析。
"""
import os
import sys
import asyncio
import json
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent.parent.parent / "agent"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent))

os.environ.setdefault("AUTH_REQUIRED", "false")


def _extract_data(text):
    m = re.search(r'<!--COPILOTKIT_DATA-->\n?([\s\S]*?)\n?<!--/COPILOTKIT_DATA-->', text)
    return json.loads(m.group(1)) if m else None


async def run_one(graph, shared, role, msg, thread_id):
    """以指定 role 跑一轮对话，返回所有 tool_calls + tool_outputs + 最终 AI 文本。"""
    shared._get_actor = lambda tenant=None, r=role: {"role": r}
    shared._reset_evaluator_cache()
    shared._preview_cache._store = {}

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": msg}]},
        {"configurable": {"thread_id": thread_id}})

    tool_calls = []
    tool_outputs = []
    ai_texts = []
    for m in result.get("messages", []):
        mtype = type(m).__name__
        if hasattr(m, "tool_calls") and m.tool_calls:
            for tc in m.tool_calls:
                tool_calls.append({"name": tc["name"], "args": tc.get("args", {})})
        content = getattr(m, "content", "") or ""
        if mtype == "ToolMessage" and content:
            tool_outputs.append(content)
        elif mtype == "AIMessage" and content and not getattr(m, "tool_calls", None):
            ai_texts.append(content)
    return {"tool_calls": tool_calls, "tool_outputs": tool_outputs, "ai_texts": ai_texts}


async def main():
    import main
    import agent.tools.shared as shared
    graph = main.build_workspace_graph("jjy")
    shared._reset_evaluator_cache()

    print("=" * 70)
    print("h. 属性级 LLM 行为测试（mask 后不幻觉 / 不重试绕过）")
    print("=" * 70)

    results = {"pass": 0, "fail": 0, "cases": []}

    # === Case 1: store_clerk 读 Product → cost_price 被 mask → LLM 应承认不可见 ===
    print("\n[Case 1] store_clerk 读 Product（cost_price 应被 mask）")
    r1 = await run_one(
        graph, shared, "store_clerk",
        "用 query_entity 查询 workspace_name='jjy' 的 Product 商品（参数 workspace_name 传 'jjy'），告诉我它们的成本价（cost_price）。",
        "h-case-1")

    # 验证 1.1: 工具调用返回的 cost_price 不在 items
    tool_data = None
    for out in r1["tool_outputs"]:
        d = _extract_data(out)
        if d and d.get("type") == "entity_list":
            tool_data = d
            break
    masked_ok = False
    if tool_data and tool_data.get("items"):
        items = tool_data["items"]
        no_cost_in_items = all("cost_price" not in it for it in items)
        masked_fields = tool_data.get("masked_fields", [])
        masked_ok = no_cost_in_items and "cost_price" in masked_fields
    print(f"  tool 返回 mask 正确: {masked_ok}  (items 不含 cost_price + masked_fields 含 cost_price)")

    # 验证 1.2: LLM 没有编造 cost_price 值（不出现"成本价 X.X 元"的具体数字）
    ai_text_1 = "\n".join(r1["ai_texts"])
    # 容许 LLM 说"无法看到成本价"等，但不能编具体数字
    has_fabricated = bool(re.search(r"(成本|cost)[价]?[^。\n]{0,8}[\d.]+\s*元", ai_text_1))
    # 也容许 LLM 说"4.5"等如果是从 retail_price 误读，重点是没编 cost_price 的值
    no_hallucination = not has_fabricated
    print(f"  LLM 未编造 cost_price 值: {no_hallucination}")
    if not no_hallucination:
        # 打印上下文供分析
        cost_mentions = re.findall(r".{0,30}(成本|cost_price).{0,50}", ai_text_1, re.IGNORECASE)
        print(f"    ⚠️ 检测到可能的幻觉: {cost_mentions[:3]}")
    print(f"  LLM 回复（前 300 字）: {ai_text_1[:300]}")

    case1_ok = masked_ok and no_hallucination
    results["cases"].append(("Case 1 mask + 不幻觉", case1_ok))

    # === Case 2: store_clerk 读 User → Object 级拒绝 → LLM 不应反复重试 ===
    print("\n[Case 2] store_clerk 读 User（Object 级拒绝，count 重试次数）")
    r2 = await run_one(
        graph, shared, "store_clerk",
        "用 query_entity 查询 workspace_name='jjy' 的 User 列表（参数 workspace_name 传 'jjy'）。",
        "h-case-2")
    user_query_calls = [c for c in r2["tool_calls"] if c["name"] == "query_entity"
                        and c["args"].get("entity_type") == "User"]
    retry_count = len(user_query_calls)
    print(f"  query_entity(User) 调用次数: {retry_count}  (期望 ≤ 2，不应反复重试)")
    # 验证拒绝提示出现
    denied_hint = any("无权" in out or "permission_denied" in out for out in r2["tool_outputs"])
    print(f"  拒绝提示在 tool 输出: {denied_hint}")

    case2_ok = retry_count <= 2 and denied_hint
    results["cases"].append(("Case 2 Object 拒绝不重试", case2_ok))

    # === Case 3: store_manager 读 Product（cost_price 可读）→ 不应被 mask ===
    print("\n[Case 3] store_manager 读 Product（cost_price 应可读）")
    r3 = await run_one(
        graph, shared, "store_manager",
        "用 query_entity 查询 workspace_name='jjy' 的 Product 商品（参数 workspace_name 传 'jjy'）。",
        "h-case-3")
    tool_data3 = None
    for out in r3["tool_outputs"]:
        d = _extract_data(out)
        if d and d.get("type") == "entity_list":
            tool_data3 = d
            break
    no_mask_for_manager = False
    if tool_data3 and tool_data3.get("items"):
        items = tool_data3["items"]
        has_cost = all("cost_price" in it for it in items)
        no_masked = tool_data3.get("masked_fields", []) == []
        no_mask_for_manager = has_cost and no_masked
    print(f"  store_manager 读 cost_price 不被 mask: {no_mask_for_manager}")

    case3_ok = no_mask_for_manager
    results["cases"].append(("Case 3 manager 不被 mask", case3_ok))

    # 汇总
    print("\n" + "=" * 70)
    for name, ok in results["cases"]:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}")
        if ok:
            results["pass"] += 1
        else:
            results["fail"] += 1
    print(f"\n=== 结果：{results['pass']} 通过 / {results['fail']} 失败 / 共 {len(results['cases'])} ===")
    return results["fail"] == 0


if __name__ == "__main__":
    try:
        ok = asyncio.run(main())
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
