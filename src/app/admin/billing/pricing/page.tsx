'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface PricingEntry {
    provider: string;
    model: string;
    input_cost_1m: number;
    output_cost_1m: number;
    credits_per_usd: number;
}

export default function ProviderPricingPage() {
    const { token } = useAuth();
    const [pricing, setPricing] = useState<PricingEntry[]>([]);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchPricing();
    }, []);

    const fetchPricing = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/payments/config/pricing`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPricing(data.pricing || []);
            }
        } catch (e) {
            console.error('Failed to load pricing');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-admin-primary/20 rounded-full border-4 border-t-admin-primary animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Pricing Config...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500 border border-blue-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">monitoring</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">LLM Model Pricing</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Configure the credit consumption rates for different LLM providers and models. Costs are calculated based on 1M tokens.
                    </p>
                </div>
                <div className="flex gap-4">
                    <button
                        className="flex items-center gap-2 px-6 py-3 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">sync</span>
                        Refresh From Provider
                    </button>
                </div>
            </header>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Provider</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Model Name</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">In / 1M</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Out / 1M</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">CR / $1.00</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] text-right">Edit</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {pricing.map((item, idx) => (
                            <tr key={`${item.provider}-${item.model}-${idx}`} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-3">
                                        <div className="size-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-[10px] font-black text-slate-400 group-hover:text-admin-primary transition-colors border border-slate-200 dark:border-slate-700 uppercase tracking-tighter">
                                            {item.provider.slice(0, 2)}
                                        </div>
                                        <span className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">{item.provider}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-mono text-slate-600 dark:text-slate-400">{item.model}</span>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] font-bold text-slate-400">$</span>
                                        <span className="text-sm font-black text-slate-900 dark:text-white">{item.input_cost_1m.toFixed(2)}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] font-bold text-slate-400">$</span>
                                        <span className="text-sm font-black text-slate-900 dark:text-white">{item.output_cost_1m.toFixed(2)}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-extrabold text-admin-primary tracking-tighter italic">{item.credits_per_usd} CR</span>
                                </td>
                                <td className="px-8 py-6 text-right">
                                    <button className="text-[10px] font-black text-slate-400 hover:text-admin-primary uppercase tracking-[0.2em] transition-colors border border-transparent hover:border-admin-primary/20 px-4 py-2 rounded-xl">
                                        Adjust
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="bg-gradient-to-br from-admin-primary/10 to-blue-500/5 border border-admin-primary/20 p-8 rounded-[2.5rem] space-y-4">
                    <h3 className="text-lg font-black text-slate-900 dark:text-white flex items-center gap-2 italic">
                        <span className="material-symbols-outlined text-admin-primary">info</span>
                        Multiplier Logic
                    </h3>
                    <p className="text-xs font-medium text-slate-500 leading-relaxed">
                        The final credit cost for a request is calculated by converting the USD token cost to credits using the
                        <span className="text-admin-primary font-bold mx-1">credits_per_usd</span>
                        for that specific model. This allows for fine-grained control over margins and platform incentives.
                    </p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 p-8 rounded-[2.5rem] space-y-4">
                    <h3 className="text-lg font-black text-slate-900 dark:text-white flex items-center gap-2 italic">
                        <span className="material-symbols-outlined text-slate-400">history</span>
                        Audit History
                    </h3>
                    <p className="text-xs font-medium text-slate-500 leading-relaxed">
                        All pricing changes are logged with the admin ID and timestamp. You can view the full change history in the
                        <Link href="/admin/billing" className="text-admin-primary hover:underline mx-1">Config History</Link>
                        section.
                    </p>
                </div>
            </div>
        </div>
    );
}

import Link from 'next/link';
