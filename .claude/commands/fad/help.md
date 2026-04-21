---
name: fad:help
description: 显示 FAD 命令列表和使用指南
---

<objective>
提供 FAD 工作流的简洁入口说明。
</objective>

## FAD 命令

| 命令 | 说明 |
|------|------|
| `/fad:pipeline` | 端到端交付流水线（发现→计划→构建→review→优化→质量门） |
| `/fad:optimize` | review 之后的代码质量/性能优化 |
| `/fad:help` | 本帮助 |

## 支持命令

| 命令 | 说明 |
|------|------|
| `/review` | 严重级别优先的代码审查 |
| `/code-quality-gate` | lint + test 质量门检查 |

## 工作目录

- 项目根目录：`/mnt/d/ObsidianVault/store-ontology`
- FAD 命令目录：`.claude/commands/fad/`
- 审计日志：`.planning/audit/runs/`
- 风险文档：`.planning/pm/current/RISK-IMPACT.md`

## 快速开始

```
/fad:pipeline <任务描述>  # 新功能/需求
/fad:optimize            # 优化现有代码
/review                   # 审查代码变更
```
