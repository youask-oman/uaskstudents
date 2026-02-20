"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import AdminUserAutocomplete from "@/components/admin/AdminUserAutocomplete";

type InspectorUser = {
    id: number;
    email: string;
    name?: string;
    role: string;
};

type InspectorCredits = {
    available_credits: number;
    reserved_credits: number;
    lots_count: number;
    holds_count?: number;
    ledger_count: number;
};

type InspectorResult = {
    user: InspectorUser;
    credits: InspectorCredits;
};

type CursorPage<T> = {
    items: T[];
    next_cursor?: string | null;
    total?: number;
};

type CreditLot = {
    lot_id: string;
    source: string;
    credits_total: number;
    credits_remaining: number;
    expires_at?: string | null;
    created_at: string;
};

type CreditHold = {
    hold_id: string;
    status: string;
    tier?: string | null;
    action?: string | null;
    reserved: number;
    settled: number;
    released: number;
    expires_at?: string | null;
    created_at: string;
};

type CreditLedger = {
    ledger_id: string;
    action: string;
    tier?: string | null;
    total_cost: number;
    outcome: string;
    request_id?: string | null;
    created_at: string;
};

type WalletProgram = {
    id: number;
    program_name?: string | null;
    status: string;
    started_at: string;
    last_grant_month?: string | null;
    next_grant_date?: string | null;
    next_grant_status?: string | null;
};

type WalletSummary = {
    cached_balance: number;
    computed_balance: number;
    delta: number;
    total_lots: number;
    active_lots: number;
    pending_holds: number;
    pending_hold_credits: number;
    expiring_soon_credits: number;
    expiring_soon_lots: number;
};

export default function UserCreditInspectorPage() {
    const { pushToast } = useToast();
    const [query, setQuery] = useState("");
    const [result, setResult] = useState<InspectorResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [detailsLoading, setDetailsLoading] = useState(false);
    const [reason, setReason] = useState("");
    const [role, setRole] = useState("");
    const [grantAmount, setGrantAmount] = useState("50");
    const [grantExpiryDays, setGrantExpiryDays] = useState("30");
    const [granting, setGranting] = useState(false);
    const [lots, setLots] = useState<CreditLot[]>([]);
    const [holds, setHolds] = useState<CreditHold[]>([]);
    const [ledger, setLedger] = useState<CreditLedger[]>([]);
    const [programs, setPrograms] = useState<WalletProgram[]>([]);
    const [walletSummary, setWalletSummary] = useState<WalletSummary | null>(null);
    const canGrant = role === "superadmin" || role === "admin";

    useEffect(() => {
        if (typeof window !== "undefined") {
            setRole((localStorage.getItem("user_role") || "").toLowerCase());
        }
    }, []);

    const headers = useMemo<Record<string, string>>(() => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const out: Record<string, string> = { "Content-Type": "application/json" };
        if (token) out.Authorization = `Bearer ${token}`;
        return out;
    }, []);

    const loadDetails = async (userId: number) => {
        setDetailsLoading(true);
        try {
            const [lotsRes, holdsRes, ledgerRes, programsRes] = await Promise.all([
                fetchApi(`/api/v1/admin/credits/lots?user_id=${userId}&limit=8`, { headers }),
                fetchApi(`/api/v1/admin/credits/holds?user_id=${userId}&limit=8`, { headers }),
                fetchApi(`/api/v1/admin/credits/ledger?user_id=${userId}&limit=8`, { headers }),
                fetchApi(`/api/admin/billing/users/${userId}/enrollments?limit=8&offset=0`, { headers }),
            ]);
            const walletSummaryRes = await fetchApi(`/api/admin/billing/users/${userId}/wallet_summary`, { headers });

            if (!lotsRes.ok || !holdsRes.ok || !ledgerRes.ok) {
                const fallback = !lotsRes.ok ? lotsRes : !holdsRes.ok ? holdsRes : ledgerRes;
                const err = await parseApiError(fallback);
                pushToast({ type: "error", title: "Detail load failed", message: err.message, requestId: err.requestId });
                return;
            }

            const lotsPayload = (await lotsRes.json()) as CursorPage<CreditLot>;
            const holdsPayload = (await holdsRes.json()) as CursorPage<CreditHold>;
            const ledgerPayload = (await ledgerRes.json()) as CursorPage<CreditLedger>;

            setLots(Array.isArray(lotsPayload.items) ? lotsPayload.items : []);
            setHolds(Array.isArray(holdsPayload.items) ? holdsPayload.items : []);
            setLedger(Array.isArray(ledgerPayload.items) ? ledgerPayload.items : []);

            if (programsRes.ok) {
                const programsPayload = (await programsRes.json()) as { items?: WalletProgram[] };
                setPrograms(Array.isArray(programsPayload.items) ? programsPayload.items : []);
            } else {
                setPrograms([]);
            }

            if (walletSummaryRes.ok) {
                const summaryPayload = (await walletSummaryRes.json()) as WalletSummary;
                setWalletSummary(summaryPayload);
            } else {
                setWalletSummary(null);
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Unexpected error";
            pushToast({ type: "error", title: "Detail load failed", message: msg });
        } finally {
            setDetailsLoading(false);
        }
    };

    const search = async () => {
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await fetchApi(`/api/v1/admin/credits/user?query=${encodeURIComponent(query.trim())}`, { headers });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({ type: "error", title: "Search failed", message: err.message, requestId: err.requestId });
                setResult(null);
                return;
            }
            const payload = (await res.json()) as InspectorResult;
            setResult(payload);
            await loadDetails(payload.user.id);
        } finally {
            setLoading(false);
        }
    };

    const grant = async () => {
        if (!canGrant) {
            pushToast({ type: "error", title: "Forbidden", message: "Only admin/superadmin can grant credits." });
            return;
        }
        if (!result?.user?.id) return;
        const credits = Number(grantAmount);
        if (!Number.isFinite(credits) || credits <= 0) return;
        const expiryDays = Number(grantExpiryDays);
        const expiresAt = Number.isFinite(expiryDays) && expiryDays > 0
            ? new Date(Date.now() + expiryDays * 24 * 60 * 60 * 1000).toISOString()
            : null;
        if (!reason.trim()) {
            pushToast({ type: "error", title: "Reason required", message: "Provide reason before grant." });
            return;
        }
        setGranting(true);
        try {
            const res = await fetchApi(`/api/v1/admin/credits/grant`, {
                method: "POST",
                headers: { ...headers, "Idempotency-Key": `grant_${result.user.id}_${Date.now()}` },
                body: JSON.stringify({ user_id: result.user.id, credits, expires_at: expiresAt, reason }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({ type: "error", title: "Grant failed", message: err.message, requestId: err.requestId });
                return;
            }
            pushToast({ type: "success", title: "Credits granted", message: `${credits.toFixed(2)} credits granted.` });
            await search();
        } finally {
            setGranting(false);
        }
    };

    const netAvailable = result
        ? Number(result.credits.available_credits || 0) - Number(result.credits.reserved_credits || 0)
        : 0;

    const formatTime = (value?: string | null) => {
        if (!value) return "N/A";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString();
    };

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(20,184,166,0.12),_transparent_45%),linear-gradient(180deg,#f8fafc,#eef2ff)] dark:bg-[radial-gradient(circle_at_top,_rgba(20,184,166,0.16),_transparent_45%),linear-gradient(180deg,#0f172a,#020617)]">
            <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-6">
                <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white/90 dark:bg-slate-900/70 backdrop-blur">
                    <div className="px-6 py-5 md:px-8 md:py-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                        <div>
                            <p className="text-[11px] uppercase tracking-[0.2em] font-semibold text-teal-600 dark:text-teal-300">Admin Billing</p>
                            <h1 className="text-3xl md:text-4xl font-black text-slate-900 dark:text-white">Credit Inspector</h1>
                            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Search any user, inspect wallet internals, and run audited credit actions.</p>
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 bg-slate-100/80 dark:bg-slate-800/70 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700">
                            Signed in as <span className="font-bold uppercase">{role || "unknown"}</span>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 md:p-6 space-y-4">
                        <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">Lookup User</label>
                        <div className="flex gap-3">
                            <AdminUserAutocomplete
                                value={query}
                                onValueChange={setQuery}
                                onSelect={(user) => setQuery(user.email)}
                                placeholder="Type user email"
                                className="flex-1"
                                inputClassName="w-full border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm bg-slate-50 dark:bg-slate-800/60"
                            />
                            <button
                                className="px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold disabled:opacity-60"
                                onClick={() => void search()}
                                disabled={loading}
                            >
                                {loading ? "Searching..." : "Search"}
                            </button>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Start typing email and select from the users table autocomplete.</p>
                    </div>

                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 md:p-6 space-y-3">
                        <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">Audit Reason</label>
                        <textarea
                            rows={4}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            className="w-full border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm bg-slate-50 dark:bg-slate-800/60"
                            placeholder="Required: why you are running this action."
                        />
                    </div>
                </div>

                {result && (
                    <>
                        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                            <div className="xl:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                        <p className="text-xs uppercase tracking-[0.2em] font-semibold text-slate-500">User Profile</p>
                                        <h2 className="text-xl font-black text-slate-900 dark:text-white">{result.user.name || result.user.email}</h2>
                                        <p className="text-sm text-slate-500 dark:text-slate-400">{result.user.email} • #{result.user.id}</p>
                                    </div>
                                    <span className="px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-700/60">
                                        {result.user.role}
                                    </span>
                                </div>

                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-slate-50 dark:bg-slate-800/50">
                                        <p className="text-[11px] uppercase text-slate-500">Available</p>
                                        <p className="text-xl font-black text-slate-900 dark:text-white">{result.credits.available_credits.toFixed(2)}</p>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-slate-50 dark:bg-slate-800/50">
                                        <p className="text-[11px] uppercase text-slate-500">Reserved</p>
                                        <p className="text-xl font-black text-amber-600 dark:text-amber-400">{result.credits.reserved_credits.toFixed(2)}</p>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-slate-50 dark:bg-slate-800/50">
                                        <p className="text-[11px] uppercase text-slate-500">Net Spendable</p>
                                        <p className="text-xl font-black text-emerald-600 dark:text-emerald-400">{netAvailable.toFixed(2)}</p>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-slate-50 dark:bg-slate-800/50">
                                        <p className="text-[11px] uppercase text-slate-500">Activity</p>
                                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                            {result.credits.lots_count} lots • {result.credits.holds_count || 0} holds • {result.credits.ledger_count} ledger
                                        </p>
                                    </div>
                                </div>
                                {walletSummary && (
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-white dark:bg-slate-900">
                                            <p className="text-[11px] uppercase text-slate-500">Cached</p>
                                            <p className="text-sm font-bold text-slate-900 dark:text-white">{walletSummary.cached_balance.toFixed(2)}</p>
                                        </div>
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-white dark:bg-slate-900">
                                            <p className="text-[11px] uppercase text-slate-500">Computed</p>
                                            <p className="text-sm font-bold text-slate-900 dark:text-white">{walletSummary.computed_balance.toFixed(2)}</p>
                                        </div>
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-white dark:bg-slate-900">
                                            <p className="text-[11px] uppercase text-slate-500">Pending Holds</p>
                                            <p className="text-sm font-bold text-slate-900 dark:text-white">{walletSummary.pending_holds} ({walletSummary.pending_hold_credits.toFixed(2)})</p>
                                        </div>
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-white dark:bg-slate-900">
                                            <p className="text-[11px] uppercase text-slate-500">Expiring Soon</p>
                                            <p className="text-sm font-bold text-slate-900 dark:text-white">{walletSummary.expiring_soon_lots} ({walletSummary.expiring_soon_credits.toFixed(2)})</p>
                                        </div>
                                    </div>
                                )}

                                <div className="flex flex-wrap gap-2">
                                    <a className="px-3 py-2 rounded-lg bg-slate-200 dark:bg-slate-700 text-sm font-semibold" href={`/admin/billing/users/${result.user.id}/wallet`}>
                                        Open Wallet Page
                                    </a>
                                    <a className="px-3 py-2 rounded-lg bg-slate-200 dark:bg-slate-700 text-sm font-semibold" href={`/admin/billing/ledger?user_id=${result.user.id}`}>
                                        Full Ledger
                                    </a>
                                    <a className="px-3 py-2 rounded-lg bg-slate-200 dark:bg-slate-700 text-sm font-semibold" href={`/admin/billing/holds?user_id=${result.user.id}`}>
                                        Full Holds
                                    </a>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
                                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-slate-500">Quick Grant</p>
                                <div className="space-y-2">
                                    <label className="text-xs font-semibold text-slate-500">Credits</label>
                                    <input
                                        value={grantAmount}
                                        onChange={(e) => setGrantAmount(e.target.value)}
                                        className="w-full border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm bg-slate-50 dark:bg-slate-800/60"
                                        placeholder="50"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-semibold text-slate-500">Expiry (days)</label>
                                    <input
                                        value={grantExpiryDays}
                                        onChange={(e) => setGrantExpiryDays(e.target.value)}
                                        className="w-full border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm bg-slate-50 dark:bg-slate-800/60"
                                        placeholder="30"
                                    />
                                </div>
                                <button
                                    className="w-full px-4 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold disabled:opacity-50"
                                    onClick={() => void grant()}
                                    disabled={!canGrant || granting}
                                    title={!canGrant ? "Only admin/superadmin can grant credits." : undefined}
                                >
                                    {granting ? "Granting..." : "Grant Credits"}
                                </button>
                                {!canGrant && (
                                    <p className="text-xs text-rose-500">Your role cannot grant credits.</p>
                                )}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
                                <h3 className="text-lg font-black text-slate-900 dark:text-white mb-3">Recent Lots</h3>
                                {detailsLoading ? (
                                    <p className="text-sm text-slate-500">Loading details...</p>
                                ) : lots.length === 0 ? (
                                    <p className="text-sm text-slate-500">No lots found.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {lots.map((lot) => (
                                            <div key={lot.lot_id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 text-sm">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p className="font-semibold text-slate-900 dark:text-white truncate">{lot.source}</p>
                                                    <p className="font-bold text-slate-900 dark:text-white">{lot.credits_remaining.toFixed(2)} / {lot.credits_total.toFixed(2)}</p>
                                                </div>
                                                <p className="text-xs text-slate-500">Created: {formatTime(lot.created_at)}</p>
                                                <p className="text-xs text-slate-500">Expires: {formatTime(lot.expires_at)}</p>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
                                <h3 className="text-lg font-black text-slate-900 dark:text-white mb-3">Recent Holds</h3>
                                {detailsLoading ? (
                                    <p className="text-sm text-slate-500">Loading details...</p>
                                ) : holds.length === 0 ? (
                                    <p className="text-sm text-slate-500">No holds found.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {holds.map((hold) => (
                                            <div key={hold.hold_id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 text-sm">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p className="font-semibold text-slate-900 dark:text-white">{hold.action || "HOLD"}</p>
                                                    <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase font-bold ${hold.status === "active" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>
                                                        {hold.status}
                                                    </span>
                                                </div>
                                                <p className="text-xs text-slate-500">Reserved {hold.reserved.toFixed(2)} • Settled {hold.settled.toFixed(2)} • Released {hold.released.toFixed(2)}</p>
                                                <p className="text-xs text-slate-500">Created: {formatTime(hold.created_at)}</p>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
                                <h3 className="text-lg font-black text-slate-900 dark:text-white mb-3">Recent Ledger Entries</h3>
                                {detailsLoading ? (
                                    <p className="text-sm text-slate-500">Loading details...</p>
                                ) : ledger.length === 0 ? (
                                    <p className="text-sm text-slate-500">No ledger entries found.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {ledger.map((entry) => (
                                            <div key={entry.ledger_id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 text-sm">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p className="font-semibold text-slate-900 dark:text-white">{entry.action} {entry.tier ? `• ${entry.tier}` : ""}</p>
                                                    <p className={`font-bold ${entry.total_cost > 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                                        {entry.total_cost > 0 ? "-" : "+"}{Math.abs(entry.total_cost).toFixed(2)}
                                                    </p>
                                                </div>
                                                <p className="text-xs text-slate-500">Outcome: {entry.outcome}</p>
                                                <p className="text-xs text-slate-500">At: {formatTime(entry.created_at)}</p>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
                                <h3 className="text-lg font-black text-slate-900 dark:text-white mb-3">Program Enrollments</h3>
                                {detailsLoading ? (
                                    <p className="text-sm text-slate-500">Loading details...</p>
                                ) : programs.length === 0 ? (
                                    <p className="text-sm text-slate-500">No enrollments found or inaccessible for this account.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {programs.map((program) => (
                                            <div key={program.id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 text-sm">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p className="font-semibold text-slate-900 dark:text-white">{program.program_name || `Program #${program.id}`}</p>
                                                    <span className="px-2 py-0.5 rounded-full text-[10px] uppercase font-bold bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
                                                        {program.status}
                                                    </span>
                                                </div>
                                                <p className="text-xs text-slate-500">Started: {formatTime(program.started_at)}</p>
                                                <p className="text-xs text-slate-500">Last grant month: {program.last_grant_month || "N/A"}</p>
                                                {program.next_grant_date && (
                                                    <p className="text-xs text-slate-500">Next grant: {formatTime(program.next_grant_date)} ({program.next_grant_status || "pending"})</p>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
