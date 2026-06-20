import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

import pytest

# 以 backend/ 为 sys.path 根，使 from ontology... / from models... 可用
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def tmp_data_dir(tmp_path):
    """提供一个空数据目录 + 基础 stores.json，供 Repository 测试用。"""
    stores = [{
        "id": "store_001", "name": "测试门店", "region_id": "region_001",
        "address": "测试地址", "manager_id": "emp_001",
        "created_at": "2024-01-01T00:00:00",
    }]
    (tmp_path / "stores.json").write_text(json.dumps(stores, ensure_ascii=False), encoding="utf-8")
    return str(tmp_path)
