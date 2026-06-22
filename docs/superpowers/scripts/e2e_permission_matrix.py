"""Playwright e2e：权限矩阵端到端验证（设计文档 §5 WP5 接入 + §11.3）。

不走真实 LLM（慢且不确定），直接用 frontend BFF + 真实 backend 跑：
1. 用 admin 登录（system_admin 短路，所有权限过）
2. 模拟不同 role 的 actor（monkeypatch backend？太复杂）

实际策略：**走真实 LLM 链路**（与 c 验证相同）+ 多角色 fixture。

启动前提：
  1. backend 起在 :8123（INITIAL_ADMIN_PASSWORD=admin123 JWT_SECRET=...）
  2. 已 seed 多个 Employee+User（不同 role）—— 见下方 prepare_users()

执行：
  /opt/miniconda3/envs/store-ontology/bin/python docs/superpowers/scripts/e2e_permission_matrix.py

验证矩阵（role × 操作）：
  admin(system_admin) × query User        = 允许（短路）
  admin × create_entity(Region)            = 允许（manifest 锁 admin）
  store_manager × query User               = 拒绝（read_roles=system_admin）
  store_manager × query Product            = 允许 + cost_price 可读
  store_clerk × query Product              = 允许 + cost_price 不可读（mask）
  store_clerk × create_entity              = 拒绝（manifest 锁 admin）
"""
import os
import sys
import asyncio
import json
from pathlib import Path

# 让 from engine... / from agent... 可用
BACKEND = Path(__file__).resolve().parent.parent.parent.parent / "agent"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent))

os.environ.setdefault("AUTH_REQUIRED", "false")


def _extract_data(text):
    import re
    m = re.search(r'<!--COPILOTKIT_DATA-->\n?([\s\S]*?)\n?<!--/COPILOTKIT_DATA-->', text)
    return json.loads(m.group(1)) if m else None


async def run_matrix():
    """跑权限矩阵。"""
    # 在 backend 上下文 import main（触发 bootstrap）
    import main
    import agent.tools.shared as shared
    from agent.tools.query_tools import query_entity
    from agent.tools.crud_tools import create_entity
    shared._reset_evaluator_cache()

    print("=" * 60)
    print("权限矩阵 e2e（真实 retail workspace + 真实 TTL 权限元数据）")
    print("=" * 60)

    cases = [
        # (role, action, expect_granted, description)
        ("system_admin",    "query_user",        True,  "system_admin 读 User（短路）"),
        ("store_clerk",     "query_user",        False, "store_clerk 读 User（read_roles=system_admin）"),
        ("region_cat_mgr",  "query_user",        False, "region_cat_mgr 读 User"),
        ("store_manager",   "query_product",     True,  "store_manager 读 Product"),
        ("store_clerk",     "query_product",     True,  "store_clerk 读 Product（Object 级允许）"),
        ("system_admin",    "create_region",     True,  "system_admin 调 create_entity（manifest 锁 admin）"),
        ("store_clerk",     "create_region",     False, "store_clerk 调 create_entity（拒绝）"),
        ("store_manager",   "create_region",     False, "store_manager 调 create_entity（拒绝）"),
    ]

    passed = 0
    failed = 0
    for role, action, expect_granted, desc in cases:
        # 设置 actor
        shared._get_actor = lambda tenant=None, r=role: {"role": r}
        shared._reset_evaluator_cache()

        try:
            if action == "query_user":
                out = query_entity.invoke({"entity_type": "User", "workspace_name": "jjy"})
                d = _extract_data(out)
                granted = not d.get("permission_denied", False) and d.get("total", 0) >= 0 \
                    and not d.get("permission_denied")
                # clerk/region_cat_mgr 应被拒绝
                granted = d.get("total", 0) > 0 and not d.get("permission_denied", False)
            elif action == "query_product":
                out = query_entity.invoke({"entity_type": "Product", "workspace_name": "jjy"})
                d = _extract_data(out)
                granted = d.get("total", 0) > 0 and not d.get("permission_denied", False)
                # 特殊：store_clerk 读 Product 应过 Object 级但 cost_price 被 mask
                if role == "store_clerk":
                    masked = d.get("masked_fields", [])
                    if "cost_price" not in masked:
                        print(f"  ❌ {desc}: store_clerk 应 mask cost_price，实际 masked={masked}")
                        failed += 1
                        continue
                elif role == "store_manager":
                    masked = d.get("masked_fields", [])
                    if "cost_price" in masked:
                        print(f"  ❌ {desc}: store_manager 不应 mask cost_price")
                        failed += 1
                        continue
            elif action == "create_region":
                # 用临时 id 避免污染
                import uuid
                tmp_id = f"region_test_{uuid.uuid4().hex[:6]}"
                out = create_entity.invoke({
                    "entity_type": "Region", "workspace_name": "jjy",
                    "id": tmp_id, "name": "test", "code": "T"})
                d = _extract_data(out)
                granted = d.get("success", False)
                # 清理：写过的删除（用 system_admin）
                if granted:
                    shared._get_actor = lambda tenant=None: {"role": "system_admin"}
                    shared._reset_evaluator_cache()
                    try:
                        from engine.workspace_bootstrap import bootstrap_workspace
                        from engine.tenant import TenantContext
                        inst = bootstrap_workspace("jjy")
                        inst.repository.delete("Region", TenantContext(workspace_name="jjy", org_unit_id="*"), tmp_id)
                    except Exception:
                        pass

            ok = (granted == expect_granted)
            mark = "✅" if ok else "❌"
            print(f"  {mark} {role:18s} × {action:18s} expect={expect_granted} actual={granted}  | {desc}")
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ {role} × {action}: 异常 {type(e).__name__}: {e}")
            failed += 1

    print()
    print(f"=== 结果：{passed} 通过 / {failed} 失败 / 共 {len(cases)} ===")
    return failed == 0


if __name__ == "__main__":
    try:
        ok = asyncio.run(run_matrix())
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        sys.exit(1)
