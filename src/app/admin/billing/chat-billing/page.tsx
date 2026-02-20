"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import AdminUserAutocomplete from "@/components/admin/AdminUserAutocomplete";

type QuestionCharge = {
  ledger_id: string;
  hold_id?: string | null;
  attempt_id?: string | null;
  question_id?: string | null;
  question_index?: number | null;
  action: string;
  tier: string;
  outcome: string;
  total_cost: number;
  created_at: string;
};

type ChatBillingRow = {
  session_id: number;
  message_id: number;
  role: string;
  created_at: string;
  user_id: number;
  user_email: string;
  request_id?: string | null;
  content_preview: string;
  question_count: number;
  charge_mode: string;
  credits_charged_total: number;
  credits_source?: string;
  provider_cost_usd_total: number;
  provider_cost_source?: string;
  provider?: string | null;
  model?: string | null;
  input_tokens_total: number;
  output_tokens_total: number;
  total_tokens: number;
  latency_ms?: number | null;
  billing_entries_count: number;
  usage_entries_count?: number;
  ledger_entries_total_count?: number;
  billing_statuses: string[];
  per_question_total_credits: number;
  per_question_charges: QuestionCharge[];
};

type ChatBillingResponse = {
  total: number;
  limit: number;
  offset: number;
  items: ChatBillingRow[];
};

type DateGroup = {
  dateKey: string;
  rows: ChatBillingRow[];
  credits: number;
  providerCost: number;
  users: UserGroup[];
};

type UserGroup = {
  userKey: string;
  userId: number;
  userEmail: string;
  rows: ChatBillingRow[];
  credits: number;
  providerCost: number;
  latestTs: number;
};

const PAGE_SIZE = 15;

const dateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

const timeFmt = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
});

export default function AdminChatBillingPage() {
  const { pushToast } = useToast();
  const [items, setItems] = useState<ChatBillingRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [userQuery, setUserQuery] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [requestId, setRequestId] = useState("");
  const [role, setRole] = useState("assistant");
  const [page, setPage] = useState(1);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

  const rowKey = (row: ChatBillingRow, idx: number): string =>
    `${row.request_id || "no_req"}:${row.session_id}:${row.message_id}:${row.created_at}:${idx}`;

  const summary = useMemo(() => {
    let credits = 0;
    let provider = 0;
    let tokensIn = 0;
    let tokensOut = 0;
    let batches = 0;
    let singles = 0;
    let fallback = 0;
    for (const row of items) {
      credits += Number(row.credits_charged_total || 0);
      provider += Number(row.provider_cost_usd_total || 0);
      tokensIn += Number(row.input_tokens_total || 0);
      tokensOut += Number(row.output_tokens_total || 0);
      if (row.charge_mode === "batch") batches += 1;
      if (row.charge_mode === "single") singles += 1;
      if (row.session_id <= 0 || row.message_id <= 0) fallback += 1;
    }
    return { credits, provider, tokensIn, tokensOut, batches, singles, fallback };
  }, [items]);

  const sortedItems = useMemo(
    () =>
      [...items].sort(
        (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime(),
      ),
    [items],
  );

  const pageCount = useMemo(() => Math.max(1, Math.ceil(sortedItems.length / PAGE_SIZE)), [sortedItems.length]);

  const pagedItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return sortedItems.slice(start, start + PAGE_SIZE);
  }, [page, sortedItems]);

  const groupedByDate = useMemo<DateGroup[]>(() => {
    const days = new Map<string, DateGroup>();
    for (const row of pagedItems) {
      const dt = new Date(row.created_at || 0);
      const day = Number.isNaN(dt.getTime()) ? "unknown" : dt.toISOString().slice(0, 10);
      const existing = days.get(day);
      if (existing) {
        existing.rows.push(row);
        existing.credits += Number(row.credits_charged_total || 0);
        existing.providerCost += Number(row.provider_cost_usd_total || 0);
      } else {
        days.set(day, {
          dateKey: day,
          rows: [row],
          credits: Number(row.credits_charged_total || 0),
          providerCost: Number(row.provider_cost_usd_total || 0),
          users: [],
        });
      }
    }

    const output = Array.from(days.values()).sort((a, b) => b.dateKey.localeCompare(a.dateKey));
    for (const dateGroup of output) {
      dateGroup.rows.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
      const users = new Map<string, UserGroup>();
      for (const row of dateGroup.rows) {
        const key = `${row.user_id}|${row.user_email}`;
        const ts = new Date(row.created_at || 0).getTime();
        const existingUser = users.get(key);
        if (existingUser) {
          existingUser.rows.push(row);
          existingUser.credits += Number(row.credits_charged_total || 0);
          existingUser.providerCost += Number(row.provider_cost_usd_total || 0);
          existingUser.latestTs = Math.max(existingUser.latestTs, Number.isNaN(ts) ? 0 : ts);
        } else {
          users.set(key, {
            userKey: key,
            userId: row.user_id,
            userEmail: row.user_email,
            rows: [row],
            credits: Number(row.credits_charged_total || 0),
            providerCost: Number(row.provider_cost_usd_total || 0),
            latestTs: Number.isNaN(ts) ? 0 : ts,
          });
        }
      }
      dateGroup.users = Array.from(users.values()).sort(
        (a, b) => b.latestTs - a.latestTs || a.userEmail.localeCompare(b.userEmail),
      );
      for (const user of dateGroup.users) {
        user.rows.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
      }
    }
    return output;
  }, [pagedItems]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "300");
      params.set("offset", "0");
      if (userQuery.trim()) params.set("user_query", userQuery.trim());
      if (sessionId.trim()) params.set("session_id", sessionId.trim());
      if (requestId.trim()) params.set("request_id", requestId.trim());
      if (role.trim()) params.set("role", role.trim());

      const res = await fetch(`${API_BASE_URL}/api/v1/admin/observability/chat-billing?${params.toString()}`, {
        headers,
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as ChatBillingResponse;
      const rows = Array.isArray(data.items) ? data.items : [];
      setItems(rows);
      setTotal(Number(data.total || 0));
      setExpandedRow(null);
      setPage(1);
    } catch (err) {
      pushToast({
        type: "error",
        title: "Failed to load chat billing data",
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
    <div className="w-full min-h-screen p-8 space-y-6 bg-gradient-to-b from-cyan-50/50 via-white to-white dark:from-slate-950 dark:via-slate-950 dark:to-slate-950">
      <section className="rounded-3xl border border-cyan-100 dark:border-slate-800 bg-white dark:bg-[#0f172a] p-6 shadow-sm">
        <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white">Billing Investigation Console</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Grouped by date (newest first), then user. IDs are linked to their related admin pages for fast investigation.
        </p>
        <div className="mt-5 grid grid-cols-1 md:grid-cols-6 gap-3">
          <Kpi title="Requests" value={items.length} subtitle={`Total matched: ${total}`} />
          <Kpi title="Credits" value={summary.credits.toFixed(4)} subtitle="charged total" />
          <Kpi title="Provider Cost" value={summary.provider.toFixed(4)} subtitle="USD total" />
          <Kpi title="Input / Output" value={`${summary.tokensIn} / ${summary.tokensOut}`} subtitle="token totals" />
          <Kpi title="Single / Batch" value={`${summary.singles} / ${summary.batches}`} subtitle="solve mode count" />
          <Kpi title="Fallback" value={summary.fallback} subtitle="no chatmessage source" />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-4">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <AdminUserAutocomplete
            value={userQuery}
            onValueChange={setUserQuery}
            onSelect={(user) => setUserQuery(user.email)}
            placeholder="Lookup user email"
          />
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Session ID"
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          />
          <input
            value={requestId}
            onChange={(e) => setRequestId(e.target.value)}
            placeholder="Request ID"
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          >
            <option value="assistant">assistant</option>
            <option value="user">user</option>
            <option value="system">system</option>
          </select>
          <button onClick={() => void fetchItems()} className="px-4 py-2 rounded-xl bg-admin-primary text-white font-semibold text-sm">
            {loading ? "Loading..." : "Search"}
          </button>
          <button
            onClick={() => {
              setUserQuery("");
              setSessionId("");
              setRequestId("");
              setRole("assistant");
              setPage(1);
              void fetchItems();
            }}
            className="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-semibold text-sm"
          >
            Reset
          </button>
        </div>
      </section>

      <section className="space-y-5">
        {!loading && groupedByDate.length === 0 && (
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-6 text-slate-600 dark:text-slate-300">
            No records match the current filters.
          </div>
        )}

        {!loading &&
          groupedByDate.map((dateGroup) => (
            <article key={dateGroup.dateKey} className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] overflow-hidden shadow-sm">
              <header className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/40 flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-black text-slate-900 dark:text-white">
                  {dateGroup.dateKey === "unknown"
                    ? "Unknown date"
                    : dateFmt.format(new Date(`${dateGroup.dateKey}T00:00:00`))}
                </h2>
                <Pill label={`${dateGroup.rows.length} request(s)`} tone="slate" />
                <Pill label={`${dateGroup.credits.toFixed(4)} credits`} tone="rose" />
                <Pill label={`$${dateGroup.providerCost.toFixed(4)} provider`} tone="cyan" />
              </header>

              <div className="p-4 space-y-4">
                {dateGroup.users.map((userGroup) => (
                  <section key={`${dateGroup.dateKey}:${userGroup.userKey}`} className="rounded-2xl border border-slate-200 dark:border-slate-800">
                    <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/30 flex flex-wrap items-center gap-2">
                      <div className="h-9 w-9 rounded-lg bg-cyan-100 dark:bg-cyan-900/40 text-cyan-800 dark:text-cyan-200 grid place-items-center font-black">
                        {(userGroup.userEmail || "U").slice(0, 1).toUpperCase()}
                      </div>
                      <div className="font-bold text-slate-900 dark:text-white">{userGroup.userEmail}</div>
                      <Pill label={`${userGroup.rows.length} request(s)`} tone="slate" />
                      <Pill label={`${userGroup.credits.toFixed(4)} credits`} tone="rose" />
                      <Pill label={`$${userGroup.providerCost.toFixed(4)} provider`} tone="cyan" />
                      <Link href={`/admin/users/${userGroup.userId}`} className="ml-auto px-2.5 py-1 rounded-full border border-slate-300 dark:border-slate-700 text-xs">
                        open user
                      </Link>
                    </div>

                    <div className="p-3 space-y-3">
                      {userGroup.rows.map((row, idx) => {
                        const key = rowKey(row, idx);
                        const expanded = expandedRow === key;
                        const isFallback = row.session_id <= 0 || row.message_id <= 0;
                        return (
                          <article key={key} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950/40 p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-sm font-bold text-slate-900 dark:text-white">
                                {row.charge_mode === "batch" ? "Batch solve request" : "Single solve request"}
                              </div>
                              <Pill label={`${row.question_count} question(s)`} tone="indigo" />
                              <Pill label={`${row.credits_charged_total.toFixed(4)} credits`} tone="rose" />
                              <Pill label={`$${row.provider_cost_usd_total.toFixed(4)} provider`} tone="cyan" />
                              {isFallback && <Pill label="fallback source" tone="amber" />}
                              <div className="ml-auto text-xs text-slate-500">{timeFmt.format(new Date(row.created_at))}</div>
                            </div>

                            <div className="mt-2 text-sm text-slate-700 dark:text-slate-200">{row.content_preview}</div>

                            <div className="mt-3 grid grid-cols-1 lg:grid-cols-4 gap-2 text-xs">
                              <InfoCell
                                title="Session Context"
                                value={
                                  row.session_id > 0 ? (
                                    <div className="space-y-1">
                                      <Link href={`/chat/${row.session_id}`} className="text-cyan-700 dark:text-cyan-300 font-semibold">
                                        Session {row.session_id}
                                      </Link>
                                      <div>
                                        Message{" "}
                                        <Link
                                          href={`/chat/${row.session_id}`}
                                          className="text-cyan-700 dark:text-cyan-300 underline"
                                        >
                                          {row.message_id}
                                        </Link>{" "}
                                        ({row.role})
                                      </div>
                                    </div>
                                  ) : (
                                    <div>no chat session row</div>
                                  )
                                }
                              />
                              <InfoCell
                                title="Model + Runtime"
                                value={
                                  <div className="space-y-1">
                                    <div>{row.provider || "unknown"} / {row.model || "unknown"}</div>
                                    <div>latency: {row.latency_ms ?? "n/a"} ms</div>
                                    <div>tokens in/out/total: {row.input_tokens_total}/{row.output_tokens_total}/{row.total_tokens}</div>
                                  </div>
                                }
                              />
                              <InfoCell
                                title="Billing Sources"
                                value={
                                  <div className="space-y-1">
                                    <div>credits source: {row.credits_source || "none"}</div>
                                    <div>provider source: {row.provider_cost_source || "none"}</div>
                                    <div>billingledger entries: {row.billing_entries_count}</div>
                                    <div>usage_ledger entries: {row.usage_entries_count ?? row.per_question_charges.length}</div>
                                    <div>ledger total: {row.ledger_entries_total_count ?? (row.billing_entries_count + (row.usage_entries_count ?? row.per_question_charges.length))}</div>
                                  </div>
                                }
                              />
                              <InfoCell
                                title="Request Trace"
                                value={
                                  <div className="space-y-1 font-mono text-[11px]">
                                    <div className="break-all">
                                      request:{" "}
                                      {row.request_id ? (
                                        <Link
                                          href={`/admin/billing/chat-billing?request_id=${encodeURIComponent(row.request_id)}`}
                                          className="text-cyan-700 dark:text-cyan-300 underline"
                                        >
                                          {row.request_id}
                                        </Link>
                                      ) : (
                                        "n/a"
                                      )}
                                    </div>
                                    {row.request_id && (
                                      <div className="break-all">
                                        <Link
                                          href={`/admin/billing/ledger?request_id=${encodeURIComponent(row.request_id)}`}
                                          className="text-cyan-700 dark:text-cyan-300 underline"
                                        >
                                          open in ledger
                                        </Link>{" "}
                                        |{" "}
                                        <Link
                                          href={`/admin/observability/llm-usage?request_id=${encodeURIComponent(row.request_id)}`}
                                          className="text-cyan-700 dark:text-cyan-300 underline"
                                        >
                                          open in llm-usage
                                        </Link>
                                      </div>
                                    )}
                                  </div>
                                }
                              />
                            </div>

                            <div className="mt-3">
                              <button
                                onClick={() => setExpandedRow(expanded ? null : key)}
                                className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs font-semibold"
                              >
                                {expanded ? "Hide full question ledger" : "Show full question ledger"}
                              </button>
                            </div>

                            {expanded && (
                              <div className="mt-3 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                                <div className="grid grid-cols-8 gap-2 px-3 py-2 text-[11px] font-bold uppercase tracking-wide bg-slate-50 dark:bg-slate-900/40 text-slate-600 dark:text-slate-300">
                                  <div>Question</div>
                                  <div>Action</div>
                                  <div>Tier</div>
                                  <div>Outcome</div>
                                  <div>Cost</div>
                                  <div>Ledger</div>
                                  <div>Attempt</div>
                                  <div>Hold</div>
                                </div>
                                <div className="divide-y divide-slate-200 dark:divide-slate-800">
                                  {row.per_question_charges.length === 0 && (
                                    <div className="px-3 py-3 text-xs text-slate-500">No per-question usage_ledger rows found.</div>
                                  )}
                                  {row.per_question_charges.map((q) => (
                                    <div key={q.ledger_id} className="grid grid-cols-8 gap-2 px-3 py-3 text-xs text-slate-700 dark:text-slate-200">
                                      <div className="font-semibold">{q.question_id || `q${q.question_index ?? "?"}`}</div>
                                      <div>{q.action}</div>
                                      <div>{q.tier}</div>
                                      <div>{q.outcome}</div>
                                      <div className="font-semibold">{Number(q.total_cost || 0).toFixed(4)}</div>
                                      <div className="font-mono break-all">
                                        {row.request_id ? (
                                          <Link
                                            href={`/admin/billing/ledger?request_id=${encodeURIComponent(row.request_id)}`}
                                            className="text-cyan-700 dark:text-cyan-300 underline"
                                          >
                                            {q.ledger_id}
                                          </Link>
                                        ) : (
                                          q.ledger_id
                                        )}
                                      </div>
                                      <div className="font-mono break-all">
                                        {q.attempt_id ? (
                                          <Link
                                            href={`/admin/solver-attempts?query=${encodeURIComponent(q.attempt_id)}`}
                                            className="text-cyan-700 dark:text-cyan-300 underline"
                                          >
                                            {q.attempt_id}
                                          </Link>
                                        ) : (
                                          "n/a"
                                        )}
                                      </div>
                                      <div className="font-mono break-all">
                                        {q.hold_id ? (
                                          <Link
                                            href={`/admin/billing/holds`}
                                            className="text-cyan-700 dark:text-cyan-300 underline"
                                          >
                                            {q.hold_id}
                                          </Link>
                                        ) : (
                                          "n/a"
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            </article>
          ))}
      </section>

      <footer className="flex items-center justify-between rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-4">
        <div className="text-xs text-slate-500">
          Page size: {PAGE_SIZE} | Page {page} of {pageCount} | Requests in filter: {items.length}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1 || loading}
            onClick={() => {
              setPage((p) => Math.max(1, p - 1));
              setExpandedRow(null);
            }}
            className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-50"
          >
            Prev
          </button>
          <button
            disabled={page >= pageCount || loading}
            onClick={() => {
              setPage((p) => Math.min(pageCount, p + 1));
              setExpandedRow(null);
            }}
            className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </footer>
    </div>
  );
}

function Kpi({ title, value, subtitle }: { title: string; value: string | number; subtitle: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{title}</div>
      <div className="text-2xl font-black text-slate-900 dark:text-white">{value}</div>
      <div className="text-xs text-slate-500">{subtitle}</div>
    </div>
  );
}

function Pill({ label, tone }: { label: string; tone: "slate" | "indigo" | "rose" | "cyan" | "amber" }) {
  const palette: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
    indigo: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-200",
    rose: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200",
    cyan: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-200",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
  };
  return <span className={`px-2 py-1 rounded-full text-[11px] font-bold ${palette[tone]}`}>{label}</span>;
}

function InfoCell({ title, value }: { title: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{title}</div>
      <div className="mt-1">{value}</div>
    </div>
  );
}
