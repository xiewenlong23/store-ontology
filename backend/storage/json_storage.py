"""JSON 文件存储层"""

import json
import os
from pathlib import Path
from typing import TypeVar, Generic, Type, List, Optional
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class JSONStorage(Generic[T]):
    """JSON 文件存储基类"""

    def __init__(self, file_path: str, model_class: Type[T]):
        self.file_path = Path(file_path)
        self.model_class = model_class
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """确保文件存在"""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._save([])

    def _load(self) -> List[dict]:
        """加载数据"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save(self, data: List[dict]):
        """保存数据"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def find_all(self) -> List[T]:
        """查询所有"""
        data = self._load()
        return [self.model_class(**item) for item in data]

    def find_by_id(self, id: str) -> Optional[T]:
        """根据ID查询"""
        data = self._load()
        for item in data:
            if item.get('id') == id:
                return self.model_class(**item)
        return None

    def find_by_field(self, field: str, value) -> List[T]:
        """根据字段查询"""
        data = self._load()
        return [self.model_class(**item) for item in data if item.get(field) == value]

    def create(self, item: T) -> T:
        """创建"""
        data = self._load()
        item_dict = item.model_dump()
        data.append(item_dict)
        self._save(data)
        return item

    def update(self, id: str, item: T) -> Optional[T]:
        """更新"""
        data = self._load()
        for i, existing in enumerate(data):
            if existing.get('id') == id:
                data[i] = item.model_dump()
                self._save(data)
                return item
        return None

    def delete(self, id: str) -> bool:
        """删除"""
        data = self._load()
        original_len = len(data)
        data = [item for item in data if item.get('id') != id]
        if len(data) < original_len:
            self._save(data)
            return True
        return False

    def save_all(self, items: List[T]):
        """批量保存"""
        data = [item.model_dump() for item in items]
        self._save(data)


class StoreStorage(JSONStorage):
    """门店存储"""
    pass


class EmployeeStorage(JSONStorage):
    """员工存储"""
    pass


class ProductStorage(JSONStorage):
    """商品存储"""
    pass


class NearExpiryProductStorage(JSONStorage):
    """临期商品存储"""
    pass


class DiscountRuleStorage(JSONStorage):
    """折扣规则存储"""
    pass


class ClearanceTaskStorage(JSONStorage):
    """出清任务存储"""
    pass
