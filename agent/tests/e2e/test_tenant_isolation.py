"""E2E 测试 —— workspace 隔离场景（workspace_name 模型）。"""
import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_tenant_isolation_two_tenants_see_different_data(
        e2e_agent, e2e_data_dir, scripted_llm):
    """不同 workspace 查询临期商品，只看到各自 workspace 的数据。

    驱动：agent→工具的 workspace 链路（_tc_ctx 从 contextvar 读 workspace_name）。
    准备：给 NearExpiryProduct 打两个 workspace_name（ws_a / ws_b）。
    """
    # 给种子数据打 workspace_name：nep_001/002/003/006/007 → ws_a；nep_004 → ws_b
    nep_path = Path(e2e_data_dir) / "near_expiry_products.json"
    rows = json.loads(nep_path.read_text(encoding="utf-8"))
    for r in rows:
        r["workspace_name"] = "ws_b" if r["id"] == "nep_004" else "ws_a"
    nep_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # 设 contextvar 到 ws_a，agent 调 query_near_expiry（工具从 _tc_ctx 读 ws_a）
    import main
    from engine.tenant import TenantContext

    token = main.tenant_ctx.set(TenantContext(workspace_name="ws_a", org_unit_id="*"))
    scripted_llm.script(
        ([{"name": "query_near_expiry", "args": {"store_id": "store_001"}}], ""),
        ([], "done_a"),
    )
    try:
        r_a = await e2e_agent.ask("查 store_001 的临期商品", thread_id="t_c2_a")
        assert "query_near_expiry" in r_a.tool_calls
        assert r_a.tool_outputs, "应有工具输出"
        a_output = " ".join(r_a.tool_outputs)
        assert "nep_001" in a_output, f"ws_a 应见 nep_001，工具输出: {a_output[:300]}"
        assert "nep_004" not in a_output, \
            f"ws_a 不应见 ws_b 的 nep_004，工具输出: {a_output[:300]}"
    finally:
        main.tenant_ctx.reset(token)

    # 切到 ws_b
    token = main.tenant_ctx.set(TenantContext(workspace_name="ws_b", org_unit_id="*"))
    scripted_llm.script(
        ([{"name": "query_near_expiry", "args": {"store_id": "store_002"}}], ""),
        ([], "done_b"),
    )
    try:
        r_b = await e2e_agent.ask("查 store_002 的临期商品", thread_id="t_c2_b")
        assert "query_near_expiry" in r_b.tool_calls
        b_output = " ".join(r_b.tool_outputs)
        assert "nep_004" in b_output, f"ws_b 应见 nep_004，工具输出: {b_output[:300]}"
        assert "nep_001" not in b_output, \
            f"ws_b 不应见 ws_a 的 nep_001，工具输出: {b_output[:300]}"
    finally:
        main.tenant_ctx.reset(token)
