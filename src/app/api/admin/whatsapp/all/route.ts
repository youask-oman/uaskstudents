import { proxyJson } from "../_proxy";

export async function DELETE(request: Request) {
  return proxyJson(request, "DELETE", "/api/v1/admin/whatsapp/all");
}

