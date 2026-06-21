"""内核自动化调度器 —— 封装 APScheduler BackgroundScheduler。

承载后端自动化的定时触发（架构文档 §2.4）：盘点完成、到期报损等无 LLM 在环的步骤。
行业包通过 register 函数把自己的 job 加进来（见 workspace/<pack>/skills/<process>/automation.py）。

设计：
- job 函数签名统一：def job() —— 执行所需 executor/tenant 由 job 闭包捕获
- interval 触发（MVP）；cron 留扩展
- start 前 add_job 会缓存，start 时统一注册
"""
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler


class AutomationScheduler:
    """APScheduler 的轻量封装。

    用法：
        sched = AutomationScheduler()
        sched.add_job("expiry_check", my_job, interval_seconds=1800)
        sched.start()           # FastAPI startup
        sched.shutdown()        # FastAPI shutdown
    """

    def __init__(self):
        self._scheduler: Optional[BackgroundScheduler] = None
        self._pending = []  # start 前注册的 (job_id, func, interval)

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = BackgroundScheduler()
        # 把 start 前注册的 job 统一加入
        for job_id, func, interval in self._pending:
            self._scheduler.add_job(func, "interval", seconds=interval, id=job_id)
        self._pending.clear()
        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None

    def add_job(self, job_id: str, func: Callable, interval_seconds: int) -> None:
        """注册一个 interval 触发的 job。start 前注册会延迟到 start 时生效。"""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.add_job(func, "interval", seconds=interval_seconds, id=job_id)
        else:
            self._pending.append((job_id, func, interval_seconds))
