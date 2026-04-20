---
name: fad:pipeline
description: 统一 FAD 交付流水线，从需求到交付，严格 review/optimize 门禁
argument-hint: "<需求或阶段> [--mode brownfield|greenfield]"
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
运行一个端到端流水线，包含明确的阶段、严格的质量门禁和完整的审计跟踪。
</objective>

<context>
输入: $ARGUMENTS

阶段命令:
- @.claude/commands/fad/optimize.md
- @.claude/commands/fad/quality-gate.md
- @.claude/commands/fad/ship.md
- @.claude/commands/fad/pr-branch.md
- @.claude/commands/review.md

审计/日志:
- @.claude/scripts/audit_log.py
- @.planning/pm/current/

交付物:
- @.planning/pm/current/
</context>

<process>
1. 解析输入，确定运行模式（brownfield 或 greenfield）
2. 生成 run ID 并创建审计记录：
   - 运行 `python3 .claude/scripts/audit_log.py --step fad-pipeline-start --command "fad:pipeline" --goal "$ARGUMENTS" --status done`
   - 捕获 `run_id` 并用于每个阶段的日志
3. 理解需求阶段：
   - 明确需求范围
   - 确定是 greenfield 新功能还是 brownfield 改进
4. 规划/执行阶段：
   - brownfield 模式：先运行 `fad:map-codebase` 了解项目结构
   - 拆分任务，编写实现计划
5. 验证阶段：
   - 运行基础测试验证
6. Review 阶段（严格）：
   - 运行 `review`
   - 阻塞级问题必须解决
7. 优化阶段（发布前必须）：
   - 运行 `fad:optimize`
   - 保持行为稳定
8. 质量门禁阶段（严格）：
   - 运行 `fad:quality-gate`
   - lint/类型检查/测试失败或高危风险未解决则阻塞
9. 结束分支阶段：
   - 如果所有门禁通过，提供：
     - 创建干净 PR 分支 (`fad:pr-branch`)
     - 打开 PR / 发布流程 (`fad:ship`)
     - 继续开发
10. 为每个阶段追加 markdown 审计日志到 `.planning/audit/runs/<run_id>/`
11. 返回简洁流水线报告：
    - run_id
    - 各阶段状态
    - 门禁结果
    - 阻塞/风险
    - 推荐下一步命令
</process>
