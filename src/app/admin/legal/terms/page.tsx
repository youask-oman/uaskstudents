"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type LegalListItem = {
  id: number;
  key: string;
  version: string;
  status: "draft" | "published";
  effective_at?: string | null;
  published_at?: string | null;
  checksum_sha256: string;
};

type LegalDetail = LegalListItem & {
  content_md: string;
  content_html: string;
};

export default function AdminTermsOfServicePage() {
  const { pushToast } = useToast();
  const [items, setItems] = useState<LegalListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [doc, setDoc] = useState<LegalDetail | null>(null);
  const [contentMd, setContentMd] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [bootstrapped, setBootstrapped] = useState(false);

  const baseUrl = API_BASE_URL;
  const fallbackUrl = process.env.NEXT_PUBLIC_API_FALLBACK_URL || API_BASE_URL || "http://localhost:9000";

  const getHeaders = (contentType = false): HeadersInit => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    return {
      ...(contentType ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchAdmin = async (path: string, init?: RequestInit) => {
    const candidates = Array.from(
      new Set(
        [baseUrl, fallbackUrl, "http://localhost:9000", "http://127.0.0.1:9000"]
          .map((x) => (x || "").trim())
          .filter(Boolean),
      ),
    );
    let lastNetworkError: unknown = null;

    for (const candidate of candidates) {
      try {
        const res = await fetch(`${candidate}${path}`, {
          ...init,
          headers: {
            ...getHeaders(Boolean(init?.body)),
            ...(init?.headers || {}),
          },
        });
        // If a base points to the wrong app/server, keep trying other candidates.
        if (res.status === 404 || res.status >= 500) {
          continue;
        }
        return res;
      } catch (err) {
        lastNetworkError = err;
      }
    }

    if (lastNetworkError) {
      throw new Error("Network error");
    }
    throw new Error("API endpoint not reachable");
  };

  const loadDetailWithTermsFallback = async (id: number): Promise<LegalDetail> => {
    const detailRes = await fetchAdmin(`/api/admin/legal-documents/${id}`);
    if (!detailRes.ok) {
      const err = await parseApiError(detailRes);
      throw new Error(err.message);
    }
    let detail = (await detailRes.json()) as LegalDetail;

    // If a draft exists but is empty, seed it from terms_of_service.md inventory.
    if ((detail.content_md || "").trim().length === 0) {
      const seedRes = await fetchAdmin(`/api/admin/legal-documents`, {
        method: "PUT",
        body: JSON.stringify({
          id: detail.id,
          key: "terms_of_service",
          generate_from_inventory: true,
        }),
      });
      if (seedRes.ok) {
        const seedPayload = await seedRes.json();
        const seededId = typeof seedPayload?.id === "number" ? seedPayload.id : detail.id;
        const seededDetailRes = await fetchAdmin(`/api/admin/legal-documents/${seededId}`);
        if (seededDetailRes.ok) {
          detail = (await seededDetailRes.json()) as LegalDetail;
        }
      }
    }

    // Final fallback: pull inventory source directly and persist into this draft.
    if ((detail.content_md || "").trim().length === 0) {
      const inventoryRes = await fetchAdmin(`/api/legal/terms/inventory`);
      if (inventoryRes.ok) {
        const inv = (await inventoryRes.json()) as { content_md?: string };
        const fallbackMd = (inv.content_md || "").trim();
        if (fallbackMd) {
          detail = { ...detail, content_md: fallbackMd };
          await fetchAdmin(`/api/admin/legal-documents`, {
            method: "PUT",
            body: JSON.stringify({
              id: detail.id,
              key: "terms_of_service",
              content_md: fallbackMd,
            }),
          });
        }
      }
    }

    return detail;
  };

  const refresh = async (preferredId?: number | null) => {
    setLoading(true);
    try {
      const res = await fetchAdmin(`/api/admin/legal-documents?key=terms_of_service`);
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      let data = (await res.json()) as LegalListItem[];
      if (data.length === 0 && !bootstrapped) {
        const createRes = await fetchAdmin(`/api/admin/legal-documents`, {
          method: "POST",
          body: JSON.stringify({ key: "terms_of_service", generate_from_inventory: true }),
        });
        if (createRes.ok) {
          setBootstrapped(true);
          const retryRes = await fetchAdmin(`/api/admin/legal-documents?key=terms_of_service`);
          if (retryRes.ok) {
            data = (await retryRes.json()) as LegalListItem[];
          }
        }
      }
      setItems(data);
      const availableIds = new Set(data.map((d) => d.id));
      const latestPublishedId = data.find((d) => d.status === "published")?.id ?? null;
      const nextId =
        (preferredId && availableIds.has(preferredId) ? preferredId : null) ??
        (selectedId && availableIds.has(selectedId) ? selectedId : null) ??
        (latestPublishedId && availableIds.has(latestPublishedId) ? latestPublishedId : null) ??
        data[0]?.id ??
        null;
      setSelectedId(nextId);
      if (!nextId) {
        setDoc(null);
        setContentMd("");
        setEffectiveAt("");
        return;
      }
      const detail = await loadDetailWithTermsFallback(nextId);
      setDoc(detail);
      setContentMd(detail.content_md || "");
      setEffectiveAt(detail.effective_at ? detail.effective_at.slice(0, 10) : "");
    } catch (error) {
      pushToast({
        type: "error",
        title: "Failed to load legal documents",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveDraft = async () => {
    setSaving(true);
    try {
      const res = await fetchAdmin(`/api/admin/legal-documents`, {
        method: "PUT",
        body: JSON.stringify({
          id: doc?.id ?? undefined,
          key: "terms_of_service",
          content_md: contentMd,
          effective_at: effectiveAt ? new Date(`${effectiveAt}T00:00:00.000Z`).toISOString() : undefined,
        }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Saved draft" });
      const payload = await res.json();
      const nextId = typeof payload?.id === "number" ? payload.id : null;
      await refresh(nextId);
    } catch (error) {
      pushToast({ type: "error", title: "Save failed", message: error instanceof Error ? error.message : "Unknown error" });
    } finally {
      setSaving(false);
    }
  };

  const createDraft = async () => {
    setSaving(true);
    try {
      const res = await fetchAdmin(`/api/admin/legal-documents`, {
        method: "POST",
        body: JSON.stringify({ key: "terms_of_service", generate_from_inventory: true }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Created draft from terms file" });
      const payload = await res.json();
      const nextId = typeof payload?.id === "number" ? payload.id : null;
      await refresh(nextId);
    } catch (error) {
      pushToast({ type: "error", title: "Create failed", message: error instanceof Error ? error.message : "Unknown error" });
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    if (!doc?.id) return;
    setSaving(true);
    try {
      // Persist current editor content first; this also creates a new draft/version
      // when attempting to update an already-published document.
      const upsertRes = await fetchAdmin(`/api/admin/legal-documents`, {
        method: "PUT",
        body: JSON.stringify({
          id: doc.id,
          key: "terms_of_service",
          content_md: contentMd,
          effective_at: effectiveAt ? new Date(`${effectiveAt}T00:00:00.000Z`).toISOString() : undefined,
        }),
      });
      if (!upsertRes.ok) {
        const err = await parseApiError(upsertRes);
        throw new Error(err.message);
      }
      const upsertPayload = await upsertRes.json();
      const publishId = typeof upsertPayload?.id === "number" ? upsertPayload.id : doc.id;

      const res = await fetchAdmin(`/api/admin/legal-documents/${publishId}/publish`, {
        method: "POST",
        body: JSON.stringify({
          effective_at: effectiveAt ? new Date(`${effectiveAt}T00:00:00.000Z`).toISOString() : undefined,
        }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Published Terms" });
      await refresh(publishId);
    } catch (error) {
      pushToast({ type: "error", title: "Publish failed", message: error instanceof Error ? error.message : "Unknown error" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
      <aside className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 h-fit">
        <h2 className="text-lg font-bold mb-3">ToS Versions</h2>
        <div className="space-y-2">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={async () => {
                setSelectedId(item.id);
                const detail = await loadDetailWithTermsFallback(item.id);
                setDoc(detail);
                setContentMd(detail.content_md || "");
                setEffectiveAt(detail.effective_at ? detail.effective_at.slice(0, 10) : "");
              }}
              className={`w-full text-left border rounded-lg px-3 py-2 ${selectedId === item.id ? "border-admin-primary bg-admin-primary/10" : "border-slate-200 dark:border-slate-700"}`}
            >
              <p className="text-xs font-bold">{item.version}</p>
              <p className="text-[11px] text-slate-500 uppercase">{item.status}</p>
            </button>
          ))}
        </div>
      </aside>

      <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        {loading && <p className="text-xs text-slate-500 mb-3">Loading legal documents...</p>}
        <div className="flex flex-wrap gap-2 justify-between items-center mb-4">
          <h1 className="text-xl font-bold">Legal - Terms of Service</h1>
          <div className="flex gap-2">
            <button className="px-3 py-2 text-xs rounded border" onClick={createDraft} disabled={saving}>New Draft</button>
            <button className="px-3 py-2 text-xs rounded bg-admin-primary text-white" onClick={saveDraft} disabled={saving}>Save Draft</button>
            <button className="px-3 py-2 text-xs rounded bg-emerald-600 text-white" onClick={publish} disabled={saving || !doc}>Publish</button>
          </div>
        </div>

        <div className="mb-4">
          <label className="text-xs uppercase tracking-widest text-slate-500">Effective Date</label>
          <input
            type="date"
            className="mt-1 w-64 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            value={effectiveAt}
            onChange={(e) => setEffectiveAt(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <textarea
            className="w-full min-h-[680px] rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-mono"
            value={contentMd}
            onChange={(e) => setContentMd(e.target.value)}
          />
          <article className="min-h-[680px] rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-4 py-3 prose prose-slate dark:prose-invert max-w-none markdown-math overflow-auto">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {contentMd || "_No content yet._"}
            </ReactMarkdown>
          </article>
        </div>
      </section>
    </div>
  );
}
