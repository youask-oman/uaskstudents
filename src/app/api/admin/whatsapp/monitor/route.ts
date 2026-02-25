import { proxyJson } from "../_proxy";

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const limit = searchParams.get("limit") || "50";
    const phone = searchParams.get("phone") || "";
    const direction = searchParams.get("direction") || "";
    const qs = new URLSearchParams({ limit });
    if (phone) qs.set("phone", phone);
    if (direction) qs.set("direction", direction);
    return proxyJson(request, "GET", "/api/admin/whatsapp/monitor", qs.toString());
}
