---
name: code-quality-gate
description: 运行 lint、类型检查（如果有 TS）和测试
argument-hint: "[--strict-missing]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

<objective>
执行一致的质量门禁并输出机器可读的证据。
</objective>

<context>
输入: $ARGUMENTS

References:
- @.claude/scripts/code_quality_gate.py
- @.claude/rules/testing.md
</context>

<process>
1. 解析仓库根目录（默认当前工作区）
2. 运行质量检查：
   - Python: `pytest tests/ -v`
   - Frontend: `npm test` 或检查测试文件存在
3. 检查 lint：
   - Python: `ruff check .` 或 `flake8 .`
4. 检查类型（如果配置）：
   - Python: `mypy app/`
5. 如果 `--strict-missing` 传入，缺失检查脚本视为失败
6. 处理检查结果：
   - `failed` => 阻塞构建/部署
   - `passed` with skipped => 继续但报告 `done_with_concerns`
7. 写审计日志
8. 返回简洁门禁摘要和阻塞项
</process>
