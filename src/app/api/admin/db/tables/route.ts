import { NextResponse } from "next/server";

const FALLBACK_BACKEND_URL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || "http://localhost:9000";

export async function GET(request: Request) {
    const headers: Record<string, string> = {};
    const auth = request.headers.get("authorization");
    if (auth) headers.Authorization = auth;

    const url = `${FALLBACK_BACKEND_URL}/api/v1/admin/db/tables`;
    const res = await fetch(url, { headers });
    const text = await res.text();
    return new NextResponse(text, { status: res.status, headers: { "Content-Type": "application/json" } });
}

