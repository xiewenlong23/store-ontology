import { CopilotRuntime, ExperimentalEmptyAdapter, copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

/**
 * MVP：向 Deep Agent 后端转发请求时注入 X-Tenant-ID header。
 *
 * 说明：CopilotKit runtime 的 LangGraphHttpAgent 在构造时接受静态 headers，
 * 但不提供按请求动态注入 header 的 hook（co-agent 的 selected_store 走 body state，
 * 不会自动成为出站 header）。因此 MVP 阶段用静态默认租户，保证后端 middleware
 * 总能拿到合法的 X-Tenant-ID（避免 401）。
 *
 * v2：要按选中门店动态注入，需要自定义 fetch wrapper 或 Next.js rewrites 代理
 * （绕过 CopilotRuntime），届时再实现。
 */
const DEFAULT_TENANT = process.env.DEFAULT_TENANT_ID || "tenant_default";

const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
    agents: {
        default: new LangGraphHttpAgent({
            url: process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8123/api/copilotkit",
            headers: { "X-Tenant-ID": DEFAULT_TENANT },
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
