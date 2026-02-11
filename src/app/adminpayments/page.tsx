"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";
import { useSearchParams } from "next/navigation";

// --- Types ---
type OverviewData = {
    start_date: string;
    days: number;
    metrics: {
        provider_cost_usd: number;
        credits_consumed: number;
        credits_minted: number;
        stripe_revenue_gross_usd: number;
        refunds_total_usd: number;
        successful_payments: number;
        failed_payments: number;
        request_count: number;
        total_tokens: number;
        outstanding_hold_credits: number;
    };
};

type RequestItem = {
    id: number;
    created_at: string;
    user_id: number;
    status: string;
    product_code?: string;
    product_name?: string;
    credits: number;
    price_usd: number;
    currency: string;
    stripe_checkout_session_id?: string | null;
    stripe_payment_intent_id?: string | null;
    credit_lot_id?: number | null;
};

type PricingItem = {
    provider: string;
    model: string;
    price_in_per_1m: number;
    price_out_per_1m: number;
    effective_from: string;
    effective_to?: string;
};

type TopUpPack = {
    id: number;
    code: string;
    name: string;
    credits: number;
    price_usd: number;
    is_active: boolean;
};

type StripePriceMapItem = {
    id: number;
    kind: string;
    internal_code: string;
    stripe_price_id: string;
    currency: string;
    active: boolean;
};

type StripeEventItem = {
    stripe_event_id: string;
    type: string;
    process_status: string;
    received_at: string;
    last_error?: string;
};

type InvoiceItem = {
    id: number;
    invoice_number: string;
    kind: string;
    status: string;
    total_amount: number;
    currency: string;
    created_at: string;
    user_id: number;
};

type ReconciliationReport = {
    missing_payment_rows: string[];
    missing_credit_lots_for_paid_orders: number[];
    duplicate_credit_lots: Array<{ external_ref: string; count: number }>;
    mismatched_pack_amounts: Array<{ topup_order_id: number; order_credits: number; lot_credits: number }>;
    orphan_ledger_events: number[];
    stale_holds: number[];
};

type ApiErrorState = {
    message: string;
    requestId?: string | null;
};

// --- API Helper ---
async function fetchAdmin<T = unknown>(path: string, options: RequestInit = {}): Promise<{ data: T; requestId: string }> {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
        window.location.href = "/login?redirect=" + window.location.pathname;
        throw new Error("Missing token");
    }
    const requestId = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());

    const res = await fetch(`/api/admin/payments${path}`, {
        ...options,
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
            "X-Request-ID": requestId,
            ...options.headers
        }
    });

    if (res.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login?redirect=" + window.location.pathname;
        throw new Error("Unauthorized");
    }

    if (!res.ok) {
        const responseRequestId = res.headers.get("X-Request-ID") || requestId;
        let detail = `API Error: ${res.status}`;
        try {
            const body = await res.json();
            if (body?.detail) detail = body.detail;
        } catch {
            // ignore
        }
        const err = new Error(detail) as Error & { requestId?: string | null };
        err.requestId = responseRequestId;
        throw err;
    }
    const data = (await res.json()) as T;
    return { data, requestId: res.headers.get("X-Request-ID") || requestId };
}

export default function AdminPaymentsPage() {
    const READ_ONLY = false;
    const { pushToast } = useToast();
    const searchParams = useSearchParams();
    const tab = searchParams.get("tab") || "overview";

    const [overview, setOverview] = useState<OverviewData | null>(null);
    const [requests, setRequests] = useState<RequestItem[]>([]);
    const [pricing, setPricing] = useState<PricingItem[]>([]);
    const [packs, setPacks] = useState<TopUpPack[]>([]);
    const [stripeMap, setStripeMap] = useState<StripePriceMapItem[]>([]);
    const [stripeEvents, setStripeEvents] = useState<StripeEventItem[]>([]);
    const [reconciliation, setReconciliation] = useState<ReconciliationReport | null>(null);
    const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
    const [error, setError] = useState<ApiErrorState | null>(null);

    // Pagination & Filtering
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("");

    const [loading, setLoading] = useState(false);

    const viewInvoiceHtml = async (invoiceId: number) => {
        const token = localStorage.getItem("token");
        if (!token) return;

        try {
            const res = await fetch(`/api/admin/payments/invoices/${invoiceId}/html`, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!res.ok) throw new Error("Failed to load invoice");

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            window.open(url, "_blank");
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Invoice load failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

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
            fetchAdmin<OverviewData>("/overview?range_days=30")
                .then(({ data }) => setOverview(data))
                .catch(err => setError({ message: err.message, requestId: err.requestId }))
                .finally(() => setLoading(false));
        } else if (tab === "requests") {
            if (search) params.append("user_id", search); // Special case for requests search by ID
            fetchAdmin<{ total: number; data: RequestItem[] }>(`/requests?${params.toString()}`)
                .then(({ data }) => { setRequests(data.data); setTotal(data.total); })
                .catch(err => setError({ message: err.message, requestId: err.requestId }))
                .finally(() => setLoading(false));
        } else if (tab === "pricing") {
            fetchAdmin<{
                provider_pricing?: { pricing?: PricingItem[] };
                topup_packs?: TopUpPack[];
                stripe_price_map?: StripePriceMapItem[];
            }>("/pricing")
                .then(({ data }) => {
                    const pricing = data?.provider_pricing?.pricing || [];
                    setPricing(Array.isArray(pricing) ? pricing : []);
                    setPacks(Array.isArray(data?.topup_packs) ? data.topup_packs : []);
                    setStripeMap(Array.isArray(data?.stripe_price_map) ? data.stripe_price_map : []);
                })
                .catch(err => setError({ message: err.message, requestId: err.requestId }))
                .finally(() => setLoading(false));
        } else if (tab === "invoices") {
            fetchAdmin<{ total: number; data: InvoiceItem[] }>(`/invoices?${params.toString()}`)
                .then(({ data }) => { setInvoices(data.data); setTotal(data.total); })
                .catch(err => setError({ message: err.message, requestId: err.requestId }))
                .finally(() => setLoading(false));
        } else if (tab === "stripe_events") {
            if (statusFilter) params.delete("status"); // stripe events use status param differently
            if (statusFilter) params.append("status", statusFilter);
            fetchAdmin<{ total: number; data: StripeEventItem[] }>(`/stripe/events?${params.toString()}`)
                .then(({ data }) => { setStripeEvents(data.data); setTotal(data.total); })
                .catch(err => setError({ message: err.message, requestId: err.requestId }))
                .finally(() => setLoading(false));
        } else if (tab === "reconciliation") {
            fetchAdmin<ReconciliationReport>("/reconciliation")
                .then(({ data }) => setReconciliation(data))
                .catch(err => setError({ message: err.message, requestId: err.requestId }))
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
        setError(null);
    }, [tab]);

    const renderOverview = () => {
        if (!overview) return <div className="p-8">Loading Overview...</div>;
        const m = overview.metrics;
        const safeNumber = (value: unknown, fallback = 0) => {
            if (typeof value === "number" && Number.isFinite(value)) return value;
            if (typeof value === "string") {
                const parsed = Number(value);
                if (Number.isFinite(parsed)) return parsed;
            }
            return fallback;
        };
        return (
            <div className="p-8 space-y-8">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Payments & Cost Overview (Last {overview.days} Days)</h2>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <Card title="Stripe Revenue (Gross)" value={`$${safeNumber(m.stripe_revenue_gross_usd).toFixed(2)}`} sub="Captured payments" color="text-emerald-600" />
                    <Card title="Refunds" value={`$${safeNumber(m.refunds_total_usd).toFixed(2)}`} sub="Refunded payments" color="text-orange-600" />
                    <Card title="Credits Minted" value={safeNumber(m.credits_minted).toFixed(0)} sub="Top-up credits" color="text-blue-600" />
                    <Card title="Credits Consumed" value={safeNumber(m.credits_consumed).toFixed(0)} sub="Usage debits" color="text-red-600" />
                </div>

                <div className="grid grid-cols-2 gap-6">
                    <div className="bg-white dark:bg-slate-800 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
                        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Volume</h3>
                        <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                            <span>Total Requests</span>
                            <span className="font-mono">{safeNumber(m.request_count)}</span>
                        </div>
                        <div className="flex justify-between items-center py-2">
                            <span>Total Tokens Processed</span>
                            <span className="font-mono">{(safeNumber(m.total_tokens) / 1000000).toFixed(2)} M</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-t border-slate-100 dark:border-slate-700">
                            <span>Outstanding Holds</span>
                            <span className="font-mono">{safeNumber(m.outstanding_hold_credits).toFixed(2)} cr</span>
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
                <strong>Audit Log:</strong> These prices are used for provider cost estimation and are audited on change.
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
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Payment Requests</h2>
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
                        <option value="CREATED">Created</option>
                        <option value="CHECKOUT_CREATED">Checkout Created</option>
                        <option value="PAID">Paid</option>
                        <option value="FULFILLED">Fulfilled</option>
                        <option value="FAILED">Failed</option>
                    </select>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Time</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Order</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">User</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Amount</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {requests.map(r => (
                            <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">#{r.id}</td>
                                <td className="px-6 py-3 text-xs">User #{r.user_id}</td>
                                <td className="px-6 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                                    ${r.price_usd?.toFixed(2) || "0.00"}
                                </td>
                                <td className="px-6 py-3">
                                    <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-slate-100 text-slate-700">
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

    const renderInvoices = () => (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Invoices & Receipts</h2>
                <div className="flex gap-4">
                    <select
                        className="px-4 py-2 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-sm"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="">All Statuses</option>
                        <option value="PAID">Paid</option>
                        <option value="OPEN">Open</option>
                        <option value="VOID">Void</option>
                        <option value="REFUNDED">Refunded</option>
                    </select>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Date</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Number</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">User</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Kind</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Total</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {invoices.map(inv => (
                            <tr key={inv.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500 whitespace-nowrap">{new Date(inv.created_at).toLocaleDateString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">{inv.invoice_number}</td>
                                <td className="px-6 py-3 text-xs">User #{inv.user_id}</td>
                                <td className="px-6 py-3">
                                    <span className="text-[10px] font-bold uppercase text-slate-400">{inv.kind}</span>
                                </td>
                                <td className="px-6 py-3 font-bold">
                                    {inv.currency} ${inv.total_amount.toFixed(2)}
                                </td>
                                <td className="px-6 py-3">
                                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${inv.status === 'PAID' ? 'bg-green-100 text-green-700' :
                                        inv.status === 'REFUNDED' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-700'
                                        }`}>
                                        {inv.status}
                                    </span>
                                </td>
                                <td className="px-6 py-3 text-right">
                                    <button
                                        onClick={() => viewInvoiceHtml(inv.id)}
                                        className="text-emerald-600 hover:text-emerald-700 font-medium text-xs underline"
                                    >
                                        View HTML
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <p className="text-xs text-slate-500">Showing {invoices.length} of {total} records</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Prev</button>
                        <button
                            disabled={invoices.length < 25}
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
                                    {READ_ONLY ? (
                                        <span className="text-xs text-slate-400 font-semibold">Read-only</span>
                                    ) : (
                                        <button
                                            onClick={() => {
                                                if (confirm("Replay this event?")) {
                                                    fetchAdmin(`/stripe/events/${e.stripe_event_id}/replay`, { method: "POST" })
                                                        .then(() => window.location.reload())
                                                        .catch(err => {
                                                            pushToast({
                                                                type: "error",
                                                                title: "Replay failed",
                                                                message: err instanceof Error ? err.message : String(err),
                                                            });
                                                        });
                                                }
                                            }}
                                            className="text-emerald-600 hover:text-emerald-700 font-medium text-xs"
                                        >
                                            Replay
                                        </button>
                                    )}
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
                        {!reconciliation && (
                            <tr><td colSpan={3} className="px-6 py-8 text-center text-slate-400 italic">No reconciliation data available.</td></tr>
                        )}
                        {reconciliation && (
                            <>
                                <tr>
                                    <td className="px-6 py-3 text-slate-500">Missing payment rows</td>
                                    <td className="px-6 py-3 text-red-600 font-mono">{reconciliation.missing_payment_rows.length}</td>
                                    <td className="px-6 py-3 text-slate-600 text-xs">Stripe PI succeeded with no local Payment row.</td>
                                </tr>
                                <tr>
                                    <td className="px-6 py-3 text-slate-500">Paid orders missing credit lots</td>
                                    <td className="px-6 py-3 text-red-600 font-mono">{reconciliation.missing_credit_lots_for_paid_orders.length}</td>
                                    <td className="px-6 py-3 text-slate-600 text-xs">Top-up order fulfilled but no CreditLot.</td>
                                </tr>
                                <tr>
                                    <td className="px-6 py-3 text-slate-500">Duplicate credit lots</td>
                                    <td className="px-6 py-3 text-red-600 font-mono">{reconciliation.duplicate_credit_lots.length}</td>
                                    <td className="px-6 py-3 text-slate-600 text-xs">Duplicate external_ref values.</td>
                                </tr>
                                <tr>
                                    <td className="px-6 py-3 text-slate-500">Mismatched pack amounts</td>
                                    <td className="px-6 py-3 text-red-600 font-mono">{reconciliation.mismatched_pack_amounts.length}</td>
                                    <td className="px-6 py-3 text-slate-600 text-xs">Credit lot credits ≠ top-up order credits.</td>
                                </tr>
                                <tr>
                                    <td className="px-6 py-3 text-slate-500">Orphan ledger events</td>
                                    <td className="px-6 py-3 text-red-600 font-mono">{reconciliation.orphan_ledger_events.length}</td>
                                    <td className="px-6 py-3 text-slate-600 text-xs">TOPUP ledger missing request ID.</td>
                                </tr>
                                <tr>
                                    <td className="px-6 py-3 text-slate-500">Stale holds</td>
                                    <td className="px-6 py-3 text-red-600 font-mono">{reconciliation.stale_holds.length}</td>
                                    <td className="px-6 py-3 text-slate-600 text-xs">Holds older than 2 hours.</td>
                                </tr>
                            </>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="mt-10">
                <h3 className="text-xl font-bold text-slate-800 dark:text-white mb-4">Credit Packs</h3>
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                            <tr>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Code</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Name</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Credits</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">USD</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Active</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                            {packs.length === 0 && (
                                <tr><td colSpan={5} className="px-6 py-6 text-center text-slate-400">No packs found.</td></tr>
                            )}
                            {packs.map((p) => (
                                <tr key={p.id}>
                                    <td className="px-6 py-3 font-mono text-xs">{p.code}</td>
                                    <td className="px-6 py-3">{p.name}</td>
                                    <td className="px-6 py-3 text-right">{p.credits}</td>
                                    <td className="px-6 py-3 text-right">${p.price_usd.toFixed(2)}</td>
                                    <td className="px-6 py-3">{p.is_active ? "Yes" : "No"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="mt-10">
                <h3 className="text-xl font-bold text-slate-800 dark:text-white mb-4">Stripe Price Map</h3>
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                            <tr>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Kind</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Internal Code</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Stripe Price ID</th>
                                <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Active</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                            {stripeMap.length === 0 && (
                                <tr><td colSpan={4} className="px-6 py-6 text-center text-slate-400">No Stripe mappings found.</td></tr>
                            )}
                            {stripeMap.map((m) => (
                                <tr key={m.id}>
                                    <td className="px-6 py-3">{m.kind}</td>
                                    <td className="px-6 py-3 font-mono text-xs">{m.internal_code}</td>
                                    <td className="px-6 py-3 font-mono text-xs">{m.stripe_price_id}</td>
                                    <td className="px-6 py-3">{m.active ? "Yes" : "No"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );

    return (
        <div className="min-h-full">
            <div className="sr-only">Payments Dashboard</div>
            {loading && <div className="fixed top-0 left-0 w-full h-1 bg-emerald-500 animate-pulse z-50"></div>}
            {error && (
                <div className="mx-8 mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <div className="font-semibold">Request failed</div>
                    <div>{error.message}</div>
                    {error.requestId && <div className="text-xs text-red-500 mt-1">request_id: {error.requestId}</div>}
                </div>
            )}
            {tab === "overview" && renderOverview()}
            {tab === "requests" && renderRequests()}
            {tab === "pricing" && renderPricing()}
            {tab === "invoices" && renderInvoices()}
            {tab === "stripe_events" && renderStripeEvents()}
            {tab === "reconciliation" && renderReconciliation()}
            {tab === "credits" && (
                <div className="p-8">
                    <div className="rounded-xl border border-amber-200 bg-amber-50 text-amber-900 p-4 text-sm">
                        Legacy credits view has been retired. Use the Billing Control Center ledger and wallet views.
                    </div>
                </div>
            )}
        </div>
    );
}

type CardProps = {
    title: string;
    value: string | number;
    sub: string;
    color: string;
};

function Card({ title, value, sub, color }: CardProps) {
    return (
        <div className="bg-white dark:bg-slate-800 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{title}</h3>
            <div className={`text-3xl font-bold ${color}`}>{value}</div>
            <p className="text-xs text-slate-400 mt-1">{sub}</p>
        </div>
    );
}
