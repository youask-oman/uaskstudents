"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type Offender = {
  user_id: number;
  lock_count: number;
  rate_limit_hits: number;
  quota_exceeded: number;
  abuse_hits: number;
  score: number;
};

type LockItem = {
  key: string;
  scope: string;
  subject: string;
  ttl_seconds: number;
  reason: string;
};

type AuditItem = {
  timestamp: string;
  action: string;
  actor: string;
  payload?: Record<string, unknown>;
};

type Overview = {
  ingress_metrics?: Record<string, number>;
  realtime?: {
    inbound?: number;
    enqueued?: number;
    dropped?: number;
    dropped_by_reason?: Record<string, number>;
  };
  top_offenders?: Offender[];
  circuits?: {
    disable_solve?: boolean;
    disable_media?: boolean;
  };
};

export default function WhatsAppAbusePage() {
  const { pushToast } = useToast();
  const [minutes, setMinutes] = useState("15");
  const [offenderLimit, setOffenderLimit] = useState("200");
  const [lockLimit, setLockLimit] = useState("1000");
  const [auditLimit, setAuditLimit] = useState("1000");
  const [searchUser, setSearchUser] = useState("");
  const [searchLock, setSearchLock] = useState("");
  const [searchAudit, setSearchAudit] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [locks, setLocks] = useState<LockItem[]>([]);
  const [audit, setAudit] = useState<AuditItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [forceUserId, setForceUserId] = useState("");
  const [forcePhone, setForcePhone] = useState("");
  const [forceSeconds, setForceSeconds] = useState("300");
  const [forceReason, setForceReason] = useState("ops_manual_lock");

  const authHeaders = (): HeadersInit => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [overviewRes, locksRes, auditRes] = await Promise.all([
        fetch(`/api/admin/whatsapp/abuse/overview?minutes=${encodeURIComponent(minutes)}&top_limit=${encodeURIComponent(offenderLimit)}`, { headers: authHeaders() }),
        fetch(`/api/admin/whatsapp/abuse/locks?limit=${encodeURIComponent(lockLimit)}`, { headers: authHeaders() }),
        fetch(`/api/admin/whatsapp/abuse/audit?limit=${encodeURIComponent(auditLimit)}`, { headers: authHeaders() }),
      ]);
      if (!overviewRes.ok || !locksRes.ok || !auditRes.ok) {
        throw new Error("Failed to load abuse controls.");
      }
      setOverview((await overviewRes.json()) as Overview);
      const lockJson = (await locksRes.json()) as { items?: LockItem[] };
      const auditJson = (await auditRes.json()) as { items?: AuditItem[] };
      setLocks(Array.isArray(lockJson.items) ? lockJson.items : []);
      setAudit(Array.isArray(auditJson.items) ? auditJson.items : []);
    } catch (e: unknown) {
      pushToast({
        type: "error",
        title: "Load failed",
        message: e instanceof Error ? e.message : "Unexpected error",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 15000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setCircuit = async (body: { disable_solve?: boolean; disable_media?: boolean }) => {
    try {
      const res = await fetch("/api/admin/whatsapp/abuse/circuit", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Circuit updated", message: "WhatsApp abuse circuit updated." });
      fetchAll();
    } catch (e: unknown) {
      pushToast({ type: "error", title: "Circuit update failed", message: e instanceof Error ? e.message : "Unexpected error" });
    }
  };

  const forceLock = async () => {
    try {
      const res = await fetch("/api/admin/whatsapp/abuse/lock", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: forceUserId ? Number(forceUserId) : undefined,
          phone: forcePhone || undefined,
          seconds: Number(forceSeconds || "300"),
          reason: forceReason || "ops_manual_lock",
        }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Lock applied", message: "Lock created successfully." });
      fetchAll();
    } catch (e: unknown) {
      pushToast({ type: "error", title: "Lock failed", message: e instanceof Error ? e.message : "Unexpected error" });
    }
  };

  const clearLock = async (item: LockItem) => {
    try {
      const body = item.scope === "user" ? { user_id: Number(item.subject) } : { phone: item.subject };
      const res = await fetch("/api/admin/whatsapp/abuse/lock", {
        method: "DELETE",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message);
      }
      pushToast({ type: "success", title: "Lock cleared", message: `${item.scope}:${item.subject} cleared.` });
      fetchAll();
    } catch (e: unknown) {
      pushToast({ type: "error", title: "Clear failed", message: e instanceof Error ? e.message : "Unexpected error" });
    }
  };

  const offenders = useMemo(() => {
    const rows = overview?.top_offenders || [];
    if (!searchUser.trim()) return rows;
    return rows.filter((r) => String(r.user_id).includes(searchUser.trim()));
  }, [overview, searchUser]);

  const filteredLocks = useMemo(() => {
    if (!searchLock.trim()) return locks;
    const q = searchLock.toLowerCase();
    return locks.filter((l) => `${l.scope} ${l.subject} ${l.reason}`.toLowerCase().includes(q));
  }, [locks, searchLock]);

  const filteredAudit = useMemo(() => {
    if (!searchAudit.trim()) return audit;
    const q = searchAudit.toLowerCase();
    return audit.filter((a) => `${a.timestamp} ${a.action} ${a.actor}`.toLowerCase().includes(q));
  }, [audit, searchAudit]);

  const exportCsv = (kind: "offenders" | "locks" | "audit") => {
    const token = localStorage.getItem("token");
    const params = new URLSearchParams({ limit: kind === "offenders" ? offenderLimit : kind === "locks" ? lockLimit : auditLimit });
    if (token) params.set("token", token);
    window.location.href = `/api/admin/whatsapp/abuse/export/${kind}?${params.toString()}`;
  };

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">WhatsApp Abuse Operations</h1>
          <p className="text-slate-600 dark:text-slate-400">
            Dedicated operations console for anti-abuse policy enforcement, large-table review, and exports.
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Use this page for incident response. Use <Link className="underline" href="/admin/whatsapp-monitor">WhatsApp Monitor</Link> for message stream.
          </p>
        </div>
        <button onClick={fetchAll} className="px-4 py-2 rounded bg-slate-900 text-white text-sm">
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-6">
        <div className="p-3 border rounded border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500">Inbound ({minutes}m)</p>
          <p className="text-xl font-semibold">{overview?.realtime?.inbound ?? 0}</p>
        </div>
        <div className="p-3 border rounded border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500">Enqueued ({minutes}m)</p>
          <p className="text-xl font-semibold">{overview?.realtime?.enqueued ?? 0}</p>
        </div>
        <div className="p-3 border rounded border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500">Dropped ({minutes}m)</p>
          <p className="text-xl font-semibold">{overview?.realtime?.dropped ?? 0}</p>
        </div>
        <div className="p-3 border rounded border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500">Solve Circuit</p>
          <p className="text-xl font-semibold">{overview?.circuits?.disable_solve ? "DISABLED" : "ENABLED"}</p>
        </div>
        <div className="p-3 border rounded border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500">Media Circuit</p>
          <p className="text-xl font-semibold">{overview?.circuits?.disable_media ? "DISABLED" : "ENABLED"}</p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4 mb-6">
        <h2 className="font-semibold mb-2">Policy Controls</h2>
        <p className="text-xs text-slate-500 mb-3">
          Emergency controls: circuit breakers pause solve/media lanes immediately. Force lock isolates abusive users or phones during incidents.
        </p>
        <div className="flex flex-wrap gap-2 mb-3">
          <button onClick={() => setCircuit({ disable_solve: !(overview?.circuits?.disable_solve ?? false) })} className="px-3 py-2 rounded bg-amber-600 text-white text-xs">
            {overview?.circuits?.disable_solve ? "Enable Solve Lane" : "Disable Solve Lane"}
          </button>
          <button onClick={() => setCircuit({ disable_media: !(overview?.circuits?.disable_media ?? false) })} className="px-3 py-2 rounded bg-amber-600 text-white text-xs">
            {overview?.circuits?.disable_media ? "Enable Media Lane" : "Disable Media Lane"}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <input value={forceUserId} onChange={(e) => setForceUserId(e.target.value)} placeholder="User ID (optional)" className="px-2 py-2 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-sm" />
          <input value={forcePhone} onChange={(e) => setForcePhone(e.target.value)} placeholder="Phone (optional)" className="px-2 py-2 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-sm" />
          <input value={forceSeconds} onChange={(e) => setForceSeconds(e.target.value)} placeholder="Seconds" className="px-2 py-2 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-sm" />
          <input value={forceReason} onChange={(e) => setForceReason(e.target.value)} placeholder="Reason" className="px-2 py-2 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-sm" />
        </div>
        <button onClick={forceLock} className="mt-3 px-3 py-2 rounded bg-rose-600 text-white text-xs">
          Apply Force Lock
        </button>
      </div>

      <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Top Offenders</h2>
          <div className="flex items-center gap-2">
            <input value={minutes} onChange={(e) => setMinutes(e.target.value)} placeholder="Minutes" className="w-20 px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs" />
            <input value={offenderLimit} onChange={(e) => setOffenderLimit(e.target.value)} placeholder="Limit" className="w-20 px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs" />
            <button onClick={() => exportCsv("offenders")} className="px-3 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs">Export CSV</button>
          </div>
        </div>
        <p className="text-xs text-slate-500 mb-2">Ranked by lock count, rate-limit hits, quota violations, and abuse score.</p>
        <input value={searchUser} onChange={(e) => setSearchUser(e.target.value)} placeholder="Filter by user id" className="w-full md:w-72 px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs mb-2" />
        <div className="overflow-auto max-h-[420px] border rounded border-slate-200 dark:border-slate-700">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
              <tr>
                <th className="text-left p-2">User ID</th>
                <th className="text-left p-2">Locks</th>
                <th className="text-left p-2">Rate Hits</th>
                <th className="text-left p-2">Quota Exceeded</th>
                <th className="text-left p-2">Abuse Hits</th>
                <th className="text-left p-2">Score</th>
              </tr>
            </thead>
            <tbody>
              {offenders.map((o) => (
                <tr key={o.user_id} className="border-t border-slate-100 dark:border-slate-700/60">
                  <td className="p-2">{o.user_id}</td>
                  <td className="p-2">{o.lock_count}</td>
                  <td className="p-2">{o.rate_limit_hits}</td>
                  <td className="p-2">{o.quota_exceeded}</td>
                  <td className="p-2">{o.abuse_hits}</td>
                  <td className="p-2">{o.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Active Locks</h2>
            <div className="flex items-center gap-2">
              <input value={lockLimit} onChange={(e) => setLockLimit(e.target.value)} placeholder="Limit" className="w-20 px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs" />
              <button onClick={() => exportCsv("locks")} className="px-3 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs">Export CSV</button>
            </div>
          </div>
          <p className="text-xs text-slate-500 mb-2">Temporary lock records currently blocking user or phone traffic.</p>
          <input value={searchLock} onChange={(e) => setSearchLock(e.target.value)} placeholder="Filter by subject/reason" className="w-full px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs mb-2" />
          <div className="overflow-auto max-h-[460px] border rounded border-slate-200 dark:border-slate-700">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
                <tr>
                  <th className="text-left p-2">Scope</th>
                  <th className="text-left p-2">Subject</th>
                  <th className="text-left p-2">TTL(s)</th>
                  <th className="text-left p-2">Reason</th>
                  <th className="text-left p-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredLocks.map((item) => (
                  <tr key={item.key} className="border-t border-slate-100 dark:border-slate-700/60">
                    <td className="p-2">{item.scope}</td>
                    <td className="p-2">{item.subject}</td>
                    <td className="p-2">{item.ttl_seconds}</td>
                    <td className="p-2 break-words">{item.reason}</td>
                    <td className="p-2">
                      <button onClick={() => clearLock(item)} className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700">
                        Clear
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Audit Trail</h2>
            <div className="flex items-center gap-2">
              <input value={auditLimit} onChange={(e) => setAuditLimit(e.target.value)} placeholder="Limit" className="w-20 px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs" />
              <button onClick={() => exportCsv("audit")} className="px-3 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs">Export CSV</button>
            </div>
          </div>
          <p className="text-xs text-slate-500 mb-2">Immutable operational actions: force-lock, clear-lock, and circuit changes.</p>
          <input value={searchAudit} onChange={(e) => setSearchAudit(e.target.value)} placeholder="Filter by timestamp/action/actor" className="w-full px-2 py-1 border rounded border-slate-200 dark:border-slate-700 bg-transparent text-xs mb-2" />
          <div className="overflow-auto max-h-[460px] border rounded border-slate-200 dark:border-slate-700">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
                <tr>
                  <th className="text-left p-2">Timestamp</th>
                  <th className="text-left p-2">Action</th>
                  <th className="text-left p-2">Actor</th>
                  <th className="text-left p-2">Payload</th>
                </tr>
              </thead>
              <tbody>
                {filteredAudit.map((item, idx) => (
                  <tr key={`${item.timestamp}-${idx}`} className="border-t border-slate-100 dark:border-slate-700/60">
                    <td className="p-2">{item.timestamp}</td>
                    <td className="p-2">{item.action}</td>
                    <td className="p-2">{item.actor}</td>
                    <td className="p-2">
                      <pre className="whitespace-pre-wrap break-words">{JSON.stringify(item.payload || {}, null, 0)}</pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {loading && <p className="text-xs text-slate-500 mt-4">Refreshing data...</p>}
    </div>
  );
}
