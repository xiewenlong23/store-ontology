# Audit Logging Runbook — 门店本体项目

> 来源：昊晴整理 | 作者：谢文龙团队 | 时间：2026-04-22
> 标签：store-ontology, 审计日志, 运营, 本体迭代
> 描述：store-ontology 项目审计日志的记录规范和路径

---

## 一、审计日志路径

### 标准路径（首选）

```
.planning/audit/runs/<run-id>/<timestamp>-<step>.md
```

示例：

```
.planning/audit/runs/run-20260422/174536-discovery.md
.planning/audit/runs/run-20260422/174612-build.md
.planning/audit/runs/run-20260422/174720-qc-verify.md
.planning/audit/runs/run-20260422/174845-review.md
```

### 遗留路径（兼容）

```
.planning/audit/*.md
```

---

## 二、日志记录命令

```bash
# 记录一个新步骤
python3 .claude/scripts/audit_log.py \
  --step fad-pipeline-start \
  --command "fad:pipeline" \
  --goal "LLM Agent 多步工作流迭代" \
  --status done \
  --pretty

# 追加到已有 run
python3 .claude/scripts/audit_log.py \
  --run-id run-20260422 \
  --step optimize \
  --command "fad:optimize" \
  --goal "双重渲染修复" \
  --status done
```

### 常用参数

| 参数 | 说明 |
|---|---|
| `--run-id` | 追加到已有 run |
| `--status` | `done` / `done_with_concerns` / `blocked` / `needs_context` |
| `--artifact` | 可重复输出的产物 |
| `--next-action` | 建议的后续步骤 |

---

## 三、最低覆盖要求

每个 FAD pipeline 迭代至少记录以下步骤：

| 步骤 | 说明 |
|---|---|
| `discovery` | 需求理解与对齐 |
| `build` | 构建执行 |
| `qc-verify` | QC 验证 |
| `review` | 代码/设计 review |
| `optimize` | 优化（无行为改变）|
| `quality-gate` | 严格质量门禁 |
| `incident` | 故障时记录 |
| `rollback` | 回滚时记录 |

---

## 四、store-ontology 项目的关键审计节点

| 迭代事件 | 审计内容 |
|---|---|
| TTL 本体修改 | 变更内容、triples 数量变化、验证结果 |
| SPARQL 查询修复 | 修复原因、原查询错误、新查询逻辑 |
| Agent 执行器改进 | System Prompt 变更、工具调用链路变化 |
| 数据层调整（app/data → data）| 路径变更影响、修复操作 |
| 前端双重渲染修复 | 根因分析、修复方案、验证结果 |

---

## 五、为什么重要

- 端到端追溯每个需求的全生命周期
- 保留风险决策和工具证据
- 支持跨团队成员和机器的可复现性
- 本体迭代历史的权威记录（类/属性/规则变更均可追溯）
