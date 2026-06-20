"""E2E 测试 —— C 类多 vertical / tenant 隔离场景。"""
import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_tenant_isolation_two_tenants_see_different_data(
        e2e_agent, e2e_data_dir, scripted_llm):
    """C2: 不同 tenant 查询临期商品，只看到各自租户的数据。

    驱动：agent→工具的 tenant 链路打通（架构 spec §3.3 最后一公里）。
    现状：工具默认 tenant_default，agent 未传 tenant_id —— 本测试应 RED。

    准备：在临时数据目录里给 NearExpiryProduct 打两个 tenant_id（tenant_a / tenant_b）。
    """
    # 给种子数据打 tenant_id：nep_001/002/003/006/007 → tenant_a；nep_004 → tenant_b
    nep_path = Path(e2e_data_dir) / "near_expiry_products.json"
    rows = json.loads(nep_path.read_text(encoding="utf-8"))
    tenant_a_ids = {"nep_001", "nep_002", "nep_003", "nep_006", "nep_007"}
    for r in rows:
        r["tenant_id"] = "tenant_b" if r["id"] == "nep_004" else "tenant_a"
    nep_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    scripted_llm.script(
        # tenant_a 查询：传 tenant_id=tenant_a
        ([{"name": "query_near_expiry", "args": {"store_id": "store_001",
          "tenant_id": "tenant_a"}}], ""),
        ([], "done_a"),
        # tenant_b 查询：传 tenant_id=tenant_b
        ([{"name": "query_near_expiry", "args": {"store_id": "store_002",
          "tenant_id": "tenant_b"}}], ""),
        ([], "done_b"),
    )

    # tenant_a 查询：工具实际返回应只含 tenant_a 的数据
    r_a = await e2e_agent.ask("查 store_001 的临期商品", thread_id="t_c2_a")
    assert "query_near_expiry" in r_a.tool_calls
    assert r_a.tool_outputs, "应有工具输出"
    a_output = " ".join(r_a.tool_outputs)
    assert "nep_001" in a_output, f"tenant_a 应见 nep_001，工具输出: {a_output[:300]}"
    assert "nep_004" not in a_output, \
        f"tenant_a 不应见 tenant_b 的 nep_004，工具输出: {a_output[:300]}"

    # tenant_b 查询：工具实际返回应只含 tenant_b 的数据
    r_b = await e2e_agent.ask("查 store_002 的临期商品", thread_id="t_c2_b")
    assert "query_near_expiry" in r_b.tool_calls
    b_output = " ".join(r_b.tool_outputs)
    assert "nep_004" in b_output, f"tenant_b 应见 nep_004，工具输出: {b_output[:300]}"
    assert "nep_001" not in b_output, \
        f"tenant_b 不应见 tenant_a 的 nep_001，工具输出: {b_output[:300]}"
