
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

type RequestItem = {
    request_id: string;
    created_at: string;
    user_id: number;
    provider: string;
    model: string;
    cost_estimated: number;
    status: string;
    cost_stored: number | null;
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

export default function RequestsPage() {
    const [requests, setRequests] = useState<RequestItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedRequest, setSelectedRequest] = useState<string | null>(null);
    const [consumptions, setConsumptions] = useState<any[]>([]);
    const [consLoading, setConsLoading] = useState(false);

    useEffect(() => {
        setLoading(true);
        fetchAdmin("/requests?page_size=50")
            .then(data => setRequests(data.data))
            .catch(err => console.error(err))
            .finally(() => setLoading(false));
    }, []);

    const fetchConsumptions = async (requestId: string) => {
        setSelectedRequest(requestId);
        setConsLoading(true);
        try {
            const data = await fetchAdmin(`/consumption/${requestId}`);
            setConsumptions(data);
        } catch (err) {
            console.error(err);
        } finally {
            setConsLoading(false);
        }
    };

    return (
        <div className="p-8 space-y-6">
            <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Request Cost Explorer</h2>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Time</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Request ID</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Model</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400 text-right">Est. Cost</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {loading && (
                            <tr><td colSpan={6} className="px-6 py-4 text-center">Loading...</td></tr>
                        )}
                        {requests.map(r => (
                            <tr key={r.request_id} className={`hover:bg-slate-50 dark:hover:bg-slate-800/50 ${selectedRequest === r.request_id ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : ''}`}>
                                <td className="px-6 py-3 text-slate-500 text-xs">{new Date(r.created_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">
                                    <span className="truncate block w-32" title={r.request_id}>{r.request_id}</span>
                                    <span className="text-slate-400">User {r.user_id}</span>
                                </td>
                                <td className="px-6 py-3">
                                    <span className="inline-flex items-center px-2 py-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-[10px] font-medium">
                                        {r.provider}/{r.model}
                                    </span>
                                </td>
                                <td className="px-6 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                                    ${(r.cost_estimated || r.cost_stored || 0).toFixed(5)}
                                </td>
                                <td className="px-6 py-3">
                                    <span className={`inline-flex items-center px-2 py-1 rounded text-[10px] font-semibold uppercase ${r.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                                        }`}>
                                        {r.status}
                                    </span>
                                </td>
                                <td className="px-6 py-3">
                                    <button
                                        onClick={() => fetchConsumptions(r.request_id)}
                                        className="text-xs font-bold text-indigo-600 hover:text-indigo-500 uppercase tracking-tight"
                                    >
                                        Consumptions
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {selectedRequest && (
                <div className="bg-slate-900 text-white rounded-xl p-6 shadow-xl animate-in fade-in slide-in-from-bottom-4">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="text-lg font-bold">Credit Allocation Drilldown</h3>
                        <button onClick={() => setSelectedRequest(null)} className="text-slate-400 hover:text-white">✕</button>
                    </div>

                    {consLoading ? (
                        <div className="py-12 text-center text-slate-400 italic">Analyzing consumption records...</div>
                    ) : consumptions.length === 0 ? (
                        <div className="py-12 text-center text-slate-400 italic">No credit consumption records found for this request.</div>
                    ) : (
                        <div className="space-y-4">
                            {consumptions.map((group, idx) => (
                                <div key={idx} className="border border-slate-700 rounded-lg p-4 bg-slate-800/50">
                                    <div className="flex justify-between items-center mb-3 pb-2 border-b border-slate-700">
                                        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Transaction #{group.usage_ledger.id}</span>
                                        <span className="text-sm font-mono text-emerald-400">-{group.usage_ledger.amount} cr</span>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                        {group.lot_allocations.map((alloc: any) => (
                                            <div key={alloc.id} className="bg-slate-900 border border-slate-700 p-3 rounded flex flex-col gap-1">
                                                <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase">
                                                    <span>Lot ID</span>
                                                    <span>Amount</span>
                                                </div>
                                                <div className="flex justify-between items-baseline font-mono">
                                                    <span className="text-slate-300">#{alloc.credit_lot_id}</span>
                                                    <span className="text-indigo-400 text-lg">{alloc.amount}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
