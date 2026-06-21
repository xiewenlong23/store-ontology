import { CopilotRuntime, ExperimentalEmptyAdapter, copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

/**
 * 动态 workspace 注入（roadmap v2-tenant动态）。
 *
 * CopilotKit runtime 自动把前端 headers prop 注入的 incoming request header
 * （X-Workspace + X-Org-Unit-ID）透传给后端 agent，**本 route 无需任何 header 逻辑**。
 *
 * 前端（layout.tsx）的 CopilotKit headers 函数注入：
 *   X-Workspace: customer_default（固定）
 *   X-Org-Unit-ID: 选中门店 id（随切换变化）
 * 经 runtime 透传 → 后端 middleware 读 header → contextvar → Repository 按 org_unit 过滤。
 *
 * 详见 docs/superpowers/specs/2026-06-21-v2-tenant-dynamic-design.md。
 */
const BACKEND_URL = process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8123/api/copilotkit";

const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
    agents: {
        default: new LangGraphHttpAgent({
            url: BACKEND_URL,
        }),
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
