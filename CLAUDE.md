# Store-Ontology AI Delivery Pipeline

## 项目概述

门店大脑 AI 原生应用本体论项目 —— 飞书小程序为前端，TTL 本体为业务语义层，AI 通过 SPARQL 查询本体 + 推理执行任务。

核心场景：**临期打折**（当前唯一），后续扩展补货/盘点/排班。

## 架构

- `app/` — FastAPI 后端（任务管理、折扣推理）
- `frontend/` — React 前端（飞书小程序）
- `modules/` — TTL 本体模块（OWL/Turtle）
- `examples/` — 示例数据和规则引擎
- `validation/` — 本体验证工具
- `tests/` — API 和业务逻辑测试

## 核心命令

| 命令 | 说明 |
|------|------|
| `/fad:pipeline` | 端到端交付流程 |
| `/fad:optimize` | 编码后优化 |
| `/fad:quality-gate` | 严格质量门禁 |
| `/fad:map-codebase` | 项目架构/约定映射 |
| `/review` | 代码审查 |
| `/pm-to-build` | PM 交付物转执行 |

## 交付物规范

PM 交付包存于 `.planning/pm/current/`:
- `PRD.md` — 产品需求（含需求 ID）
- `SPRINT.md` — 当前 Sprint 范围
- `STORIES.md` — 用户故事和验收标准
- `HANDOFF.md` — 工程约束、设计输入、风险
- `RISK-IMPACT.md` — 风险登记和影响地图

## 质量门禁

- 每次实现后必须运行 `review`
- `fad:optimize` 必须在 review 之后
- `fad:quality-gate` 是发布的硬性门禁
- 高危/阻塞风险未解决不得发布

## 代码规范

- Python: Pydantic models, Enum, type hints
- React: functional components, hooks
- TTL: OWL2 DL, 标准本体建模
- 测试: pytest, 隔离数据

## 审计规则

每个关键步骤必须写入审计日志：
`.planning/audit/runs/<run-id>/`
