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
    features: Record<string, unknown>;
    multipliers: Record<string, unknown>;
    version?: number;
}

export default function LegacySubscriptionsPage() {
    const { token } = useAuth();
    const [plans, setPlans] = useState<LegacyPlan[]>([]);
    const [drafts, setDrafts] = useState<Record<number, LegacyPlan>>({});
    const [multiplierText, setMultiplierText] = useState<Record<number, string>>({});
    const [savingPlanId, setSavingPlanId] = useState<number | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:9000';

    const fetchPlans = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/plans`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                const rows = Array.isArray(data) ? data as LegacyPlan[] : [];
                setPlans(rows);
                const nextDrafts: Record<number, LegacyPlan> = {};
                rows.forEach((row) => {
                    nextDrafts[row.id] = {
                        ...row,
                        features: row.features || {},
                        multipliers: row.multipliers || {},
                    };
                });
                setDrafts(nextDrafts);
                const nextMultiplierText: Record<number, string> = {};
                rows.forEach((row) => {
                    nextMultiplierText[row.id] = JSON.stringify(row.multipliers || {}, null, 2);
                });
                setMultiplierText(nextMultiplierText);
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

    const onFieldChange = (planId: number, key: keyof LegacyPlan, value: unknown) => {
        setDrafts((prev) => ({
            ...prev,
            [planId]: {
                ...prev[planId],
                [key]: value,
            },
        }));
    };

    const savePlan = async (planId: number) => {
        const draft = drafts[planId];
        if (!draft) return;
        setSaveError(null);
        setSavingPlanId(planId);
        try {
            let parsedMultipliers: Record<string, unknown> = {};
            try {
                parsedMultipliers = JSON.parse(multiplierText[planId] || "{}");
            } catch {
                throw new Error("Invalid multipliers JSON. Fix formatting and retry.");
            }
            const res = await fetch(`${API_BASE}/api/v1/admin/plans/${planId}`, {
                method: 'PUT',
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: draft.name,
                    slug: draft.slug,
                    credits_per_month: Number(draft.credits_per_month || 0),
                    price_monthly_cents: Number(draft.price_monthly_cents || 0),
                    price_yearly_cents: Number(draft.price_yearly_cents || 0),
                    seats: Number(draft.seats || 1),
                    is_active: Boolean(draft.is_active),
                    features: draft.features || {},
                    multipliers: parsedMultipliers,
                }),
            });
            if (!res.ok) {
                const raw = await res.text();
                throw new Error(raw || `Failed to save plan ${planId}`);
            }
            await fetchPlans();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to save plan';
            setSaveError(message);
        } finally {
            setSavingPlanId(null);
        }
    };

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
                        Manage legacy plan rows and pricing multipliers used by solve credit estimation.
                    </p>
                </div>
            </header>
            {saveError && (
                <div className="rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                    {saveError}
                </div>
            )}

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Legacy Plan</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Slug</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Credits/Mo</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Price</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Multipliers (JSON)</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {plans.map((plan) => {
                            const draft = drafts[plan.id] || plan;
                            return (
                            <tr key={plan.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex flex-col gap-1">
                                        <input
                                            className="rounded border border-slate-300 px-2 py-1 text-sm font-bold text-slate-900"
                                            value={draft.name}
                                            onChange={(e) => onFieldChange(plan.id, "name", e.target.value)}
                                        />
                                        <span className="text-[10px] font-mono text-slate-400">#P-{plan.id}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6 font-mono text-[11px] text-slate-500">
                                    <input
                                        className="rounded border border-slate-300 px-2 py-1 text-[11px] font-mono text-slate-700"
                                        value={draft.slug}
                                        onChange={(e) => onFieldChange(plan.id, "slug", e.target.value)}
                                    />
                                </td>
                                <td className="px-8 py-6">
                                    <input
                                        type="number"
                                        className="w-28 rounded border border-slate-300 px-2 py-1 text-sm font-black text-amber-600 italic"
                                        value={draft.credits_per_month}
                                        onChange={(e) => onFieldChange(plan.id, "credits_per_month", Number(e.target.value || 0))}
                                    />
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex flex-col gap-2">
                                        <input
                                            type="number"
                                            className="w-32 rounded border border-slate-300 px-2 py-1 text-sm font-black text-slate-900 italic"
                                            value={draft.price_monthly_cents}
                                            onChange={(e) => onFieldChange(plan.id, "price_monthly_cents", Number(e.target.value || 0))}
                                        />
                                        <span className="text-xs text-slate-500">${(Number(draft.price_monthly_cents || 0) / 100).toFixed(2)} / mo</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <label className="inline-flex items-center gap-2 text-xs font-bold text-slate-700">
                                        <input
                                            type="checkbox"
                                            checked={Boolean(draft.is_active)}
                                            onChange={(e) => onFieldChange(plan.id, "is_active", e.target.checked)}
                                        />
                                        {draft.is_active ? 'ACTIVE' : 'INACTIVE'}
                                    </label>
                                </td>
                                <td className="px-8 py-6">
                                    <textarea
                                        className="min-h-32 w-[480px] rounded border border-slate-300 px-2 py-1 text-[11px] font-mono text-slate-700"
                                        value={multiplierText[plan.id] || ""}
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            setMultiplierText((prev) => ({ ...prev, [plan.id]: value }));
                                            if (saveError) setSaveError(null);
                                        }}
                                    />
                                </td>
                                <td className="px-8 py-6">
                                    <button
                                        className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-black uppercase tracking-widest text-white disabled:opacity-60"
                                        onClick={() => savePlan(plan.id)}
                                        disabled={savingPlanId === plan.id}
                                    >
                                        {savingPlanId === plan.id ? 'Saving...' : 'Save'}
                                    </button>
                                </td>
                            </tr>
                            );
                        })}
                        {plans.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-8 py-20 text-center">
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
