import { proxyJson } from "../_proxy";
#claude
export async function POST(request: Request) {
  return proxyJson(request, "POST", "/api/admin/whatsapp/initialize");
}
