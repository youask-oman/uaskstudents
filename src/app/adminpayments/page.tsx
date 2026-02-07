"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";

// --- Types ---
type OverviewData = {
    start_date: string;
    days: number;
    metrics: {
        provider_cost_usd: number;
        credits_consumed: number;
        estimated_revenue_usd: number;
        gross_margin_usd: number;
        request_count: number;
        total_tokens: number;
    }
};

type RequestItem = {
    request_id: string;
    created_at: string;
    user_id: number;
    provider: string;
    model: string;
    cost_estimated: number;
    status: string;
};

type PricingItem = {
    provider: string;
    model: string;
    price_in_per_1m: number;
    price_out_per_1m: number;
    effective_from: string;
    effective_to?: string;
};

type StripeEventItem = {
    stripe_event_id: string;
    type: string;
    process_status: string;
    received_at: string;
    last_error?: string;
};

type ReconciliationItem = {
    id: number;
    level: string;
    message: string;
    created_at: string;
};

// --- API Helper ---
async function fetchAdmin(path: string, options: RequestInit = {}) {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }

    const res = await fetch(`/api/admin/payments${path}`, {
        ...options,
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
            ...options.headers
        }
    });

    if (res.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }

    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
}

export default function AdminPaymentsPage() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const tab = searchParams.get("tab") || "overview";

    const [overview, setOverview] = useState<OverviewData | null>(null);
    const [requests, setRequests] = useState<RequestItem[]>([]);
    const [pricing, setPricing] = useState<PricingItem[]>([]);
    const [stripeEvents, setStripeEvents] = useState<StripeEventItem[]>([]);
    const [reconciliation, setReconciliation] = useState<ReconciliationItem[]>([]);

    // Pagination & Filtering
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("");

    const [loading, setLoading] = useState(false);

    useEffect(() => {
        setLoading(true);
        const token = localStorage.getItem("token");
        if (!token) return;

        const pageSize = 25;
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString()
        });
        if (search) params.append("search", search);
        if (statusFilter) params.append("status", statusFilter);

        if (tab === "overview") {
            fetchAdmin("/overview?range_days=30")
                .then(data => setOverview(data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else if (tab === "requests") {
            if (search) params.append("user_id", search); // Special case for requests search by ID
            fetchAdmin(`/requests?${params.toString()}`)
                .then(data => { setRequests(data.data); setTotal(data.total); })
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else if (tab === "pricing") {
            fetchAdmin("/pricing")
                .then(data => setPricing(data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else if (tab === "stripe_events") {
            if (statusFilter) params.delete("status"); // stripe events use status param differently
            if (statusFilter) params.append("status", statusFilter);
            fetchAdmin(`/stripe/events?${params.toString()}`)
                .then(data => { setStripeEvents(data.data); setTotal(data.total); })
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else if (tab === "reconciliation") {
            fetchAdmin("/stripe/reconciliation")
                .then(data => setReconciliation(data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
    }, [tab, page, search, statusFilter]);

    // Reset page on tab change
    useEffect(() => {
        setPage(1);
        setSearch("");
        setStatusFilter("");
    }, [tab]);

    const renderOverview = () => {
        if (!overview) return <div className="p-8">Loading Overview...</div>;
        const m = overview.metrics;
        return (
            <div className="p-8 space-y-8">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Payments & Cost Overview (Last {overview.days} Days)</h2>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <Card title="Est. Provider Cost" value={`$${m.provider_cost_usd}`} sub="Total estimated cost" color="text-red-600" />
                    <Card title="Credits Consumed" value={m.credits_consumed.toFixed(0)} sub="User credit usage" color="text-blue-600" />
                    <Card title="Est. Revenue" value={`$${m.estimated_revenue_usd}`} sub="Based on $1=25Cr" color="text-green-600" />
                    <Card title="Gross Margin" value={`$${m.gross_margin_usd}`} sub="Revenue - Cost" color={m.gross_margin_usd >= 0 ? "text-emerald-600" : "text-red-500"} />
                </div>

                <div className="grid grid-cols-2 gap-6">
                    <div className="bg-white dark:bg-slate-800 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
                        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Volume</h3>
                        <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                            <span>Total Requests</span>
                            <span className="font-mono">{m.request_count}</span>
                        </div>
                        <div className="flex justify-between items-center py-2">
                            <span>Total Tokens Processed</span>
                            <span className="font-mono">{(m.total_tokens / 1000000).toFixed(2)} M</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    const renderPricing = () => (
        <div className="p-8">
            <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-6">Provider Pricing Configuration</h2>
            <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900 rounded-lg text-sm text-blue-700 dark:text-blue-300">
                <strong>Audit Log:</strong> These prices are used to calculate the "Estimated Provider Cost" for audit purposes. Changes here create a new version effective immediately.
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Provider</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Model</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Input ($/1M)</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Output ($/1M)</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Effective From</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {pricing.map((p, i) => (
                            <tr key={i} className={`hover:bg-slate-50 dark:hover:bg-slate-800/50 ${p.effective_to ? 'opacity-50 grayscale' : ''}`}>
                                <td className="px-6 py-3 font-medium text-slate-900 dark:text-white capitalize">{p.provider}</td>
                                <td className="px-6 py-3 font-mono text-xs">{p.model}</td>
                                <td className="px-6 py-3 text-right">${p.price_in_per_1m}</td>
                                <td className="px-6 py-3 text-right">${p.price_out_per_1m}</td>
                                <td className="px-6 py-3 text-slate-500 text-xs">
                                    {new Date(p.effective_from).toLocaleDateString()}
                                    {p.effective_to && <span className="text-red-500 ml-2">(Ended)</span>}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );

    const renderRequests = () => (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Request Cost Explorer</h2>
                <div className="flex gap-4">
                    <input
                        type="text"
                        placeholder="Search User ID..."
                        className="px-4 py-2 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-sm"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                    <select
                        className="px-4 py-2 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-sm"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="">All Statuses</option>
                        <option value="success">Success</option>
                        <option value="error">Error</option>
                    </select>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Time</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Request ID</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Model</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Est. Cost</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {requests.map(r => (
                            <tr key={r.request_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">{r.request_id.substring(0, 8)}...</td>
                                <td className="px-6 py-3">
                                    <span className="inline-flex items-center px-2 py-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium">
                                        {r.provider}/{r.model}
                                    </span>
                                </td>
                                <td className="px-6 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                                    ${r.cost_estimated?.toFixed(5) || "0.00000"}
                                </td>
                                <td className="px-6 py-3">
                                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${r.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                                        }`}>
                                        {r.status}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <p className="text-xs text-slate-500">Showing {requests.length} of {total} records</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Prev</button>
                        <button
                            disabled={requests.length < 25}
                            onClick={() => setPage(p => p + 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Next</button>
                    </div>
                </div>
            </div>
        </div>
    );

    const renderStripeEvents = () => (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Stripe Webhook Events</h2>
                <div className="flex gap-4">
                    <select
                        className="px-4 py-2 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-sm"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="">All Process Statuses</option>
                        <option value="PROCESSED">Processed</option>
                        <option value="FAILED">Failed</option>
                        <option value="RECEIVED">Received</option>
                    </select>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Received At</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Event ID</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Type</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {stripeEvents.map(e => (
                            <tr key={e.stripe_event_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500 whitespace-nowrap">{new Date(e.received_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">{e.stripe_event_id}</td>
                                <td className="px-6 py-3">{e.type}</td>
                                <td className="px-6 py-3">
                                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${e.process_status === 'PROCESSED' ? 'bg-green-100 text-green-700' :
                                        e.process_status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-700'
                                        }`}>
                                        {e.process_status}
                                    </span>
                                    {e.last_error && <p className="text-[10px] text-red-500 mt-1 max-w-xs truncate">{e.last_error}</p>}
                                </td>
                                <td className="px-6 py-3 text-right">
                                    <button
                                        onClick={() => {
                                            if (confirm("Replay this event?")) {
                                                fetchAdmin(`/stripe/events/${e.stripe_event_id}/replay`, { method: "POST" })
                                                    .then(() => window.location.reload())
                                                    .catch(err => alert(err));
                                            }
                                        }}
                                        className="text-emerald-600 hover:text-emerald-700 font-medium text-xs"
                                    >
                                        Replay
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <p className="text-xs text-slate-500">Showing {stripeEvents.length} of {total} records</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Prev</button>
                        <button
                            disabled={stripeEvents.length < 25}
                            onClick={() => setPage(p => p + 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Next</button>
                    </div>
                </div>
            </div>
        </div>
    );

    const renderReconciliation = () => (
        <div className="p-8">
            <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-6">Stripe Reconciliation Mismatches</h2>
            <div className="bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900 rounded-xl p-6 mb-8 text-red-700 dark:text-red-400">
                <div className="flex items-start gap-4">
                    <span className="material-symbols-outlined text-red-500">warning</span>
                    <div>
                        <h4 className="font-bold mb-1">System Alerts</h4>
                        <p className="text-sm opacity-90">The follow items were identified during nightly background checks as having data mismatches between Stripe and our local ledger.</p>
                    </div>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Time</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Level</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Message</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {reconciliation.length === 0 && (
                            <tr><td colSpan={3} className="px-6 py-8 text-center text-slate-400 italic">No reconciliation errors found. System is balanced.</td></tr>
                        )}
                        {reconciliation.map(r => (
                            <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                                <td className="px-6 py-3">
                                    <span className="text-xs font-bold text-red-600 uppercase tracking-tighter">{r.level}</span>
                                </td>
                                <td className="px-6 py-3 text-slate-800 dark:text-slate-200 font-medium">{r.message}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );

    return (
        <div className="min-h-full">
            {loading && <div className="fixed top-0 left-0 w-full h-1 bg-emerald-500 animate-pulse z-50"></div>}
            {tab === "overview" && renderOverview()}
            {tab === "requests" && renderRequests()}
            {tab === "pricing" && renderPricing()}
            {tab === "stripe_events" && renderStripeEvents()}
            {tab === "reconciliation" && renderReconciliation()}
            {tab === "credits" && <div className="p-8">Credits View (Coming Soon)</div>}
        </div>
    );
}

function Card({ title, value, sub, color }: any) {
    return (
        <div className="bg-white dark:bg-slate-800 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{title}</h3>
            <div className={`text-3xl font-bold ${color}`}>{value}</div>
            <p className="text-xs text-slate-400 mt-1">{sub}</p>
        </div>
    );
}
