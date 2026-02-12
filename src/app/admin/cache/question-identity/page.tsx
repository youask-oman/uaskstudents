"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type QIEntry = {
  id: number;
  question_key: string;
  normalized_stem: string;
  normalized_options?: string | null;
  question_type: string;
  solution_json: Record<string, unknown>;
  original_variants: string[];
  hit_count: number;
  created_at: string;
  last_seen_at: string;
};

type CreatePayload = {
  question_key: string;
  normalized_stem: string;
  normalized_options?: string;
  question_type: string;
  solution_json: string;
  original_variants: string;
  hit_count: number;
  reason: string;
};

export default function AdminQuestionIdentityPage() {
  const { pushToast } = useToast();
  const [items, setItems] = useState<QIEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("");
  const [editing, setEditing] = useState<QIEntry | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<CreatePayload>({
    question_key: "",
    normalized_stem: "",
    normalized_options: "",
    question_type: "unknown",
    solution_json: "{}",
    original_variants: "[]",
    hit_count: 0,
    reason: "",
  });

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter((x) => JSON.stringify(x).toLowerCase().includes(q));
  }, [items, search]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/cache/question-identity?limit=200`, { headers });
      if (!res.ok) throw new Error((await parseApiError(res)).message);
      const data = await res.json();
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      pushToast({ type: "error", title: "Load failed", message: err instanceof Error ? err.message : "Failed to load" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const parseVariants = (raw: string): string[] => {
    try {
      const parsed = JSON.parse(raw || "[]");
      return Array.isArray(parsed) ? parsed.map((x) => String(x)) : [];
    } catch {
      return [];
    }
  };

  const createEntry = async () => {
    if (!createForm.reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Create reason is required." });
    let solution: Record<string, unknown> = {};
    try {
      solution = JSON.parse(createForm.solution_json || "{}");
    } catch {
      return pushToast({ type: "error", title: "Invalid JSON", message: "solution_json must be valid JSON." });
    }
    const body = {
      question_key: createForm.question_key,
      normalized_stem: createForm.normalized_stem,
      normalized_options: createForm.normalized_options || undefined,
      question_type: createForm.question_type,
      solution_json: solution,
      original_variants: parseVariants(createForm.original_variants),
      hit_count: createForm.hit_count,
      reason: createForm.reason,
    };
    const res = await fetch(`${API_BASE_URL}/api/v1/admin/cache/question-identity`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Create failed", message: (await parseApiError(res)).message });
    setShowCreate(false);
    await load();
  };

  const updateEntry = async () => {
    if (!editing) return;
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Update reason is required." });
    const res = await fetch(`${API_BASE_URL}/api/v1/admin/cache/question-identity/${editing.id}`, {
      method: "PATCH",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        question_key: editing.question_key,
        normalized_stem: editing.normalized_stem,
        normalized_options: editing.normalized_options || undefined,
        question_type: editing.question_type,
        solution_json: editing.solution_json,
        original_variants: editing.original_variants,
        hit_count: editing.hit_count,
        reason,
      }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Update failed", message: (await parseApiError(res)).message });
    setEditing(null);
    await load();
  };

  const deleteEntry = async (id: number) => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Delete reason is required." });
    const res = await fetch(`${API_BASE_URL}/api/v1/admin/cache/question-identity/${id}`, {
      method: "DELETE",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Delete failed", message: (await parseApiError(res)).message });
    await load();
  };

  return (
    <div className="p-8 max-w-[1500px] mx-auto w-full flex flex-col gap-5">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">Question Identity Cache</h2>
      <p className="text-sm text-slate-500">Full control over `question_identity_cache` records.</p>

      <div className="flex flex-wrap gap-3">
        <input value={search} onChange={(e) => setSearch(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm min-w-[260px]" placeholder="Search..." />
        <input value={reason} onChange={(e) => setReason(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm min-w-[320px]" placeholder="Audit reason for update/delete" />
        <button onClick={() => void load()} className="px-4 py-2 rounded-lg bg-slate-700 text-white text-sm">Refresh</button>
        <button onClick={() => setShowCreate((v) => !v)} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm">New Entry</button>
      </div>

      {showCreate && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <input value={createForm.question_key} onChange={(e) => setCreateForm({ ...createForm, question_key: e.target.value })} className="px-3 py-2 rounded-lg border" placeholder="question_key" />
          <input value={createForm.question_type} onChange={(e) => setCreateForm({ ...createForm, question_type: e.target.value })} className="px-3 py-2 rounded-lg border" placeholder="question_type" />
          <textarea value={createForm.normalized_stem} onChange={(e) => setCreateForm({ ...createForm, normalized_stem: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" rows={2} placeholder="normalized_stem" />
          <input value={createForm.normalized_options || ""} onChange={(e) => setCreateForm({ ...createForm, normalized_options: e.target.value })} className="px-3 py-2 rounded-lg border" placeholder="normalized_options (optional)" />
          <input type="number" value={createForm.hit_count} onChange={(e) => setCreateForm({ ...createForm, hit_count: Number(e.target.value) || 0 })} className="px-3 py-2 rounded-lg border" placeholder="hit_count" />
          <textarea value={createForm.solution_json} onChange={(e) => setCreateForm({ ...createForm, solution_json: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2 font-mono text-xs" rows={5} placeholder="solution_json" />
          <textarea value={createForm.original_variants} onChange={(e) => setCreateForm({ ...createForm, original_variants: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2 font-mono text-xs" rows={3} placeholder='original_variants JSON, e.g. ["q1","q2"]' />
          <input value={createForm.reason} onChange={(e) => setCreateForm({ ...createForm, reason: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" placeholder="create reason (required)" />
          <button onClick={() => void createEntry()} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm">Create</button>
        </div>
      )}

      <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-auto max-h-[740px]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
            <tr>
              <th className="px-3 py-2 text-left">ID</th>
              <th className="px-3 py-2 text-left">Key</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Hits</th>
              <th className="px-3 py-2 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((x) => (
              <tr key={x.id} className="border-t border-slate-200 dark:border-slate-800">
                <td className="px-3 py-2">{x.id}</td>
                <td className="px-3 py-2 font-mono text-xs">{x.question_key}</td>
                <td className="px-3 py-2">{x.question_type}</td>
                <td className="px-3 py-2">{x.hit_count}</td>
                <td className="px-3 py-2 flex gap-2">
                  <button onClick={() => setEditing({ ...x })} className="px-2 py-1 rounded bg-slate-700 text-white text-xs">Edit</button>
                  <button onClick={() => void deleteEntry(x.id)} className="px-2 py-1 rounded bg-rose-600 text-white text-xs">Delete</button>
                </td>
              </tr>
            ))}
            {!loading && filtered.length === 0 && (
              <tr><td className="px-3 py-4 text-slate-500" colSpan={5}>No rows found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <input value={editing.question_key} onChange={(e) => setEditing({ ...editing, question_key: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <input value={editing.question_type} onChange={(e) => setEditing({ ...editing, question_type: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <textarea value={editing.normalized_stem} onChange={(e) => setEditing({ ...editing, normalized_stem: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" rows={2} />
          <input value={editing.normalized_options || ""} onChange={(e) => setEditing({ ...editing, normalized_options: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <input type="number" value={editing.hit_count} onChange={(e) => setEditing({ ...editing, hit_count: Number(e.target.value) || 0 })} className="px-3 py-2 rounded-lg border" />
          <textarea value={JSON.stringify(editing.solution_json || {}, null, 2)} onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              setEditing({ ...editing, solution_json: parsed });
            } catch {
              // ignore invalid json until valid
            }
          }} className="px-3 py-2 rounded-lg border md:col-span-2 font-mono text-xs" rows={5} />
          <textarea value={JSON.stringify(editing.original_variants || [], null, 2)} onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (Array.isArray(parsed)) setEditing({ ...editing, original_variants: parsed.map((x) => String(x)) });
            } catch {
              // ignore invalid json until valid
            }
          }} className="px-3 py-2 rounded-lg border md:col-span-2 font-mono text-xs" rows={3} />
          <div className="flex gap-2">
            <button onClick={() => void updateEntry()} className="px-4 py-2 rounded-lg bg-admin-primary text-white text-sm">Save</button>
            <button onClick={() => setEditing(null)} className="px-4 py-2 rounded-lg bg-slate-500 text-white text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}

