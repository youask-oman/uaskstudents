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
  created_at: string;
  updated_at: string;
};

type LegalDetail = LegalListItem & {
  content_md: string;
  content_html: string;
};

export default function AdminPrivacyPolicyPage() {
  const { pushToast } = useToast();
  const [items, setItems] = useState<LegalListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [doc, setDoc] = useState<LegalDetail | null>(null);
  const [contentMd, setContentMd] = useState("");
  const [effectiveAt, setEffectiveAt] = useState("");
  const [loading, setLoading] = useState(true);
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
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents?key=privacy_policy`, { headers });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as LegalListItem[];
      setItems(data);
      const nextId = selectedId ?? data[0]?.id ?? null;
      setSelectedId(nextId);
      if (nextId) {
        const detail = await fetch(`${API_BASE_URL}/api/admin/legal-documents/${nextId}`, { headers });
        if (!detail.ok) {
          const err = await parseApiError(detail);
          throw new Error(err.message);
        }
        const detailJson = (await detail.json()) as LegalDetail;
        setDoc(detailJson);
        setContentMd(detailJson.content_md || "");
        setEffectiveAt(detailJson.effective_at ? detailJson.effective_at.slice(0, 10) : "");
      } else {
        setDoc(null);
        setContentMd("");
        setEffectiveAt("");
      }
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
      const payload = {
        id: doc?.id ?? undefined,
        key: "privacy_policy",
        content_md: contentMd,
        effective_at: effectiveAt ? new Date(`${effectiveAt}T00:00:00.000Z`).toISOString() : undefined,
      };
      const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents`, {
        method: "PUT",
        headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Saved draft" });
      await refresh();
    } catch (error) {
      pushToast({
        type: "error",
        title: "Failed to save draft",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setSaving(false);
    }
  };

  const createGeneratedDraft = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents`, {
        method: "POST",
        headers,
        body: JSON.stringify({ key: "privacy_policy", generate_from_inventory: true }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Generated new draft from inventory" });
      await refresh();
    } catch (error) {
      pushToast({
        type: "error",
        title: "Failed to generate draft",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setSaving(false);
    }
  };

  const publishCurrent = async () => {
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
      pushToast({ type: "success", title: "Published privacy policy" });
      await refresh();
    } catch (error) {
      pushToast({
        type: "error",
        title: "Failed to publish",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
      <aside className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 h-fit">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">Privacy Policy Versions</h2>
          <button className="px-2 py-1 text-xs border rounded" onClick={() => void refresh()} disabled={loading}>
            Refresh
          </button>
        </div>
        <div className="space-y-2">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={async () => {
                setSelectedId(item.id);
                const res = await fetch(`${API_BASE_URL}/api/admin/legal-documents/${item.id}`, { headers });
                if (!res.ok) return;
                const detail = (await res.json()) as LegalDetail;
                setDoc(detail);
                setContentMd(detail.content_md || "");
                setEffectiveAt(detail.effective_at ? detail.effective_at.slice(0, 10) : "");
              }}
              className={`w-full text-left border rounded-lg px-3 py-2 ${
                selectedId === item.id ? "border-admin-primary bg-admin-primary/10" : "border-slate-200 dark:border-slate-700"
              }`}
            >
              <p className="text-xs font-bold text-slate-800 dark:text-slate-100">{item.version}</p>
              <p className="text-[11px] text-slate-500 uppercase tracking-wide">{item.status}</p>
              <p className="text-[10px] text-slate-400 font-mono truncate">{item.checksum_sha256}</p>
            </button>
          ))}
          {!items.length && <p className="text-xs text-slate-500">No legal documents yet.</p>}
        </div>
      </aside>

      <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div className="flex flex-wrap gap-3 items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">Legal Documents - Privacy Policy Editor</h1>
          <div className="flex gap-2">
            <button className="px-3 py-2 rounded border text-xs font-semibold" onClick={createGeneratedDraft} disabled={saving}>
              New Draft from Inventory
            </button>
            <button className="px-3 py-2 rounded bg-admin-primary text-white text-xs font-semibold" onClick={saveDraft} disabled={saving}>
              Save Draft
            </button>
            <button className="px-3 py-2 rounded bg-emerald-600 text-white text-xs font-semibold" onClick={publishCurrent} disabled={saving || !doc}>
              Publish
            </button>
          </div>
        </div>

        <div className="mb-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs uppercase tracking-widest text-slate-500">Effective Date</label>
            <input
              type="date"
              className="mt-1 w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
              value={effectiveAt}
              onChange={(e) => setEffectiveAt(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-slate-500">Version</label>
            <div className="mt-1 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-sm">
              {doc?.version || "new draft"}
            </div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-slate-500">Checksum</label>
            <div className="mt-1 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-xs font-mono truncate">
              {doc?.checksum_sha256 || "pending"}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div>
            <label className="text-xs uppercase tracking-widest text-slate-500">Markdown</label>
            <textarea
              className="mt-1 w-full min-h-[640px] rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-mono"
              value={contentMd}
              onChange={(e) => setContentMd(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-slate-500">Preview</label>
            <article className="mt-1 min-h-[640px] rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-4 py-3 prose prose-slate dark:prose-invert max-w-none markdown-math overflow-auto">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {contentMd || "_No content yet._"}
              </ReactMarkdown>
            </article>
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700">
          <p className="font-semibold mb-1">TODO Checklist</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>[LEGAL_ENTITY_NAME]</li>
            <li>[BUSINESS_ADDRESS]</li>
            <li>[PRIVACY_CONTACT_EMAIL]</li>
            <li>Confirm model training policy on user content.</li>
            <li>Confirm uploads storage region/residency.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
