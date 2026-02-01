import { NextResponse } from "next/server";

const FALLBACK_BACKEND_URL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || "http://127.0.0.1:8000";

export async function GET(request: Request, { params }: { params: { table: string } }) {
    const headers: Record<string, string> = {};
    const auth = request.headers.get("authorization");
    if (auth) headers.Authorization = auth;

    const { searchParams } = new URL(request.url);
    const limit = searchParams.get("limit") || "200";
    const offset = searchParams.get("offset") || "0";
    const url = `${FALLBACK_BACKEND_URL}/api/v1/admin/db/table/${encodeURIComponent(params.table)}?limit=${encodeURIComponent(limit)}&offset=${encodeURIComponent(offset)}`;
    const res = await fetch(url, { headers });
    const text = await res.text();
    return new NextResponse(text, { status: res.status, headers: { "Content-Type": "application/json" } });
}
