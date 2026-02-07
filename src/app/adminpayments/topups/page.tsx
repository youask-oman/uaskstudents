
"use client";

import { useEffect, useState } from "react";

type TopUpProduct = {
    id: number;
    code: string;
    name: string;
    credits: number;
    price_usd: number;
};

type CreditLot = {
    id: number;
    user_id: number;
    user_email: string;
    credits_total: number;
    credits_remaining: number;
    status: string;
    purchased_at: string;
    amount_paid: number;
    currency: string;
    external_ref: string;
    source: string;
    lot_type: string;
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

export default function TopUpsPage() {
    const [lots, setLots] = useState<CreditLot[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [search, setSearch] = useState("");

    useEffect(() => {
        setLoading(true);
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: "25"
        });
        if (search) params.append("search", search);

        fetchAdmin(`/topups?${params.toString()}`)
            .then(data => {
                setLots(data.data);
                setTotal(data.total);
            })
            .catch(err => console.error(err))
            .finally(() => setLoading(false));
    }, [page, search]);

    return (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Top-Up History</h2>
                <div className="flex gap-4">
                    <input
                        type="text"
                        placeholder="Search Ref or Amount..."
                        className="px-4 py-2 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-sm"
                        value={search}
                        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                    />
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Date</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">User ID</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">User Email</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Credits</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Amount</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Ref</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {loading && (
                            <tr><td colSpan={7} className="px-6 py-4 text-center">Loading...</td></tr>
                        )}
                        {!loading && lots.length === 0 && (
                            <tr><td colSpan={7} className="px-6 py-4 text-center">No top-ups found.</td></tr>
                        )}
                        {lots.map(lot => (
                            <tr key={lot.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500">{new Date(lot.purchased_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">{lot.user_id}</td>
                                <td className="px-6 py-3 text-xs">{lot.user_email}</td>
                                <td className="px-6 py-3 font-medium">
                                    {lot.credits_remaining} / {lot.credits_total}
                                </td>
                                <td className="px-6 py-3 text-emerald-600 font-medium">
                                    {lot.amount_paid ? `$${lot.amount_paid}` : '-'}
                                </td>
                                <td className="px-6 py-3">
                                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium 
                                        ${lot.status === 'ACTIVE' ? 'bg-green-100 text-green-700' :
                                            lot.status === 'DEPLETED' ? 'bg-slate-100 text-slate-600' : 'bg-red-100 text-red-700'}`}>
                                        {lot.status}
                                    </span>
                                </td>
                                <td className="px-6 py-3 font-mono text-xs text-slate-400">
                                    {lot.external_ref || '-'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <p className="text-xs text-slate-500">Showing {lots.length} of {total} records</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Prev</button>
                        <button
                            disabled={lots.length < 25}
                            onClick={() => setPage(p => p + 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Next</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
