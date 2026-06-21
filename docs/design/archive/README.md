# 归档文档

> **🗄 本目录是只读历史归档。** 所有文档均已被 `docs/design/` 下的权威版本取代。**请勿据此实施**——路径与术语均已过时。保留作决策追溯与历史脉络。

## 取代映射表

| 归档文档 | 原位置 | 被谁取代 |
|---------|--------|---------|
| `legacy-项目设计文档.md` | `docs/项目设计文档.md` | [`00-architecture.md`](../00-architecture.md) + [`industry-packs/retail-clearance.md`](../industry-packs/retail-clearance.md) |
| `legacy-ontologyagent-design-CN.md` | `docs/ontologyagent-design-CN.md` | [`00-architecture.md`](../00-architecture.md)（三文档 reconcile 的单一权威） |
| `legacy-Harness-Design.md` | `docs/Harness-Design.md` | [`roadmap.md`](../roadmap.md)（前瞻部分摘要，标"未实现"） |
| `legacy-system-architecture.md` | `docs/architecture/system-architecture.md` | [`00-architecture.md`](../00-architecture.md)（合并） |
| `legacy-api-and-data-spec.md` | `docs/architecture/api-and-data-spec.md` | [`20-api-data-contract.md`](../20-api-data-contract.md)（治愈） |
| `legacy-development-guide.md` | `docs/architecture/development-guide.md` | [`30-development-guide.md`](../30-development-guide.md)（治愈） |
| `legacy-architecture-README.md` | `docs/architecture/README.md` | [`README.md`](../README.md)（全 design 导航） |
| `legacy-业务本体建模规范.md` | `docs/业务本体建模规范.md` | [`40-ontology-modeling-spec.md`](../40-ontology-modeling-spec.md)（治愈） |
| `legacy-manual/` | `docs/manual/`（5 文档 + 8 模板） | [`manual/`](../manual/)（4 文档 + 8 模板重写，对齐 pack 模型） |
| `superpowers/specs/` | `docs/superpowers/specs/`（5 + 1 本项目 spec） | brainstorming 设计决策，产物并入 [`docs/design/`](../) 权威文档 |
| `superpowers/plans/` | `docs/superpowers/plans/`（4 + 1 本项目 plan） | brainstorming 实施计划，产物已实现 |

## 归档原则

- **不编辑内容**：原文完整保留，仅在顶部加"被谁取代"头注。
- **可追溯**：每份文档能查到"它说了什么、为什么被取代、取代者是谁"。
- **不据此实施**：路径（`backend/`、`verticals/`）与术语（`vertical`、`customer_id`）均已过时。

## 为什么保留

- **决策脉络**：理解"为什么这么设计"需要历史上下文（如三文档 reconcile 的张力来源）。
- **变更追溯**：从 brainstorming spec → plan → 实现 的完整链条可查。
- **回滚参考**：若新设计有问题，可回看被取代版本。
