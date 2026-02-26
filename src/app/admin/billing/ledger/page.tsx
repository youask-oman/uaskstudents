"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import AdminUserAutocomplete from "@/components/admin/AdminUserAutocomplete";

type LedgerRow = {
  ledger_id: string;
  user_id: number;
  user_email?: string;
  hold_id?: string | null;
  request_id: string | null;
  attempt_id?: string | null;
  idempotency_key?: string | null;
  tier: string | null;
  action: string;
  question_id?: string | null;
  question_index?: number | null;
  base_cost: number;
  addons_cost: number;
  attempt_fee: number;
  total_cost: number;
  balance_after?: number | null;
  channel?: string | null;
  outcome: string;
  pricing_snapshot?: Record<string, unknown> | null;
  created_at: string;
};

type LedgerResponse = {
  items: LedgerRow[];
  next_cursor?: string | null;
  limit: number;
  total?: number;
};

const PAGE_SIZE = 15;

export default function LedgerExplorerPage() {
  const { token } = useAuth();
  const { pushToast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [rows, setRows] = useState<LedgerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState<number | null>(null);

  const [filterUser, setFilterUser] = useState("");
  const [filterUserLookup, setFilterUserLookup] = useState("");
  const [filterRequestId, setFilterRequestId] = useState("");
  const [filterAttemptId, setFilterAttemptId] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"ledger" | "details">("ledger");

  const hasPrev = cursorHistory.length > 0;
  const hasNext = Boolean(nextCursor);

  const summary = useMemo(() => {
    const charged = rows.reduce((sum, row) => sum + Number(row.total_cost || 0), 0);
    const batchRows = rows.filter((row) => row.action === "solve_batch").length;
    const uniqueRequests = new Set(rows.map((r) => r.request_id).filter(Boolean)).size;
    return { charged, batchRows, uniqueRequests };
  }, [rows]);

  const fetchLedger = useCallback(async (cursorValue?: string | null) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      if (filterUser.trim()) params.set("user_id", filterUser.trim());
      if (filterRequestId.trim()) params.set("request_id", filterRequestId.trim());
      if (filterAttemptId.trim()) params.set("attempt_id", filterAttemptId.trim());
      if (cursorValue) params.set("cursor", cursorValue);

      const res = await fetchApi(`/api/v1/admin/credits/ledger?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      const data = (await res.json()) as LedgerResponse;
      setRows(Array.isArray(data.items) ? data.items : []);
      setNextCursor(data.next_cursor || null);
      setTotal(typeof data.total === "number" ? data.total : null);
    } catch (err) {
      pushToast({
        type: "error",
        title: "Failed to load ledger",
        message: err instanceof Error ? err.message : "Unexpected error",
      });
    } finally {
      setLoading(false);
    }
  }, [filterAttemptId, filterRequestId, filterUser, pushToast, token]);

  useEffect(() => {
    void fetchLedger(cursor);
  }, [cursor, fetchLedger]);

  useEffect(() => {
    const qpRequest = (searchParams.get("request_id") || "").trim();
    const qpAttempt = (searchParams.get("attempt_id") || "").trim();
    const qpUser = (searchParams.get("user_id") || "").trim();
    const qpTab = (searchParams.get("tab") || "").trim().toLowerCase();

    setFilterRequestId(qpRequest);
    setFilterAttemptId(qpAttempt);
    setFilterUser(qpUser);
    setFilterUserLookup(qpUser);
    setActiveTab(qpTab === "details" ? "details" : "ledger");
    setCursor(null);
    setCursorHistory([]);
    setPage(1);
  }, [searchParams]);

  useEffect(() => {
    if (activeTab !== "details" || rows.length === 0) return;
    const qpRequest = (searchParams.get("request_id") || "").trim();
    const qpAttempt = (searchParams.get("attempt_id") || "").trim();
    if (!qpRequest && !qpAttempt) return;
    const match = rows.find(
      (row) =>
        (qpRequest ? String(row.request_id || "").trim() === qpRequest : true) &&
        (qpAttempt ? String(row.attempt_id || "").trim() === qpAttempt : true)
    );
    if (match) setExpandedId(match.ledger_id);
  }, [activeTab, rows, searchParams]);

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams(searchParams.toString());
    const request = filterRequestId.trim();
    const attempt = filterAttemptId.trim();
    const user = filterUser.trim();
    if (request) params.set("request_id", request);
    else params.delete("request_id");
    if (attempt) params.set("attempt_id", attempt);
    else params.delete("attempt_id");
    if (user) params.set("user_id", user);
    else params.delete("user_id");
    params.set("tab", activeTab);
    router.push(`/admin/billing/ledger?${params.toString()}`);
    setCursor(null);
    setCursorHistory([]);
    setPage(1);
    void fetchLedger(null);
  };

  const onNext = () => {
    if (!nextCursor) return;
    setCursorHistory((prev) => [...prev, cursor]);
    setCursor(nextCursor);
    setPage((p) => p + 1);
    setExpandedId(null);
  };

  const onPrev = () => {
    if (!hasPrev) return;
    setCursorHistory((prev) => {
      const copy = [...prev];
      const previousCursor = copy.pop() ?? null;
      setCursor(previousCursor);
      return copy;
    });
    setPage((p) => Math.max(1, p - 1));
    setExpandedId(null);
  };

  return (
    <div className="p-8 max-w-[1800px] mx-auto w-full space-y-6">
      <section className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-gradient-to-r from-white via-slate-50 to-cyan-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950 p-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white">Ledger Explorer</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Full usage-ledger intelligence with per-row costs, request tracing, question granularity, and pricing snapshot context.
            </p>
          </div>
          <div className="text-sm text-slate-500">
            Page {page} {total !== null ? `| Total rows: ${total}` : ""}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          <Stat title="Rows On Page" value={rows.length} sub={`limit ${PAGE_SIZE}`} />
          <Stat title="Charged Credits" value={summary.charged.toFixed(4)} sub="sum(total_cost)" />
          <Stat title="Batch Rows" value={summary.batchRows} sub="action=solve_batch" />
          <Stat title="Unique Requests" value={summary.uniqueRequests} sub="request_id count" />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-4">
        <form onSubmit={onSearch} className="grid grid-cols-1 md:grid-cols-7 gap-3">
          <AdminUserAutocomplete
            value={filterUserLookup}
            onValueChange={(nextValue) => {
              setFilterUserLookup(nextValue);
              const trimmed = nextValue.trim();
              if (/^\d+$/.test(trimmed)) setFilterUser(trimmed);
              else setFilterUser("");
            }}
            onSelect={(user) => {
              setFilterUserLookup(user.email);
              setFilterUser(String(user.id));
            }}
            placeholder="Lookup user email"
          />
          <input
            type="text"
            placeholder="Request ID"
            value={filterRequestId}
            onChange={(e) => setFilterRequestId(e.target.value)}
            className="md:col-span-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          />
          <input
            type="text"
            placeholder="Attempt ID"
            value={filterAttemptId}
            onChange={(e) => setFilterAttemptId(e.target.value)}
            className="md:col-span-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
          />
          <button type="submit" className="px-4 py-2 rounded-xl bg-admin-primary text-white font-semibold text-sm">
            Search
          </button>
          <button
            type="button"
            onClick={() => {
              setFilterUser("");
              setFilterUserLookup("");
              setFilterRequestId("");
              setFilterAttemptId("");
              setCursor(null);
              setCursorHistory([]);
              setPage(1);
              setActiveTab("ledger");
              router.push("/admin/billing/ledger");
              void fetchLedger(null);
            }}
            className="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-semibold text-sm"
          >
            Reset
          </button>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-3">
        <div className="inline-flex rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
          <button
            type="button"
            onClick={() => {
              setActiveTab("ledger");
              const params = new URLSearchParams(searchParams.toString());
              params.set("tab", "ledger");
              router.push(`/admin/billing/ledger?${params.toString()}`);
            }}
            className={`px-4 py-2 text-sm font-semibold ${activeTab === "ledger" ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200"}`}
          >
            Ledger
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab("details");
              const params = new URLSearchParams(searchParams.toString());
              params.set("tab", "details");
              router.push(`/admin/billing/ledger?${params.toString()}`);
            }}
            className={`px-4 py-2 text-sm font-semibold ${activeTab === "details" ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200"}`}
          >
            Details
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] overflow-hidden">
        <div className="overflow-auto max-h-[70vh]">
          <table className="w-full text-sm min-w-[1700px]">
            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Action</th>
                <th className="px-3 py-2 text-left">User</th>
                <th className="px-3 py-2 text-left">Tier</th>
                <th className="px-3 py-2 text-left">Channel</th>
                <th className="px-3 py-2 text-left">Request / Attempt</th>
                <th className="px-3 py-2 text-left">Question</th>
                <th className="px-3 py-2 text-left">Costs (Base+Addon+Fee)</th>
                <th className="px-3 py-2 text-left">Total</th>
                <th className="px-3 py-2 text-left">Balance After</th>
                <th className="px-3 py-2 text-left">Outcome</th>
                <th className="px-3 py-2 text-left">Ledger / Hold</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-left">Details</th>
              </tr>
            </thead>
            <tbody>
              {!loading && rows.map((row) => (
                <Fragment key={row.ledger_id}>
                  <tr className="border-t border-slate-200 dark:border-slate-800 hover:bg-slate-50/70 dark:hover:bg-slate-900/40">
                    <td className="px-3 py-3 font-bold text-slate-900 dark:text-white">{row.action}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-col">
                        <Link href={`/admin/users/${row.user_id}`} className="font-semibold text-cyan-700 dark:text-cyan-300">
                          {row.user_email || `User #${row.user_id}`}
                        </Link>
                        <span className="text-xs text-slate-500">id: {row.user_id}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3">{row.tier || "n/a"}</td>
                    <td className="px-3 py-3">
                      <span className="px-2 py-1 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800">
                        {(row.channel || "app").toString().toLowerCase()}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px]">
                      <div>
                        {row.request_id ? (
                          <Link
                            href={`/admin/billing/ledger?tab=details&request_id=${encodeURIComponent(row.request_id)}${row.attempt_id ? `&attempt_id=${encodeURIComponent(row.attempt_id)}` : ""}`}
                            className="text-cyan-700 dark:text-cyan-300 hover:underline"
                          >
                            {row.request_id}
                          </Link>
                        ) : "n/a"}
                      </div>
                      <div className="text-slate-500">
                        {row.attempt_id ? (
                          <Link
                            href={`/admin/billing/ledger?tab=details&attempt_id=${encodeURIComponent(row.attempt_id)}${row.request_id ? `&request_id=${encodeURIComponent(row.request_id)}` : ""}`}
                            className="text-cyan-700 dark:text-cyan-300 hover:underline"
                          >
                            {row.attempt_id}
                          </Link>
                        ) : "attempt n/a"}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      <div>{row.question_id || "n/a"}</div>
                      <div className="text-slate-500">index: {row.question_index ?? "n/a"}</div>
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px]">
                      {fmt(row.base_cost)} + {fmt(row.addons_cost)} + {fmt(row.attempt_fee)}
                    </td>
                    <td className="px-3 py-3 font-black text-rose-600 dark:text-rose-300">-{fmt(row.total_cost)}</td>
                    <td className="px-3 py-3 font-mono text-[11px]">
                      {row.balance_after !== null && row.balance_after !== undefined ? fmt(row.balance_after) : "n/a"}
                    </td>
                    <td className="px-3 py-3">
                      <span className="px-2 py-1 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800">{row.outcome}</span>
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px]">
                      <div>{row.ledger_id}</div>
                      <div className="text-slate-500">{row.hold_id || "hold n/a"}</div>
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</td>
                    <td className="px-3 py-3">
                      <button
                        onClick={() => {
                          const nextOpen = expandedId === row.ledger_id ? null : row.ledger_id;
                          setExpandedId(nextOpen);
                          if (nextOpen) {
                            setActiveTab("details");
                            const params = new URLSearchParams(searchParams.toString());
                            params.set("tab", "details");
                            if (row.request_id) params.set("request_id", row.request_id);
                            if (row.attempt_id) params.set("attempt_id", row.attempt_id);
                            router.push(`/admin/billing/ledger?${params.toString()}`);
                          }
                        }}
                        className="px-2 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 text-xs"
                      >
                        {expandedId === row.ledger_id ? "Hide" : "Show"}
                      </button>
                    </td>
                  </tr>
                  {expandedId === row.ledger_id && (
                    <tr key={`${row.ledger_id}-details`} className="border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/50">
                      <td colSpan={13} className="px-4 py-3">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                          <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                            <div className="font-semibold mb-2">Identifiers</div>
                            <div>idempotency_key: <span className="font-mono">{row.idempotency_key || "n/a"}</span></div>
                            <div>request_id: <span className="font-mono">{row.request_id || "n/a"}</span></div>
                            <div>attempt_id: <span className="font-mono">{row.attempt_id || "n/a"}</span></div>
                            <div>channel: <span className="font-mono">{row.channel || "app"}</span></div>
                            <div>balance_after: <span className="font-mono">{row.balance_after ?? "n/a"}</span></div>
                          </div>
                          <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                            <div className="font-semibold mb-2">Pricing Snapshot</div>
                            <pre className="overflow-auto max-h-44 text-[11px] bg-slate-100 dark:bg-slate-950 p-2 rounded">
                              {JSON.stringify(row.pricing_snapshot || {}, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {loading && (
                <tr>
                  <td colSpan={13} className="px-4 py-8 text-center text-slate-500">Loading ledger...</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="flex items-center justify-between">
        <p className="text-xs text-slate-500">Pagination is fixed to 15 rows per page.</p>
        <div className="flex items-center gap-2">
          <button
            disabled={!hasPrev || loading}
            onClick={onPrev}
            className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-50"
          >
            Prev
          </button>
          <span className="text-sm text-slate-500">Page {page}</span>
          <button
            disabled={!hasNext || loading}
            onClick={onNext}
            className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </footer>
    </div>
  );
}

function fmt(value: number | null | undefined): string {
  return Number(value || 0).toFixed(4);
}

function Stat({ title, value, sub }: { title: string; value: string | number; sub: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{title}</div>
      <div className="text-2xl font-black text-slate-900 dark:text-white">{value}</div>
      <div className="text-xs text-slate-500">{sub}</div>
    </div>
  );
}
