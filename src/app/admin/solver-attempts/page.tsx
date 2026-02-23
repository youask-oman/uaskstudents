"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

interface SolverOutputAttemptListItem {
  id: number;
  request_id: string;
  user_id?: number | null;
  session_id?: number | null;
  message_id?: number | null;
  output_format: string;
  prompt_id?: string | null;
  prompt_version?: string | null;
  attempt_number: number;
  provider?: string | null;
  model?: string | null;
  latency_ms?: number | null;
  char_count: number;
  status: string;
  archive_path?: string | null;
  created_at: string;
  output_preview: string;
}

interface SolverOutputAttemptDetail extends SolverOutputAttemptListItem {
  extracted_answer?: string | null;
  validation_json?: Record<string, unknown> | null;
  error_message?: string | null;
  raw_solution_text: string;
}

export default function AdminSolverAttemptsPage() {
  const { pushToast } = useToast();
  const [rows, setRows] = useState<SolverOutputAttemptListItem[]>([]);
  const [selected, setSelected] = useState<SolverOutputAttemptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [format, setFormat] = useState("");

  const getHeaders = () => {
    const token = localStorage.getItem("token");
    return token ? ({ Authorization: `Bearer ${token}` } as HeadersInit) : {};
  };

  const fetchRows = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: "500",
        offset: "0",
      });
      if (query.trim()) params.set("request_id", query.trim());
      if (status) params.set("status", status);
      if (format) params.set("output_format", format);
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/solver-output-attempts?${params.toString()}`, {
        headers: getHeaders(),
      });
      if (!res.ok) throw new Error("Failed to load solver attempts");
      const data = (await res.json()) as SolverOutputAttemptListItem[];
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      setError((err as Error).message || "Unable to load solver output attempts.");
    } finally {
      setLoading(false);
    }
  };

  const fetchDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/solver-output-attempts/${id}`, {
        headers: getHeaders(),
      });
      if (!res.ok) throw new Error("Failed to load details");
      const data = (await res.json()) as SolverOutputAttemptDetail;
      setSelected(data);
    } catch (err) {
      setError((err as Error).message || "Unable to load attempt detail.");
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    void fetchRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => rows, [rows]);

  return (
    <div className="p-8 max-w-[1500px] mx-auto w-full flex flex-col gap-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Solver Output Attempts</h1>
        <p className="text-sm text-slate-500">Inspect each solver transaction and open full model output quickly.</p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <input
          className="w-[360px] rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
          placeholder="Search by request_id..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All Status</option>
          <option value="success">success</option>
          <option value="failure">failure</option>
          <option value="processing">processing</option>
          <option value="ambiguous">ambiguous</option>
          <option value="error">error</option>
        </select>
        <select
          className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
          value={format}
          onChange={(e) => setFormat(e.target.value)}
        >
          <option value="">All Formats</option>
          <option value="freeform">freeform</option>
          <option value="json_schema">json_schema</option>
        </select>
        <button
          type="button"
          className="rounded-lg bg-admin-primary text-white px-4 py-2 text-sm font-semibold"
          onClick={() => void fetchRows()}
        >
          Refresh
        </button>
        <button
          type="button"
          className="rounded-lg bg-rose-500 hover:bg-rose-600 text-white px-4 py-2 text-sm font-semibold"
          onClick={async () => {
            if (!confirm("Are you sure you want to PERMANENTLY delete ALL solver attempts?")) return;
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_BASE_URL}/api/v1/admin/solver-attempts/all`, {
              method: "DELETE",
              headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
              fetchRows();
            } else {
              const err = await parseApiError(res);
              pushToast({
                type: "error",
                title: "Failed to clear attempts",
                message: err.message,
                requestId: err.requestId,
              });
            }
          }}
        >
          Clear All
        </button>
        <span className="text-xs text-slate-500">{filtered.length} rows</span>
      </div>

      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 text-rose-700 px-4 py-2 text-sm">{error}</div> : null}

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-6">
        <section className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
          <div className="max-h-[720px] overflow-y-auto divide-y divide-slate-200 dark:divide-slate-800">
            {loading ? (
              <div className="p-6 text-sm text-slate-500">Loading...</div>
            ) : filtered.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">No solver attempts found.</div>
            ) : (
              filtered.map((row) => (
                <button
                  type="button"
                  key={row.id}
                  onClick={() => void fetchDetail(row.id)}
                  className="w-full text-left px-5 py-4 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
                >
                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                    <span className="font-mono text-slate-700 dark:text-slate-200">{row.request_id}</span>
                    <span>id:{row.id}</span>
                    <span>user:{row.user_id ?? "-"}</span>
                    <span>{row.provider || "-"}</span>
                    <span>{row.model || "-"}</span>
                    <span>{row.status}</span>
                    <span>{row.char_count} chars</span>
                    <span>{row.latency_ms ?? "-"} ms</span>
                    <span>{new Date(row.created_at).toLocaleString()}</span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 line-clamp-2">{row.output_preview || "(empty)"}</p>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Attempt Details</h2>
            <button
              type="button"
              className="rounded-md border border-slate-300 dark:border-slate-700 px-2 py-1 text-xs"
              disabled={!selected?.raw_solution_text}
              onClick={async () => {
                if (!selected?.raw_solution_text) return;
                await navigator.clipboard.writeText(selected.raw_solution_text);
              }}
            >
              Copy Output
            </button>
          </div>

          {detailLoading ? (
            <div className="text-sm text-slate-500">Loading details...</div>
          ) : !selected ? (
            <div className="text-sm text-slate-500">Select an attempt to view full output.</div>
          ) : (
            <>
              <pre className="text-[11px] whitespace-pre-wrap break-words rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 p-3 max-h-[200px] overflow-y-auto">
                {JSON.stringify(
                  {
                    id: selected.id,
                    request_id: selected.request_id,
                    user_id: selected.user_id,
                    provider: selected.provider,
                    model: selected.model,
                    prompt_id: selected.prompt_id,
                    prompt_version: selected.prompt_version,
                    attempt_number: selected.attempt_number,
                    status: selected.status,
                    char_count: selected.char_count,
                    latency_ms: selected.latency_ms,
                    archive_path: selected.archive_path,
                    created_at: selected.created_at,
                    extracted_answer: selected.extracted_answer,
                    error_message: selected.error_message,
                    validation_json: selected.validation_json,
                  },
                  null,
                  2
                )}
              </pre>
              <textarea
                readOnly
                value={selected.raw_solution_text || ""}
                className="w-full min-h-[420px] rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 p-3 text-xs font-mono"
              />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
