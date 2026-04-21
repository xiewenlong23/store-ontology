---
name: fad:pipeline
description: 端到端交付流水线，从需求到完成交付
argument-hint: "<任务描述>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

<objective>
跑一个完整的端到端流水线，包含明确的阶段、严格的质量门、完整的审计追踪。
</objective>

<context>
项目：store-ontology（门店自动化运营本体）
根目录：/mnt/d/ObsidianVault/store-ontology
技术栈：Python (FastAPI) + React + TTL/RDF 本体论

关键参考：
- @.claude/commands/review.md
- @.claude/commands/fad/optimize.md
- @.claude/scripts/audit_log.py
- @.planning/pm/current/RISK-IMPACT.md
</context>

<process>
## Phase 1：理解需求
1. 解析用户输入，生成 run_id
2. 运行：`python3 .claude/scripts/audit_log.py --step fad-pipeline-start --command "fad:pipeline" --goal "$ARGUMENTS" --status done`
3. 确认工作范围和边界

## Phase 2：发现与分析
1. 分析现有代码结构（TTL 本体、FastAPI、React）
2. 检查相关模块的现状
3. 识别风险和依赖

## Phase 3：规划与执行
1. 制定实现计划
2. TDD 方式实现（先写测试）
3. TTL 本体修改需用 rapper 验证语法
4. Python 代码需保持向后兼容

## Phase 4：Review
1. 运行 `/review` 进行严重级别优先审查
2. blocker 级别问题必须修复后才能继续

## Phase 5：优化（必须）
1. 运行 `/fad:optimize`
2. 消除重复代码、死分支
3. 改善命名和模块边界
4. 不得改变行为/需求

## Phase 6：质量门（必须）
1. 运行 `python3 .claude/scripts/code_quality_gate.py --repo-root /mnt/d/ObsidianVault/store-ontology`
2. TTL 语法检查：`rapper -i turtle -o ntriples`
3. Python 测试（如有）：`PYTHONPATH=/mnt/d/ObsidianVault/store-ontology pytest`
4. 安全扫描：`python3 .claude/scripts/secrets_scan.py`

## Phase 7：交付
1. 所有质量门通过后，提供：
   - 变更摘要
   - 测试结果
   - 剩余风险
2. 询问是否创建 PR 或保留分支继续开发

## 审计日志
每个阶段完成后追加日志到 `.planning/audit/runs/<run_id>/`
</process>
