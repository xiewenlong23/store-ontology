"""测试内核 AutomationScheduler（APScheduler 封装）。

分离两类测试避免 flaky：
- 生命周期：start/shutdown 不跑真 job，只验状态
- job 真跑：短 interval + 计数器断言 job 确实执行了
"""
import time

import pytest

from ontology.scheduler import AutomationScheduler


def test_lifecycle_start_shutdown():
    """start 后运行中，shutdown 后停止。"""
    sched = AutomationScheduler()
    assert sched.running is False
    sched.start()
    assert sched.running is True
    sched.shutdown()
    assert sched.running is False


def test_add_job_runs():
    """注册的 job 真的被调度执行（短 interval + 计数器）。"""
    sched = AutomationScheduler()
    counter = {"n": 0}

    def tick():
        counter["n"] += 1

    sched.start()
    try:
        sched.add_job("tick", tick, interval_seconds=0.3)
        time.sleep(1.0)  # 等 ~3 次触发
    finally:
        sched.shutdown()
    assert counter["n"] >= 2, f"job 应被多次触发，实际 {counter['n']}"


def test_add_job_before_start_defers():
    """start 前注册的 job，start 后才跑。"""
    sched = AutomationScheduler()
    counter = {"n": 0}
    sched.add_job("tick", tick_fn := (lambda: counter.__setitem__("n", counter["n"] + 1)),
                  interval_seconds=0.2)
    assert counter["n"] == 0  # 还没 start，没跑
    sched.start()
    try:
        time.sleep(0.7)
    finally:
        sched.shutdown()
    assert counter["n"] >= 1
