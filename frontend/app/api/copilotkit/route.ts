import { CopilotRuntime, ExperimentalEmptyAdapter, copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

/**
 * MVP：向 Deep Agent 后端转发请求时注入 X-Tenant-ID + X-Workspace header。
 *
 * 说明：CopilotKit runtime 的 LangGraphHttpAgent 在构造时接受静态 headers，
 * 但不提供按请求动态注入 header 的 hook（co-agent 的 selected_store 走 body state，
 * 不会自动成为出站 header）。因此 MVP 阶段用静态默认租户 + workspace，保证后端
 * middleware 总能拿到合法的 header（避免 401）。
 *
 * v2：要按选中门店/客户动态注入，需要自定义 fetch wrapper 或 Next.js rewrites 代理
 * （绕过 CopilotRuntime），届时再实现。
 *
 * 架构文档 §3.4：前端通过 X-Workspace header 告诉后端运行在哪个 workspace。
 */
const DEFAULT_TENANT = process.env.DEFAULT_TENANT_ID || "tenant_default";
const DEFAULT_WORKSPACE = process.env.DEFAULT_WORKSPACE || "customer_default";

const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
    agents: {
        default: new LangGraphHttpAgent({
            url: process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8123/api/copilotkit",
            headers: { "X-Tenant-ID": DEFAULT_TENANT, "X-Workspace": DEFAULT_WORKSPACE },
        }),
    }
});

export const POST = async (req: NextRequest) => {
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
        runtime,
        serviceAdapter,
        endpoint: "/api/copilotkit",
    });

    return handleRequest(req);
};
