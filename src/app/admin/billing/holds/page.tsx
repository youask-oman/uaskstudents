'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

interface CreditHold {
    id: number;
    user_id: number;
    user_email: string;
    request_id: string;
    reserved_credits: number;
    status: string;
    age_seconds: number;
    created_at: string;
}

interface Stats {
    active_holds: number;
    stuck_holds_1hr: number;
    max_age_seconds: number;
    total_reserved_credits: number;
}

export default function ActiveHoldsPage() {
    const { token } = useAuth();
    const [holds, setHolds] = useState<CreditHold[]>([]);
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);
    const [isSuper, setIsSuper] = useState(false);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchData();
        const storedRole = typeof window !== 'undefined' ? localStorage.getItem('user_role') : '';
        if (storedRole === 'system_admin' || storedRole === 'superadmin') {
            setIsSuper(true);
        }
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [holdsRes, statsRes] = await Promise.all([
                fetch(`${API_BASE}/admin/billing/holds?limit=50`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE}/admin/billing/holds/stats`, {
                    headers: { Authorization: `Bearer ${token}` },
                })
            ]);

            if (holdsRes.ok) {
                const data = await holdsRes.json();
                setHolds(data.items);
            }
            if (statsRes.ok) {
                const data = await statsRes.json();
                setStats(data);
            }
        } catch (e) {
            console.error('Failed to load holds');
        } finally {
            setLoading(false);
        }
    };

    const handleRelease = async (holdId: number) => {
        const reason = prompt('Reason for forced release?');
        if (!reason) return;

        try {
            const res = await fetch(`${API_BASE}/admin/billing/holds/${holdId}/release`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason })
            });
            if (res.ok) {
                fetchData();
                alert('Hold released successfully');
            } else {
                const data = await res.json();
                alert(data.detail || 'Failed to release hold');
            }
        } catch (e) {
            alert('Error releasing hold');
        }
    };

    if (loading && holds.length === 0) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-amber-500/20 rounded-full border-4 border-t-amber-500 animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Inspecting Credit Holds...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500 border border-amber-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">timer</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Active Credit Holds</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Monitor credits that are temporarily reserved for active requests. Holds are typically finalized within seconds, but may occasionally become "stuck" due to worker crashes.
                    </p>
                </div>
                <button
                    onClick={fetchData}
                    className="flex items-center gap-2 px-6 py-3 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-bold rounded-2xl transition-all border border-slate-200 dark:border-slate-800 shadow-lg"
                >
                    <span className="material-symbols-outlined text-[20px]">refresh</span>
                    Refresh
                </button>
            </header>

            {stats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-[2rem] shadow-2xl flex flex-col gap-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Total Active</span>
                        <div className="flex items-end justify-between">
                            <h3 className="text-4xl font-black text-slate-900 dark:text-white">{stats.active_holds}</h3>
                            <span className="material-symbols-outlined text-amber-500 opacity-50">pending</span>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-[2rem] shadow-2xl flex flex-col gap-2">
                        <span className="text-[10px] font-bold text-rose-500 uppercase tracking-widest">Stuck (&gt;1hr)</span>
                        <div className="flex items-end justify-between">
                            <h3 className="text-4xl font-black text-rose-500">{stats.stuck_holds_1hr}</h3>
                            <span className="material-symbols-outlined text-rose-500 opacity-50">warning</span>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-[2rem] shadow-2xl flex flex-col gap-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Reserved Credits</span>
                        <div className="flex items-end justify-between">
                            <h3 className="text-4xl font-black text-slate-900 dark:text-white italic">{stats.total_reserved_credits.toFixed(0)}</h3>
                            <span className="text-xs font-bold text-slate-400 mb-1 uppercase tracking-widest">CR</span>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-[2rem] shadow-2xl flex flex-col gap-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Max Age</span>
                        <div className="flex items-end justify-between">
                            <h3 className="text-4xl font-black text-slate-900 dark:text-white tabular-nums">{(stats.max_age_seconds / 60).toFixed(0)}</h3>
                            <span className="text-xs font-bold text-slate-400 mb-1 uppercase tracking-widest">MIN</span>
                        </div>
                    </div>
                </div>
            )}

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Hold ID</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">User</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Reserved</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Request ID</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Age</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {holds.map((hold) => (
                            <tr key={hold.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <span className="text-xs font-mono font-bold text-slate-900 dark:text-white">#H-{hold.id}</span>
                                </td>
                                <td className="px-8 py-6">
                                    <Link href={`/admin/users/${hold.user_id}`} className="text-sm font-semibold text-slate-500 hover:text-amber-500 transition-colors">
                                        {hold.user_email || `User #${hold.user_id}`}
                                    </Link>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-black text-amber-600 italic">{hold.reserved_credits.toFixed(2)} CR</span>
                                </td>
                                <td className="px-8 py-6 font-mono text-[10px] text-slate-400">
                                    {hold.request_id}
                                </td>
                                <td className="px-8 py-6">
                                    <span className={`px-2 py-0.5 rounded-lg text-[10px] font-black uppercase tracking-widest border transition-colors ${hold.age_seconds > 300
                                        ? 'bg-rose-500/10 text-rose-500 border-rose-500/20 animate-pulse'
                                        : 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'}`}>
                                        {hold.age_seconds < 60 ? `${hold.age_seconds}s` : `${Math.floor(hold.age_seconds / 60)}m`}
                                    </span>
                                </td>
                                <td className="px-8 py-6 text-right">
                                    {isSuper && (
                                        <button
                                            onClick={() => handleRelease(hold.id)}
                                            className="text-[10px] font-black text-rose-500 hover:text-rose-600 uppercase tracking-[0.2em] transition-colors bg-rose-500/5 hover:bg-rose-500/10 px-4 py-2 rounded-xl border border-rose-500/20"
                                        >
                                            Force Release
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {holds.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-8 py-20 text-center">
                                    <div className="flex flex-col items-center gap-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-600">check_circle</span>
                                        <p className="text-slate-400 font-bold uppercase tracking-widest text-[10px]">No active holds found in system</p>
                                    </div>
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
