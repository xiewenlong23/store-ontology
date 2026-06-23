# OntologyAgent 设计文档

> **单一权威入口。** 本目录是 OntologyAgent 平台所有设计/规范文档的家。每份文档顶部有状态徽章，标明它是当前生效、前瞻未实现、还是已归档历史。

## 状态徽章图例

| 徽章 | 含义 | 处置 |
|------|------|------|
| ✅ **当前** | 已实现、生效中 | 据此实施、据此理解现状 |
| 🔮 **前瞻** | 方向性设计、**尚未实现** | 仅参考，不可据此认为已落地 |
| 🗄 **归档** | 历史文档，已被取代 | 只读追溯，**不可据此实施** |
| 📚 **参考** | 第三方资料 | 背景阅读，非本平台自有规范 |

## 文档导航

### 权威与规范（✅ 当前）

| 文档 | 路径 | 一句话说明 |
|------|------|-----------|
| **平台架构（单一权威）** | [`00-architecture.md`](./00-architecture.md) | 五层架构、四概念分工、内核/工作目录边界。平台架构的**唯一**权威来源 |
| **API 与数据契约** | [`20-api-data-contract.md`](./20-api-data-contract.md) | AG-UI 端点、Tool Schema、Action Type 契约、workspace 传递链路 |
| **平台开发规范** | [`30-development-guide.md`](./30-development-guide.md) | 本体/Tool/Skill 开发步骤、权限、错误处理、测试规范 |
| **业务本体建模规范** | [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md) | 建模硬规范：命名、元数据、via 归属、Action 边界、反模式 |

### 演进路线（部分已落地）

| 文档 | 路径 | 一句话说明 |
|------|------|-----------|
| **演进路线** | [`roadmap.md`](./roadmap.md) | v2 方向：存储/权限/本体深化/自动化/多 Agent/UI。每节带 ✅/🔜 标注，部分已落地、部分前瞻 |

### 接入手册（✅ 当前）

| 文档 | 路径 | 一句话说明 |
|------|------|-----------|
| **接入总览** | [`manual/00-overview.md`](./manual/00-overview.md) | 内核/工作目录边界、何时建工作目录、阅读路线 |
| **接入手册** | [`manual/01-onboarding.md`](./manual/01-onboarding.md) | 新工作目录接入的 Phase A-F 标准流程 |
| **模板说明** | [`manual/02-templates.md`](./manual/02-templates.md) | 8 个模板的占位符填法与常见错误 |
| **Worked Example** | [`manual/03-worked-example-customerA.md`](./manual/03-worked-example-customerA.md) | 设备维修工作目录端到端实例 |
| **模板** | [`manual/templates/`](./manual/templates/) | 8 个可填模板（workspace.py / action.yaml / ...） |

### 参考（📚 第三方）

| 资料 | 路径 | 说明 |
|------|------|------|
| **Palantir Foundry Ontology 精读** | [`reference/palantir-ontology-docs/`](./reference/palantir-ontology-docs/) | 本平台本体设计的主要参考来源（只读） |
| **Palantir 功能需求清单** | [`palantir-ontology-functional-requirements.md`](./palantir-ontology-functional-requirements.md) | 从 Palantir 资料提炼的功能需求清单（36 节、~350 条 F-XX-NN），只描述 Palantir 侧能力 |
| **Palantir 功能需求实现识别** | [`palantir-implementation-assessment.md`](./palantir-implementation-assessment.md) | 对需求清单的项目侧实现识别（四档判定：完全/部分/转换/不建议），含优先级建议 |

### 归档（🗄 历史）

| 资料 | 路径 | 说明 |
|------|------|------|
| **归档文档** | [`archive/`](./archive/) | 3 份被取代的平台设计 + brainstorming specs/plans。每份顶部有"被谁取代"头注 |

## 阅读路线

- **第一次理解架构** → [`00-architecture.md`](./00-architecture.md) → [`40-ontology-modeling-spec.md`](./40-ontology-modeling-spec.md)
- **第一次接入新工作目录** → [`manual/00-overview.md`](./manual/00-overview.md) → [`manual/01-onboarding.md`](./manual/01-onboarding.md) → 卡住查 [`manual/02-templates.md`](./manual/02-templates.md) → 对照 [`manual/03-...`](./manual/03-worked-example-customerA.md)
- **看 API/契约** → [`20-api-data-contract.md`](./20-api-data-contract.md)
- **看前瞻方向** → [`roadmap.md`](./roadmap.md)（注意：**未实现**）
- **查历史决策** → [`archive/`](./archive/)

## 术语基线

全目录统一术语（对齐活代码 `agent/engine/` + `workspace/` 模型）：

| 术语 | 含义 | 取代的旧术语 |
|------|------|-------------|
| **workspace**（`workspace_name`） | 硬隔离边界 | customer / tenant（笼统） |
| **org_unit**（`org_unit_id`） | workspace 内权限范围（`*`=总部全可见） | — |
| **TenantContext** | workspace + org_unit 双层上下文（代码类名保留） | — |
| **工作目录**（WorkspaceDef） | 业务场景包，`workspace/<name>/workspace.py` 声明 | vertical |
| **能力域**（CapabilityDomain） | 原子 Object/Link/Action，`ontology/domains/<域>/` | — |
| **价值链流程**（ValueChainProcess） | 跨域编排（状态机+Skill+工具），如 clearance/repair | — |

`vertical` 一词仅保留在 `archive/`（历史）和必要兼容说明里。`backend/`、`verticals/` 路径已全部治愈为 `agent/engine/`、`workspace/`。
