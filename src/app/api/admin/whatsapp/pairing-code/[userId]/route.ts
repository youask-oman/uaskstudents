import { proxyJson } from "../../_proxy";

type Params = { params: Promise<{ userId: string }> };

export async function GET(request: Request, context: Params) {
  const { userId } = await context.params;
  return proxyJson(request, "GET", `/api/admin/whatsapp/pairing-code/${encodeURIComponent(userId)}`);
}

export async function DELETE(request: Request, context: Params) {
  const { userId } = await context.params;
  return proxyJson(request, "DELETE", `/api/admin/whatsapp/pairing-code/${encodeURIComponent(userId)}`);
}
