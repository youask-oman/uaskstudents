"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import AdminUserAutocomplete from "@/components/admin/AdminUserAutocomplete";

type RequestSummary = {
  question_count?: number;
  question_ids?: string[];
  billed_credits_total?: number;
  tiers?: string[];
  actions?: string[];
  billing_entries_count?: number;
  billing_credits_total?: number;
  provider_cost_usd_total?: number;
};

type LlmUsageItem = {
  id: number;
  solve_session_id?: number | null;
  followup_turn_id?: number | null;
  user_id?: number | null;
  user_email?: string | null;
  session_id?: number | null;
  message_id?: number | null;
  provider: string;
  model: string;
  request_id?: string | null;
  output_format?: string | null;
  prompt_id?: string | null;
  prompt_version?: string | null;
  attempt_id?: string | null;
  attempt_number?: number | null;
  status?: string | null;
  char_count?: number | null;
  error_message?: string | null;
  source_record?: string;
  chat_session_title?: string | null;
  chat_message_preview?: string | null;
  solve_problem_preview?: string | null;
  request_summary?: RequestSummary | null;
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
  source?: string;
};

export default function AdminLlmUsagePage() {
  const { pushToast } = useToast();
  const [items, setItems] = useState<LlmUsageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<string>("llmusageledger");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [userId, setUserId] = useState("");
  const [userLookup, setUserLookup] = useState("");
  const [requestId, setRequestId] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

  const filtered = useMemo(() => {
    if (!query.trim()) return items;
    const q = query.toLowerCase();
    return items.filter((x) => JSON.stringify(x).toLowerCase().includes(q));
  }, [items, query]);

  const stats = useMemo(() => {
    let totalTokens = 0;
    let inputTokens = 0;
    let outputTokens = 0;
    let latencyCount = 0;
    let latencySum = 0;
    const reqs = new Set<string>();
    for (const row of filtered) {
      totalTokens += Number(row.total_tokens || 0);
      inputTokens += Number(row.input_tokens || 0);
      outputTokens += Number(row.output_tokens || 0);
      if (typeof row.latency_ms === "number" && row.latency_ms > 0) {
        latencyCount += 1;
        latencySum += row.latency_ms;
      }
      if (row.request_id) reqs.add(row.request_id);
    }
    return {
      totalTokens,
      inputTokens,
      outputTokens,
      avgLatency: latencyCount ? Math.round(latencySum / latencyCount) : null,
      uniqueRequests: reqs.size,
    };
  }, [filtered]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (provider.trim()) params.set("provider", provider.trim());
      if (model.trim()) params.set("model", model.trim());
      if (userId.trim()) params.set("user_id", userId.trim());
      if (requestId.trim()) params.set("request_id", requestId.trim());
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/observability/llm-usage?${params.toString()}`, { headers });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as LlmUsageListResponse;
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotal(Number(data.total || 0));
      setDataSource((data.source || "llmusageledger").toLowerCase());
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

  return (
    <div className="p-8 max-w-[1700px] mx-auto w-full flex flex-col gap-6">
      <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-gradient-to-r from-cyan-50 via-white to-emerald-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950 p-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white">LLM Usage Intelligence</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Context-rich observability for each model call. IDs are enriched with chat/request metadata so admins can understand what each record represents.
            </p>
          </div>
          <div className="text-sm text-slate-500">Total rows: {total} | Showing: {filtered.length}</div>
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <Stat title="Unique Requests" value={stats.uniqueRequests} subtitle="request_id count" />
          <Stat title="Input Tokens" value={stats.inputTokens.toLocaleString()} subtitle="sum of input" />
          <Stat title="Output Tokens" value={stats.outputTokens.toLocaleString()} subtitle="sum of output" />
          <Stat title="Total Tokens" value={stats.totalTokens.toLocaleString()} subtitle="input + output + system" />
          <Stat title="Avg Latency" value={stats.avgLatency !== null ? `${stats.avgLatency} ms` : "n/a"} subtitle="over rows with latency" />
        </div>
        {dataSource !== "llmusageledger" && (
          <div className="mt-4 inline-flex w-fit items-center rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
            Source fallback: {dataSource}
          </div>
        )}
      </section>

      <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
        <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
          <input className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm" placeholder="Search all fields" value={query} onChange={(e) => setQuery(e.target.value)} />
          <input className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm" placeholder="Provider" value={provider} onChange={(e) => setProvider(e.target.value)} />
          <input className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm" placeholder="Model" value={model} onChange={(e) => setModel(e.target.value)} />
          <AdminUserAutocomplete
            value={userLookup}
            onValueChange={(nextValue) => {
              setUserLookup(nextValue);
              const trimmed = nextValue.trim();
              if (/^\d+$/.test(trimmed)) setUserId(trimmed);
              else setUserId("");
            }}
            onSelect={(user) => {
              setUserLookup(user.email);
              setUserId(String(user.id));
            }}
            placeholder="Lookup user email"
          />
          <input className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm" placeholder="Request ID" value={requestId} onChange={(e) => setRequestId(e.target.value)} />
          <button onClick={() => void fetchItems()} className="px-4 py-2 rounded-xl bg-admin-primary text-white text-sm font-semibold">{loading ? "Loading..." : "Refresh"}</button>
          <button
            onClick={() => {
              setQuery("");
              setProvider("");
              setModel("");
              setUserId("");
              setUserLookup("");
              setRequestId("");
              void fetchItems();
            }}
            className="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-sm font-semibold"
          >
            Reset
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {!loading &&
          filtered.map((item) => (
            <article key={`${item.source_record}-${item.id}-${item.request_id || "none"}`} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2 py-1 text-xs rounded-lg bg-slate-100 dark:bg-slate-800 font-semibold">{item.provider}/{item.model}</span>
                <span className="px-2 py-1 text-xs rounded-lg bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-200 font-semibold">{item.source_record || "llmusageledger"}</span>
                {item.status && <span className="px-2 py-1 text-xs rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200 font-semibold">{item.status}</span>}
                <span className="ml-auto text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</span>
              </div>

              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div className="space-y-1">
                  <div className="text-slate-500 text-xs uppercase">User</div>
                  <div className="font-semibold">{item.user_email || `User #${item.user_id ?? "n/a"}`}</div>
                  <div className="text-xs text-slate-500">ID: {item.user_id ?? "n/a"}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-slate-500 text-xs uppercase">Request</div>
                  <div className="font-mono text-xs break-all">{item.request_id || "n/a"}</div>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                <ContextCard
                  title="Chat Context"
                  body={
                    <>
                      <div className="text-xs text-slate-500">
                        Session: {item.session_id ? <Link href={`/chat/${item.session_id}`} className="text-cyan-700 dark:text-cyan-300 font-semibold">#{item.session_id}</Link> : "n/a"}
                        {" "} | Message: {item.message_id ?? "n/a"}
                      </div>
                      <div className="text-sm font-semibold">{item.chat_session_title || "No session title available"}</div>
                      <div className="text-xs text-slate-600 dark:text-slate-300">{item.chat_message_preview || "No chat message preview available."}</div>
                    </>
                  }
                />
                <ContextCard
                  title="Solve Context"
                  body={<div className="text-xs text-slate-600 dark:text-slate-300">{item.solve_problem_preview || "No solve-session problem text linked."}</div>}
                />
              </div>

              <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                <Metric label="Tokens (sys/in/out)" value={`${item.system_prompt_tokens}/${item.input_tokens}/${item.output_tokens}`} />
                <Metric label="Total Tokens" value={String(item.total_tokens)} />
                <Metric label="Latency" value={item.latency_ms ? `${item.latency_ms} ms` : "n/a"} />
              </div>

              <div className="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 p-3">
                <div className="text-xs uppercase text-slate-500 mb-2">Request Summary</div>
                {item.request_summary ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <Info label="Questions" value={String(item.request_summary.question_count ?? 0)} />
                    <Info label="Billed Credits" value={Number(item.request_summary.billed_credits_total || 0).toFixed(4)} />
                    <Info label="Billing Rows" value={String(item.request_summary.billing_entries_count ?? 0)} />
                    <Info label="Provider Cost USD" value={Number(item.request_summary.provider_cost_usd_total || 0).toFixed(4)} />
                    <Info label="Question IDs" value={(item.request_summary.question_ids || []).join(", ") || "n/a"} wide />
                    <Info label="Tiers" value={(item.request_summary.tiers || []).join(", ") || "n/a"} />
                    <Info label="Actions" value={(item.request_summary.actions || []).join(", ") || "n/a"} />
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">No request-level rollup available.</div>
                )}
              </div>
            </article>
          ))}
        {loading && <div className="text-slate-500">Loading...</div>}
      </section>
    </div>
  );
}

function Stat({ title, value, subtitle }: { title: string; value: string | number; subtitle: string }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/70 p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{title}</div>
      <div className="text-2xl font-black text-slate-900 dark:text-white">{value}</div>
      <div className="text-xs text-slate-500">{subtitle}</div>
    </div>
  );
}

function ContextCard({ title, body }: { title: string; body: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
      <div className="text-xs uppercase text-slate-500 mb-1">{title}</div>
      {body}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

function Info({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 p-2 ${wide ? "col-span-2" : ""}`}>
      <div className="text-[10px] uppercase text-slate-500">{label}</div>
      <div className="text-xs font-semibold">{value}</div>
    </div>
  );
}
