"use client";

import { useEffect, useState } from "react";

type TopUpRow = {
    id: number;
    created_at: string;
    user_id: number;
    user_email?: string | null;
    status: string;
    credits: number;
    price_usd: number;
    currency: string;
    product_code?: string | null;
    product_name?: string | null;
    stripe_payment_intent_id?: string | null;
    stripe_checkout_session_id?: string | null;
    credit_lot_id?: number | null;
    ledger_id?: number | null;
};

type TopUpDetail = {
    topup: TopUpRow;
    payment: Record<string, unknown> | null;
    credit_lot: Record<string, unknown> | null;
};

type ApiErrorState = { message: string; requestId?: string | null };

async function fetchAdmin(path: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }
    const requestId = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());

    const res = await fetch(`/api/admin/payments${path}`, {
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
            "X-Request-ID": requestId,
        }
    });

    if (res.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }

    if (!res.ok) {
        const responseRequestId = res.headers.get("X-Request-ID") || requestId;
        let detail = `API Error: ${res.status}`;
        try {
            const body = await res.json();
            if (body?.detail) detail = body.detail;
        } catch {}
        const err = new Error(detail) as Error & { requestId?: string | null };
        err.requestId = responseRequestId;
        throw err;
    }
    const data = await res.json();
    return { data, requestId: res.headers.get("X-Request-ID") || requestId };
}

export default function TopUpsPage() {
    const [rows, setRows] = useState<TopUpRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [search, setSearch] = useState("");
    const [error, setError] = useState<ApiErrorState | null>(null);
    const [detail, setDetail] = useState<TopUpDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    useEffect(() => {
        setLoading(true);
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: "25"
        });
        if (search) params.append("search", search);

        fetchAdmin(`/topups?${params.toString()}`)
            .then(({ data }) => {
                setRows(data.data);
                setTotal(data.total);
            })
            .catch(err => setError({ message: err.message, requestId: err.requestId }))
            .finally(() => setLoading(false));
    }, [page, search]);

    const openDetail = async (id: number) => {
        setDetailLoading(true);
        try {
            const res = await fetchAdmin(`/topups/${id}`);
            setDetail(res.data as TopUpDetail);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Request failed";
            const requestId = err instanceof Error && "requestId" in err ? (err as { requestId?: string | null }).requestId : null;
            setError({ message, requestId });
        } finally {
            setDetailLoading(false);
        }
    };

    return (
        <div className="p-8 space-y-6">
            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <div className="font-semibold">Request failed</div>
                    <div>{error.message}</div>
                    {error.requestId && <div className="text-xs text-red-500 mt-1">request_id: {error.requestId}</div>}
                </div>
            )}

            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Top-Up History</h2>
                <div className="flex gap-4">
                    <input
                        type="text"
                        placeholder="Search Stripe ref..."
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
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Order</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">User</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Credits</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Amount</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Status</th>
                            <th className="px-6 py-3 font-semibold text-slate-600 dark:text-slate-400">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {loading && (
                            <tr><td colSpan={7} className="px-6 py-4 text-center">Loading...</td></tr>
                        )}
                        {!loading && rows.length === 0 && (
                            <tr><td colSpan={7} className="px-6 py-4 text-center">No top-ups found.</td></tr>
                        )}
                        {rows.map(row => (
                            <tr key={row.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="px-6 py-3 text-slate-500">{new Date(row.created_at).toLocaleString()}</td>
                                <td className="px-6 py-3 font-mono text-xs">#{row.id}</td>
                                <td className="px-6 py-3 text-xs">{row.user_email || `User #${row.user_id}`}</td>
                                <td className="px-6 py-3 font-medium">{row.credits}</td>
                                <td className="px-6 py-3 text-emerald-600 font-medium">${row.price_usd?.toFixed(2)}</td>
                                <td className="px-6 py-3">
                                    <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-slate-100 text-slate-700">
                                        {row.status}
                                    </span>
                                </td>
                                <td className="px-6 py-3">
                                    <button
                                        onClick={() => openDetail(row.id)}
                                        className="text-xs font-semibold text-emerald-600 hover:text-emerald-700"
                                    >
                                        View
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <p className="text-xs text-slate-500">Showing {rows.length} of {total} records</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Prev</button>
                        <button
                            disabled={rows.length < 25}
                            onClick={() => setPage(p => p + 1)}
                            className="px-3 py-1 rounded border border-slate-200 text-xs font-medium disabled:opacity-50"
                        >Next</button>
                    </div>
                </div>
            </div>

            {detail && (
                <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-lg font-bold">Top-Up Detail #{detail.topup.id}</h3>
                        <button onClick={() => setDetail(null)} className="text-slate-400 hover:text-slate-600">Close</button>
                    </div>
                    {detailLoading ? (
                        <div className="py-8 text-center text-slate-500">Loading detail...</div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <div>
                                <div className="text-xs uppercase text-slate-400">Stripe Payment Intent</div>
                                <div className="font-mono">{detail.topup.stripe_payment_intent_id || "-"}</div>
                            </div>
                            <div>
                                <div className="text-xs uppercase text-slate-400">Credit Lot</div>
                                <div className="font-mono">{detail.topup.credit_lot_id || "-"}</div>
                            </div>
                            <div>
                                <div className="text-xs uppercase text-slate-400">Ledger ID</div>
                                <div className="font-mono">{detail.topup.ledger_id || "-"}</div>
                            </div>
                            <div>
                                <div className="text-xs uppercase text-slate-400">Status</div>
                                <div>{detail.topup.status}</div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
