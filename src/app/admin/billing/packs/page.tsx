'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface TopupProduct {
    id: number;
    name: string;
    description: string | null;
    credits_amount: number;
    price_cents: number;
    currency: string;
    is_active: string;
}

export default function CreditPacksPage() {
    const { token } = useAuth();
    const [packs, setPacks] = useState<TopupProduct[]>([]);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchPacks();
    }, []);

    const fetchPacks = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/v1/topups/products`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPacks(data.products || []);
            }
        } catch (e) {
            console.error('Failed to load credit packs');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-admin-primary/20 rounded-full border-4 border-t-admin-primary animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Credit Packs...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500 border border-emerald-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">database</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Credit Packs</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Manage top-up products available for users to purchase. These credits typically don't expire and are used after monthly allowances.
                    </p>
                </div>
                <div className="flex gap-4">
                    <button
                        className="flex items-center gap-2 px-6 py-3 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        Create Pack
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {packs.map((pack) => (
                    <div key={pack.id} className="relative group perspective">
                        <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-8 rounded-[2.5rem] shadow-2xl transition-all duration-500 group-hover:-translate-y-2 group-hover:rotate-1 ring-1 ring-slate-200/50 group-hover:ring-admin-primary/30 flex flex-col gap-6 overflow-hidden">
                            {/* Decorative Background */}
                            <div className="absolute top-0 right-0 size-32 bg-admin-primary/5 rounded-full -mr-16 -mt-16 blur-3xl group-hover:bg-admin-primary/10 transition-colors"></div>

                            <div className="flex justify-between items-start">
                                <div className="space-y-1">
                                    <h3 className="text-xl font-black text-slate-900 dark:text-white tracking-tight">{pack.name}</h3>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">{pack.is_active === '1' ? 'Active Product' : 'Draft'}</p>
                                </div>
                                <div className="px-3 py-1 bg-emerald-500/10 text-emerald-500 text-[10px] font-black uppercase tracking-widest rounded-lg border border-emerald-500/20">
                                    TOPUP
                                </div>
                            </div>

                            <div className="flex items-baseline gap-2">
                                <span className="text-5xl font-black text-admin-primary tracking-tighter">{(pack.credits_amount / 1000).toFixed(0)}K</span>
                                <span className="text-lg font-bold text-slate-400 uppercase tracking-widest italic">Credits</span>
                            </div>

                            <p className="text-sm font-medium text-slate-500 leading-relaxed min-h-[3rem]">
                                {pack.description || 'Standalone credit pack for high-volume usage.'}
                            </p>

                            <div className="pt-6 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
                                <div className="flex flex-col">
                                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Price</span>
                                    <span className="text-2xl font-black text-slate-900 dark:text-white tracking-tight italic">
                                        {(pack.price_cents / 100).toFixed(2)} <span className="text-xs uppercase ml-1 opacity-50">{pack.currency}</span>
                                    </span>
                                </div>
                                <div className="flex gap-2">
                                    <button className="size-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-400 hover:text-admin-primary transition-colors border border-slate-200 dark:border-slate-700">
                                        <span className="material-symbols-outlined text-[20px]">edit</span>
                                    </button>
                                    <button className="size-10 rounded-xl bg-rose-500/10 flex items-center justify-center text-rose-500 border border-rose-500/20 hover:bg-rose-500 hover:text-white transition-all">
                                        <span className="material-symbols-outlined text-[20px]">delete</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}

                {packs.length === 0 && (
                    <div className="lg:col-span-3 py-20 bg-slate-50/50 dark:bg-slate-900/50 border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-[3rem] flex flex-col items-center justify-center gap-6">
                        <div className="size-20 rounded-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-slate-400">
                            <span className="material-symbols-outlined text-4xl">inventory</span>
                        </div>
                        <div className="text-center space-y-2">
                            <p className="text-lg font-bold text-slate-700 dark:text-slate-300">No active packs</p>
                            <p className="text-sm text-slate-500 max-w-xs px-6">Create your first credit top-up product to allow users to purchase manual increments.</p>
                        </div>
                        <button className="px-8 py-3 bg-admin-primary text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/20">
                            Create First Pack
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
