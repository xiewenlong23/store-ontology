---
name: fad:optimize
description: review 后必须执行的优化阶段
argument-hint: "[--run-id <id>] [可选范围]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

<objective>
在保持产品行为不变的前提下，改善可维护性和性能信号。
</objective>

<context>
范围: $ARGUMENTS

References:
- @.claude/commands/review.md
- @.claude/rules/code-style.md
- @.claude/rules/project-structure.md
- @.planning/pm/current/RISK-IMPACT.md
- @.claude/scripts/audit_log.py
</context>

<process>
1. 从参数或变更文件解析范围
2. 读取最新 review 发现和风险影响记录
3. 运行仅优化的编辑：
   - 删除重复和死代码
   - 改善命名和模块边界
   - 降低高风险路径复杂度
   - 应用低风险性能修复（N+1 查询、不必要循环、明显内存问题）
4. 优化期间不改变行为/需求：
   - 如果需要行为变更，停止并请求新的范围任务
5. 重新验证：
   - 针对触及模块的定向测试
   - 代码质量门禁
6. 写审计日志
7. 返回简洁输出：
   - 优化区域
   - 行为不变保证
   - 质量门禁结果
   - 剩余技术债务
</process>
