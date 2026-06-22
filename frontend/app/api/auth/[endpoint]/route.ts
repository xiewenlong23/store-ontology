import { NextRequest, NextResponse } from "next/server";

/**
 * v2 认证 BFF（设计文档 §5 WP7）。
 *
 * 把前端 /api/auth/<endpoint> 请求转发到后端 8123 的 /api/auth/<endpoint>。
 * 为什么需要 BFF：
 * - 浏览器跨域受 CORS 限制（虽然后端开了 CORS，但 dev/部署链路可能复杂）
 * - 后端 Authorization header 经 BFF 时无遗漏（fetch 透传）
 * - 集中管理 backend URL（process.env.BACKEND_URL）
 *
 * 支持 endpoint: login / refresh / me / logout（path param 透传）
 */
const BACKEND_BASE = process.env.BACKEND_URL || "http://localhost:8123";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ endpoint: string }> }
) {
  const { endpoint } = await params
  const backendUrl = `${BACKEND_BASE}/api/auth/${endpoint}`;
  const body = await req.text();

  // 透传 Authorization header（如果有）+ Content-Type
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const authHeader = req.headers.get("Authorization");
  if (authHeader) headers["Authorization"] = authHeader;

  const resp = await fetch(backendUrl, {
    method: "POST",
    headers,
    body,
  });
  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ endpoint: string }> }
) {
  const { endpoint } = await params
  const backendUrl = `${BACKEND_BASE}/api/auth/${endpoint}`;

  // 透传 Authorization header
  const headers: Record<string, string> = {};
  const authHeader = req.headers.get("Authorization");
  if (authHeader) headers["Authorization"] = authHeader;

  const resp = await fetch(backendUrl, { method: "GET", headers });
  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
