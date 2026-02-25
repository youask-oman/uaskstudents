import { proxyJson } from "../../_proxy";

export async function POST(request: Request) {
  return proxyJson(request, "POST", "/api/admin/whatsapp/pairing-code/issue");
}

