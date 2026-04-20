# Testing Rules

## 覆盖率目标
- 核心业务逻辑（reasoning.py）：>80%
- API endpoints：100%
- 模型验证：>90%

## 测试文件位置
```
tests/
├── test_api.py          # API endpoint 测试
├── test_reasoning.py    # 折扣推理逻辑测试
├── test_models.py       # Pydantic 模型测试
└── conftest.py          # 共享 fixtures
```

## 测试命名
```python
def test_function_name_scenario():
    """描述测试场景和预期结果"""
    ...
```

## 测试隔离
- 每个测试负责自己的数据 setup/teardown
- 使用临时文件或 mock 避免文件冲突
- 测试之间无依赖

## Mock 策略
- 外部 API 调用使用 mock
- 文件 I/O 使用 fixture 或 mock
- 数据库（如果添加）使用测试数据库

## 断言
- 优先验证行为而非实现细节
- 提供清晰的失败消息
