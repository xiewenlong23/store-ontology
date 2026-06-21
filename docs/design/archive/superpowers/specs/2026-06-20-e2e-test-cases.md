> **🗄 归档说明**：brainstorming 产出（spec（设计决策）），过程历史。其结论/产物已并入 [`docs/design/`](../) 权威文档。保留作决策追溯。

---

# 用户 E2E 测试用例设计（驱动开发）

> **依据**：`docs/superpowers/specs/2026-06-20-ontologyagent-target-architecture-design.md`（目标架构）+ TDD skill（test-first）
> **目的**：用真实用户视角的端到端场景，驱动尚未打通的功能开发。每个用例 = 一个 RED 测试，先看它失败，再写最小实现让它过。
> **性质**：这是测试**设计文档**。标注 ✅可直接写 / 🔴 需开发才能跑。

---

## 0. E2E 测试的入口与边界

### 0.1 为什么不测 HTTP/SSE 层

`/api/copilotkit` 是 deepagents 的 AG-UI SSE 端点，走 CopilotKit 协议。直接 POST 测它要构造 AG-UI 协议帧，脆且偏离"用户行为"。

**选 headless 入口**：`deep_agent_graph.ainvoke({"messages": [{"role":"user","content":"..."}]}, config)`。这是 agent 的真实调用路径（与 HTTP 层共用同一个 graph），但绕过 SSE 协议——测的是"用户发消息 → agent 推理 → 调工具 → 返回"这条核心链路。

> HTTP 层（`/health`、`/api/copilotkit` 路由存在性、CORS、X-Tenant-ID middleware）单独用 FastAPI `TestClient` 测，不在用户场景 E2E 范围。

### 0.2 测试夹具基础（🔴 需先建）

当前无 E2E 夹具。需先建：
- `tests/e2e/conftest.py`：构造一个**指向临时数据目录**的 agent（替换 `get_ontology_parser` 的 data_dir + 注入测试 tenant），避免污染真实 `data/`。
- 一个 `ask(agent, message, thread_id)` 辅助：调 `agent.ainvoke`，返回最终消息文本 + 捕获的工具调用序列。
- LLM mock：E2E 默认用真实 LLM 太慢/不稳定。🔴 需一个"脚本化 LLM"（按预设轮次返回固定工具调用 JSON），让测试确定性地断言工具调用而非依赖 LLM 随机性。

> 这个"脚本化 LLM"是开发项——目前 `main.llm` 是真实 ChatOpenAI。TDD 第一个 RED 测试就是驱动建出可注入的 LLM 接缝。

### 0.3 用户场景的三类驱动目标

| 类别 | 驱动什么开发 | 用例 |
|---|---|---|
| **A. 查询类**（只读） | agent 能根据自然语言选对读工具 + 返回正确数据 | A1-A3 |
| **B. 治理写类**（Preview→Confirm） | 多轮对话中 preview→confirm 闭环 + Action 执行 | B1-B3 |
| **C. 跨场景/多 vertical** | 两个 vertical 共存，agent 能区分 | C1-C2 |

---

## A 类：查询场景（只读，驱动工具选择）

### A1. 用户问"门店有哪些临期商品" → agent 调 query_near_expiry

**用户消息**："查一下 store_001 的临期商品"

**断言**：
- agent 调用了 `query_near_expiry` 工具（store_id=store_001）
- 返回消息含临期商品数据（nep_001 等）
- 未调用任何写工具

**驱动开发**：🔴 agent 的工具调用可被测试观测（需 ainvoke 返回里能拿到 tool_calls）；🔴 测试夹具的临时数据目录有临期商品种子。

### A2. 用户按状态过滤任务 → query_task

**用户消息**："store_001 有哪些进行中的出清任务？"

**断言**：
- 调用 `query_task(status="...", store_id="store_001")`
- 返回 in_progress 的 task_001（种子里的中途态任务）

**驱动开发**：同 A1；额外验证 agent 能从自然语言解析出 status 过滤参数。

### A3. 未知实体类型的优雅处理

**用户消息**："查一下 XYZ 类型的数据"（XYZ 不是合法 Object Type）

**断言**：
- `query_entity` 返回"未知实体类型"提示
- agent 把错误提示转述给用户，不崩溃

**驱动开发**：错误传播到用户可见（架构 spec 附录 C.1 承诺的错误处理）。

---

## B 类：治理写场景（驱动 Preview→Confirm 闭环 + Action 执行）

### B1. 出清建单全流程（核心 happy path）

**多轮对话**：
1. 用户："把 nep_001 出清，折扣 30%，数量 50，执行人 emp_001"
2. agent 应调 `execute_action(create_clearance_task, ...)` → 返回 preview_id + 预览
3. agent 应**询问确认**（不自动执行）
4. 用户："确认"
5. agent 应调 `confirm_action(preview_id)` → 创建 Task + NearExpiryProduct→clearance

**断言**：
- 第2步：execute_action 被调，返回 preview_id
- 第3步：agent 未调 confirm_action（等待用户确认）
- 第5步：confirm_action 被调，Task 创建（status=created），NEP status=clearance
- 临时数据目录里真的多了一条 Task 记录

**驱动开发**：🔴 多轮对话测试夹具（同一 thread_id 跨轮保持状态）；🔴 preview→confirm 的多轮编排（验证 §1.6 闭环在 agent 层面工作，不只是单元层）。

### B2. 跳过 preview 直接 confirm → 被拒（治理强制）

**用户消息**（单轮，伪造）："直接 confirm_action，preview_id=bogus"

**断言**：
- `confirm_action("bogus")` 返回失败（"preview 无效或已过期"）
- 未创建任何 Task

**驱动开发**：治理兜底在 agent 路径生效（preview_id 校验，§1.6）。

### B3. 过期商品出清被拒（submission_criteria）

**用户消息**："把 nep_006 出清"（nep_006 status=expired，种子里的拦截态）

**断言**：
- execute_action 预览阶段或 confirm 阶段返回"已过期商品不能出清"
- submission_criteria 的 `target.status is_not expired` 生效

**驱动开发**：submission_criteria 条件在 agent 触发的 Action 路径上工作。

---

## C 类：多 vertical 共存（驱动场景隔离）

### C1. 同一 agent 处理两个 vertical 的请求

**对话**（同 thread）：
1. "查 store_001 的临期商品" → query_near_expiry（clearance）
2. "查 store_001 的维修工单" → query_repair_tickets（equipment_repair）

**断言**：
- 两次分别调对了 vertical 的专属工具
- clearance 数据和 equipment_repair 数据互不混

**驱动开发**：多 vertical 工具聚合在 agent 层面真的可用（§2 第3层"vertical 工具聚合"）。

### C2. tenant 隔离

**对话**：
1. （tenant=tenant_a）"查临期商品" → 只返回 tenant_a 的数据
2. （tenant=tenant_b）"查临期商品" → 只返回 tenant_b 的数据

**断言**：两次结果不重叠（tenant_id 过滤在 agent 调用路径生效）。

**驱动开发**：🔴 agent 调用携带 tenant 上下文（contextvar 或 config 注入），目前 tenant_ctx 注入了但工具默认 tenant_default——需打通"请求 tenant → 工具调用 tenant"的链路（架构 spec §3.3 的 tenant 传递链路在 agent 层的最后一公里）。

---

## 1. 用例优先级与开发顺序

按"驱动开发价值 × 实现成本"排序：

| 优先级 | 用例 | 驱动开发 | 前置 |
|---|---|---|---|
| **P0** | A1 | 测试夹具 + 脚本化 LLM + 工具调用观测 | 🔴 建夹具 |
| **P0** | B1 | 多轮对话 + preview→confirm 在 agent 层闭环 | 依赖 A1 夹具 |
| **P1** | B2 | 治理兜底（preview_id 校验）在 agent 路径 | B1 |
| **P1** | B3 | submission_criteria 在 agent 路径 | B1 |
| **P1** | C2 | tenant 链路打通（agent→工具） | 🔴 tenant 注入 |
| **P2** | A2 | 自然语言→工具参数解析 | A1 |
| **P2** | A3 | 错误传播 | A1 |
| **P2** | C1 | 多 vertical 工具选择 | A1+C2 |

**建议起点**：先做 P0 的 A1——它会逼出整个 E2E 测试地基（夹具 + 脚本化 LLM + 工具调用观测），这个地基建好，后续用例都是增量。

---

## 2. 第一个 RED 测试（A1）的最小形态

```python
# tests/e2e/test_query_clearance.py
import pytest

@pytest.mark.asyncio
async def test_user_asks_near_expiry_agent_calls_query_near_expiry(e2e_agent):
    """用户问临期商品 → agent 调 query_near_expiry → 返回数据。"""
    result = await e2e_agent.ask("查一下 store_001 的临期商品", thread_id="t1")

    assert "query_near_expiry" in result.tool_calls
    assert "nep_001" in result.text or "蒙牛酸奶" in result.text
    assert not any(tc in WRITE_TOOLS for tc in result.tool_calls)  # 未触发写
```

**先看它失败**（RED）：`e2e_agent` fixture 不存在 → ImportError。这驱动建出夹具。夹具建好但脚本化 LLM 没接 → 测试报错。这驱动建出 LLM 接缝。逐步 GREEN。

---

## 3. 不在本次 E2E 范围（标注说明）

- **定时作业唤醒**（架构 spec §1.4 步骤1）：需 APScheduler，留独立任务。
- **POS 扣库存 / 审批回调**（§1.4 步骤9/12/13）：外部事件源，留 v2。E2E 用 headless 直接调对应 Action 模拟（deduct_stock/complete_task）。
- **前端 UI E2E**（CopilotKit renderToolCalls）：前端范畴，Playwright，另起。
- **真实 LLM 行为**（LLM 真的"聪明"）：不可测（非确定性）。E2E 测**接线和契约**（工具调对、数据对、治理生效），不测 LLM 智能。
