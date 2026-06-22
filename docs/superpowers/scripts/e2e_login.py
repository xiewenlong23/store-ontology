"""Playwright 端到端验证：登录页交互 + 链路验证。

启动前提：
  1. backend 起在 :8123（INITIAL_ADMIN_PASSWORD=admin123 JWT_SECRET=...）
  2. frontend 起在 :3000（npm run dev）

执行：
  /opt/miniconda3/envs/store-ontology/bin/python docs/superpowers/scripts/e2e_login.py

验证项：
  1. /login 页面渲染（h1 + form 元素齐全）
  2. 错密码登录 → 显示错误
  3. 正确密码登录 → token 写入 localStorage + 跳首页
  4. 首页 workspace 选择器来自 memberships（取代硬编码 KNOWN_WORKSPACES）
  5. logout → 清 token + 跳回 /login
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:3000")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # 收集 console 错误
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        # === 1. 访问 /login ===
        print("[1] 访问 /login")
        page.goto(f"{BASE}/login", wait_until="load")
        # 等登录表单渲染（Next.js hydration 较慢，等 onSubmit 真正绑上）
        page.wait_for_selector("#username", timeout=15000)
        # 等 React hydration 完成（form 的 onSubmit handler 绑上）
        page.wait_for_function(
            "() => { const f = document.querySelector('form');"
            "  const k = Object.keys(f).find(x => x.startsWith('__reactProps'));"
            "  return !!(k && f[k].onSubmit); }",
            timeout=20000
        )
        print("    React hydration 完成，form onSubmit 已绑")
        # 验证登录页关键元素
        h1 = page.locator("h1").inner_text()
        assert "登录" in h1, f"登录页 h1 应含'登录'，实际：{h1}"
        print(f"    h1: {h1}")

        username_input = page.locator("#username")
        password_input = page.locator("#password")
        submit_btn = page.locator('button[type="submit"]')
        assert username_input.count() == 1, "用户名输入框应存在"
        assert password_input.count() == 1, "密码输入框应存在"
        assert submit_btn.count() == 1, "提交按钮应存在"
        print("    登录页元素齐全（username/password/submit）")

        # === 2. 错密码 login ===
        print("[2] 错密码登录")
        page.locator("#username").fill("")
        page.locator("#username").fill("admin")
        page.locator("#password").fill("wrong_password")
        page.wait_for_function("() => document.querySelector('#username').value === 'admin'", timeout=3000)
        page.wait_for_function("() => document.querySelector('#password').value === 'wrong_password'", timeout=3000)
        page.locator('button[type="submit"]').click()
        # 等错误文本出现（handler 跑通后 React 渲染错误）
        page.wait_for_selector("text=用户名或密码错误", timeout=15000)
        print("    错误提示已显示: '用户名或密码错误'")

        # === 3. 正确密码 login → 跳 / ===
        print("[3] 正确密码登录 → 跳首页")
        page.locator("#username").fill("admin")
        page.locator("#password").fill("admin123")
        page.locator('button[type="submit"]').click()
        # 等 token 写入 localStorage（不依赖 url 跳转，因 / 首次编译慢）
        page.wait_for_function(
            "() => !!localStorage.getItem('store-ontology:token')",
            timeout=15000)
        print("    token 已写入 localStorage")
        # 等首页内容（workspace 选择器渲染）。用更长超时（首次编译 / 路由）
        page.wait_for_selector("text=切换工作空间", timeout=40000)
        print(f"    当前 URL: {page.url}")

        # 验证 localStorage 有 token
        token = page.evaluate("() => window.localStorage.getItem('store-ontology:token')")
        assert token and len(token) > 50, f"localStorage 应有 token，实际：{token}"
        print(f"    localStorage token len: {len(token)}")

        # 验证首页含 workspace 选择器（来自 memberships：客户 A / 客户 jjy / 零售）
        body_text = page.locator("body").inner_text()
        for ws_label in ["客户 A", "客户 jjy", "零售"]:
            assert ws_label in body_text, f"首页应含 workspace '{ws_label}'"
        print("    首页含 3 个 workspace（客户 A / 客户 jjy / 零售）—— 来自 memberships")

        # === 4. 验证 logout 按钮 ===
        print("[4] 验证 logout 按钮")
        logout_btn = page.locator("button").filter(has_text="退出")
        assert logout_btn.count() == 1, "应有'退出'按钮"
        print("    logout 按钮存在")

        # === 5. logout → 清 token ===
        print("[5] 点击 logout")
        logout_btn.click()
        # 等 token 清空
        page.wait_for_function(
            "() => !localStorage.getItem('store-ontology:token')",
            timeout=10000)
        print("    localStorage token 已清空")
        # 应跳回 /login
        page.wait_for_url(f"{BASE}/login", timeout=15000)
        print(f"    跳转到: {page.url}")

        # 报错检查
        if errors:
            print(f"\n⚠️ 页面错误: {errors}")
        else:
            print("\n✅ 无页面错误")

        browser.close()
        print("\n=== 全部 e2e 步骤通过 ===")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\n❌ 断言失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        sys.exit(1)
