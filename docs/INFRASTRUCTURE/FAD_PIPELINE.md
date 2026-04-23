# FAD Pipeline Runbook — store-ontology 项目

> 更新时间：2026-04-22
> 定位：store-ontology 项目的 FAD pipeline 使用说明

---

## 一、概述

store-ontology 项目使用 FAD（Feature/Agent/Delivery）pipeline 作为主要交付工作流，通过 `/fad:pipeline` 命令驱动从需求到交付的完整流程。

![FAD Pipeline Overview](../assets/fad-pipeline-overview.svg)

---

## 二、标准执行

```bash
/fad:pipeline "<requirement or phase>"
```

The pipeline enforces:

1. **Brainstorm / Discovery** — 需求理解与对齐
2. **Build** — 构建执行，带需求追溯
3. **Review Gate** — 代码/设计 review
4. **Optimize Gate** — 优化（无行为改变）
5. **Strict Quality Gate** — 严格质量门禁
6. **Finish / Ship** — 完成或发布

---

## 三、store-ontology 项目常用命令

### 完整交付流程
```bash
/fad:pipeline "LLM Agent 多步工作流迭代"
```

### 代码优化
```bash
/fad:optimize
```

### 代码审查
```bash
/fad:code review
```

### 质量门禁
```bash
/fad:quality-gate
```

---

## 四、门禁语义

| 门禁 | 阻塞条件 |
|------|---------|
| **Review** | 未解决的 blocker findings |
| **Optimize** | 必须避免行为改变 |
| **Strict Quality Gate** | lint/typecheck/test 失败、安全/密钥发现、未解决的高危/严重风险 |

---

## 五、相关命令

- `/fad:optimize` — 代码优化
- `/fad:quality-gate` — 质量门禁
- `/deploy <env>` — 部署到指定环境
- `/fix-issue` — 修复问题
- `/review` — 代码审查

---

## 六、审计日志

每个 FAD pipeline 迭代应记录审计日志：

```bash
python3 .claude/scripts/audit_log.py \
  --step fad-pipeline-start \
  --command "fad:pipeline" \
  --goal "<requirement>" \
  --status done
```

详见 `docs/OPERATIONS/AUDIT_LOGGING.md`
