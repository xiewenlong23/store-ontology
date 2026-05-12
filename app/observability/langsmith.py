# ============================================================
# LangSmith 配置 — Phase 5.2
# 环境变量：LANGSMITH_API_KEY（可选，有值时自动启用）
# ============================================================
import os
from typing import Optional
from app.config import settings

# LangSmith 配置（key 有值时启用）
LANGSMITH_CONFIG = {
    "api_key": os.environ.get("LANGSMITH_API_KEY"),
    "project": os.environ.get("LANGSMITH_PROJECT", "store-ontology"),
    "endpoint": os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
    "default_tags": ["store-ontology", "phase-5"],
    "enabled": bool(os.environ.get("LANGSMITH_API_KEY")),
}


def get_langsmith_config() -> dict:
    """
    获取 LangSmith 配置字典
    用于 create_deep_agent 的 langsmith_tracing 参数
    """
    if not LANGSMITH_CONFIG["enabled"]:
        return {"enabled": False}

    return {
        "enabled": True,
        "api_key": LANGSMITH_CONFIG["api_key"],
        "project": LANGSMITH_CONFIG["project"],
        "endpoint": LANGSMITH_CONFIG["endpoint"],
        "tags": LANGSMITH_CONFIG["default_tags"],
        "debug": settings.debug,
    }


def langsmith_tracing_enabled() -> bool:
    """判断 LangSmith tracing 是否已启用"""
    return LANGSMITH_CONFIG["enabled"]
