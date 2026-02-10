
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Subscription = {
    id: number;
    user_id: number;
    plan_name: string;
    status: string;
    current_period_start: string;
    current_period_end: string;
    credits_balance: number;
    credits_used_this_period: number;
    feature_usage: any;
    auto_renew: boolean;
};

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

export default function AdminSubscriptionsPage() {
    const [subs, setSubs] = useState<Subscription[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const router = useRouter();

    const [selectedSub, setSelectedSub] = useState<number | null>(null);
    const [periods, setPeriods] = useState<any[]>([]);
    const [periodsLoading, setPeriodsLoading] = useState(false);

    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [statusFilter, setStatusFilter] = useState("");

    const fetchSubs = async () => {
        setLoading(true);
        setError("");
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                page_size: "25"
            });
            if (statusFilter) params.append("status", statusFilter);

            const data = await fetchAdmin(`/subscriptions?${params.toString()}`);
            setSubs(data.data);
            setTotal(data.total);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchPeriods = async (subId: number) => {
        setSelectedSub(subId);
        setPeriodsLoading(true);
        try {
            const data = await fetchAdmin(`/subscriptions/${subId}/periods`);
            setPeriods(data);
        } catch (err: any) {
            console.error(err);
        } finally {
            setPeriodsLoading(false);
        }
    };

    useEffect(() => {
        fetchSubs();
    }, []);

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-6">
            <header className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Legacy Subscriptions</h1>
                    <p className="text-slate-500 dark:text-slate-400">Phase 3: Monthly Grants & Overage</p>
                </div>
                <div className="flex gap-4">
                    <select
                        className="px-4 py-2 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-sm"
                        value={statusFilter}
                        onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                    >
                        <option value="">All Statuses</option>
                        <option value="active">Active</option>
                        <option value="canceled">Canceled</option>
                        <option value="expired">Expired</option>
                    </select>
                    <button
                        onClick={fetchSubs}
                        className="px-4 py-2 bg-slate-200 dark:bg-slate-700 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors"
                    >
                        Refresh
                    </button>
                </div>
            </header>

            {error && (
                <div className="p-4 bg-red-50 text-red-700 border border-red-200 rounded-lg">
                    {error}
                </div>
            )}

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">ID</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">User ID</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Plan</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Status</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Balance</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Usage (Period)</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Period End</th>
                                <th className="p-4 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                            {loading ? (
                                <tr><td colSpan={8} className="p-8 text-center">Loading...</td></tr>
                            ) : subs.length === 0 ? (
                                <tr><td colSpan={8} className="p-8 text-center text-slate-500">No subscriptions found.</td></tr>
                            ) : (
                                subs.map((sub: any) => (
                                    <tr key={sub.id} className={`hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors ${selectedSub === sub.id ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : ''}`}>
                                        <td className="p-4 font-mono text-sm text-slate-600 dark:text-slate-400">#{sub.id}</td>
                                        <td className="p-4 font-medium text-slate-900 dark:text-white">{sub.user_id}</td>
                                        <td className="p-4">
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                                                {sub.plan_name}
                                            </span>
                                        </td>
                                        <td className="p-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${sub.status === 'active'
                                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-400'
                                                : 'bg-slate-100 text-slate-800'
                                                }`}>
                                                {sub.status}
                                            </span>
                                        </td>
                                        <td className="p-4 font-mono text-slate-700 dark:text-slate-300">
                                            {sub.credits_balance.toFixed(2)}
                                        </td>
                                        <td className="p-4 font-mono text-slate-700 dark:text-slate-300">
                                            {sub.credits_used_this_period?.toFixed(2) || "0.00"}
                                        </td>
                                        <td className="p-4 text-sm text-slate-600 dark:text-slate-400">
                                            {new Date(sub.current_period_end).toLocaleDateString()}
                                        </td>
                                        <td className="p-4">
                                            <button
                                                onClick={() => fetchPeriods(sub.id)}
                                                className="text-sm font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 px-3 py-1 rounded-md hover:bg-indigo-50 dark:hover:bg-indigo-900/20"
                                            >
                                                History
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <p className="text-xs text-slate-500">Showing {subs.length} of {total} records</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Prev</button>
                        <button
                            disabled={subs.length < 25}
                            onClick={() => setPage(p => p + 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Next</button>
                    </div>
                </div>
            </div>

            {selectedSub && (
                <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-6 border border-slate-200 dark:border-slate-700 animate-in fade-in slide-in-from-bottom-2">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                            Subscription History (Sub #{selectedSub})
                        </h2>
                        <button onClick={() => setSelectedSub(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                            ✕
                        </button>
                    </div>
                    {periodsLoading ? (
                        <div className="py-8 text-center text-slate-500">Loading periods...</div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {periods.map((p) => (
                                <div key={p.id} className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm">
                                    <div className="flex justify-between items-start mb-2">
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${p.status === 'OPEN' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                                            {p.status}
                                        </span>
                                        <span className="text-xs text-slate-400">#{p.id}</span>
                                    </div>
                                    <div className="space-y-1">
                                        <div className="text-sm font-medium text-slate-900 dark:text-white">
                                            {new Date(p.period_start).toLocaleDateString()} - {new Date(p.period_end).toLocaleDateString()}
                                        </div>
                                        <div className="text-xs text-slate-500 dark:text-slate-400 flex justify-between">
                                            <span>Grant:</span>
                                            <span className="font-mono">{p.granted_credits} cr</span>
                                        </div>
                                        <div className="text-xs text-slate-500 dark:text-slate-400 flex justify-between">
                                            <span>Lot ID:</span>
                                            <span className="font-mono">#{p.grant_lot_id || 'N/A'}</span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {periods.length === 0 && (
                                <div className="col-span-full py-8 text-center text-slate-500 italic">
                                    No historical periods found for this subscription.
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
