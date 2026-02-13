import fs from "fs/promises";
import path from "path";

export type PublicLegalDocument = {
  id?: number;
  key: string;
  version: string;
  status: string;
  content_md: string;
  content_html?: string;
  effective_at?: string | null;
  published_at?: string | null;
  checksum_sha256?: string;
};

export function formatEffectiveDate(effectiveAt?: string | null): string {
  if (!effectiveAt) {
    return "Not published yet";
  }
  const dt = new Date(effectiveAt);
  if (Number.isNaN(dt.getTime())) {
    return "Not published yet";
  }
  // Keep this deterministic across server/client environments.
  return dt.toLocaleDateString("en-US", { timeZone: "UTC" });
}

const SERVER_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:9000";

export async function fetchPublicPrivacyPolicy(version?: string): Promise<PublicLegalDocument> {
  const query = version ? `?version=${encodeURIComponent(version)}` : "";
  const res = await fetch(`${SERVER_API_BASE_URL}/api/legal/privacy${query}`, { cache: "no-store" });
  if (res.ok) {
    return (await res.json()) as PublicLegalDocument;
  }

  const fallbackPath = path.join(process.cwd(), "privacy_policy.md");
  const fallbackMd = await fs.readFile(fallbackPath, "utf-8");
  return {
    key: "privacy_policy",
    version: "local-fallback",
    status: "draft",
    content_md: fallbackMd,
    effective_at: null,
    published_at: null,
  };
}

export async function fetchPublicTermsOfService(version?: string): Promise<PublicLegalDocument> {
  const query = version ? `?version=${encodeURIComponent(version)}` : "";
  const res = await fetch(`${SERVER_API_BASE_URL}/api/legal/terms${query}`, { cache: "no-store" });
  if (res.ok) {
    return (await res.json()) as PublicLegalDocument;
  }

  const fallbackPath = path.join(process.cwd(), "terms_of_service.md");
  const fallbackMd = await fs.readFile(fallbackPath, "utf-8");
  return {
    key: "terms_of_service",
    version: "local-fallback",
    status: "draft",
    content_md: fallbackMd,
    effective_at: null,
    published_at: null,
  };
}
