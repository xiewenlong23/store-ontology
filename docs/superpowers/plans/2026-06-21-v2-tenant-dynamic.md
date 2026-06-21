# v2-tenant 动态注入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让前端切换门店后，`X-Workspace` + `X-Org-Unit-ID` header 动态注入，后端按选中门店过滤数据。用 CopilotKit 两个官方 API（前端 headers prop 函数式 + 后端 AgentsFactory）。

**Architecture:** 前端用独立 `WorkspaceContext` 作 selected_store 真源（供 CopilotKit headers prop 读）；门店选择器同时写 WorkspaceContext（header 用）和 useCoAgent（LLM 读）。route.ts 改 AgentsFactory，per-request 从进来的 request header 读 workspace+org_unit 透传给后端 agent。后端零改。

**Tech Stack:** Next.js 15 (App Router) / React 19 / TypeScript / @copilotkit/runtime 1.57.4 / @copilotkit/react-core。

**关联 spec:** `docs/superpowers/specs/2026-06-21-v2-tenant-dynamic-design.md`

**关键 API（已读类型定义核实）:**
- 前端 `CopilotKit` 的 `headers` prop 接受 `() => Record<string,string>`（函数式，响应式，源码 line 3498/4130）
- 后端 `CopilotRuntime({ agents: ({request}) => ({...}) })` 的 AgentsFactory，`request.headers.get('x-org-unit-id')`（官方多租户示例）

---

## File Structure

- Create: `frontend/app/workspace-context.tsx`（WorkspaceContext + Provider）
- Modify: `frontend/app/layout.tsx`（挂 WorkspaceProvider + headers prop 函数式）
- Modify: `frontend/app/home-page.tsx`（门店选择器写 WorkspaceContext + useCoAgent）
- Modify: `frontend/app/api/copilotkit/route.ts`（agents 改 AgentsFactory）

---

## Task 1：建 WorkspaceContext

**Files:**
- Create: `frontend/app/workspace-context.tsx`

- [ ] **Step 1: 写 WorkspaceContext + Provider + useWorkspace hook**

新建 `frontend/app/workspace-context.tsx`：

```tsx
'use client'

import { createContext, useContext, useState, ReactNode } from 'react'

interface WorkspaceState {
  selectedStore: string
  setSelectedStore: (store: string) => void
}

const WorkspaceContext = createContext<WorkspaceState | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [selectedStore, setSelectedStore] = useState('store_001')
  return (
    <WorkspaceContext.Provider value={{ selectedStore, setSelectedStore }}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) {
    throw new Error('useWorkspace must be used within WorkspaceProvider')
  }
  return ctx
}
```

- [ ] **Step 2: 验证 TS 编译无误**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep workspace-context || echo "✅ 无 TS 错误"`
Expected: 无错误（或仅已有的无关警告）。

- [ ] **Step 3: Commit**

```bash
git add frontend/app/workspace-context.tsx
git commit -m "feat(frontend): 建 WorkspaceContext（selected_store 真源，供 header 注入）"
```

## Task 2：layout.tsx 挂 Provider + headers prop 函数式

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: import WorkspaceProvider + useWorkspace，挂到 CopilotKit 外层**

在 `layout.tsx` 顶部加 import：
```tsx
import { WorkspaceProvider, useWorkspace } from './workspace-context'
```

把 `<CopilotKit ...>` 包进 `<WorkspaceProvider>`，并加 `headers` prop 函数。因为 `headers` 函数要读 `useWorkspace()`（必须在 Provider 内），需把 CopilotKit 的渲染抽到一个内部组件（hooks 不能在 RootLayout 直接调，因 RootLayout 在 Provider 外）。

修改 `RootLayout` 的 return 部分：
```tsx
return (
  <html lang="zh-CN">
    <body className={inter.className}>
      <WorkspaceProvider>
        <AppWithWorkspace headers />
      </WorkspaceProvider>
    </body>
  </html>
)
```

新建内部组件 `AppWithWorkspace`（在 RootLayout 之前定义），它调 useWorkspace 读 selectedStore，传给 CopilotKit 的 headers：
```tsx
function AppWithWorkspace({ children, renderToolCalls }: { children: ReactNode; renderToolCalls: any }) {
  const { selectedStore } = useWorkspace()
  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent="default"
      headers={() => ({
        'X-Workspace': 'customer_default',
        'X-Org-Unit-ID': selectedStore || '*',
      })}
      renderToolCalls={renderToolCalls}
    >
      <div className="golden-layout">
        <div className="golden-left">{children}</div>
        <div className="golden-right"><CopilotChat /></div>
      </div>
    </CopilotKit>
  )
}
```

> 注意：RootLayout 的 `renderToolCalls` useMemo 需传给 AppWithWorkspace。调整 RootLayout 让它把 renderToolCalls 作为参数传下去（renderToolCalls 的 useMemo 逻辑保持在 RootLayout，或移到 AppWithWorkspace——后者更内聚，推荐移）。

- [ ] **Step 2: 验证 TS 编译 + dev 启动**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: 无错误。

Run: `cd frontend && npm run dev`（后台启动，sleep 6，curl localhost:3000 返回 200，然后 kill）
Expected: 前端正常启动，首页可达。

- [ ] **Step 3: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat(frontend): layout 挂 WorkspaceProvider + CopilotKit headers 函数式注入"
```

## Task 3：home-page.tsx 门店选择器写双份

**Files:**
- Modify: `frontend/app/home-page.tsx`

- [ ] **Step 1: 门店选择器同时写 WorkspaceContext + useCoAgent**

import useWorkspace：
```tsx
import { useWorkspace } from './workspace-context'
```

在 HomePage 组件内加 `const { selectedStore, setSelectedStore } = useWorkspace()`。

把门店选择按钮的 onClick 从 `setAgentState({ selected_store: s.id })` 改为同时写两边：
```tsx
onClick={() => {
  setSelectedStore(s.id)            // 供 header（WorkspaceContext 真源）
  setAgentState({ selected_store: s.id })  // 供 LLM 读门店（co-agent state）
}}
```

显示用的 `selectedStore` 改从 WorkspaceContext 读（已是），`useCoAgent` 仍保留（LLM 读用，且 initialState 与 WorkspaceContext 默认值一致 store_001）。

更新文件顶部注释（说明双写：WorkspaceContext 供 header，useCoAgent 供 LLM）。

- [ ] **Step 2: 验证 TS 编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: 无错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/app/home-page.tsx
git commit -m "feat(frontend): 门店选择器双写 WorkspaceContext（header）+ useCoAgent（LLM）"
```

## Task 4：route.ts 改 AgentsFactory

**Files:**
- Modify: `frontend/app/api/copilotkit/route.ts`

- [ ] **Step 1: 把 agents 静态 record 改为 AgentsFactory 函数**

全文替换 route.ts 的 runtime 构造部分。保留 import，改 runtime：

```typescript
import { CopilotRuntime, ExperimentalEmptyAdapter, copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

/**
 * 动态 workspace 注入（roadmap v2-tenant动态）。
 *
 * 前端经 CopilotKit headers prop 注入 X-Workspace + X-Org-Unit-ID（随选中门店变化）。
 * 本 route 用 AgentsFactory（CopilotKit 官方多租户机制）per-request 从进来的 request
 * header 读这两个值，透传给后端 LangGraphHttpAgent。
 *
 * 后端 middleware 读 X-Workspace → contextvar，Repository 按 workspace_name + org_unit_id 过滤。
 * 详见 docs/superpowers/specs/2026-06-21-v2-tenant-dynamic-design.md。
 */
const BACKEND_URL = process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8123/api/copilotkit";

const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
    agents: ({ request }) => {
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

export const POST = async (req: NextRequest) => {
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
        runtime,
        serviceAdapter,
        endpoint: "/api/copilotkit",
    });

    return handleRequest(req);
};
```

- [ ] **Step 2: 验证 TS 编译 + route 可达**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: 无错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/app/api/copilotkit/route.ts
git commit -m "feat(route): agents 改 AgentsFactory，per-request 透传 X-Workspace + X-Org-Unit-ID"
```

## Task 5：端到端验证

- [ ] **Step 1: 启动前后端**

```bash
# 后端（用 conda env，从 agent/ 目录）
cd agent && /opt/miniconda3/envs/store-ontology/bin/python main.py &
sleep 4
curl -s http://localhost:8123/health   # 预期 {"status":"healthy"}

# 前端
cd ../frontend && npm run dev &
sleep 6
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000   # 预期 200
```

- [ ] **Step 2: 验证 header 透传（直连 route.ts 模拟前端请求）**

```bash
# 模拟前端带 X-Workspace + X-Org-Unit-ID 发到 route.ts
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:3000/api/copilotkit \
  -H "Content-Type: application/json" \
  -H "X-Workspace: customer_default" \
  -H "X-Org-Unit-ID: store_002" \
  -d '{"messages":[]}'
# 预期：非 500（route 正常处理；具体 4xx 取决于 CopilotKit 对空 messages 的处理，重点是不因 factory 崩）
```

- [ ] **Step 3: 人工验证（浏览器）**

打开 http://localhost:3000：
1. 默认门店 store_001，对话问"有哪些临期商品" → 看 store_001 数据
2. 点"上海浦东店"切换到 store_002
3. 再问"有哪些临期商品" → 应看到 store_002 数据（或不同结果）
4. 检查后端日志：确认 X-Workspace/X-Org-Unit-ID 随切换变化（需在后端 middleware 临时加日志，或用 curl 抓 route.ts 转发的 header）

> 若需确认 header 真的传到后端：在后端 `agent/main.py` 的 workspace_middleware 临时加 `print(f"[ws] {tc.workspace_name} / {tc.org_unit_id}")`，切门店后看日志变化。验证后删日志行。

- [ ] **Step 4: 回归确认**

- dashboard 页（/dashboard）仍正常（它独立 fetch 带 header，不受本次改动影响）
- 现有对话流程（查询/出清/确认）不崩

- [ ] **Step 5: 如有 TS 编译警告或运行时问题，修复后 amend**

- [ ] **Step 6: 关闭前后端**

```bash
# 找 PID 并 kill
lsof -nP -iTCP:8123 -sTCP:LISTEN | tail -1   # 取 PID
lsof -nP -iTCP:3000 -sTCP:LISTEN | tail -1   # 取 PID
kill <pid1> <pid2>
```

---

## Self-Review

**1. Spec 覆盖：**
- §3.2 In 1（state 提升）→ Task 1 + Task 2 ✅
- §3.2 In 2（headers prop）→ Task 2 ✅
- §3.2 In 3（route.ts AgentsFactory）→ Task 4 ✅
- §3.2 In 4（验证）→ Task 5 ✅
- §3.4 成功标准 1-5 → Task 5 逐条验证 ✅

**2. 占位扫描：** 无 TBD。Task 2 Step 1 对 renderToolCalls 放置（RootLayout vs AppWithWorkspace）给了推荐（移到 AppWithWorkspace），非占位。

**3. 类型/命名一致性：**
- `WorkspaceProvider`/`useWorkspace` —— Task 1 定义，Task 2/3 消费 ✅
- `headers` 函数返回 `{X-Workspace, X-Org-Unit-ID}` —— Task 2（前端发）与 Task 4（route 读）键名一致 ✅
- `selectedStore` —— Task 1 定义，Task 2 读，Task 3 写 ✅
- route.ts `request.headers.get("x-workspace")` / `get("x-org-unit-id")` —— 与前端发的 header 名一致（HTTP header 大小写不敏感，Headers.get 不敏感）✅
