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
    features: {
        allow_research?: boolean;
        allow_verify?: boolean;
        allow_plot?: boolean;
        daily_credit_cap?: number;
        ocr_monthly_cap?: number;
        voice_monthly_cap?: number;
        make_it_right_monthly_cap?: number;
        [key: string]: unknown;
    };
    multipliers: {
        version?: number;
        credits?: {
            solve: {
                free: { text: number; snap_image: number; snap_pdf: number; voice: number };
                short: { text: number; snap_image: number; snap_pdf: number; voice: number };
                standard: { text: number; snap_image: number; snap_pdf: number; voice: number };
                research: { text: number; snap_image: number; snap_pdf: number; voice: number };
            };
            verify: { free: number; short: number; standard: number; research: number };
            plot_trigger: number;
            plot_spec: number;
        };
        // Legacy
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        [key: string]: any;
    };
}

function PricingPreviewPanel({ plans }: { plans: Plan[] }) {
    const [planId, setPlanId] = useState<string>("");
    const [tier, setTier] = useState<string>("standard");
    const [source, setSource] = useState<string>("text");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string>("");
    const [loading, setLoading] = useState(false);

    const handleCheck = async () => {
        setLoading(true);
        setError("");
        setResult(null);
        try {
            const selectedPlan = plans.find(p => p.id.toString() === planId);
            if (!selectedPlan) throw new Error("Select a plan");

            // Client-side mimic of SubscriptionService logic
            const mults = selectedPlan.multipliers?.credits?.solve?.[tier as "free" | "short" | "standard" | "research"];
            if (!mults) throw new Error("Invalid tier configuration");

            let cost = 0;
            if (source === "text") cost = mults.text;
            else if (source === "snap_image") cost = mults.snap_image;
            else if (source === "snap_pdf") cost = mults.snap_pdf;
            else if (source === "voice") cost = mults.voice;

            // Check gates
            let allowed = true;
            let reason = "OK";
            const feats = selectedPlan.features || {};

            if (tier === "research" && !feats.allow_research) { allowed = false; reason = "Tier Not Allowed"; }

            setResult({
                total_credits: cost,
                allowed,
                reason,
                breakdown: { base: cost },
                pricing_version: selectedPlan.multipliers?.version
            });

        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-80 shrink-0 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 sticky top-8">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-admin-primary">calculate</span>
                Pricing Simulator
            </h3>

            <div className="space-y-4">
                <div className="space-y-1">
                    <label className="text-xs font-bold text-slate-400 uppercase">Plan</label>
                    <select className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-2 text-sm"
                        value={planId} onChange={e => setPlanId(e.target.value)}
                    >
                        <option value="">-- Select Plan --</option>
                        {plans.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                </div>

                <div className="space-y-1">
                    <label className="text-xs font-bold text-slate-400 uppercase">Tier</label>
                    <select className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-2 text-sm"
                        value={tier} onChange={e => setTier(e.target.value)}
                    >
                        <option value="free">Free</option>
                        <option value="short">Short</option>
                        <option value="standard">Standard</option>
                        <option value="research">Research</option>
                    </select>
                </div>

                <div className="space-y-1">
                    <label className="text-xs font-bold text-slate-400 uppercase">Input</label>
                    <select className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-2 text-sm"
                        value={source} onChange={e => setSource(e.target.value)}
                    >
                        <option value="text">Text (Typing)</option>
                        <option value="snap_image">Image (Snap)</option>
                        <option value="snap_pdf">PDF (Import)</option>
                        <option value="voice">Voice</option>
                    </select>
                </div>

                <button onClick={handleCheck} disabled={loading || !planId}
                    className="w-full py-2 bg-admin-primary text-white rounded font-bold text-sm shadow hover:bg-sky-600 disabled:opacity-50"
                >
                    Simulate Cost
                </button>

                {result && (
                    <div className={`mt-4 p-3 rounded text-sm ${result.allowed ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-600' : 'bg-red-500/10 border border-red-500/20 text-red-600'}`}>
                        <div className="font-bold flex justify-between">
                            <span>{result.allowed ? "Allowed" : "Blocked"}</span>
                            <span>{result.allowed ? `${result.total_credits} Credits` : ""}</span>
                        </div>
                        {!result.allowed && <div className="text-xs mt-1">{result.reason}</div>}
                        {result.allowed && (
                            <div className="text-xs mt-2 opacity-70 border-t border-emerald-500/20 pt-2">
                                Base: {result.breakdown?.base} <br />
                                Schema v{result.pricing_version}
                            </div>
                        )}
                    </div>
                )}

                {error && <div className="mt-4 text-xs text-red-500 font-bold">{error}</div>}
            </div>
        </div>
    );
}

export default function AdminSubscriptionsPage() {
    const [plans, setPlans] = useState<Plan[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
    const fetchPlans = async () => {
        try {
            const token = localStorage.getItem("token");
            const headers = { Authorization: `Bearer ${token}` };
            const plansRes = await fetch("http://localhost:8000/api/v1/admin/plans", { headers });

            if (plansRes.ok) {
                setPlans(await plansRes.json());
            }
        } catch (error) {
            console.error("Failed to fetch data", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPlans();
    }, []);

    const handleEditClick = (plan: Plan) => {
        setSelectedPlan(plan);
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

        setSelectedPlan(null);
        fetchPlans();
    };

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
                <div className="flex gap-8 items-start">
                    {/* Plans Grid (Left) */}
                    <div className="flex-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6">
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
                                        <span className="text-slate-900 dark:text-white font-mono">{plan.seats || 1}</span>
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

                    {/* Pricing Preview Panel (Right) */}
                    <PricingPreviewPanel plans={plans} />
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

                            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                                <h3 className="text-slate-900 dark:text-white font-bold">Prompt Routing</h3>
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-4 text-sm text-slate-600 dark:text-slate-300">
                                    Plan prompt links were removed. Prompt routing is now managed centrally via Prompt Registry bindings.
                                    Open <a className="text-admin-primary font-semibold hover:underline ml-1" href="/admin/prompt-bindings">/admin/prompt-bindings</a>.
                                </div>
                            </div>


                            {/* Multipliers Section */}
                            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">

                                <h3 className="text-slate-900 dark:text-white font-bold">Multipliers (Credit Cost)</h3>

                                {selectedPlan.multipliers?.version ? (
                                    <div className="space-y-6">
                                        <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded text-xs">
                                            Pricing Schema v{selectedPlan.multipliers.version}
                                        </div>

                                        {/* Solve Credits */}
                                        <div className="space-y-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg">
                                            <h4 className="text-sm font-bold text-slate-700 dark:text-slate-300">Solve Costs by Tier</h4>

                                            {/* Header */}
                                            <div className="grid grid-cols-5 gap-2 text-xs font-mono text-slate-500 mb-1">
                                                <span>Tier</span>
                                                <span>Text</span>
                                                <span>Img</span>
                                                <span>PDF</span>
                                                <span>Voice</span>
                                            </div>

                                            {["free", "short", "standard", "research"].map((t) => {
                                                const tier = t as "free" | "short" | "standard" | "research";
                                                const cost = selectedPlan.multipliers.credits?.solve?.[tier];
                                                if (!cost) return null;

                                                return (
                                                    <div key={tier} className="grid grid-cols-5 gap-2 items-center">
                                                        <span className="text-xs uppercase font-bold text-slate-400">{tier}</span>
                                                        <input type="number" className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-1 text-sm"
                                                            value={cost.text}
                                                            onChange={e => {
                                                                const val = parseInt(e.target.value) || 0;
                                                                const newMults = { ...selectedPlan.multipliers };
                                                                if (newMults.credits?.solve?.[tier]) {
                                                                    newMults.credits.solve[tier].text = val;
                                                                    setSelectedPlan({ ...selectedPlan, multipliers: newMults });
                                                                }
                                                            }}
                                                        />
                                                        <input type="number" className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-1 text-sm"
                                                            value={cost.snap_image}
                                                            onChange={e => {
                                                                const val = parseInt(e.target.value) || 0;
                                                                const newMults = { ...selectedPlan.multipliers };
                                                                if (newMults.credits?.solve?.[tier]) {
                                                                    newMults.credits.solve[tier].snap_image = val;
                                                                    setSelectedPlan({ ...selectedPlan, multipliers: newMults });
                                                                }
                                                            }}
                                                        />
                                                        <input type="number" className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-1 text-sm"
                                                            value={cost.snap_pdf}
                                                            onChange={e => {
                                                                const val = parseInt(e.target.value) || 0;
                                                                const newMults = { ...selectedPlan.multipliers };
                                                                if (newMults.credits?.solve?.[tier]) {
                                                                    newMults.credits.solve[tier].snap_pdf = val;
                                                                    setSelectedPlan({ ...selectedPlan, multipliers: newMults });
                                                                }
                                                            }}
                                                        />
                                                        <input type="number" className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-1 text-sm"
                                                            value={cost.voice}
                                                            onChange={e => {
                                                                const val = parseInt(e.target.value) || 0;
                                                                const newMults = { ...selectedPlan.multipliers };
                                                                if (newMults.credits?.solve?.[tier]) {
                                                                    newMults.credits.solve[tier].voice = val;
                                                                    setSelectedPlan({ ...selectedPlan, multipliers: newMults });
                                                                }
                                                            }}
                                                        />
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {/* Verify Costs */}
                                        <div className="space-y-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg">
                                            <h4 className="text-sm font-bold text-slate-700 dark:text-slate-300">Verify & Plot</h4>
                                            <div className="grid grid-cols-2 gap-4">
                                                {["free", "short", "standard", "research"].map((t) => {
                                                    const tier = t as "free" | "short" | "standard" | "research";
                                                    return (
                                                        <div key={`verify-${tier}`} className="flex justify-between items-center text-sm">
                                                            <span className="text-slate-500 capitalize">Verify {tier}</span>
                                                            <input type="number" className="w-16 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-1"
                                                                value={selectedPlan.multipliers.credits?.verify?.[tier] || 0}
                                                                onChange={e => {
                                                                    const val = parseInt(e.target.value) || 0;
                                                                    const newMults = { ...selectedPlan.multipliers };
                                                                    if (newMults.credits?.verify) {
                                                                        newMults.credits.verify[tier] = val;
                                                                        setSelectedPlan({ ...selectedPlan, multipliers: newMults });
                                                                    }
                                                                }}
                                                            />
                                                        </div>
                                                    );
                                                })}
                                                <div className="flex justify-between items-center text-sm">
                                                    <span className="text-slate-500">Plot Spec</span>
                                                    <input type="number" className="w-16 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-1"
                                                        value={selectedPlan.multipliers.credits?.plot_spec || 0}
                                                        onChange={e => {
                                                            const val = parseInt(e.target.value) || 0;
                                                            const newMults = { ...selectedPlan.multipliers };
                                                            if (newMults.credits) {
                                                                newMults.credits.plot_spec = val;
                                                                setSelectedPlan({ ...selectedPlan, multipliers: newMults });
                                                            }
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    /* Legacy Helper */
                                    <div className="grid grid-cols-2 gap-4">
                                        {Object.entries(selectedPlan.multipliers || {}).map(([key, val]) => (
                                            <div key={key} className="flex flex-col gap-1">
                                                <label className="text-xs text-slate-500 font-mono">{key}</label>
                                                <input
                                                    type="number"
                                                    value={val as number}
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
                                )}
                            </div>

                            {/* Features & Limits */}
                            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                                <h3 className="text-slate-900 dark:text-white font-bold">Features & Limits</h3>
                                <div className="grid grid-cols-2 gap-8">
                                    <div className="space-y-3">
                                        <span className="text-xs uppercase font-bold text-slate-400">Feature Toggles</span>
                                        <div className="space-y-2">
                                            {[
                                                { label: "Allow Research Tier", key: "allow_research" },
                                                { label: "Allow Verification", key: "allow_verify" },
                                                { label: "Allow Plotting", key: "allow_plot" }
                                            ].map(({ label, key }) => (
                                                <label key={key} className="flex items-center gap-2 cursor-pointer">
                                                    <input type="checkbox"
                                                        checked={!!selectedPlan.features?.[key]}
                                                        onChange={e => setSelectedPlan({
                                                            ...selectedPlan,
                                                            features: { ...selectedPlan.features, [key]: e.target.checked }
                                                        })}
                                                        className="rounded border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-admin-primary focus:ring-admin-primary"
                                                    />
                                                    <span className="text-sm text-slate-700 dark:text-slate-300">{label}</span>
                                                </label>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="space-y-3">
                                        <span className="text-xs uppercase font-bold text-slate-400">Usage Caps</span>
                                        <div className="grid grid-cols-2 gap-3">
                                            {[
                                                { label: "Daily Credits", key: "daily_credit_cap" },
                                                { label: "Monthly OCR", key: "ocr_monthly_cap" },
                                                { label: "Monthly Voice", key: "voice_monthly_cap" }
                                            ].map(({ label, key }) => (
                                                <div key={key}>
                                                    <label className="text-xs text-slate-500 mb-1 block">{label}</label>
                                                    <input type="number"
                                                        value={(selectedPlan.features?.[key] as number) || 0}
                                                        onChange={e => setSelectedPlan({
                                                            ...selectedPlan,
                                                            features: { ...selectedPlan.features, [key]: parseInt(e.target.value) || 0 }
                                                        })}
                                                        className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-sm font-mono"
                                                    />
                                                </div>
                                            ))}
                                        </div>
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
