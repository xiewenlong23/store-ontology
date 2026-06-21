# v2-tenant 动态注入设计

> **状态**：设计已确认，待实现
> **日期**：2026-06-21
> **性质**：前端 + route.ts 代码实现，落地 roadmap 的"v2-tenant动态"项。
> **关联**：[`docs/design/roadmap.md`](../design/roadmap.md) §8、[`docs/design/00-architecture.md`](../design/00-architecture.md) §3.3

---

## 0. 问题陈述

当前 `X-Workspace` header（告诉后端运行在哪个 workspace/org_unit）在 `frontend/app/api/copilotkit/route.ts` 里是**静态默认**（`customer_default`）。用户切换门店时，前端 `selected_store` 写入 co-agent state，但这个 state 走 request **body**，**不会**变成出站 header——后端始终收到静态 `customer_default`，多门店数据切换名存实亡。

route.ts 注释坦承："`LangGraphHttpAgent` 的 headers 构造时静态，不提供按请求动态注入的 hook"——这是 MVP 阶段的权宜绕过。

### 方案演进（为什么不是最早提的"反解 body"）

brainstorming 第一轮提的方案 A（给 Client 加 `onRequest` 钩子，反解 request body 取 selected_store 注入 header）**经重新审视被否决**：
- 依赖 CopilotKit 内部 minified 代码的序列化格式，无公开 API 保证，升级即脆。
- "读自己的 body 决定自己的 header"是反模式。

深挖 CopilotKit 类型定义后，发现**两个官方 API** 专为多租户场景设计（见 §1），方案 D 据此确立。

---

## 1. 方案 D：显式 header + AgentsFactory（两个官方 API）

### 1.1 机制 1：前端 `headers` prop（CopilotKit Provider 官方支持）

`CopilotKitProvider` 的 `headers` prop（类型 `Record<string,string> | () => Record<string,string>`），注释："additional headers to be sent with the request"。**支持函数形式**（源码 line 3498：`typeof headersProp === "function" ? headersProp() : headersProp`），且响应式——headers 变化时 CopilotKit 用 `useEffect` 自动更新 agent 的 headers（源码 line 4130-4131）。

### 1.2 机制 2：后端 `AgentsFactory`（CopilotKit runtime 官方多租户机制）

`CopilotRuntime({ agents: factory })`，`AgentsFactory = (ctx: { request: Request }) => agents`。类型定义注释白纸黑字："**Useful for multi-tenant scenarios or request-scoped agent configuration**"，并给出示例：
```typescript
agents: ({ request }) => {
  const tenantId = request.headers.get("x-tenant-id");
  return { default: createAgentForTenant(tenantId) };
}
```

`ctx.request` 是浏览器发来的原始 HTTP request（含前端 `headers` prop 注入的 header）。

---

## 2. 术语与映射（关键决策）

`TenantContext(workspace_name, org_unit_id)` 双层语义：
- **workspace_name**：硬隔离边界（如 `customer_default`）。
- **org_unit_id**：workspace 内权限范围（`*`=总部全可见，或具体门店 id）。

**门店 id（`selected_store`，如 `store_001`）映射到 `X-Org-Unit-ID`，不是 `X-Workspace`**。门店是 workspace 内的组织单元，不是隔离边界。`X-Workspace` 保持 `customer_default`（当前单 workspace）。

---

## 3. 目标 / 范围 / 成功标准

### 3.1 目标
切换门店后，后端按选中门店的 org_unit 过滤数据；多门店数据真正隔离。

### 3.2 范围 — In
1. **前端 state 提升**：`selected_store` 从 `home-page.tsx` 提升到共享 context（因 `CopilotKit` Provider 在 `layout.tsx` 外层，需在 Provider 外提供 selected_store）。
2. **前端 `headers` prop**：`CopilotKit` 的 `headers` 改为函数 `() => ({ 'X-Workspace': 'customer_default', 'X-Org-Unit-ID': selectedStore })`。
3. **route.ts 改 AgentsFactory**：`agents: ({request}) => ({ default: new LangGraphHttpAgent({ url, headers: 从 request 读 X-Workspace + X-Org-Unit-ID 透传 }) })`。
4. **验证**：手工 + 自动化（如有前端测试基建）确认切换门店后 header 变化、数据隔离。

### 3.3 范围 — Out
- ❌ 后端业务代码零改（middleware 已读 X-Workspace + X-Org-Unit-ID → contextvar）。
- ❌ 不动 dashboard/page.tsx（它已手动带 header）。
- ❌ 不重构 CopilotRuntime / 不引入新依赖。
- ❌ 不做多 workspace（`customer_default` 固定），只做 org_unit 动态。

### 3.4 成功标准
1. 切换门店 → 后端收到的 `X-Org-Unit-ID` 随之变化（日志或测试验证）。
2. 不同门店的数据隔离（切到 store_001 看 store_001 数据，store_002 看 store_002）。
3. 默认/回退：selected_store 缺失时 header 回退 `*`（总部全可见），不崩。
4. dashboard 已有的动态 header 不受影响。
5. 前端编译无 TS 错误，dev 启动正常。

---

## 4. 实现要点

### 4.1 前端 state 提升

`layout.tsx` 的 `CopilotKit` Provider 在最外层，但 `useCoAgent`（selected_store 来源）在 `home-page.tsx`（children 内）。Provider 无法直接读子组件 hook。

**方案**：建一个轻量 `WorkspaceContext`（React Context），在 Provider 外层（layout.tsx 的 body 内、CopilotKit 外）提供 `{ selectedStore, setSelectedStore }`。`home-page.tsx` 的门店选择器写 `setSelectedStore`，`CopilotKit` 的 `headers` 函数读 `selectedStore`。

> 备选：把 `useCoAgent` 也提到 layout 层。但 useCoAgent 必须在 CopilotKit 内（它是 CopilotKit 的 hook），而 headers 在 CopilotKit 上——形成"Provider 需要 state、state 需要 Provider 内"的循环。故用独立 Context 解耦。

### 4.2 前端 headers prop

```tsx
// layout.tsx
<CopilotKit
  runtimeUrl="/api/copilotkit"
  agent="default"
  headers={() => ({
    'X-Workspace': 'customer_default',
    'X-Org-Unit-ID': workspaceCtx.selectedStore || '*',
  })}
  renderToolCalls={...}
>
```

### 4.3 route.ts AgentsFactory

```typescript
const BACKEND_URL = process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8123/api/copilotkit";

const runtime = new CopilotRuntime({
    agents: ({ request }) => {
        // 从前端发来的 request header 读 workspace + org_unit，透传给后端
        const workspace = request.headers.get("x-workspace") || "customer_default";
        const orgUnit = request.headers.get("x-org-unit-id") || "*";
        return {
            default: new LangGraphHttpAgent({
                url: BACKEND_URL,
                headers: { "X-Workspace": workspace, "X-Org-Unit-ID": orgUnit },
            }),
        };
    },
});

// serviceAdapter 保持 ExperimentalEmptyAdapter
```

### 4.4 后端零改确认

`agent/main.py` 的 middleware 已从 `X-Workspace`（回退 `X-Customer-ID`）+ `X-Org-Unit-ID` 构造 `TenantContext`（`agent/engine/tenant.py:from_headers`）。Repository 已按 `workspace_name + org_unit_id` 过滤。无需改。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|------|------|
| AgentsFactory 每请求 new 一个 LangGraphHttpAgent | agent 是轻量配置容器，无状态；MVP 不缓存。若性能敏感可加按 workspace 的缓存。 |
| 前端 headers 函数每次渲染重算 | 返回小对象；CopilotKit 内部 JSON.stringify 去重比较（源码 line 4092/4601），开销可忽略。 |
| WorkspaceContext + useCoAgent 两套 state 不同步 | selected_store 的唯一真源是 WorkspaceContext；home-page 的 useCoAgent 仍保留（供 LLM 读门店），但门店选择器同时写两边。或简化：门店选择器只写 WorkspaceContext，useCoAgent 删掉（LLM 改读 system prompt 的门店上下文）。实现时定。 |
| AgentsFactory 是 v2 runtime API，当前用 v1 import | `AgentsFactory` 从主包 `@copilotkit/runtime` 导出（已核实），`CopilotRuntime` 构造接受 `AgentsConfig`（含 factory）。不换 import 路径。 |

---

## 6. 验证

1. **手工**：启动前后端，浏览器切门店 → 对话查询 → 后端日志确认 `X-Org-Unit-ID` 变化 + 数据按门店过滤。
2. **回归**：dashboard 页仍正常（它独立 fetch 带 header）；现有对话流程不崩。

---

## 附录：方案否决记录

- **方案 A（onRequest 反解 body）**：否决。依赖 undocumented 内部序列化格式，反模式。
- **方案 B（后端 middleware 读 body）**：否决。违反 header 传租户架构约定，耦合 CopilotKit state 结构，SSE body 解析复杂。
- **方案 C（Next.js rewrites 绕过 CopilotRuntime）**：否决。改动大，丢失 runtime 处理。
- **方案 D（显式 header + AgentsFactory）**：采纳。两个官方公开 API，正道、稳健、正是 CopilotKit 设计场景。
