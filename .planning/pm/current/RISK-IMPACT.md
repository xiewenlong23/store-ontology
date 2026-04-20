# RISK-IMPACT.md

## 风险登记

| ID | 风险 | 严重性 | 状态 | 修复措施 |
|----|------|--------|------|----------|
| R-001 | TTL 本体文件被覆盖为空文件 | Critical | ✅ 已修复 | 从 GitHub 旧 commit 恢复（2504行） |
| R-002 | api.js 缺少 fetchTasks 函数 | Critical | ✅ 已修复 | 补充完整函数定义 |
| R-003 | 硬编码相对路径 | Medium | ✅ 已修复 | 用 Path 模块重构（tasks.py, reasoning.py） |
| R-004 | 前端无测试覆盖 | Medium | ✅ 已修复 | 添加 Vitest + React Testing Library 测试 |

## 修复验证

- Python 测试：7 passed
- api.js：已添加 fetchTasks
- 路径重构：DATA_DIR + TASKS_FILE/PRODUCTS_FILE
- 前端测试：3 个测试文件（ProductCard, ChatAssistant, Dashboard）
