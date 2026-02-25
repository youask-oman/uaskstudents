import { NextResponse } from "next/server";
import { BACKEND_URL, FALLBACK_BACKEND_URL, requireAdminAuth } from "../../../_proxy";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") || "1000";
  const qs = new URLSearchParams({ limit });
  const auth = requireAdminAuth(request);
  if (auth instanceof NextResponse) return auth;
  const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);
  let lastError: unknown = null;
  for (const baseUrl of urls) {
    try {
      const response = await fetch(`${baseUrl}/api/admin/whatsapp/abuse/export/locks?${qs.toString()}`, {
        method: "GET",
        headers: { Authorization: auth },
      });
      const blob = await response.blob();
      return new NextResponse(blob, {
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": "attachment; filename=whatsapp_abuse_locks.csv",
        },
      });
    } catch (err) {
      lastError = err;
    }
  }
  console.error("WhatsApp abuse locks export failed", lastError);
  return NextResponse.json({ error: "Failed to export locks" }, { status: 500 });
}
