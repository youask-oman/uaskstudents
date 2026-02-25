import { proxyJson } from "../../../_proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ userId: string }> }
) {
  const resolved = await params;
  const { searchParams } = new URL(request.url);
  const qs = new URLSearchParams();
  for (const [key, value] of searchParams.entries()) {
    if (value !== "") qs.set(key, value);
  }
  return proxyJson(
    request,
    "GET",
    `/api/admin/whatsapp/users/${encodeURIComponent(resolved.userId)}/transactions`,
    qs.toString()
  );
}
