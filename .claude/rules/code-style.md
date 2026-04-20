# Code Style Rules

## Python

### 格式
- 使用 4 空格缩进
- 行长度不超过 120 字符
- 使用 Black 格式化（如果可用）

### 命名
- 类名：`PascalCase`（如 `ReductionTask`）
- 函数/变量：`snake_case`（如 `fetch_tasks`）
- 常量：`UPPER_SNAKE_CASE`（如 `DISCOUNT_TIERS`）
- 枚举值：小写（`PENDING = "pending"`）

### 类型提示
- 所有公开函数必须有类型提示
- 使用 `Optional[T]` 而非 `T | None`

### Imports
```python
# 标准库
import json
from pathlib import Path

# 第三方
from fastapi import FastAPI
from pydantic import BaseModel

# 本地（相对于项目根）
from app.models import ReductionTask
```

## React/JSX

- 使用函数组件和 Hooks
- 组件名：`PascalCase`
- 文件扩展：`.jsx`
- CSS 类使用 Tailwind

## 通用
- 不使用 `any` 类型
- 不使用 `// eslint-disable`
- 魔法数字提取为常量
