#!/usr/bin/env python3
"""
DataService 数据访问抽象层

提供统一的数据访问接口，支持切换后端实现（JSON/SQLite/GraphDB）。
所有数据访问通过 DataService，避免散落在多处。
"""

from app.services.data.base import DataService
from app.services.data.factory import get_data_service

__all__ = ["DataService", "get_data_service"]
