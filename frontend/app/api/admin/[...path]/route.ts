import { NextRequest, NextResponse } from "next/server";

/**
 * v2 admin BFF（设计文档 §5 WP7 配套）。
 *
 * 把前端 /api/admin/<...path> 转发到后端 8123 的 /api/admin/<...path>。
 * 透传 Authorization header + X-Workspace。
 */
const BACKEND_BASE = process.env.BACKEND_URL || "http://localhost:8123";

async function proxy(req: NextRequest, method: string, paramsPromise: Promise<{ path?: string[] }>) {
  const params = await paramsPromise;
  const path = params.path;
  if (!path || !path.length) {
    return NextResponse.json({ detail: "missing path" }, { status: 400 });
  }
  const pathStr = path.join("/");
  const backendUrl = `${BACKEND_BASE}/api/admin/${pathStr}`;

  const headers: Record<string, string> = {};
  const authHeader = req.headers.get("Authorization");
  if (authHeader) headers["Authorization"] = authHeader;
  const wsHeader = req.headers.get("X-Workspace");
  if (wsHeader) headers["X-Workspace"] = wsHeader;

  const init: RequestInit = { method, headers };
  if (method !== "GET" && method !== "HEAD") {
    init.body = await req.text();
    headers["Content-Type"] = "application/json";
  }

  const resp = await fetch(backendUrl, init);
  const data = await resp.json().catch(() => ({}));
  return NextResponse.json(data, { status: resp.status });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(req, "GET", params);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(req, "POST", params);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(req, "PUT", params);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(req, "DELETE", params);
}
