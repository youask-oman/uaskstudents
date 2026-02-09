'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface LegacyPlan {
    id: number;
    name: string;
    slug: string;
    price_monthly_cents: number;
    credits_per_month: number;
    scans_per_month: number;
    is_active: boolean;
}

export default function LegacyPlansPage() {
    const { token } = useAuth();
    const [plans, setPlans] = useState<LegacyPlan[]>([]);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchPlans();
    }, []);

    const fetchPlans = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/config/plans`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPlans(data.plans || []);
            }
        } catch (e) {
            console.error('Failed to load legacy plans');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-slate-200 rounded-full border-4 border-t-slate-400 animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Legacy Data...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-slate-500/10 flex items-center justify-center text-slate-500 border border-slate-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">history</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Legacy Plans <span className="text-slate-400 text-lg not-italic font-medium ml-2 opacity-50">(Read Only)</span></h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Reference view for the old subscription-based plan table. These records are preserved for backward compatibility and migration reconciliation only.
                    </p>
                </div>
                <div className="flex gap-4">
                    <div className="px-6 py-3 bg-amber-500/10 border border-amber-500/20 rounded-2xl flex items-center gap-3">
                        <span className="material-symbols-outlined text-amber-500 text-[20px]">warning</span>
                        <span className="text-[10px] font-black text-amber-600 uppercase tracking-widest leading-none">Immutability Protocol Active</span>
                    </div>
                </div>
            </header>

            <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden relative">
                {/* Watermark */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03] rotate-[-12deg] select-none text-[120px] font-black uppercase text-slate-900 dark:text-white whitespace-nowrap">
                    Legacy Reference
                </div>

                <table className="w-full text-left border-collapse relative z-10">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Plan Name</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Slug</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">USD / Mo</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Quota (Q/S)</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {plans.map((plan) => (
                            <tr key={plan.id} className="group transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-4">
                                        <div className="size-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 border border-slate-200 dark:border-slate-700">
                                            <span className="material-symbols-outlined text-[20px]">inventory_2</span>
                                        </div>
                                        <div className="flex flex-col gap-0.5">
                                            <span className="text-sm font-bold text-slate-900 dark:text-white">{plan.name}</span>
                                            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">ID: #{plan.id}</span>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-8 py-6 font-mono text-[11px] text-slate-500">{plan.slug}</td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-black text-slate-900 dark:text-white tracking-tight italic">
                                        ${(plan.price_monthly_cents / 100).toFixed(2)}
                                    </span>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-2">
                                        <div className="px-2 py-0.5 bg-blue-500/10 text-blue-500 text-[10px] font-bold rounded uppercase tracking-tighter border border-blue-500/20">{plan.credits_per_month}Q</div>
                                        <div className="px-2 py-0.5 bg-purple-500/10 text-purple-500 text-[10px] font-bold rounded uppercase tracking-tighter border border-purple-500/20">{plan.scans_per_month}S</div>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <span
                                        className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${plan.is_active
                                            ? 'bg-slate-500/10 text-slate-500 border-slate-500/20'
                                            : 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                                            }`}
                                    >
                                        {plan.is_active ? 'RETAINED' : 'DEPRECATED'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="p-8 bg-blue-500/5 border border-blue-500/10 rounded-[2.5rem]">
                <div className="flex gap-6 items-start">
                    <div className="p-4 bg-admin-primary/10 text-admin-primary rounded-2xl">
                        <span className="material-symbols-outlined text-3xl">lightbulb</span>
                    </div>
                    <div className="space-y-2">
                        <h4 className="text-lg font-black text-slate-900 dark:text-white tracking-tight italic uppercase">Reconciliation Strategy</h4>
                        <p className="text-sm font-medium text-slate-500 max-w-3xl leading-relaxed">
                            These legacy plans are mapped to the new <span className="text-admin-primary font-bold">Credit Programs</span> based on usage patterns. Any active user on a legacy plan should be migrated to the equivalent Credit Program to ensure continued service and correct billing reconciliation.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
