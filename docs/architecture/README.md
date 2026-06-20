# OntologyAgent 平台架构与规范文档

> **版本**：0.1.0（MVP）
> **最后更新**：2026-06-20
> **状态**：编写中

---

## 文档导航

本目录包含 OntologyAgent 平台的**架构设计与工程实施规范**。与本目录配套的设计决策文档为：

| 文档 | 路径 | 性质 |
|------|------|------|
| **目标架构设计（三文档合一）** | [`../superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md`](../superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md) | **权威设计文档**——定方向、消冲突、明边界。回答"做什么"和"不做什么" |
| **业务本体建模规范** | [`../业务本体建模规范.md`](../业务本体建模规范.md) | 本体建模的命名约定、格式规范、Anti-pattern |
| **Palantir 参考摘要** | [`../palantir-ontology-docs/summary.md`](../palantir-ontology-docs/summary.md) | Palantir Foundry Ontology 精读笔记，设计决策的参考来源 |

**本目录文档**是上述设计文档的**工程化细化**——回答"怎么实现"和"怎么开发"。不重复设计决策，侧重于可执行的规范、接口定义和开发步骤。

### 本目录文档

| 文档 | 内容 | 读者 |
|------|------|------|
| [**系统架构**](./system-architecture.md) | 五层架构总览、核心概念模型、模块设计、数据流、技术选型、目录结构、部署架构 | 所有开发者 |
| [**API 与数据契约**](./api-and-data-spec.md) | AG-UI 端点、Tool Schema、Action Type 契约、数据模型 JSON Schema、Skill 格式、多租户传递链路 | 后端 / 全栈开发者 |
| [**平台开发规范**](./development-guide.md) | 本体开发、Tool 开发、Skill 开发、权限开发、错误处理、多租户开发、代码规范、测试规范 | 所有开发者 |

### 阅读顺序

```
1. 系统架构           ← 先读这个，建立全局认知
2. API 与数据契约     ← 了解接口和数据格式
3. 平台开发规范       ← 动手开发前参考
```

如果是新加入项目的开发者，建议额外阅读：
- [`README.md`](../../README.md)（项目根目录）——快速了解项目背景和启动方式
- 目标架构设计文档 ——了解设计决策和 MVP/v2 边界

---

## 术语表

### 核心概念

| 术语 | 英文 | 定义 |
|------|------|------|
| **本体** | Ontology | 描述领域世界的结构化知识——实体类型（Object Type）、关系类型（Link Type）、行为契约（Action Type）的声明式定义 |
| **Object Type** | Object Type | 业务实体类型定义，如"门店"、"员工"、"临期商品" |
| **Link Type** | Link Type | 两个 Object Type 之间的关系定义，如"门店位于区域"、"员工属于门店" |
| **Action Type** | Action Type | 声明式变更契约——描述受治理的业务事务（参数 + 约束 + submission criteria + 副作用），如"出清"、"调拨" |
| **Tool** | Tool | LLM 可直接调用的函数，schema 注入 prompt，LLM 决定何时调用 |
| **Skill** | Skill | 给 LLM 读的指令文档（SKILL.md），描述流程编排、领域知识、策略指南 |
| **计算逻辑** | Computation Logic | 普通 Python 模块，被多个 Tool/Action 复用的纯计算函数（如折扣计算） |
| **Interface Type** | Interface Type | 抽象类型定义，跨 Object 共享形状（v2，MVP 不实现） |

### 平台术语

| 术语 | 英文 | 定义 |
|------|------|------|
| **通用内核** | Core Kernel | 平台的通用能力层——本体元数据 + CRUD + 多租户抽象 + 权限/审计 + Agent harness + Tool/Skill 体系 |
| **Vertical** | Vertical | 行业特化层——在通用内核之上构建的领域实体与工作流，如零售 vertical |
| **Preview→Confirm** | Preview→Confirm | 人机协作模式——Tool 先生成预览（不修改数据），用户确认后执行 |
| **edits-only-via-actions** | edits-only-via-actions | 治理强制机制——核心业务实体的写操作只能通过 Action Type 执行，通用 CRUD 被拦截 |
| **tenant** | Tenant | 多租户隔离单位，通过 `tenant_id` 在 Repository 层过滤实现数据隔离 |
| **Repository** | Repository | 数据访问抽象层——上层工具/Agent 不直接操作文件，统一通过 Repository 接口读写 |
| **EntityRegistry** | EntityRegistry | 本体元数据的内存注册表——由 Parser 从 TTL/YAML 加载，提供 Object/Link/Action Type 的查找 |
| **Preview ID** | preview_id | Preview→Confirm 治理闭环的关联标识——execute_action 生成，confirm_action 校验 |

### 前端术语

| 术语 | 英文 | 定义 |
|------|------|------|
| **Generative UI** | Generative UI | CopilotKit 的核心能力——Tool 返回结构化数据，前端根据 Tool 名和状态动态渲染 UI 组件 |
| **AG-UI** | AG-UI Protocol | CopilotKit 定义的前后端通信协议（Agent-UI Protocol），基于 SSE 流式传输 |
| **renderToolCalls** | renderToolCalls | CopilotKit React 组件，根据 Tool 名匹配渲染函数，展示 Tool 执行过程和结果 |
| **COPILOTKIT_DATA** | COPILOTKIT_DATA | Tool 返回值中嵌入 JSON 数据的约定格式——`<!--COPILOTKIT_DATA-->...\n<!--/COPILOTKIT_DATA-->` |

### 参考来源

| 术语 | 英文 | 定义 |
|------|------|------|
| **Palantir Foundry** | Palantir Foundry | AIP 领域的本体驱动平台，是 OntologyAgent 的设计参考。核心区别：Foundry 消费者是人+应用，OntologyAgent 消费者是 LLM |
| **Function** | Function（Palantir） | Palantir 的命名计算单元（有类型、版本、沙箱）。OntologyAgent **不引入**此概念——Tool 就是 LLM 时代的 Function |
| **Submission Criteria** | Submission Criteria | Palantir 的细粒度门控——给定 user + parameter，此 Action 实例能否提交。独立于粗粒度 RBAC |
| **Deep Agents** | Deep Agents | `cauchyturing/deepagents` 库——LangGraph Agent 框架，提供工具循环、SummarizationMiddleware、SkillsMiddleware |
| **CopilotKit** | CopilotKit | `copilotkit/react-core` ——前端 Agent 框架，提供 Chat UI、Generative UI、Shared State、AG-UI 协议 |
