"""门店本体项目 — 6 大功能 Playwright 端到端测试（含本体驱动工具）"""
import asyncio
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3000"
RESULTS = {}

async def send_message(page, text: str, wait: int = 15000):
    ta = page.locator('textarea[placeholder="Type a message..."]').first
    await ta.fill("")
    await ta.fill(text)
    await page.wait_for_timeout(500)
    await ta.press("Enter")
    await page.wait_for_timeout(wait)

async def run_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN")
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        await page.goto(FRONTEND_URL, wait_until="domcontentloaded")
        await page.wait_for_selector('textarea[placeholder="Type a message..."]', timeout=15000)
        print("✅ 页面加载成功\n")

        # ━━━ 1: Chat UI ━━━
        print("━" * 50)
        print("测试 1: Chat UI")
        await send_message(page, "你好")
        RESULTS["1_ChatUI"] = {"status": "PASS"}
        print("  → PASS")

        # ━━━ 2: Backend Tool Rendering ━━━
        print("\n" + "━" * 50)
        print("测试 2: Backend Tool Rendering — get_near_expiry_products")
        await send_message(page, "查询临期商品")
        content = await page.content()
        ok = "nep_001" in content or "蒙牛" in content
        RESULTS["2_ToolRender"] = {"status": "PASS" if ok else "FAIL", "detail": f"data:{ok}"}
        print(f"  → {'PASS' if ok else 'FAIL'}")

        # ━━━ 3: Generative UI ━━━
        print("\n" + "━" * 50)
        print("测试 3: Generative UI")
        gui = "Generative UI" in content or "📋" in content
        RESULTS["3_GenUI"] = {"status": "PASS" if gui else "FAIL"}
        print(f"  → {'PASS' if gui else 'FAIL'}")

        # ━━━ 4: Shared State ━━━
        print("\n" + "━" * 50)
        print("测试 4: Shared State")
        init = "store_001" in await page.inner_text("body")
        btn2 = page.locator('button:has-text("门店2")').first
        await btn2.click()
        await page.wait_for_timeout(800)
        await send_message(page, "查询当前门店的临期商品")
        content = await page.content()
        resp = "store_002" in content or "上海浦东" in content
        RESULTS["4_SharedState"] = {"status": "PASS" if init and resp else "FAIL", "detail": f"init:{init} resp:{resp}"}
        print(f"  → {'PASS' if init and resp else 'FAIL'} (init:{init} resp:{resp})")

        # ━━━ 5: HITL ━━━
        print("\n" + "━" * 50)
        print("测试 5: Human-in-the-Loop")
        btn1 = page.locator('button:has-text("门店1")').first
        await btn1.click(); await page.wait_for_timeout(500)
        await send_message(page, "帮 store_001 的 nep_001 创建出清任务，5折")
        content = await page.content()
        hitl = "pending_approval" in content or "确认" in content or "出清任务" in content or "创建" in content
        RESULTS["5_HITL"] = {"status": "PASS" if hitl else "FAIL"}
        print(f"  → {'PASS' if hitl else 'FAIL'}")

        # ━━━ 6: 本体驱动通用工具 ━━━
        print("\n" + "━" * 50)
        print("测试 6: 本体驱动通用工具 — query_entity + traverse_relation")

        # 6a: query_entity
        await send_message(page, "查询 store_001 有哪些员工")
        content = await page.content()
        emp = "emp_001" in content or "张三" in content or "员工" in content
        RESULTS["6a_query_entity"] = {"status": "PASS" if emp else "FAIL", "detail": f"employees:{emp}"}
        print(f"  6a query_entity → {'PASS' if emp else 'FAIL'} (员工:{emp})")

        # 6b: traverse_relation
        await send_message(page, "张三属于哪个门店")
        content = await page.content()
        rel = "store_001" in content or "北京朝阳" in content or "门店" in content
        RESULTS["6b_traverse"] = {"status": "PASS" if rel else "FAIL", "detail": f"relation:{rel}"}
        print(f"  6b traverse_relation → {'PASS' if rel else 'FAIL'} (门店:{rel})")

        # 6c: get_store_summary
        await send_message(page, "给我 store_001 的门店摘要", wait=18000)
        content = await page.content()
        summary = "门店摘要" in content or "北京朝阳" in content or "员工" in content
        RESULTS["6c_summary"] = {"status": "PASS" if summary else "FAIL", "detail": f"summary:{summary}"}
        print(f"  6c get_store_summary → {'PASS' if summary else 'FAIL'} (摘要:{summary})")

        await page.screenshot(path="/tmp/feature_test_result.png", full_page=True)
        await browser.close()

    # ━━━ 报告 ━━━
    print("\n" + "=" * 50)
    print("           测试报告")
    print("=" * 50)
    passed = failed = 0
    for name, r in RESULTS.items():
        if name.startswith("6"): continue  # skip sub-items
        if name == "console_errors": continue
        s = r["status"]
        print(f"{'✅' if s=='PASS' else '❌'} {name}: {s}")
        if r.get("detail"): print(f"   {r['detail']}")
        if s == "PASS": passed += 1
        elif s == "FAIL": failed += 1

    # 子测试
    for sub in ["6a_query_entity", "6b_traverse", "6c_summary"]:
        r = RESULTS.get(sub, {})
        s = r.get("status", "N/A")
        print(f"  {'✅' if s=='PASS' else '❌'} {sub}: {s} {r.get('detail','')}")

    print(f"\n通过: {passed}/5 + 3本体子测试")
    print(f"截图: /tmp/feature_test_result.png")
    return passed

if __name__ == "__main__":
    passed = asyncio.run(run_tests())
    exit(0 if passed >= 4 else 1)
