import { proxyJson } from "../../_proxy";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ userId: string }> }
) {
  const resolved = await params;
  return proxyJson(request, "PATCH", `/api/admin/whatsapp/users/${encodeURIComponent(resolved.userId)}`);
}
