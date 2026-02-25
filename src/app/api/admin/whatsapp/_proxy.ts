import { NextResponse } from "next/server";

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
export const FALLBACK_BACKEND_URL =
  process.env.NEXT_PUBLIC_API_FALLBACK_URL ||
  process.env.API_BACKEND_BASE_URL ||
  `http://orchestrator:${process.env.API_BACKEND_PORT || "9000"}`;

function resolveBearer(request: Request): string | null {
  const header = request.headers.get("authorization") || request.headers.get("Authorization");
  if (header && header.startsWith("Bearer ")) return header;
  try {
    const token = new URL(request.url).searchParams.get("token");
    if (token) return `Bearer ${token}`;
  } catch {
    // ignore malformed URL
  }
  const svc = (process.env.ADMIN_SERVICE_BEARER_TOKEN || "").trim();
  if (svc) return `Bearer ${svc}`;
  return null;
}

export function requireAdminAuth(request: Request): string | NextResponse {
  const bearer = resolveBearer(request);
  if (!bearer) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return bearer;
}

export async function proxyJson(
  request: Request,
  method: "GET" | "POST" | "DELETE" | "PATCH",
  backendPath: string,
  queryString?: string
): Promise<NextResponse> {
  const auth = requireAdminAuth(request);
  if (auth instanceof NextResponse) return auth;

  const suffix = queryString ? `?${queryString}` : "";
  const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);
  let lastError: unknown = null;

  for (const baseUrl of urls) {
    try {
      const body = method === "GET" ? undefined : await request.text();
      const response = await fetch(`${baseUrl}${backendPath}${suffix}`, {
        method,
        headers: {
          Authorization: auth,
          ...(method === "GET" ? {} : { "Content-Type": "application/json" }),
        },
        ...(body ? { body } : {}),
      });
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    } catch (err) {
      lastError = err;
    }
  }

  console.error("WhatsApp admin proxy error", lastError);
  return NextResponse.json({ error: "Proxy failed" }, { status: 502 });
}
