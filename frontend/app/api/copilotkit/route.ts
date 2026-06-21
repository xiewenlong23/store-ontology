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
