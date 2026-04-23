#!/usr/bin/env python3
"""
DataService 工厂

根据环境变量 DATA_BACKEND 选择后端实现。
目前支持：
- json: JSON 文件存储（默认）
- sqlite: SQLite 存储（后续扩展）
"""

import os
from typing import Optional

from app.services.data.base import DataService
from app.services.data.json_store import JSONDataService

# 后端注册表（后续可扩展）
_BACKENDS = {
    "json": JSONDataService,
    # "sqlite": SQLiteDataService,  # TODO: 后续实现
}


def get_data_service(backend: Optional[str] = None) -> DataService:
    """
    获取 DataService 实例。

    Args:
        backend: 后端类型，可选。默认从环境变量 DATA_BACKEND 读取。

    Returns:
        DataService 实例

    Raises:
        ValueError: 当指定的后端不支持时
    """
    if backend is None:
        backend = os.environ.get("DATA_BACKEND", "json")

    backend_cls = _BACKENDS.get(backend)
    if backend_cls is None:
        available = ", ".join(_BACKENDS.keys())
        raise ValueError(
            f"Unknown DATA_BACKEND: '{backend}'. Available backends: {available}"
        )

    return backend_cls()
