---
name: fad:optimize
description: review 之后的代码质量和性能优化
argument-hint: "[可选：优化范围]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

<objective>
在保持行为不变的前提下，改善代码质量和性能。
</objective>

<context>
项目：store-ontology
根目录：/mnt/d/ObsidianVault/store-ontology

参考：
- @.claude/commands/review.md
- @.planning/pm/current/RISK-IMPACT.md
- @.claude/scripts/audit_log.py
</context>

<process>
## Step 1：确定优化范围
从变更文件或参数中确定本次优化的范围。

## Step 2：Review 结果回顾
读取最新 review 发现的问题和 RISK-IMPACT.md 中的风险项。

## Step 3：执行优化
聚焦以下方向：
1. **删除重复代码** — 相同逻辑出现多次的地方合并
2. **移除死分支** — 永远不走的 if/else 分支删除
3. **改善命名** — 让变量/函数名自解释
4. **改进模块边界** — 职责不清的模块重新划分
5. **性能热点** — N+1 查询、不必要的循环、明显的内存浪费

## Step 4：保持行为不变
- 优化期间不得改变功能行为
- 如发现行为需要改变，停止并请求新的 scoped 任务

## Step 5：验证
1. TTL 语法验证：`rapper -i turtle -o ntriples file://<ttl_path>`
2. Python 测试：`PYTHONPATH=/mnt/d/ObsidianVault/store-ontology pytest`
3. 质量门：`python3 .claude/scripts/code_quality_gate.py --repo-root /mnt/d/ObsidianVault/store-ontology`

## Step 6：写审计日志
`python3 .claude/scripts/audit_log.py --step fad-optimize --command "fad:optimize" --status done --goal "$ARGUMENTS"`

## 输出
- 优化了哪些区域
- 行为不变的保证
- 质量门结果
- 剩余技术债
</process>
