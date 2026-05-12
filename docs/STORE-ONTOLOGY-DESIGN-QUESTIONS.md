# 门店大脑（store-ontology）项目设计问题清单

> 编制日期：2026年5月12日
> 编制人：昊晴（AI助手）
> 用途：FAD 设计阶段问题发现与对齐，为正式构建提供决策依据
> 参考：CopilotKit+LangGraph+DeepAgents架构方案（飞书文档 ZE57dJSaaoaza4x2YLNcoSOenAc）

---

## 一、项目背景与目标

### 1.1 核心问题（需明确回答）

- [ ] **Q1**：门店大脑的**核心用户是谁**？总部运营人员？门店店长？店员？
- [ ] **Q2**：门店大脑的**核心场景**是什么？临期折扣？任务派发？陈列调整？库存查询？
- [ ] **Q3**：AI 对话是**面向顾客**还是**面向员工**？这决定了权限边界和交互设计
- [ ] **Q4**：当前是否有**飞书小程序**或 Web 前端？还是从零开始？

### 1.2 成功标准

- [ ] **Q5**：如何衡量项目成功？核心 KPI 是什么？（响应准确率/任务完成率/用户满意度）
- [ ] **Q6**：是否有**试点门店**可供验证？第一期覆盖多少家店？

---

## 二、技术架构选型

> 参考：飞书文档第三章「CopilotKit + LangGraph 官方集成证据」

### 2.1 前端框架

- [ ] **Q7**：前端选 **CopilotKit** 还是自研对话 UI？CopilotKit 的渐进式渲染和流式响应是否满足需求？
- [ ] **Q8**：是否需要支持**多端**（飞书小程序/Web/App）？多端是否共用同一 Agent 后端？
- [ ] **Q9**：前端身份注入（`identifyUser`）是否需要对接**飞书 SSO**？当前飞书小程序的登录态如何获取？

### 2.2 后端 Agent 框架

- [ ] **Q10**：选 **Deep Agents** 还是 **LangGraph**？
  - Deep Agents：per-tool interrupt 配置简单，适合开箱即用的人工审批
  - LangGraph：底层控制精确，适合需要精确编排执行流的场景
  - **建议**：先 Deep Agents，验证后再考虑 LangGraph

- [ ] **Q11**：是否需要 **LangGraph Platform**（云托管）？还是 FastAPI 自托管？
  - LangGraph Platform：支持 `@auth.authenticate` 装饰器，权限验证更规范
  - FastAPI 自托管：成本更低，需要自己实现 auth 注入

- [ ] **Q12**：模型选型？当前 DashScope API Key 是否可用于生产？（`minimax:MiniMax-M2.7-flash`）

### 2.3 部署方式

- [ ] **Q13**：部署环境是 **K8s/Docker** 还是**单机服务**？
- [ ] **Q14**：是否需要 **多门店多租户**部署？每个门店独立实例还是共享实例？

---

## 三、本体建模（TBOX / ABOX）

> 参考：飞书文档第十六章「16.4 本体建模：TBOX/ABOX 分离」

### 3.1 TBOX 设计（业务规则结构定义）

- [ ] **Q15**：TBOX 本体文件格式选 **TTL（Turtle）** 还是 **OWL**？还是 JSON Schema？
- [ ] **Q16**：哪些业务规则**必须进 TBOX**？哪些可以进 Skill 代码？
  - TBOX 适合：折扣规则、审批流程、品类分类
  - Skill 代码适合：计算逻辑、API 调用、外部系统对接

- [ ] **Q17**：临期折扣规则的**层级划分**（T1/T2/T3）是否已确定？品类是否完整覆盖？
- [ ] **Q18**：豁免规则（进口食品/有机商品）是否已定义？替代操作是什么？

### 3.2 ABOX 设计（业务实例数据）

- [ ] **Q19**：ABOX 数据存储选型？
  - **JSON 文件**：简单，适合小规模数据（< 10万条）
  - **PostgreSQL**：关系型，适合结构化业务数据
  - **Neo4j/NebulaGraph**：图数据库，适合实体关系复杂场景

- [ ] **Q20**：商品主数据（品名/品类/保质期）从哪个系统接入？ERP？WMS？手工录入？
- [ ] **Q21**：任务实例（DiscountTask/WorkTask）是否需要**状态机**？pending → approved → executed？

### 3.3 SPARQL 查询层

- [ ] **Q22**：SPARQL 查询引擎选 **RDFLib**（本地）还是 **GraphDB**（远程）？
- [ ] **Q23**：TBOX 和 ABOX 是否**合并查询**还是分开查询？分开的话如何做 JOIN？

---

## 四、Agent 运行时态编排

> 参考：飞书文档第十六章「16.5 Agent 运行时态：编排与多 Agent」

### 4.1 Skill 体系设计

- [ ] **Q24**：第一期上线哪几个 **Skill**？
  - 建议优先级：临期折扣 Skill（核心）> 任务管理 Skill > 商品查询 Skill

- [ ] **Q25**：Skill 的 **SKILL.md 格式**是否已定义？`allowed-tools` 字段是否必须？
- [ ] **Q26**：Skill 之间的**优先级和冲突处理**规则是什么？

### 4.2 多 Agent 编排

- [ ] **Q27**：是否需要 **Subagent** 隔离？例如：临期分析 Subagent / 审批 Subagent / 对话 Subagent
- [ ] **Q28**：Deep Agents 的 **subagents** 配置是否满足需求？还是需要 LangGraph 底层自定义？

### 4.3 HITL（人工审批）

- [ ] **Q29**：哪些操作需要 **HITL 人工审批**？
  - 建议：折扣 > 20%、新建任务、修改商品数据
  - 建议：纯查询不审批

- [ ] **Q30**：HITL 审批的 **allowed_decisions** 如何配置？
  - 高风险：`["approve", "edit", "reject"]`
  - 中风险：`["approve", "reject"]`
  - 必须审批：`["approve", "edit"]`（不允许拒绝）

- [ ] **Q31**：审批人是**店长**还是**总部**？审批时效要求是多少？

---

## 五、权限控制

> 参考：飞书文档第十六章「16.6 权限控制」

### 5.1 身份与角色

- [ ] **Q32**：角色体系是否已定义？
  - 总部：查看全部门店数据、修改折扣规则
  - 店长：管理本店、审批本店折扣（限额）
  - 店员：查询本店商品、发起折扣申请（不能审批）

- [ ] **Q33**：`user_id@store_id` 组合身份是否满足 **多门店多租户**需求？

### 5.2 数据权限（ABOX 过滤）

- [ ] **Q34**：所有 SPARQL 查询是否必须带 **store_id 过滤**？无 store_id 时是否返回空结果？
- [ ] **Q35**：店员是否可以查看其他门店的数据？总部是否可以查看全部门店？

### 5.3 Skill 粒度权限

- [ ] **Q36**：店员是否可以使用**所有 Skill**？还是只能使用查询类 Skill？
- [ ] **Q37**：SKILL.md 的 `allowed-tools` 字段是否可以动态配置？还是写死在文件里？

---

## 六、审计

> 参考：飞书文档第十六章「16.7 审计」

### 6.1 审计内容

- [ ] **Q38**：哪些操作必须**审计日志**？
  - 建议：Agent 调用、工具执行、HITL 审批、异常错误

- [ ] **Q39**：审计日志的**存储介质**是什么？
  - 结构化日志（structlog）→ 文件 / ELK / Loki
  - 数据库 → PostgreSQL audit table

- [ ] **Q40**：审计日志是否需要**防篡改**？（output_hash 字段）

### 6.2 HITL 审批记录

- [ ] **Q41**：每次审批是否记录 **approver_id / decision / comment**？
- [ ] **Q42**：审批记录是否需要**回溯查询**？（按 user_id / store_id / task_id 查询）

---

## 七、可观测性

> 参考：飞书文档第十六章「16.8 可观测性」

### 7.1 LangSmith 接入

- [ ] **Q43**：是否接入 **LangSmith**？需要 API Key 和项目名称
- [ ] **Q44**：LangSmith 追踪哪些内容？
  - Skill Match 决策
  - Tool 调用链路（Tool name / 参数 / 执行时间）
  - TBOX SPARQL 查询
  - ABOX 数据过滤
  - HITL 中断/恢复

### 7.2 结构化日志

- [ ] **Q45**：生产环境使用什么日志格式？
  - 建议：JSON 格式（structlog）→ 统一采集到 ELK / Loki
  - 建议字段：`timestamp / user_id / store_id / action / tools_used / session_id`

### 7.3 CopilotKit Inspector

- [ ] **Q46**：开发环境是否启用 **CopilotKit Inspector**（浮层调试工具）？

---

## 八、外部系统对接（MCP）

> 参考：飞书文档第十六章「16.3 后端 Agent」和飞书文档第十四章「MCP 开放协议」

- [ ] **Q47**：是否需要对接 **ERP / WMS / CRM**？
  - 如果是：发布为 MCP Server，通过 `langchain-mcp-adapters` 接入
  - 如果否：跳过 MCP，直接用 Python 工具

- [ ] **Q48**：MCP Server 由谁开发和维护？门店 IT 还是外部系统厂商？

---

## 九、非功能性需求

### 9.1 性能

- [ ] **Q49**：单次对话响应时间 **SLA** 是多少？（建议 < 3秒）
- [ ] **Q50**：高峰期并发用户数预估？（影响 Agent 实例数量）

### 9.2 安全

- [ ] **Q51**：LLM 输出是否需要 **内容安全过滤**？（防止 AI 生成错误的折扣决策）
- [ ] **Q52**：敏感数据（商品进价、供应商信息）是否需要**脱敏**？

### 9.3 合规

- [ ] **Q53**：门店 AI 应用是否需要符合**零售行业数据合规**要求？
- [ ] **Q54**：折扣决策是否需要留存**决策依据**供审计？

---

## 十、落地里程碑建议

> 参考：飞书文档第十六章「16.10 落地里程碑」

| 阶段 | 内容 | 优先级 | 前提条件 |
|------|------|--------|---------|
| Phase 1 | CopilotKit 前端集成（identifyUser + SSE 流式）| P0 | Q4/Q8/Q9 |
| Phase 2 | Deep Agents 后端部署（create_deep_agent） | P0 | Q10/Q11/Q12 |
| Phase 3 | 第一个 Skill 上线（临期折扣 Skill） | P0 | Q15/Q17/Q18 |
| Phase 4 | TBOX/ABOX 分离（SPARQL 查询 + store_id 过滤）| P1 | Q19/Q20/Q22 |
| Phase 5 | HITL 审批流（interrupt_on） | P1 | Q29/Q30/Q31 |
| Phase 6 | 权限矩阵（角色 + Skill 粒度） | P1 | Q32/Q33/Q34 |
| Phase 7 | LangSmith 可观测性接入 | P2 | Q43/Q44 |
| Phase 8 | 审计日志（结构化 + 持久化） | P2 | Q38/Q39/Q41 |
| Phase 9 | MCP Server 对接（ERP/WMS） | P2 | Q47/Q48 |

---

## 十一、决策清单

> 以下决策需要**明确回答**后才能进入 Phase 1 开发

| # | 决策问题 | 选项 | 选择 |
|---|---------|------|------|
| D1 | 前端框架 | CopilotKit / 自研 | |
| D2 | 后端 Agent 框架 | Deep Agents / LangGraph | |
| D3 | 部署方式 | LangGraph Platform / FastAPI 自托管 | |
| D4 | ABOX 存储 | JSON 文件 / PostgreSQL / NebulaGraph | |
| D5 | SPARQL 引擎 | RDFLib / GraphDB | |
| D6 | 审批人 | 店长 / 总部 / 自动 | |
| D7 | LangSmith | 接入 / 不接入 | |
| D8 | 审计存储 | 文件 / PostgreSQL | |
| D9 | MCP 对接 | 需要 / 不需要 | |
| D10 | 多租户模式 | 共享实例 / 独立实例 | |

---

## 十二、下一步行动

1. **Round 1**：由谢文龙回答以上所有问题（Q1-Q54 + D1-D10）
2. **Round 2**：昊晴整理决策结论，形成 **PRD（产品需求文档）**
3. **Round 3**：基于 PRD，开始 **Phase 1**（CopilotKit 前端集成）

---

## 附录：参考文档

- [CopilotKit+LangGraph+DeepAgents架构方案](https://www.feishu.cn/docx/ZE57dJSaaoaza4x2YLNcoSOenAc)
- [store-ontology GitHub](https://github.com/)（项目重置后待更新）
- [CopilotKit 官方文档](https://docs.copilotkit.ai/)
- [LangGraph 官方文档](https://docs.langchain.com/oss/python/langgraph/)
- [Deep Agents 官方文档](https://docs.langchain.com/oss/python/deep-agents/)
- [Agent Skills 规范](https://github.com/agentskills/agentskills)
