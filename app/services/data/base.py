#!/usr/bin/env python3
"""
DataService 抽象基类

定义数据访问接口契约，所有后端实现必须实现这些方法。
设计原则：
- 上下文感知：自动从 ToolContext 获取 store_id 进行过滤
- 接口简洁：load_* 返回过滤后的数据，save_* 接受完整数据
- 缓存支持：invalidate_cache() 用于主动失效缓存
"""

from abc import ABC, abstractmethod
from typing import Optional


class DataService(ABC):
    """
    数据访问抽象基类。

    所有数据访问必须通过此接口，确保：
    1. 统一的错误处理
    2. 统一的文件锁/并发控制
    3. 统一的缓存策略
    4. 统一的后端切换能力
    """

    @abstractmethod
    def load_products(self, store_id: Optional[str] = None) -> list[dict]:
        """
        加载商品列表。

        Args:
            store_id: 门店ID，可选。如果为 None，则尝试从 ToolContext 获取。

        Returns:
            商品列表（已按 store_id 过滤）
        """

    @abstractmethod
    def load_all_products(self) -> list[dict]:
        """
        加载所有商品（不过滤 store_id）。

        用于需要整体读取的场景（如扫描所有临期商品）。

        Returns:
            完整的商品列表
        """

    @abstractmethod
    def save_products(self, products: list[dict]) -> None:
        """
        保存商品列表。

        Args:
            products: 完整的商品列表（应包含所有门店的商品）
        """

    @abstractmethod
    def load_tasks(self, store_id: Optional[str] = None) -> list[dict]:
        """
        加载任务列表。

        Args:
            store_id: 门店ID，可选。如果为 None，则尝试从 ToolContext 获取。

        Returns:
            任务列表（已按 store_id 过滤）
        """

    @abstractmethod
    def load_all_tasks(self) -> list[dict]:
        """
        加载所有任务（不过滤 store_id）。

        用于需要整体读写修改的场景（如确认/执行/复核任务）。
        正常情况下优先使用 load_tasks()。

        Returns:
            完整的任务列表
        """

    @abstractmethod
    def save_tasks(self, tasks: list[dict]) -> None:
        """
        保存任务列表。

        Args:
            tasks: 完整的任务列表（应包含所有门店的任务）
        """

    @abstractmethod
    def load_staff(self, store_id: Optional[str] = None) -> list[dict]:
        """
        加载员工列表。

        Args:
            store_id: 门店ID，可选。

        Returns:
            员工列表（已按 store_id 过滤）
        """

    @abstractmethod
    def load_all_staff(self) -> list[dict]:
        """
        加载所有员工（不过滤 store_id）。

        Returns:
            完整的员工列表
        """

    @abstractmethod
    def save_staff(self, staff: list[dict]) -> None:
        """
        保存员工列表。

        Args:
            staff: 完整的员工列表
        """

    @abstractmethod
    def load_inventory(self, store_id: Optional[str] = None, product_id: Optional[str] = None) -> list[dict]:
        """
        加载库存列表。

        Args:
            store_id: 门店ID，可选。
            product_id: 商品ID，可选。

        Returns:
            库存列表
        """

    @abstractmethod
    def load_all_inventory(self) -> list[dict]:
        """加载所有库存（不过滤）。"""

    @abstractmethod
    def save_inventory(self, inventory: list[dict]) -> None:
        """
        保存库存列表。
        """

    @abstractmethod
    def invalidate_cache(self) -> None:
        """
        主动失效缓存。

        用于：
        - 数据写入后调用，确保下次 load 读到最新数据
        - 外部通知数据已变更的场景
        """
