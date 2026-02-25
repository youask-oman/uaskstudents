"use client";

import { useEffect, useState } from "react";
import { parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

interface MonitorEvent {
    direction: "in" | "out";
    type: string;
    from?: string;
    to?: string;
    text?: string;
    full_text?: string;
    message_id?: string;
    upload_id?: string;
    ok?: boolean;
    error?: string;
    timestamp?: string;
}

interface MonitorResponse {
    bot_status: { status: string; phoneNumber?: string };
    queue_length: number | null;
    queue_length_whatsapp?: number | null;
    events: MonitorEvent[];
    server_time?: string;
}

interface WhatsAppUserRow {
    user_id: number;
    full_name?: string | null;
    email?: string | null;
    whatsapp_number?: string | null;
    whatsapp_enabled: boolean;
    subscription_tier?: string | null;
    subscription_status?: string | null;
    last_active_at?: string | null;
    whatsapp_solve_count: number;
    whatsapp_tokens_used: number;
    last_whatsapp_activity_at?: string | null;
}

interface WhatsAppUsersResponse {
    total: number;
    limit: number;
    offset: number;
    items: WhatsAppUserRow[];
}

interface WhatsAppTransaction {
    id: number;
    action_type: string;
    tokens_used: number;
    timestamp?: string | null;
}

interface WhatsAppTransactionsResponse {
    user_id: number;
    transactions: WhatsAppTransaction[];
}

interface AbuseOverviewResponse {
    ingress_metrics?: Record<string, number>;
    realtime?: {
        inbound?: number;
        enqueued?: number;
        dropped?: number;
        dropped_by_reason?: Record<string, number>;
    };
    top_offenders?: Array<{
        user_id: number;
        lock_count: number;
        rate_limit_hits: number;
        quota_exceeded: number;
        abuse_hits: number;
        score: number;
    }>;
    circuits?: {
        disable_solve?: boolean;
        disable_media?: boolean;
    };
}

interface AbuseLock {
    key: string;
    scope: string;
    subject: string;
    ttl_seconds: number;
    reason: string;
}

interface AbuseAuditItem {
    timestamp: string;
    action: string;
    actor: string;
    payload?: Record<string, unknown>;
}

export default function WhatsAppMonitorPage() {
    const { pushToast } = useToast();
    const [data, setData] = useState<MonitorResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [phoneFilter, setPhoneFilter] = useState("");
    const [directionFilter, setDirectionFilter] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [selectedEvent, setSelectedEvent] = useState<MonitorEvent | null>(null);
    const [usersLoading, setUsersLoading] = useState(false);
    const [usersError, setUsersError] = useState<string | null>(null);
    const [usersData, setUsersData] = useState<WhatsAppUsersResponse | null>(null);
    const [userSearch, setUserSearch] = useState("");
    const [enabledFilter, setEnabledFilter] = useState("");
    const [selectedUser, setSelectedUser] = useState<WhatsAppUserRow | null>(null);
    const [transactions, setTransactions] = useState<WhatsAppTransaction[]>([]);
    const [transactionsLoading, setTransactionsLoading] = useState(false);
    const [abuseOverview, setAbuseOverview] = useState<AbuseOverviewResponse | null>(null);
    const [abuseLocks, setAbuseLocks] = useState<AbuseLock[]>([]);
    const [abuseAudit, setAbuseAudit] = useState<AbuseAuditItem[]>([]);
    const [abuseLoading, setAbuseLoading] = useState(false);
    const [forceLockUserId, setForceLockUserId] = useState("");
    const [forceLockPhone, setForceLockPhone] = useState("");
    const [forceLockSeconds, setForceLockSeconds] = useState("300");
    const [forceLockReason, setForceLockReason] = useState("manual_admin_lock");

    const getAuthHeaders = (): HeadersInit => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    const fetchData = async () => {
        try {
            const headers = getAuthHeaders();
            const params = new URLSearchParams({ limit: "80" });
            if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
            if (directionFilter) params.set("direction", directionFilter);
            const res = await fetch(`/api/admin/whatsapp/monitor?${params.toString()}`, {
                headers,
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = await res.json();
            setData(json);
            setError(null);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to fetch monitor");
        }
    };

    const fetchUsers = async () => {
        setUsersLoading(true);
        setUsersError(null);
        try {
            const params = new URLSearchParams({ limit: "100", offset: "0" });
            if (userSearch.trim()) params.set("search", userSearch.trim());
            if (enabledFilter === "true" || enabledFilter === "false") {
                params.set("enabled", enabledFilter);
            }
            const res = await fetch(`/api/admin/whatsapp/users?${params.toString()}`, {
                headers: getAuthHeaders(),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = (await res.json()) as WhatsAppUsersResponse;
            setUsersData(json);
        } catch (e: unknown) {
            setUsersError(e instanceof Error ? e.message : "Failed to fetch connected users");
        } finally {
            setUsersLoading(false);
        }
    };

    const fetchTransactions = async (user: WhatsAppUserRow) => {
        setSelectedUser(user);
        setTransactionsLoading(true);
        setTransactions([]);
        try {
            const res = await fetch(`/api/admin/whatsapp/users/${user.user_id}/transactions?limit=100`, {
                headers: getAuthHeaders(),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = (await res.json()) as WhatsAppTransactionsResponse;
            setTransactions(Array.isArray(json.transactions) ? json.transactions : []);
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Transactions fetch failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setTransactionsLoading(false);
        }
    };

    const patchUserControl = async (
        user: WhatsAppUserRow,
        body: { whatsapp_enabled?: boolean; unlink_number?: boolean; rotate_secret?: boolean },
        successTitle: string
    ) => {
        try {
            const res = await fetch(`/api/admin/whatsapp/users/${user.user_id}`, {
                method: "PATCH",
                headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            pushToast({ type: "success", title: successTitle, message: `User #${user.user_id} updated.` });
            fetchUsers();
            if (selectedUser?.user_id === user.user_id) {
                fetchTransactions(user);
            }
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Update failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

    const fetchAbusePanel = async () => {
        setAbuseLoading(true);
        try {
            const [overviewRes, locksRes, auditRes] = await Promise.all([
                fetch("/api/admin/whatsapp/abuse/overview?minutes=5&top_limit=20", { headers: getAuthHeaders() }),
                fetch("/api/admin/whatsapp/abuse/locks?limit=200", { headers: getAuthHeaders() }),
                fetch("/api/admin/whatsapp/abuse/audit?limit=100", { headers: getAuthHeaders() }),
            ]);
            if (!overviewRes.ok || !locksRes.ok || !auditRes.ok) {
                throw new Error("Failed to load abuse controls");
            }
            const overviewJson = (await overviewRes.json()) as AbuseOverviewResponse;
            const locksJson = (await locksRes.json()) as { items?: AbuseLock[] };
            const auditJson = (await auditRes.json()) as { items?: AbuseAuditItem[] };
            setAbuseOverview(overviewJson);
            setAbuseLocks(Array.isArray(locksJson.items) ? locksJson.items : []);
            setAbuseAudit(Array.isArray(auditJson.items) ? auditJson.items : []);
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Abuse panel failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setAbuseLoading(false);
        }
    };

    const setCircuits = async (payload: { disable_solve?: boolean; disable_media?: boolean }) => {
        try {
            const res = await fetch("/api/admin/whatsapp/abuse/circuit", {
                method: "POST",
                headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            pushToast({ type: "success", title: "Circuit updated", message: "Anti-abuse circuit flags updated." });
            fetchAbusePanel();
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Circuit update failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

    const submitForceLock = async () => {
        try {
            const res = await fetch("/api/admin/whatsapp/abuse/lock", {
                method: "POST",
                headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: forceLockUserId ? Number(forceLockUserId) : undefined,
                    phone: forceLockPhone || undefined,
                    seconds: Number(forceLockSeconds || "300"),
                    reason: forceLockReason || "manual_admin_lock",
                }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            pushToast({ type: "success", title: "Lock applied", message: "Lock was applied successfully." });
            fetchAbusePanel();
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Lock failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

    const clearLock = async (lock: AbuseLock) => {
        try {
            const body =
                lock.scope === "user"
                    ? { user_id: Number(lock.subject) }
                    : { phone: String(lock.subject) };
            const res = await fetch("/api/admin/whatsapp/abuse/lock", {
                method: "DELETE",
                headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            pushToast({ type: "success", title: "Lock cleared", message: "Lock entry removed." });
            fetchAbusePanel();
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Clear lock failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

    useEffect(() => {
        fetchData();
        const id = setInterval(fetchData, 5000);
        return () => clearInterval(id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [phoneFilter, directionFilter]);

    useEffect(() => {
        fetchUsers();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [userSearch, enabledFilter]);

    useEffect(() => {
        fetchAbusePanel();
        const id = setInterval(fetchAbusePanel, 10000);
        return () => clearInterval(id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!streaming) return;
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const params = new URLSearchParams();
        if (token) params.set("token", token);
        const es = new EventSource(`/api/admin/whatsapp/monitor/stream?${params.toString()}`);
        es.onmessage = (evt) => {
            try {
                const payload = JSON.parse(evt.data);
                setData(prev => {
                    const events = prev?.events ? [payload, ...prev.events].slice(0, 200) : [payload];
                    return prev ? { ...prev, events } : { bot_status: { status: "unknown" }, queue_length: null, events };
                });
            } catch {
                // ignore
            }
        };
        es.onerror = () => {
            es.close();
        };
        return () => es.close();
    }, [streaming]);

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white">WhatsApp Monitor</h1>
                    <p className="text-slate-600 dark:text-slate-400">Live inbound/outbound messages and queue depth.</p>
                </div>
                <div className="text-sm text-slate-500 dark:text-slate-400">
                    {data?.server_time ? `Server time: ${data.server_time}` : ""}
                </div>
            </div>

            {error && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
                    <p className="text-red-700 dark:text-red-300 text-sm">{error}</p>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Bot Status</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.bot_status?.status || "unknown"}</p>
                    {data?.bot_status?.phoneNumber && (
                        <p className="text-xs text-slate-500 mt-1">{data.bot_status.phoneNumber}</p>
                    )}
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Celery Queue</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.queue_length ?? "N/A"}</p>
                    <p className="text-xs text-slate-500 mt-1">WhatsApp: {data?.queue_length_whatsapp ?? "N/A"}</p>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Events</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.events?.length || 0}</p>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4 mb-6">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Anti-Abuse Controls</h2>
                    <button
                        onClick={fetchAbusePanel}
                        className="px-3 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs"
                    >
                        Refresh panel
                    </button>
                </div>
                <div className="text-xs text-slate-600 dark:text-slate-400 mb-4 space-y-1">
                    <p><b>What this does:</b> blocks floods, quota abuse, retry storms, and brute-force linking before enqueue.</p>
                    <p><b>How to use:</b> toggle circuits for emergency pause, force/clear locks for incidents, and review offenders/audit to tune limits.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <p className="text-xs text-slate-500">Inbound (5m)</p>
                        <p className="text-lg font-semibold">{abuseOverview?.realtime?.inbound ?? 0}</p>
                    </div>
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <p className="text-xs text-slate-500">Enqueued (5m)</p>
                        <p className="text-lg font-semibold">{abuseOverview?.realtime?.enqueued ?? 0}</p>
                    </div>
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <p className="text-xs text-slate-500">Dropped (5m)</p>
                        <p className="text-lg font-semibold">{abuseOverview?.realtime?.dropped ?? 0}</p>
                    </div>
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <p className="text-xs text-slate-500">Active Locks</p>
                        <p className="text-lg font-semibold">{abuseLocks.length}</p>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2 mb-4">
                    <button
                        onClick={() => setCircuits({ disable_solve: !(abuseOverview?.circuits?.disable_solve ?? false) })}
                        className={`px-3 py-2 rounded text-xs font-semibold ${(abuseOverview?.circuits?.disable_solve ?? false) ? "bg-red-600 text-white" : "border border-slate-200 dark:border-slate-700"}`}
                    >
                        {abuseOverview?.circuits?.disable_solve ? "Enable Solve" : "Disable Solve"}
                    </button>
                    <button
                        onClick={() => setCircuits({ disable_media: !(abuseOverview?.circuits?.disable_media ?? false) })}
                        className={`px-3 py-2 rounded text-xs font-semibold ${(abuseOverview?.circuits?.disable_media ?? false) ? "bg-red-600 text-white" : "border border-slate-200 dark:border-slate-700"}`}
                    >
                        {abuseOverview?.circuits?.disable_media ? "Enable Media" : "Disable Media"}
                    </button>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <h3 className="text-sm font-semibold mb-2">Force Lock</h3>
                        <p className="text-xs text-slate-500 mb-2">Lock a user or phone during abuse incidents.</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <input value={forceLockUserId} onChange={(e) => setForceLockUserId(e.target.value)} placeholder="User ID (optional)" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs bg-transparent" />
                            <input value={forceLockPhone} onChange={(e) => setForceLockPhone(e.target.value)} placeholder="Phone (optional)" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs bg-transparent" />
                            <input value={forceLockSeconds} onChange={(e) => setForceLockSeconds(e.target.value)} placeholder="Seconds" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs bg-transparent" />
                            <input value={forceLockReason} onChange={(e) => setForceLockReason(e.target.value)} placeholder="Reason" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs bg-transparent" />
                        </div>
                        <button onClick={submitForceLock} className="mt-2 px-3 py-1 rounded bg-slate-900 text-white text-xs">
                            Apply lock
                        </button>
                    </div>
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <h3 className="text-sm font-semibold mb-2">Top Offenders</h3>
                        <p className="text-xs text-slate-500 mb-2">Users ranked by lock/rate/quota abuse events.</p>
                        <div className="max-h-44 overflow-auto text-xs">
                            {(abuseOverview?.top_offenders || []).map((o) => (
                                <div key={o.user_id} className="py-1 border-b border-slate-100 dark:border-slate-700/60">
                                    <div>User #{o.user_id} | locks: {o.lock_count} | rate: {o.rate_limit_hits} | quota: {o.quota_exceeded} | score: {o.score}</div>
                                </div>
                            ))}
                            {(abuseOverview?.top_offenders || []).length === 0 && (
                                <p className="text-slate-500">No offenders recorded.</p>
                            )}
                        </div>
                    </div>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <h3 className="text-sm font-semibold mb-2">Active Locks</h3>
                        <p className="text-xs text-slate-500 mb-2">Temporary locks with TTL; clear when incident is resolved.</p>
                        <div className="max-h-44 overflow-auto text-xs space-y-1">
                            {abuseLocks.map((l) => (
                                <div key={l.key} className="flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-700/60 py-1">
                                    <div>{l.scope}:{l.subject} | {l.reason} | {l.ttl_seconds}s</div>
                                    <button onClick={() => clearLock(l)} className="px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                                        Clear
                                    </button>
                                </div>
                            ))}
                            {abuseLocks.length === 0 && <p className="text-slate-500">No active locks.</p>}
                        </div>
                    </div>
                    <div className="p-3 rounded border border-slate-200 dark:border-slate-700">
                        <h3 className="text-sm font-semibold mb-2">Audit Trail</h3>
                        <p className="text-xs text-slate-500 mb-2">Every manual lock/circuit action by admin is captured here.</p>
                        <div className="max-h-44 overflow-auto text-xs space-y-1">
                            {abuseAudit.map((a, idx) => (
                                <div key={`${a.timestamp}-${idx}`} className="border-b border-slate-100 dark:border-slate-700/60 py-1">
                                    <div>{a.timestamp}</div>
                                    <div>{a.action} by {a.actor}</div>
                                </div>
                            ))}
                            {abuseAudit.length === 0 && <p className="text-slate-500">No audit events yet.</p>}
                        </div>
                    </div>
                </div>
                {abuseLoading && <p className="text-xs text-slate-500 mt-3">Refreshing anti-abuse data...</p>}
            </div>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4 mb-6">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Connected Students</h2>
                    <span className="text-xs text-slate-500">
                        {usersData ? `${usersData.total} linked users` : "Loading..."}
                    </span>
                </div>
                <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
                    <input
                        value={userSearch}
                        onChange={(e) => setUserSearch(e.target.value)}
                        placeholder="Search by email, name, or phone"
                        className="flex-1 px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <select
                        value={enabledFilter}
                        onChange={(e) => setEnabledFilter(e.target.value)}
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    >
                        <option value="">All</option>
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                    </select>
                    <button
                        onClick={fetchUsers}
                        className="px-4 py-2 rounded border border-slate-200 dark:border-slate-700 text-sm"
                    >
                        Refresh
                    </button>
                </div>
                {usersError && (
                    <div className="mb-3 p-2 rounded border border-red-200 bg-red-50 text-red-700 text-sm">
                        {usersError}
                    </div>
                )}
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left border-b border-slate-200 dark:border-slate-700">
                                <th className="py-2 pr-3">User</th>
                                <th className="py-2 pr-3">Phone</th>
                                <th className="py-2 pr-3">Enabled</th>
                                <th className="py-2 pr-3">WA Solves</th>
                                <th className="py-2 pr-3">Tokens</th>
                                <th className="py-2 pr-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(usersData?.items || []).map((u) => (
                                <tr key={u.user_id} className="border-b border-slate-100 dark:border-slate-700/60">
                                    <td className="py-2 pr-3">
                                        <div className="font-medium text-slate-900 dark:text-white">{u.full_name || "Unknown"}</div>
                                        <div className="text-xs text-slate-500">{u.email || "-"}</div>
                                    </td>
                                    <td className="py-2 pr-3 text-xs">{u.whatsapp_number || "-"}</td>
                                    <td className="py-2 pr-3">
                                        <span
                                            className={`px-2 py-0.5 rounded text-xs ${u.whatsapp_enabled ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"}`}
                                        >
                                            {u.whatsapp_enabled ? "Enabled" : "Disabled"}
                                        </span>
                                    </td>
                                    <td className="py-2 pr-3">{u.whatsapp_solve_count}</td>
                                    <td className="py-2 pr-3">{u.whatsapp_tokens_used}</td>
                                    <td className="py-2 pr-3">
                                        <div className="flex flex-wrap gap-2">
                                            <button
                                                onClick={() => patchUserControl(u, { whatsapp_enabled: !u.whatsapp_enabled }, u.whatsapp_enabled ? "User disabled" : "User enabled")}
                                                className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs"
                                            >
                                                {u.whatsapp_enabled ? "Disable" : "Enable"}
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (!confirm(`Unlink WhatsApp for user #${u.user_id}?`)) return;
                                                    patchUserControl(u, { unlink_number: true }, "Phone unlinked");
                                                }}
                                                className="px-2 py-1 rounded border border-amber-300 text-amber-700 text-xs"
                                            >
                                                Unlink
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (!confirm(`Rotate WhatsApp secret for user #${u.user_id}?`)) return;
                                                    patchUserControl(u, { rotate_secret: true }, "Secret rotated");
                                                }}
                                                className="px-2 py-1 rounded border border-blue-300 text-blue-700 text-xs"
                                            >
                                                Rotate secret
                                            </button>
                                            <button
                                                onClick={() => fetchTransactions(u)}
                                                className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs"
                                            >
                                                Transactions
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {usersLoading && <p className="text-xs text-slate-500 mt-3">Loading users...</p>}
                    {!usersLoading && (usersData?.items || []).length === 0 && (
                        <p className="text-xs text-slate-500 mt-3">No connected users found.</p>
                    )}
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4 mb-6">
                <div className="flex flex-col md:flex-row md:items-center gap-3">
                    <input
                        value={phoneFilter}
                        onChange={(e) => setPhoneFilter(e.target.value)}
                        placeholder="Filter by phone (e.g. 12345@s.whatsapp.net)"
                        className="flex-1 px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <select
                        value={directionFilter}
                        onChange={(e) => setDirectionFilter(e.target.value)}
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    >
                        <option value="">All directions</option>
                        <option value="in">Inbound</option>
                        <option value="out">Outbound</option>
                    </select>
                    <button
                        onClick={() => {
                            const params = new URLSearchParams({ limit: "200" });
                            if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
                            if (directionFilter) params.set("direction", directionFilter);
                            const token = localStorage.getItem("token");
                            if (token) params.set("token", token);
                            window.location.href = `/api/admin/whatsapp/monitor/export?${params.toString()}`;
                        }}
                        className="px-4 py-2 rounded bg-slate-900 text-white text-sm"
                    >
                        Export CSV
                    </button>
                    <button
                        onClick={() => setStreaming(!streaming)}
                        className="px-4 py-2 rounded border border-slate-200 dark:border-slate-700 text-sm"
                    >
                        {streaming ? "Stop Live" : "Start Live"}
                    </button>
                    <button
                        onClick={async () => {
                            if (!confirm("Are you sure you want to clear the WhatsApp event monitor?")) return;
                            const token = localStorage.getItem("token");
                            try {
                                const res = await fetch(`/api/admin/whatsapp/all`, {
                                    method: "DELETE",
                                    headers: { Authorization: `Bearer ${token}` }
                                });
                                if (res.ok) {
                                    fetchData();
                                    pushToast({
                                        type: "success",
                                        title: "Monitor cleared",
                                        message: "WhatsApp events cleared successfully.",
                                    });
                                } else {
                                    const err = await parseApiError(res);
                                    pushToast({
                                        type: "error",
                                        title: "Clear failed",
                                        message: err.message,
                                        requestId: err.requestId,
                                    });
                                }
                            } catch (e) {
                                pushToast({
                                    type: "error",
                                    title: "Clear failed",
                                    message: e instanceof Error ? e.message : "Unexpected error",
                                });
                            }
                        }}
                        className="px-4 py-2 rounded bg-rose-500 hover:bg-rose-600 text-white text-sm font-bold transition-all"
                    >
                        Clear Monitor
                    </button>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Recent Events</h2>
                </div>
                <div className="divide-y divide-slate-200 dark:divide-slate-700">
                    {data?.events?.map((evt, idx) => (
                        <div key={idx} className="px-4 py-3 text-sm">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className={`px-2 py-0.5 rounded text-xs ${evt.direction === "in" ? "bg-blue-100 text-blue-800" : "bg-green-100 text-green-800"}`}>
                                        {evt.direction}
                                    </span>
                                    <span className="text-xs text-slate-500">{evt.type}</span>
                                    {evt.ok === false && <span className="text-xs text-red-600">failed</span>}
                                </div>
                                <span className="text-xs text-slate-400">{evt.timestamp || ""}</span>
                            </div>
                            <div className="mt-1 text-slate-700 dark:text-slate-200 break-words">
                                {evt.text || ""}
                            </div>
                            <div className="mt-1 text-xs text-slate-500">
                                {evt.from ? `from: ${evt.from}` : ""} {evt.to ? `to: ${evt.to}` : ""}
                            </div>
                            {evt.error && <div className="mt-1 text-xs text-red-600">{evt.error}</div>}
                            <div className="mt-2">
                                <button
                                    type="button"
                                    onClick={() => setSelectedEvent(evt)}
                                    className="text-xs font-semibold text-primary"
                                >
                                    View details
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {selectedEvent && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 w-[90%] max-w-3xl">
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 dark:text-white">WhatsApp Event Detail</h3>
                                <p className="text-xs text-slate-500">{selectedEvent.timestamp || ""}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setSelectedEvent(null)}
                                className="text-sm px-3 py-1 rounded border border-slate-200 dark:border-slate-700"
                            >
                                Close
                            </button>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="text-sm text-slate-700 dark:text-slate-200">
                                <div className="text-xs text-slate-500 mb-1">Summary</div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`px-2 py-0.5 rounded text-xs ${selectedEvent.direction === "in" ? "bg-blue-100 text-blue-800" : "bg-green-100 text-green-800"}`}>
                                        {selectedEvent.direction}
                                    </span>
                                    <span className="text-xs text-slate-500">{selectedEvent.type}</span>
                                    {selectedEvent.ok === false && <span className="text-xs text-red-600">failed</span>}
                                    {selectedEvent.message_id && <span className="text-xs text-slate-500">msg: {selectedEvent.message_id}</span>}
                                    {selectedEvent.upload_id && <span className="text-xs text-slate-500">upload: {selectedEvent.upload_id}</span>}
                                </div>
                                <div className="mt-2 text-xs text-slate-500">
                                    {selectedEvent.from ? `from: ${selectedEvent.from}` : ""} {selectedEvent.to ? `to: ${selectedEvent.to}` : ""}
                                </div>
                            </div>
                            <div className="text-sm">
                                <div className="text-xs text-slate-500 mb-1">Full Text</div>
                                <pre className="whitespace-pre-wrap text-slate-800 dark:text-slate-100 bg-slate-50 dark:bg-slate-800 p-3 rounded border border-slate-200 dark:border-slate-700 text-xs">
                                    {selectedEvent.full_text || selectedEvent.text || ""}
                                </pre>
                            </div>
                            {selectedEvent.error && (
                                <div className="text-sm">
                                    <div className="text-xs text-slate-500 mb-1">Error</div>
                                    <pre className="whitespace-pre-wrap text-red-600 bg-red-50 dark:bg-red-900/30 p-3 rounded border border-red-200 dark:border-red-800 text-xs">
                                        {selectedEvent.error}
                                    </pre>
                                </div>
                            )}
                            <div className="text-sm">
                                <div className="text-xs text-slate-500 mb-1">Raw JSON</div>
                                <pre className="whitespace-pre-wrap text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-800 p-3 rounded border border-slate-200 dark:border-slate-700 text-[11px]">
                                    {JSON.stringify(selectedEvent, null, 2)}
                                </pre>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {selectedUser && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 w-[90%] max-w-4xl">
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 dark:text-white">WhatsApp Transactions</h3>
                                <p className="text-xs text-slate-500">
                                    User #{selectedUser.user_id} {selectedUser.email ? `(${selectedUser.email})` : ""}
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setSelectedUser(null)}
                                className="text-sm px-3 py-1 rounded border border-slate-200 dark:border-slate-700"
                            >
                                Close
                            </button>
                        </div>
                        <div className="p-5">
                            {transactionsLoading ? (
                                <p className="text-sm text-slate-500">Loading transactions...</p>
                            ) : transactions.length === 0 ? (
                                <p className="text-sm text-slate-500">No WhatsApp transactions found for this user.</p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left border-b border-slate-200 dark:border-slate-700">
                                                <th className="py-2 pr-3">ID</th>
                                                <th className="py-2 pr-3">Action</th>
                                                <th className="py-2 pr-3">Tokens</th>
                                                <th className="py-2 pr-3">Timestamp</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {transactions.map((tx) => (
                                                <tr key={tx.id} className="border-b border-slate-100 dark:border-slate-700/60">
                                                    <td className="py-2 pr-3">{tx.id}</td>
                                                    <td className="py-2 pr-3">{tx.action_type}</td>
                                                    <td className="py-2 pr-3">{tx.tokens_used}</td>
                                                    <td className="py-2 pr-3 text-xs">{tx.timestamp || "-"}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
