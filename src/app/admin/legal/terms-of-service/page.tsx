"use client";

import { useEffect, useMemo, useState } from "react";
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

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token]
  );

  const refresh = async () => {
    const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents?key=terms_of_service`, { headers });
    if (!res.ok) return;
    const data = (await res.json()) as LegalListItem[];
    setItems(data);
    const nextId = selectedId ?? data[0]?.id ?? null;
    setSelectedId(nextId);
    if (!nextId) return;
    const detailRes = await fetch(`${API_BASE_URL}/api/admin/legal-documents/${nextId}`, { headers });
    if (!detailRes.ok) return;
    const detail = (await detailRes.json()) as LegalDetail;
    setDoc(detail);
    setContentMd(detail.content_md || "");
    setEffectiveAt(detail.effective_at ? detail.effective_at.slice(0, 10) : "");
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveDraft = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents`, {
        method: "PUT",
        headers,
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
      await refresh();
    } catch (error) {
      pushToast({ type: "error", title: "Save failed", message: error instanceof Error ? error.message : "Unknown error" });
    } finally {
      setSaving(false);
    }
  };

  const createDraft = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents`, {
        method: "POST",
        headers,
        body: JSON.stringify({ key: "terms_of_service", generate_from_inventory: true }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Created draft from terms file" });
      await refresh();
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
      const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents/${doc.id}/publish`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          effective_at: effectiveAt ? new Date(`${effectiveAt}T00:00:00.000Z`).toISOString() : undefined,
        }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Published Terms" });
      await refresh();
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
                const detailRes = await fetch(`${API_BASE_URL}/api/admin/legal-documents/${item.id}`, { headers });
                if (!detailRes.ok) return;
                const detail = (await detailRes.json()) as LegalDetail;
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
