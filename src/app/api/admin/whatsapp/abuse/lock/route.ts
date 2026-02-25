import { proxyJson } from "../../_proxy";

export async function POST(request: Request) {
  return proxyJson(request, "POST", "/api/admin/whatsapp/abuse/lock");
}

export async function DELETE(request: Request) {
  return proxyJson(request, "DELETE", "/api/admin/whatsapp/abuse/lock");
}
