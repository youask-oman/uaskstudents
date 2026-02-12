"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type LlmUsageItem = {
  id: number;
  solve_session_id: number;
  followup_turn_id?: number | null;
  user_id?: number | null;
  provider: string;
  model: string;
  request_id?: string | null;
  system_prompt_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms?: number | null;
  created_at: string;
};

type LlmUsageListResponse = {
  total: number;
  items: LlmUsageItem[];
};

type CreatePayload = {
  solve_session_id: number;
  followup_turn_id?: number;
  provider: string;
  model: string;
  request_id?: string;
  system_prompt_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens?: number;
  latency_ms?: number;
  reason: string;
};

type UpdatePayload = {
  provider?: string;
  model?: string;
  request_id?: string;
  system_prompt_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  latency_ms?: number;
  reason: string;
};

const emptyCreate: CreatePayload = {
  solve_session_id: 0,
  provider: "openai",
  model: "gpt-5-mini",
  system_prompt_tokens: 0,
  input_tokens: 0,
  output_tokens: 0,
  reason: "",
};

export default function AdminLlmUsagePage() {
  const { pushToast } = useToast();
  const [items, setItems] = useState<LlmUsageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [userId, setUserId] = useState("");
  const [editing, setEditing] = useState<LlmUsageItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<CreatePayload>(emptyCreate);
  const [updateReason, setUpdateReason] = useState("");
  const [deleteReason, setDeleteReason] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

  const filtered = useMemo(() => {
    if (!query.trim()) return items;
    const q = query.toLowerCase();
    return items.filter((x) => JSON.stringify(x).toLowerCase().includes(q));
  }, [items, query]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (provider.trim()) params.set("provider", provider.trim());
      if (model.trim()) params.set("model", model.trim());
      if (userId.trim()) params.set("user_id", userId.trim());
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/observability/llm-usage?${params.toString()}`, {
        headers,
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as LlmUsageListResponse;
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotal(Number(data.total || 0));
    } catch (err) {
      pushToast({
        type: "error",
        title: "Failed to load LLM usage",
        message: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreate = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/observability/llm-usage`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(createForm),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      setShowCreate(false);
      setCreateForm(emptyCreate);
      await fetchItems();
      pushToast({ type: "success", title: "Created", message: "LLM usage entry created." });
    } catch (err) {
      pushToast({
        type: "error",
        title: "Create failed",
        message: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  const onUpdate = async () => {
    if (!editing) return;
    const payload: UpdatePayload = {
      provider: editing.provider,
      model: editing.model,
      request_id: editing.request_id || undefined,
      system_prompt_tokens: editing.system_prompt_tokens,
      input_tokens: editing.input_tokens,
      output_tokens: editing.output_tokens,
      total_tokens: editing.total_tokens,
      latency_ms: editing.latency_ms ?? undefined,
      reason: updateReason,
    };
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/observability/llm-usage/${editing.id}`, {
        method: "PATCH",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      setEditing(null);
      setUpdateReason("");
      await fetchItems();
      pushToast({ type: "success", title: "Updated", message: "LLM usage entry updated." });
    } catch (err) {
      pushToast({
        type: "error",
        title: "Update failed",
        message: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  const onDelete = async () => {
    if (!editing) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/observability/llm-usage/${editing.id}`, {
        method: "DELETE",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ reason: deleteReason }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      setEditing(null);
      setDeleteReason("");
      await fetchItems();
      pushToast({ type: "success", title: "Deleted", message: "LLM usage entry deleted." });
    } catch (err) {
      pushToast({
        type: "error",
        title: "Delete failed",
        message: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  return (
    <div className="p-8 max-w-[1500px] mx-auto w-full flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">LLM Usage Ledger</h2>
        <p className="text-sm text-slate-500">Full admin control over `llmusageledger` records (read/create/update/delete).</p>
      </header>

      <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex flex-wrap gap-3">
        <input
          className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          placeholder="Search all fields"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          placeholder="Provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        />
        <input
          className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          placeholder="Model"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
        <input
          className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          placeholder="User ID"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        />
        <button
          onClick={() => void fetchItems()}
          className="px-4 py-2 rounded-lg bg-admin-primary text-white text-sm font-semibold"
        >
          Refresh
        </button>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold"
        >
          {showCreate ? "Close Create" : "Create Entry"}
        </button>
        <div className="ml-auto text-sm text-slate-500 self-center">
          Total: {total} | Showing: {filtered.length}
        </div>
      </section>

      {showCreate && (
        <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <input className="px-3 py-2 rounded-lg border" placeholder="Solve Session ID" type="number" value={createForm.solve_session_id || ""} onChange={(e) => setCreateForm({ ...createForm, solve_session_id: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Follow-up Turn ID" type="number" value={createForm.followup_turn_id || ""} onChange={(e) => setCreateForm({ ...createForm, followup_turn_id: Number(e.target.value) || undefined })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Request ID" value={createForm.request_id || ""} onChange={(e) => setCreateForm({ ...createForm, request_id: e.target.value })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Provider" value={createForm.provider} onChange={(e) => setCreateForm({ ...createForm, provider: e.target.value })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Model" value={createForm.model} onChange={(e) => setCreateForm({ ...createForm, model: e.target.value })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Latency ms" type="number" value={createForm.latency_ms || ""} onChange={(e) => setCreateForm({ ...createForm, latency_ms: Number(e.target.value) || undefined })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="System prompt tokens" type="number" value={createForm.system_prompt_tokens} onChange={(e) => setCreateForm({ ...createForm, system_prompt_tokens: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Input tokens" type="number" value={createForm.input_tokens} onChange={(e) => setCreateForm({ ...createForm, input_tokens: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" placeholder="Output tokens" type="number" value={createForm.output_tokens} onChange={(e) => setCreateForm({ ...createForm, output_tokens: Number(e.target.value) || 0 })} />
          <input className="md:col-span-2 px-3 py-2 rounded-lg border" placeholder="Reason (required)" value={createForm.reason} onChange={(e) => setCreateForm({ ...createForm, reason: e.target.value })} />
          <button onClick={() => void onCreate()} className="px-4 py-2 rounded-lg bg-emerald-600 text-white font-semibold">
            Create
          </button>
        </section>
      )}

      <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-auto max-h-[700px]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
              <tr className="text-left text-slate-500">
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">User</th>
                <th className="px-3 py-2">Session</th>
                <th className="px-3 py-2">Provider/Model</th>
                <th className="px-3 py-2">Tokens</th>
                <th className="px-3 py-2">Latency</th>
                <th className="px-3 py-2">Request ID</th>
                <th className="px-3 py-2">Created</th>
                <th className="px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {!loading &&
                filtered.map((x) => (
                  <tr key={x.id} className="border-t border-slate-200 dark:border-slate-800">
                    <td className="px-3 py-2">{x.id}</td>
                    <td className="px-3 py-2">{x.user_id ?? "n/a"}</td>
                    <td className="px-3 py-2">{x.solve_session_id}</td>
                    <td className="px-3 py-2">{x.provider} / {x.model}</td>
                    <td className="px-3 py-2">{x.system_prompt_tokens} + {x.input_tokens} + {x.output_tokens} = {x.total_tokens}</td>
                    <td className="px-3 py-2">{x.latency_ms ?? "n/a"}</td>
                    <td className="px-3 py-2 font-mono text-xs">{x.request_id || "n/a"}</td>
                    <td className="px-3 py-2">{new Date(x.created_at).toLocaleString()}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => setEditing({ ...x })} className="px-3 py-1 rounded bg-slate-700 text-white text-xs">
                        Edit/Delete
                      </button>
                    </td>
                  </tr>
                ))}
              {loading && (
                <tr>
                  <td className="px-4 py-4 text-slate-500" colSpan={9}>Loading...</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {editing && (
        <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <input className="px-3 py-2 rounded-lg border" value={editing.provider} onChange={(e) => setEditing({ ...editing, provider: e.target.value })} />
          <input className="px-3 py-2 rounded-lg border" value={editing.model} onChange={(e) => setEditing({ ...editing, model: e.target.value })} />
          <input className="px-3 py-2 rounded-lg border" value={editing.request_id || ""} onChange={(e) => setEditing({ ...editing, request_id: e.target.value })} />
          <input className="px-3 py-2 rounded-lg border" type="number" value={editing.system_prompt_tokens} onChange={(e) => setEditing({ ...editing, system_prompt_tokens: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" type="number" value={editing.input_tokens} onChange={(e) => setEditing({ ...editing, input_tokens: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" type="number" value={editing.output_tokens} onChange={(e) => setEditing({ ...editing, output_tokens: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" type="number" value={editing.total_tokens} onChange={(e) => setEditing({ ...editing, total_tokens: Number(e.target.value) || 0 })} />
          <input className="px-3 py-2 rounded-lg border" type="number" value={editing.latency_ms || ""} onChange={(e) => setEditing({ ...editing, latency_ms: Number(e.target.value) || null })} />
          <div />
          <input className="md:col-span-2 px-3 py-2 rounded-lg border" placeholder="Update reason (required)" value={updateReason} onChange={(e) => setUpdateReason(e.target.value)} />
          <button onClick={() => void onUpdate()} className="px-4 py-2 rounded-lg bg-admin-primary text-white font-semibold">
            Save Update
          </button>
          <input className="md:col-span-2 px-3 py-2 rounded-lg border" placeholder="Delete reason (required)" value={deleteReason} onChange={(e) => setDeleteReason(e.target.value)} />
          <button onClick={() => void onDelete()} className="px-4 py-2 rounded-lg bg-rose-600 text-white font-semibold">
            Delete Entry
          </button>
          <button onClick={() => setEditing(null)} className="px-4 py-2 rounded-lg bg-slate-500 text-white font-semibold">
            Close
          </button>
        </section>
      )}
    </div>
  );
}

