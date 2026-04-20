---
name: pm-to-build
description: 将 PM 交付物转换为 FAD 规划和执行
argument-hint: "<phase-number>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

<objective>
以严格的需求追踪和 TDD 策略执行构建循环。
</objective>

<context>
阶段: $ARGUMENTS

Required inputs:
- @.planning/pm/current/PRD.md
- @.planning/pm/current/STORIES.md
- @.planning/pm/current/RISK-IMPACT.md
- @CLAUDE.md
- @.claude/rules/code-style.md
- @.claude/rules/project-structure.md
- @.claude/rules/testing.md
- @.claude/commands/review.md
- @.claude/commands/fad/optimize.md
</context>

<process>
1. 验证 PM 输入存在且需求 ID 一致
2. 重新评估 RISK-IMPACT.md：
   - 更新受影响的模块/文件
   - 确认每个风险的严重性
3. 风险门禁：
   - 如果任何 high 或 critical 风险未解决，停止执行
4. 构建或更新阶段上下文
5. 执行目标阶段的本地规划 -> 执行 -> 验证循环
6. 执行期间强制策略：
   - 每个任务追踪需求 ID
   - 领域/API 任务使用 TDD
   - 新代码遵循批准的模式
7. 运行强制 review 和优化阶段：
   - review 针对变更范围
   - fad:optimize 优化后 hardening
8. 运行严格质量门禁：
   - fad:quality-gate
   - 严格门禁阻塞则阶段完成
9. 写构建报告：
   - 阶段状态
   - 需求覆盖摘要
   - 风险门禁状态
   - review 状态
   - optimize 状态
   - 质量门禁摘要
</process>
