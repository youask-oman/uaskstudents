import { proxyJson } from "../_proxy";

export async function GET(request: Request) {
  return proxyJson(request, "GET", "/api/admin/whatsapp/status");
}
