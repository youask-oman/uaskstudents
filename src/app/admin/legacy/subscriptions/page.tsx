'use client';

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface LegacyPlan {
    id: number;
    name: string;
    slug: string;
    credits_per_month: number;
    price_monthly_cents: number;
    price_yearly_cents: number;
    seats: number;
    is_active: boolean;
}

export default function LegacySubscriptionsPage() {
    const { token } = useAuth();
    const [plans, setPlans] = useState<LegacyPlan[]>([]);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    const fetchPlans = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/plans`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPlans(Array.isArray(data) ? data : []);
            }
        } catch (err) {
            console.error('Failed to load legacy subscriptions', err);
        } finally {
            setLoading(false);
        }
    }, [API_BASE, token]);

    useEffect(() => {
        fetchPlans();
    }, [fetchPlans]);

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-amber-500/20 rounded-full border-4 border-t-amber-500 animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Legacy Subscriptions...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-8">
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[10px] font-black uppercase tracking-[0.3em] text-amber-600">
                Legacy - Do Not Use
            </div>

            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500 border border-amber-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">card_membership</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Legacy Subscriptions</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Read-only view of the deprecated subscription plans. These records are maintained for historical reference only.
                    </p>
                </div>
            </header>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Legacy Plan</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Slug</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Credits/Mo</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Price</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {plans.map((plan) => (
                            <tr key={plan.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white">{plan.name}</span>
                                        <span className="text-[10px] font-mono text-slate-400">#P-{plan.id}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6 font-mono text-[11px] text-slate-500">{plan.slug}</td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-black text-amber-600 italic">{plan.credits_per_month}</span>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-black text-slate-900 dark:text-white italic">
                                        ${(plan.price_monthly_cents / 100).toFixed(2)} / mo
                                    </span>
                                </td>
                                <td className="px-8 py-6">
                                    <span className={`px-2 py-0.5 rounded-lg text-[10px] font-black uppercase tracking-widest border ${plan.is_active
                                        ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                        : 'bg-slate-500/10 text-slate-500 border-slate-500/20'
                                        }`}>
                                        {plan.is_active ? 'ACTIVE' : 'INACTIVE'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                        {plans.length === 0 && (
                            <tr>
                                <td colSpan={5} className="px-8 py-20 text-center">
                                    <div className="flex flex-col items-center gap-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-600">inventory_2</span>
                                        <p className="text-slate-400 font-bold uppercase tracking-widest text-[10px]">No legacy plans found</p>
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
