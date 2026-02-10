'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

interface PricingEntry {
    id: number;
    provider: string;
    model: string;
    price_in_per_1m: number;
    price_out_per_1m: number;
    price_cached_in_per_1m?: number;
    status: string;
    effective_from: string;
}

export default function ProviderPricingPage() {
    const { token } = useAuth();
    const [pricing, setPricing] = useState<PricingEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [showInactive, setShowInactive] = useState(false);

    // Modal
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [formData, setFormData] = useState({
        provider: 'openai',
        model: 'gpt-5-mini',
        price_in_per_1m: 0.15,
        price_out_per_1m: 0.60,
        price_cached_in_per_1m: 0.0,
        effective_from: '',
        reason: ''
    });

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchPricing();
    }, [showInactive]);

    const fetchPricing = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/pricing?show_inactive_gpt5=${showInactive}`, {
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

    const handleOpenCreate = () => {
        setFormData({
            provider: 'openai',
            model: 'gpt-5-mini',
            price_in_per_1m: 0.15,
            price_out_per_1m: 0.60,
            price_cached_in_per_1m: 0.0,
            effective_from: '',
            reason: ''
        });
        setIsModalOpen(true);
    };

    const handleAdjust = (entry: PricingEntry) => {
        // Pre-fill for "Update" which is actually creating a new version
        setFormData({
            provider: entry.provider,
            model: entry.model,
            price_in_per_1m: entry.price_in_per_1m,
            price_out_per_1m: entry.price_out_per_1m,
            price_cached_in_per_1m: entry.price_cached_in_per_1m ?? 0,
            effective_from: '', // Default to now
            reason: ''
        });
        setIsModalOpen(true);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const payload = {
                provider: formData.provider,
                model: formData.model,
                price_in_per_1m: formData.price_in_per_1m,
                price_out_per_1m: formData.price_out_per_1m,
                price_cached_in_per_1m: formData.price_cached_in_per_1m,
                effective_from: formData.effective_from || null
            };

            const res = await fetch(`${API_BASE}/api/admin/billing/pricing`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    pricing: payload,
                    reason: formData.reason
                })
            });

            if (res.ok) {
                setIsModalOpen(false);
                fetchPricing();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (error) {
            console.error(error);
            alert('Failed to save pricing');
        }
    };

    const handleRetire = async (id: number) => {
        const reason = prompt("Enter reason for retiring this price:");
        if (!reason) return;

        try {
            const res = await fetch(`${API_BASE}/api/admin/payments/config/pricing/${id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({ reason })
            });

            if (res.ok) {
                fetchPricing();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (error) {
            console.error(error);
        }
    };

    if (loading && pricing.length === 0) {
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
                    <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                        <button
                            onClick={() => setShowInactive(false)}
                            className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${!showInactive ? 'bg-white dark:bg-slate-700 shadow text-slate-900 dark:text-white' : 'text-slate-500'}`}
                        >
                            Active Only
                        </button>
                        <button
                            onClick={() => setShowInactive(true)}
                            className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${showInactive ? 'bg-white dark:bg-slate-700 shadow text-slate-900 dark:text-white' : 'text-slate-500'}`}
                        >
                            Show All
                        </button>
                    </div>
                    <button
                        onClick={handleOpenCreate}
                        className="flex items-center gap-2 px-6 py-3 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        New Pricing
                    </button>
                </div>
            </header>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Provider</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Model Name</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">In / 1M</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Out / 1M</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Cached / 1M</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] text-right">Actions</th>
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
                                    <span
                                        className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border transition-colors ${item.status === 'ACTIVE'
                                            ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                            : 'bg-slate-500/10 text-slate-500 border-slate-500/20'
                                            }`}
                                    >
                                        {item.status}
                                    </span>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] font-bold text-slate-400">$</span>
                                        <span className="text-sm font-black text-slate-900 dark:text-white">{item.price_in_per_1m.toFixed(2)}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] font-bold text-slate-400">$</span>
                                        <span className="text-sm font-black text-slate-900 dark:text-white">{item.price_out_per_1m.toFixed(2)}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-extrabold text-admin-primary tracking-tighter italic">{(item.price_cached_in_per_1m ?? 0).toFixed(2)}</span>
                                </td>
                                <td className="px-8 py-6 text-right">
                                    <div className="flex justify-end gap-2">
                                        <button
                                            onClick={() => handleAdjust(item)}
                                            className="text-[10px] font-black text-slate-400 hover:text-admin-primary uppercase tracking-[0.2em] transition-colors border border-transparent hover:border-admin-primary/20 px-4 py-2 rounded-xl"
                                        >
                                            Adjust
                                        </button>
                                        {item.status === 'ACTIVE' && (
                                            <button
                                                onClick={() => handleRetire(item.id)}
                                                className="p-2 hover:bg-red-100 dark:hover:bg-red-900/20 rounded-lg text-red-500 transition-colors"
                                                title="Retire Pricing"
                                            >
                                                <span className="material-symbols-outlined text-[18px]">block</span>
                                            </button>
                                        )}
                                    </div>
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
                        The final cost uses provider pricing for input/output tokens (per 1M) and applies the active credit economics config.
                        Adjusting these rows changes the USD basis used by billing settlement for this model family.
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

            {/* Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                    <div className="bg-white dark:bg-[#111827] w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden border border-slate-200 dark:border-slate-800">
                        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
                            <h3 className="text-xl font-bold">Configure Pricing</h3>
                            <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Provider</label>
                                    <select
                                        required
                                        value={formData.provider}
                                        onChange={e => setFormData({ ...formData, provider: e.target.value })}
                                        className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none text-sm"
                                    >
                                        <option value="openai">OpenAI</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Model Family</label>
                                    <select
                                        required
                                        value={formData.model}
                                        onChange={e => setFormData({ ...formData, model: e.target.value })}
                                        className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none text-sm font-mono"
                                    >
                                        <option value="gpt-5-mini">gpt-5-mini</option>
                                        <option value="gpt-5">gpt-5</option>
                                        <option value="gpt-5-nano">gpt-5-nano</option>
                                    </select>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Input $/1M</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        required
                                        value={formData.price_in_per_1m}
                                        onChange={e => setFormData({ ...formData, price_in_per_1m: parseFloat(e.target.value) })}
                                        className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Output $/1M</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        required
                                        value={formData.price_out_per_1m}
                                        onChange={e => setFormData({ ...formData, price_out_per_1m: parseFloat(e.target.value) })}
                                        className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Cached Input $/1M</label>
                                <input
                                    type="number"
                                    value={formData.price_cached_in_per_1m}
                                    onChange={e => setFormData({ ...formData, price_cached_in_per_1m: parseFloat(e.target.value) })}
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                />
                                <p className="text-[10px] text-slate-400 mt-1">Optional cached-input pricing (if supported by provider).</p>
                            </div>

                            <div>
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Effective From (Optional)</label>
                                <input
                                    type="datetime-local"
                                    value={formData.effective_from}
                                    onChange={e => setFormData({ ...formData, effective_from: e.target.value })}
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                />
                                <p className="text-[10px] text-slate-400 mt-1">Leave blank to start immediately.</p>
                            </div>

                            <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Reason (Audit Log)</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.reason}
                                    onChange={e => setFormData({ ...formData, reason: e.target.value })}
                                    className="w-full p-3 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-900/30 rounded-lg focus:ring-2 focus:ring-yellow-500 outline-none text-sm"
                                    placeholder="Why are you changing this price?"
                                />
                            </div>

                            <div className="flex justify-end gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setIsModalOpen(false)}
                                    className="px-4 py-2 text-slate-500 font-bold hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-6 py-2 bg-admin-primary text-white font-bold rounded-lg shadow-lg hover:bg-blue-600 transition-all"
                                >
                                    Save Pricing
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
