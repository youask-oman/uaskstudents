"use client";

import { useState, useEffect } from "react";

interface Plan {
    id: number;
    name: string;
    slug: string;
    credits_per_month: number;
    price_monthly_cents: number;
    price_yearly_cents: number;
    seats: number;
    is_active: boolean;
    features: Record<string, unknown>;
    multipliers: Record<string, number>;
    system_prompt_template_id?: number | null;
    schema_prompt_template_id?: number | null;
}

interface PromptAsset {
    id: number;
    key: string;
    kind: string;
    checksum: string | null;
}

interface PlanLinks {
    minimal: {
        system_asset_id?: number | null;
        schema_asset_id?: number | null;
    };
    detailed: {
        system_asset_id?: number | null;
        schema_asset_id?: number | null;
    };
}

export default function AdminSubscriptionsPage() {
    const [plans, setPlans] = useState<Plan[]>([]);
    const [promptAssets, setPromptAssets] = useState<PromptAsset[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
    const [currentLinks, setCurrentLinks] = useState<PlanLinks>({ minimal: {}, detailed: {} });
    const fetchPlansAndPrompts = async () => {
        try {
            const token = localStorage.getItem("token");
            const headers = { Authorization: `Bearer ${token}` };

            const [plansRes, assetsRes] = await Promise.all([
                fetch("http://localhost:8000/api/v1/admin/plans", { headers }),
                fetch("http://localhost:8000/api/v1/admin/prompt-assets", { headers })
            ]);

            if (plansRes.ok) {
                setPlans(await plansRes.json());
            }
            if (assetsRes.ok) {
                setPromptAssets(await assetsRes.json());
            }
        } catch (error) {
            console.error("Failed to fetch data", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchPlanLinks = async (planId: number) => {
        if (!planId) return;
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`http://localhost:8000/api/v1/admin/plans/${planId}/prompt-links`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setCurrentLinks({
                    minimal: {
                        system_asset_id: data.minimal?.system_asset_id || null,
                        schema_asset_id: data.minimal?.schema_asset_id || null
                    },
                    detailed: {
                        system_asset_id: data.detailed?.system_asset_id || null,
                        schema_asset_id: data.detailed?.schema_asset_id || null
                    }
                });
            }
        } catch (error) {
            console.error("Failed to fetch plan links", error);
        }
    };

    useEffect(() => {
        fetchPlansAndPrompts();
    }, []);

    const handleEditClick = async (plan: Plan) => {
        setSelectedPlan(plan);
        // Default empty links
        setCurrentLinks({ minimal: {}, detailed: {} });
        if (plan.id) {
            await fetchPlanLinks(plan.id);
        }
    };

    const handleSavePlan = async (plan: Plan) => {
        const token = localStorage.getItem("token");
        const headers = {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        };

        // 1. Save Plan Details
        await fetch("http://localhost:8000/api/v1/admin/plans", {
            method: "POST",
            headers,
            body: JSON.stringify(plan)
        });

        // 2. Save Prompt Links
        await fetch(`http://localhost:8000/api/v1/admin/plans/${plan.id}/prompt-links`, {
            method: "PUT",
            headers,
            body: JSON.stringify(currentLinks)
        });

        setSelectedPlan(null);
        fetchPlansAndPrompts();
    };

    const systemAssets = promptAssets.filter(a => a.kind === "system");
    const schemaAssets = promptAssets.filter(a => a.kind === "schema");

    return (
        <div className="p-8 max-w-7xl mx-auto w-full">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Subscriptions & Plans</h1>
                    <p className="text-slate-400">Manage pricing tiers, entitlements, and credit multipliers.</p>
                </div>
                <button
                    onClick={() => handleEditClick({
                        id: 0,
                        name: "New Plan",
                        slug: "new-plan",
                        credits_per_month: 100,
                        price_monthly_cents: 999,
                        price_yearly_cents: 9900,
                        seats: 1,
                        is_active: false,
                        features: {},
                        multipliers: { "text_concise": 1, "text_detailed": 1.5 }
                    })}
                    className="bg-admin-primary hover:bg-sky-600 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2"
                >
                    <span className="material-symbols-outlined">add</span>
                    Create Plan
                </button>
            </header>

            {loading ? (
                <div className="text-slate-400">Loading plans...</div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {plans.map(plan => (
                        <div key={plan.id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-6 hover:border-admin-primary/50 transition-colors">
                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900 dark:text-white">{plan.name}</h3>
                                    <p className="text-xs text-slate-500 font-mono uppercase tracking-wider">{plan.slug}</p>
                                </div>
                                <span className={`px-2 py-1 rounded text-xs font-bold ${plan.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-700 text-slate-400"}`}>
                                    {plan.is_active ? "ACTIVE" : "DRAFT"}
                                </span>
                            </div>

                            <div className="space-y-3 mb-6">
                                <div className="flex justify-between py-2 border-b border-slate-200 dark:border-slate-800">
                                    <span className="text-slate-400">Credits / Mo</span>
                                    <span className="text-slate-900 dark:text-white font-mono">{plan.credits_per_month}</span>
                                </div>
                                <div className="flex justify-between py-2 border-b border-slate-200 dark:border-slate-800">
                                    <span className="text-slate-400">Price (USD)</span>
                                    <span className="text-slate-900 dark:text-white font-mono">${(plan.price_monthly_cents / 100).toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between py-2 border-b border-slate-200 dark:border-slate-800">
                                    <span className="text-slate-400">Seats</span>
                                    <span className="text-slate-900 dark:text-white font-mono">{plan.seats}</span>
                                </div>
                            </div>

                            <button
                                onClick={() => handleEditClick(plan)}
                                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
                            >
                                Edit Configuration
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Edit Modal */}
            {selectedPlan && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl">
                        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center sticky top-0 bg-white dark:bg-slate-900 z-10">
                            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Edit Plan: {selectedPlan.name}</h2>
                            <button onClick={() => setSelectedPlan(null)} className="text-slate-400 hover:text-slate-900 dark:text-white">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>

                        <div className="p-6 space-y-8">
                            {/* Basic Details */}
                            <div className="grid grid-cols-2 gap-6">
                                <div className="space-y-4">
                                    <h3 className="text-slate-900 dark:text-white font-bold border-b border-slate-200 dark:border-slate-800 pb-2">Basic Details</h3>
                                    <div className="space-y-2">
                                        <label className="text-xs text-slate-400 uppercase font-bold">Plan Name</label>
                                        <input
                                            type="text"
                                            value={selectedPlan.name}
                                            onChange={(e) => setSelectedPlan({ ...selectedPlan, name: e.target.value })}
                                            className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-slate-900 dark:text-white focus:border-admin-primary outline-none"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs text-slate-400 uppercase font-bold">Slug (ID)</label>
                                        <input
                                            type="text"
                                            value={selectedPlan.slug}
                                            onChange={(e) => setSelectedPlan({ ...selectedPlan, slug: e.target.value })}
                                            className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-slate-900 dark:text-white focus:border-admin-primary outline-none font-mono text-sm"
                                        />
                                    </div>
                                    <div className="flex items-center gap-3 pt-2">
                                        <input
                                            type="checkbox"
                                            id="isActive"
                                            checked={selectedPlan.is_active}
                                            onChange={(e) => setSelectedPlan({ ...selectedPlan, is_active: e.target.checked })}
                                            className="w-5 h-5 rounded border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-admin-primary"
                                        />
                                        <label htmlFor="isActive" className="text-slate-900 dark:text-white font-medium">Active Plan</label>
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <h3 className="text-slate-900 dark:text-white font-bold border-b border-slate-200 dark:border-slate-800 pb-2">Pricing & Entitlements</h3>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-xs text-slate-400 uppercase font-bold">Credits/Mo</label>
                                            <input
                                                type="number"
                                                value={selectedPlan.credits_per_month}
                                                onChange={(e) => setSelectedPlan({ ...selectedPlan, credits_per_month: parseInt(e.target.value) })}
                                                className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-slate-900 dark:text-white focus:border-admin-primary outline-none font-mono"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs text-slate-400 uppercase font-bold">Monthly Price (Cents)</label>
                                            <input
                                                type="number"
                                                value={selectedPlan.price_monthly_cents}
                                                onChange={(e) => setSelectedPlan({ ...selectedPlan, price_monthly_cents: parseInt(e.target.value) })}
                                                className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-slate-900 dark:text-white focus:border-admin-primary outline-none font-mono"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs text-slate-400 uppercase font-bold">Seats</label>
                                            <input
                                                type="number"
                                                value={selectedPlan.seats}
                                                onChange={(e) => setSelectedPlan({ ...selectedPlan, seats: parseInt(e.target.value) })}
                                                className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-slate-900 dark:text-white focus:border-admin-primary outline-none font-mono"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Prompt Routing Section */}
                            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                                <div className="flex justify-between items-center">
                                    <h3 className="text-slate-900 dark:text-white font-bold">Tier-Aware Prompt Routing</h3>
                                    <span className="text-xs text-slate-500">Configure assets for each mode</span>
                                </div>
                                <div className="grid grid-cols-2 gap-8">
                                    {/* Minimal Mode */}
                                    <div className="bg-white dark:bg-slate-950/50 p-4 rounded-lg border border-slate-200 dark:border-slate-800">
                                        <h4 className="text-sm font-bold text-sky-400 mb-4 flex items-center gap-2">
                                            <span className="material-symbols-outlined text-sm">bolt</span>
                                            Minimal Mode (Fast)
                                        </h4>
                                        <div className="space-y-3">
                                            <div className="space-y-1">
                                                <label className="text-xs text-slate-400">System Prompt Asset</label>
                                                <select
                                                    value={currentLinks.minimal.system_asset_id || ""}
                                                    onChange={(e) => setCurrentLinks({
                                                        ...currentLinks,
                                                        minimal: { ...currentLinks.minimal, system_asset_id: e.target.value ? parseInt(e.target.value) : null }
                                                    })}
                                                    className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-2 text-slate-900 dark:text-white text-sm"
                                                >
                                                    <option value="">-- Use Default / Inherit --</option>
                                                    {systemAssets.map(a => (
                                                        <option key={a.id} value={a.id}>{a.key}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-xs text-slate-400">JSON Schema Asset</label>
                                                <select
                                                    value={currentLinks.minimal.schema_asset_id || ""}
                                                    onChange={(e) => setCurrentLinks({
                                                        ...currentLinks,
                                                        minimal: { ...currentLinks.minimal, schema_asset_id: e.target.value ? parseInt(e.target.value) : null }
                                                    })}
                                                    className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-2 text-slate-900 dark:text-white text-sm"
                                                >
                                                    <option value="">-- Use Default / Inherit --</option>
                                                    {schemaAssets.map(a => (
                                                        <option key={a.id} value={a.id}>{a.key}</option>
                                                    ))}
                                                </select>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Detailed Mode */}
                                    <div className="bg-white dark:bg-slate-950/50 p-4 rounded-lg border border-slate-200 dark:border-slate-800">
                                        <h4 className="text-sm font-bold text-violet-400 mb-4 flex items-center gap-2">
                                            <span className="material-symbols-outlined text-sm">psychology</span>
                                            Detailed Mode (Reasoning)
                                        </h4>
                                        <div className="space-y-3">
                                            <div className="space-y-1">
                                                <label className="text-xs text-slate-400">System Prompt Asset</label>
                                                <select
                                                    value={currentLinks.detailed.system_asset_id || ""}
                                                    onChange={(e) => setCurrentLinks({
                                                        ...currentLinks,
                                                        detailed: { ...currentLinks.detailed, system_asset_id: e.target.value ? parseInt(e.target.value) : null }
                                                    })}
                                                    className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-2 text-slate-900 dark:text-white text-sm"
                                                >
                                                    <option value="">-- Use Default / Inherit --</option>
                                                    {systemAssets.map(a => (
                                                        <option key={a.id} value={a.id}>{a.key}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-xs text-slate-400">JSON Schema Asset</label>
                                                <select
                                                    value={currentLinks.detailed.schema_asset_id || ""}
                                                    onChange={(e) => setCurrentLinks({
                                                        ...currentLinks,
                                                        detailed: { ...currentLinks.detailed, schema_asset_id: e.target.value ? parseInt(e.target.value) : null }
                                                    })}
                                                    className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded p-2 text-slate-900 dark:text-white text-sm"
                                                >
                                                    <option value="">-- Use Default / Inherit --</option>
                                                    {schemaAssets.map(a => (
                                                        <option key={a.id} value={a.id}>{a.key}</option>
                                                    ))}
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>


                            {/* Multipliers Section */}
                            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                                <h3 className="text-slate-900 dark:text-white font-bold">Multipliers (Credit Cost)</h3>
                                <div className="grid grid-cols-2 gap-4">
                                    {Object.entries(selectedPlan.multipliers || {}).map(([key, val]) => (
                                        <div key={key} className="flex flex-col gap-1">
                                            <label className="text-xs text-slate-500 font-mono">{key}</label>
                                            <input
                                                type="number"
                                                value={val}
                                                onChange={(e) => {
                                                    const newMultipliers = { ...selectedPlan.multipliers, [key]: parseFloat(e.target.value) };
                                                    setSelectedPlan({ ...selectedPlan, multipliers: newMultipliers });
                                                }}
                                                className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-slate-900 dark:text-white text-sm"
                                            />
                                        </div>
                                    ))}
                                    <div className="col-span-2">
                                        <button
                                            onClick={() => {
                                                const key = prompt("Enter new multiplier key (e.g., 'ocr_add')");
                                                if (key) {
                                                    setSelectedPlan({ ...selectedPlan, multipliers: { ...selectedPlan.multipliers, [key]: 1 } });
                                                }
                                            }}
                                            className="text-admin-primary text-xs font-bold hover:underline"
                                        >
                                            + Add Multiplier
                                        </button>
                                    </div>
                                </div>
                            </div>

                        </div>

                        <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 sticky bottom-0 flex justify-end gap-3 rounded-b-2xl">
                            <button
                                onClick={() => setSelectedPlan(null)}
                                className="px-5 py-2.5 text-slate-400 hover:text-slate-900 dark:text-white font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => handleSavePlan(selectedPlan)}
                                className="px-5 py-2.5 bg-admin-primary hover:bg-sky-600 text-white rounded-lg font-bold shadow-lg shadow-admin-primary/20"
                            >
                                Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
