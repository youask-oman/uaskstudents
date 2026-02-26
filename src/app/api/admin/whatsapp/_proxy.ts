import { NextResponse } from "next/server";

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
export const FALLBACK_BACKEND_URL =
  process.env.NEXT_PUBLIC_API_FALLBACK_URL ||
  process.env.API_BACKEND_BASE_URL ||
  `http://orchestrator:${process.env.API_BACKEND_PORT || "9000"}`;

function normalizeBaseUrl(input: string): string {
  return String(input || "").trim().replace(/\/+$/, "");
}

function toIpv4Loopback(baseUrl: string): string {
  return baseUrl.replace("://localhost", "://127.0.0.1");
}

function resolveBackendCandidates(): string[] {
  const seed = [
    BACKEND_URL,
    FALLBACK_BACKEND_URL,
    process.env.API_BACKEND_BASE_URL || "",
    "http://127.0.0.1:9000",
    "http://localhost:9000",
  ]
    .map(normalizeBaseUrl)
    .filter(Boolean);

  const expanded: string[] = [];
  for (const url of seed) {
    expanded.push(url);
    if (url.includes("://localhost")) expanded.push(toIpv4Loopback(url));
  }

  return Array.from(new Set(expanded));
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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
  const urls = resolveBackendCandidates();
  let lastError: unknown = null;
  const body = method === "GET" ? undefined : await request.text();

  for (const baseUrl of urls) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await fetch(`${baseUrl}${backendPath}${suffix}`, {
          method,
          headers: {
            Authorization: auth,
            ...(method === "GET" ? {} : { "Content-Type": "application/json" }),
          },
          ...(body ? { body } : {}),
        });

        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const data = await response.json();
          return NextResponse.json(data, { status: response.status });
        }
        const text = await response.text();
        return new NextResponse(text, {
          status: response.status,
          headers: { "Content-Type": contentType || "text/plain" },
        });
      } catch (err) {
        lastError = err;
        if (attempt === 0) {
          await sleep(80);
          continue;
        }
      }
    }
  }

  console.error("WhatsApp admin proxy error", lastError);
  return NextResponse.json({ error: "Proxy failed" }, { status: 502 });
}
