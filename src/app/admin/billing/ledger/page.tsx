'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import { API_BASE_URL, parseApiError } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';

interface LedgerEntry {
    id: number;
    user_id: number;
    user_email: string;
    action_type: string;
    request_id: string | null;
    status: string;
    credits_charged: number | null;
    credits_before: number | null;
    credits_after: number | null;
    tier: string | null;
    created_at: string;
}

export default function LedgerExplorerPage() {
    const { token } = useAuth();
    const { pushToast } = useToast();
    const [entries, setEntries] = useState<LedgerEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [filterUser, setFilterUser] = useState('');

    const formatCredits = (value: number | null | undefined) =>
        typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '0.00';

    const fetchLedger = useCallback(async (userId?: string) => {
        setLoading(true);
        try {
            const url = userId
                ? `${API_BASE_URL}/api/admin/billing/ledger?user_id=${userId}&limit=50`
                : `${API_BASE_URL}/api/admin/billing/ledger?limit=50`;

            const res = await fetch(url, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setEntries(data.items);
                setTotal(data.total);
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Failed to load ledger",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (err) {
            console.error('Failed to load ledger', err);
            pushToast({
                type: "error",
                title: "Failed to load ledger",
                message: err instanceof Error ? err.message : "Unexpected error",
            });
        } finally {
            setLoading(false);
        }
    }, [token, pushToast]);

    useEffect(() => {
        fetchLedger();
    }, [fetchLedger]);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        fetchLedger(filterUser);
    };

    if (loading && entries.length === 0) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-admin-primary/20 rounded-full border-4 border-t-admin-primary animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Scanning Ledger...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-500 border border-indigo-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">database</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Ledger Explorer</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        A real-time, tamper-proof record of every credit transaction in the system. Monitor consumption patterns and investigate discrepancies.
                    </p>
                </div>
                <form onSubmit={handleSearch} className="flex gap-2">
                    <input
                        type="text"
                        placeholder="User ID..."
                        value={filterUser}
                        onChange={(e) => setFilterUser(e.target.value)}
                        className="bg-white/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 text-sm focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                    />
                    <button type="submit" className="px-6 py-3 bg-indigo-500 text-white font-bold rounded-2xl shadow-xl shadow-indigo-500/20">
                        Filter
                    </button>
                    {filterUser && (
                        <button
                            type="button"
                            onClick={() => { setFilterUser(''); fetchLedger(); }}
                            className="px-4 py-3 bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-bold rounded-2xl"
                        >
                            Clear
                        </button>
                    )}
                </form>
            </header>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Transaction</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">User</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Delta</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Balance Trail</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Timestamp</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {entries.map((entry) => (
                            (() => {
                                const creditsCharged = entry.credits_charged ?? 0;
                                return (
                            <tr key={entry.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-tight">{entry.action_type.replace(/_/g, ' ')}</span>
                                        <span className="text-[10px] font-mono text-slate-400">#E-{entry.id}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <Link href={`/admin/users/${entry.user_id}`} className="text-sm font-semibold text-slate-500 hover:text-indigo-500 transition-colors">
                                        {entry.user_email || `User #${entry.user_id}`}
                                    </Link>
                                </td>
                                <td className="px-8 py-6">
                                    <span className={`text-sm font-black italic ${creditsCharged > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                                        {creditsCharged > 0 ? '-' : '+'}{formatCredits(Math.abs(creditsCharged))}
                                    </span>
                                </td>
                <td className="px-8 py-6">
                    <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400">
                        <span>{formatCredits(entry.credits_before)}</span>
                        <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                        <span className="text-slate-900 dark:text-slate-200">{formatCredits(entry.credits_after)}</span>
                    </div>
                </td>
                                <td className="px-8 py-6">
                                    <span className="px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 text-[10px] font-black uppercase tracking-widest border border-slate-200 dark:border-slate-700">
                                        {entry.status}
                                    </span>
                                </td>
                                <td className="px-8 py-6 text-xs font-medium text-slate-500 tabular-nums">
                                    {new Date(entry.created_at).toLocaleString()}
                                </td>
                            </tr>
                                );
                            })()
                        ))}
                    </tbody>
                </table>
            </div>

            <footer className="flex justify-between items-center px-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest italic leading-none">
                    Ledger entries are strictly append-only and immutable. Viewing {entries.length} of {total} records.
                </p>
                <div className="flex gap-2">
                    {/* Pagination */}
                </div>
            </footer>
        </div>
    );
}
