# ============================================================
# structlog 配置 — Phase 5.1
# 标准 JSON 日志输出，输出到 stdout（容器日志收集）
# ============================================================
import structlog
import structlog.processors
import logging
import sys
from app.config import settings

# 根据环境决定日志级别
log_level = logging.DEBUG if settings.debug else logging.INFO

# 配置根日志器
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=log_level,
)

# 配置 structlog
structlog.configure(
    processors=[
        # 1. 添加日志级别
        structlog.processors.add_log_level,
        # 2. 渲染异常堆栈
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        # 3. 渲染时间戳
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # 4. 统一 JSON 输出
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(log_level),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)


def get_logger(name: str = None):
    """获取 structlog logger 实例"""
    return structlog.get_logger(name)
