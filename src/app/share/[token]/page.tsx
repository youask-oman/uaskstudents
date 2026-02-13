import { Metadata } from "next";
import { notFound } from "next/navigation";
import ShareReadonlyClient from "./ShareReadonlyClient";

interface PublicSharePayload {
  attempt_id: string;
  paper: Record<string, unknown>;
  problem: Record<string, unknown>;
  created_at?: string | null;
  visibility: "PUBLIC";
}

export const metadata: Metadata = {
  title: "Shared Solution",
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

async function loadSharedPayload(token: string): Promise<PublicSharePayload> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:9000";
  const response = await fetch(`${apiBase}/api/v1/shares/public/${encodeURIComponent(token)}`, {
    cache: "no-store",
    headers: {
      "x-forwarded-host": "share-view",
    },
  });
  if (response.status === 404) {
    notFound();
  }
  if (!response.ok) {
    throw new Error("Failed to load shared solution");
  }
  return (await response.json()) as PublicSharePayload;
}

export default async function SharedSolutionPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const payload = await loadSharedPayload(token);
  return <ShareReadonlyClient payload={payload} />;
}

