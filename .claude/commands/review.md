---
name: review
description: 严重性优先的代码审查，带并行分析器和可操作发现
argument-hint: "[可选: 文件路径、模块或变更范围]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
---

<objective>
将审查作为风险检测工作流执行，而非风格检查清单。
</objective>

<context>
范围: $ARGUMENTS

References:
- @CLAUDE.md
- @.claude/rules/security.md
- @.claude/rules/testing.md
- @.planning/pm/current/RISK-IMPACT.md
</context>

<process>
1. 从 staged 变更或提供的路径/模块确定审查范围
2. 如果存在 RISK-IMPACT.md，优先检查高危/关键受影响模块
3. 执行两遍审查：
   - 第一遍：严重性问题
   - 第二遍：信息性问题
4. 并行审查：
   - 正确性和回归风险
   - 安全和数据处理
   - 测试充分性和可观测性
5. 应用修复优先启发式：
   - 机械性低风险发现 -> 自动修复
   - 模糊/高风险发现 -> 需要输入
6. 写审查审计文件：
   - 包含分析范围、顶级风险和未解决决策
7. 按严重性返回发现：
   - blocker
   - warning
   - info
8. 每个发现包含：
   - 文件/路径引用
   - 失败模式
   - 具体修复方向
9. 如果没有问题，明确说明并列出残余风险
</process>
