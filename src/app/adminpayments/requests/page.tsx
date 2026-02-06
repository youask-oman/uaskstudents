
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
    const token = localStorage.getItem("access_token");
    const res = await fetch(`/api/admin/payments${path}`, {
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
        }
    });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
}

export default function RequestsPage() {
    const [requests, setRequests] = useState<RequestItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        fetchAdmin("/requests?page_size=50")
            .then(data => setRequests(data.data))
            .catch(err => console.error(err))
            .finally(() => setLoading(false));
    }, []);

    return (
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
                        {loading && (
                            <tr><td colSpan={5} className="px-6 py-4 text-center">Loading...</td></tr>
                        )}
                        {requests.map(r => (
                            <tr key={r.request_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">{r.request_id}<br /><span className="text-slate-400">User {r.user_id}</span></td>
                                <td className="px-6 py-3">
                                    <span className="inline-flex items-center px-2 py-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium">
                                        {r.provider}/{r.model}
                                    </span>
                                </td>
                                <td className="px-6 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                                    ${(r.cost_estimated || r.cost_stored || 0).toFixed(5)}
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
}
