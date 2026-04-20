---
name: fad:ship
description: 严格质量门禁通过后的最终发布流程
argument-hint: "[阶段或发布名称]"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Write
---

<objective>
将严格门禁完成桥接到 PR 创建和发布就绪状态。
</objective>

<context>
目标: $ARGUMENTS

References:
- @.claude/commands/fad/quality-gate.md
- @.claude/commands/fad/pr-branch.md
- @.planning/pm/current/
</context>

<process>
1. 确认严格门禁为 green 且未解决的 blocker/high 项目已关闭
2. 总结发布包：
   - 交付范围
   - 通过的测试/检查
   - 已接受或已缓解的风险
3. 提供发布模式选择：
   - 打开/准备 PR
   - 继续开发
   - 交接给人工进行最终发布
4. 如果创建 PR，确保分支策略是 review-safe
5. 返回：
   - 发布就绪状态
   - PR/release 备注摘要
   - 剩余人工操作
</process>
