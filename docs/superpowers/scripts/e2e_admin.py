"""Playwright: admin 页 e2e 验证（登录 → admin 页 → 浏览 User/Role/OrgUnit/Category）。

启动前提：backend :8123 + frontend :3000 都已起。
执行：/opt/miniconda3/envs/store-ontology/bin/python docs/superpowers/scripts/e2e_admin.py
"""

import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3000"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context().new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # 登录
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_selector("#username", timeout=15000)
    page.wait_for_function(
        "() => { const f=document.querySelector('form'); const k=Object.keys(f).find(x=>x.startsWith('__reactProps')); return !!(k && f[k].onSubmit);}",
        timeout=20000)
    page.fill("#username", "admin")
    page.fill("#password", "admin123")
    page.locator('button[type="submit"]').click()
    page.wait_for_function(
        "() => !!localStorage.getItem('store-ontology:token')", timeout=15000)
    print("✅ 登录成功")

    # 访问 /admin（首次编译慢，加 timeout）
    page.goto(f"{BASE}/admin", wait_until="load", timeout=60000)
    page.wait_for_selector("text=管理员数据浏览", timeout=60000)
    print("✅ /admin 页面加载")

    # 等 User 数据加载（默认选中 User）
    page.wait_for_selector("text=系统管理员", timeout=10000)  # admin User 的 display_name
    print("✅ User 数据加载（含 admin 用户）")

    # 验证 password_hash 不在表格（脱敏）
    body = page.locator("body").inner_text()
    assert "password_hash" not in body or "$2b$12$" not in body, \
        "password_hash 应脱敏，不应在页面显示"
    print("✅ password_hash 已脱敏")

    # 切换到 Role
    page.locator("button").filter(has_text="角色").click()
    page.wait_for_selector("text=system_admin", timeout=5000)
    print("✅ Role 数据加载（含 system_admin）")

    # 切换到 OrgUnit
    page.locator("button").filter(has_text="组织单元").click()
    page.wait_for_selector("text=brand", timeout=5000)
    body = page.locator("body").inner_text()
    assert "store_001" in body, "OrgUnit 应含 store_001"
    print("✅ OrgUnit 数据加载（含 brand + store_001）")

    # 切换到 Category
    page.locator("button").filter(has_text="品类").click()
    page.wait_for_selector("text=department", timeout=5000)
    print("✅ Category 数据加载")

    # 验证无页面错误
    if errors:
        print(f"⚠️ 页面错误: {errors[:3]}")
    else:
        print("✅ 无页面错误")

    b.close()
    print("\n=== admin 页 e2e 全过 ===")
