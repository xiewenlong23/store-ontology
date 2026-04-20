# RISK-IMPACT.md

## 风险登记

| ID | 风险 | 严重性 | 状态 | 缓解措施 |
|----|------|--------|------|----------|
| R-001 | TTL 本体文件被覆盖为空文件 | Critical | Open | 从 GitHub 旧 commit 恢复 |
| R-002 | api.js 缺少 fetchTasks 函数 | High | Open | 补充函数定义 |
| R-003 | 硬编码相对路径 | Medium | Open | 使用 Path 模块 |
| R-004 | 前端无测试覆盖 | Medium | Open | 添加 React 组件测试 |
