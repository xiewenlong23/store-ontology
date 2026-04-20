---
name: fad:quality-gate
description: 结合代码质量、安全和未解决风险的严格合并门禁
argument-hint: "[--run-id <id>]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

<objective>
在完成或发布分支前提供明确的 go/no-go 决策。
</objective>

<context>
输入: $ARGUMENTS

References:
- @.claude/commands/code-quality-gate.md
- @.claude/commands/review.md
- @.planning/pm/current/RISK-IMPACT.md
- @.claude/scripts/audit_log.py
</context>

<process>
1. 确认所有关键阶段已完成
2. 运行代码质量门禁：
   - 检查 lint、类型、测试
3. 运行安全门禁：
   - secrets 泄露检测
   - 依赖漏洞检查
4. 运行 review 确认：
   - 未解决的 blocker/high 风险视为门禁失败
5. 风险门禁：
   - 检查 RISK-IMPACT.md
   - 未解决的 high/critical 风险阻塞
6. 写门禁总结文件
7. 写审计日志
8. 返回明确结果：
   - 只有所有严格检查通过才返回 DONE
   - 否则 BLOCKED 并说明具体失败检查
</process>
