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

// --- API Helper ---
async function fetchAdmin(path: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }

    // Use relative URL to leverage Next.js proxy (avoids CORS)
    const res = await fetch(`/api/admin/payments${path}`, {
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
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
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        setLoading(true);
        const token = localStorage.getItem("token");
        if (!token) {
            // Let layout handle redirect
            return;
        }

        if (tab === "overview") {
            fetchAdmin("/overview?range_days=30")
                .then(data => setOverview(data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else if (tab === "requests") {
            fetchAdmin("/requests?page_size=50")
                .then(data => setRequests(data.data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else if (tab === "pricing") {
            fetchAdmin("/pricing")
                .then(data => setPricing(data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
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

    const renderRequests = () => (
        <div className="p-8">
            <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-6">Request Cost Explorer</h2>
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
            </div>
        </div>
    );

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

    return (
        <div className="min-h-full">
            {loading && <div className="fixed top-0 left-0 w-full h-1 bg-emerald-500 animate-pulse z-50"></div>}
            {tab === "overview" && renderOverview()}
            {tab === "requests" && renderRequests()}
            {tab === "pricing" && renderPricing()}
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
