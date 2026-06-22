"""回归测试：进程级 DATABASE_URL 不应泄漏到未声明 PG 的测试。

背景（P0 修复）：main.py 顶部 load_dotenv(override=True) 会把 .env 里的
DATABASE_URL 注入 os.environ（模块级副作用，不经 monkeypatch，不会被自动还原）。
任何 ``import main`` 的测试（如 test_tools_tenant 的 contextvar 测试）触发后，
后续走 JSON 路径的测试（test_onboarding_e2e / test_customer_bootstrap*）会因
is_pg_enabled()=True 而错误走 PG，registry 为空 → KeyError / 断言失败。

修复：conftest.py 的 autouse fixture ``_isolate_storage_env`` 在每个测试前
delenv(DATABASE_URL) + ``db._reset_pg_state()``，提供干净起点；PG 专用测试
在自己的 fixture 里 setenv 覆盖即可。
"""
import os


def test_a_simulates_load_dotenv_pollution():
    """模拟 main.py 的 load_dotenv 注入进程级 DATABASE_URL。

    用 os.environ 直接设（不经 monkeypatch），等价于模块级副作用，
    不会被任何 fixture teardown 自动还原。
    """
    os.environ["DATABASE_URL"] = "postgresql://fake@localhost:5433/fake"
    from engine import db
    db._reset_pg_state()
    assert db.is_pg_enabled() is True  # 此时 PG 确实被启用


def test_b_isolated_from_pollution():
    """后续测试不应继承 A 的 DATABASE_URL——autouse fixture 应已隔离。"""
    from engine import db
    db._reset_pg_state()  # 清缓存让 is_pg_enabled 重新求值
    assert not db.is_pg_enabled(), (
        "DATABASE_URL 泄漏到后续测试——conftest 的 _isolate_storage_env 失效"
    )
