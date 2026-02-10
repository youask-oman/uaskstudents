"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

// --- API Helper ---
async function fetchAdmin(path: string, options: RequestInit = {}) {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }

    const res = await fetch(`/api/admin/payments${path}`, {
        ...options,
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
            ...options.headers
        }
    });

    if (res.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login?redirect=" + window.location.pathname;
        return;
    }

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
    }

    return res.json();
}

type Tab = "pricing" | "economics" | "stripe" | "invoice";

export default function AdminPaymentsConfigPage() {
    const READ_ONLY = true;
    const [tab, setTab] = useState<Tab>("pricing");
    const [loading, setLoading] = useState(false);
    const [config, setConfig] = useState<any>(null);
    const [pricing, setPricing] = useState<any[]>([]);
    const [reason, setReason] = useState("");
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const [newPricing, setNewPricing] = useState({
        provider: "openai",
        model: "gpt-5-mini",
        price_in_per_1m: 0.25,
        price_out_per_1m: 2.00,
        price_cached_in_per_1m: 0.025,
        effective_from: ""
    });

    useEffect(() => {
        loadAll();
    }, []);

    const loadAll = async () => {
        setLoading(true);
        try {
            const [cfgData, pricingData] = await Promise.all([
                fetchAdmin("/config"),
                fetchAdmin("/pricing?all_history=true")
            ]);
            setConfig(cfgData.config);
            setPricing(pricingData);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateConfig = async (sectionUpdates: any) => {
        if (READ_ONLY) {
            setError("Legacy payments console is read-only. Use Billing Control Center for credit operations.");
            return;
        }
        if (!reason) {
            setError("Reason is required for all changes");
            return;
        }
        setError("");
        setLoading(true);
        try {
            const updatedConfig = { ...config, ...sectionUpdates };
            await fetchAdmin("/config", {
                method: "PUT",
                body: JSON.stringify({ config: updatedConfig, reason })
            });
            setSuccess("Configuration updated successfully");
            setReason("");
            loadAll();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCreatePricing = async () => {
        if (READ_ONLY) {
            setError("Legacy payments console is read-only. Use Billing Control Center for credit operations.");
            return;
        }
        if (!reason) {
            setError("Reason is required for new pricing version");
            return;
        }
        setError("");
        setLoading(true);
        try {
            // Convert effective_from to local ISO or null
            const payload = {
                pricing: {
                    ...newPricing,
                    effective_from: newPricing.effective_from || null
                },
                reason
            };
            await fetchAdmin("/pricing", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            setSuccess("New pricing version created");
            setReason("");
            loadAll();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleRetirePricing = async (id: number) => {
        if (READ_ONLY) {
            setError("Legacy payments console is read-only. Use Billing Control Center for credit operations.");
            return;
        }
        if (!reason) {
            setError("Reason is required to retire pricing");
            return;
        }
        if (!confirm("Are you sure you want to retire this pricing entry?")) return;

        setError("");
        setLoading(true);
        try {
            await fetchAdmin(`/pricing/${id}`, {
                method: "DELETE",
                body: JSON.stringify({ reason })
            });
            setSuccess("Pricing entry retired");
            setReason("");
            loadAll();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (!config) return <div className="p-8">Loading configuration...</div>;

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">Payments Configuration</h1>
                <p className="text-slate-500 text-sm">Manage pricing, economics, and service integrations.</p>
            </div>

            {error && (
                <div className="mb-6 p-4 bg-red-100 border border-red-200 text-red-700 rounded-lg flex justify-between items-center">
                    <span>{error}</span>
                    <button onClick={() => setError("")} className="text-red-500 font-bold">×</button>
                </div>
            )}

            {success && (
                <div className="mb-6 p-4 bg-green-100 border border-green-200 text-green-700 rounded-lg flex justify-between items-center">
                    <span>{success}</span>
                    <button onClick={() => setSuccess("")} className="text-green-500 font-bold">×</button>
                </div>
            )}

            {READ_ONLY && (
                <div className="mb-6 p-4 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm font-semibold">
                    Legacy payments console is read-only. Use the Billing Control Center for active credit operations.
                </div>
            )}
            {/* Global Reason Box */}
            <div className="mb-8 p-4 bg-white dark:bg-slate-800 border-2 border-primary/20 rounded-xl shadow-sm">
                <label className="block text-xs font-bold text-primary uppercase mb-2 tracking-widest">Global Action Reason (Audit Required)</label>
                <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Describe why you are making these changes..."
                    className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-primary outline-none transition-all"
                    rows={2}
                    disabled={READ_ONLY}
                />
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-8 bg-slate-200 dark:bg-slate-800 p-1 rounded-xl">
                {[
                    { id: "pricing", label: "Model Pricing", icon: "price_change" },
                    { id: "economics", label: "Credit Economics", icon: "currency_exchange" },
                    { id: "stripe", label: "Stripe Setup", icon: "payments" },
                    { id: "invoice", label: "Invoice / Tax", icon: "receipt" }
                ].map(t => (
                    <button
                        key={t.id}
                        onClick={() => setTab(t.id as Tab)}
                        className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-bold transition-all ${tab === t.id
                            ? "bg-white dark:bg-slate-700 text-primary shadow-sm"
                            : "text-slate-500 hover:bg-white/50 dark:hover:bg-slate-700/50"
                            }`}
                    >
                        <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
                        {t.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div className="space-y-8">
                {tab === "pricing" && (
                    <fieldset disabled={READ_ONLY} className={READ_ONLY ? "opacity-60" : ""}>
                        <div className="space-y-6">
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Create Form */}
                            <div className="lg:col-span-1 bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                                <h3 className="text-lg font-bold mb-6">Create New Pricing</h3>
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Provider / Model</label>
                                        <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium">
                                            {newPricing.provider} / {newPricing.model}
                                        </div>
                                    </div>
                                    <div>
                                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Input USD / 1M</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={newPricing.price_in_per_1m}
                                            onChange={(e) => setNewPricing({ ...newPricing, price_in_per_1m: parseFloat(e.target.value) })}
                                            className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-primary outline-none"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Output USD / 1M</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={newPricing.price_out_per_1m}
                                            onChange={(e) => setNewPricing({ ...newPricing, price_out_per_1m: parseFloat(e.target.value) })}
                                            className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-primary outline-none"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Cached Input / 1M</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={newPricing.price_cached_in_per_1m}
                                            onChange={(e) => setNewPricing({ ...newPricing, price_cached_in_per_1m: parseFloat(e.target.value) })}
                                            className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-primary outline-none"
                                        />
                                    </div>
                                    <button
                                        onClick={handleCreatePricing}
                                        disabled={loading}
                                        className="w-full py-3 bg-primary hover:bg-primary-hover text-white rounded-xl font-bold shadow-lg shadow-primary/25 transition-all disabled:opacity-50"
                                    >
                                        Deploy New Pricing
                                    </button>
                                </div>
                            </div>

                            {/* History Table */}
                            <div className="lg:col-span-2 bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                                <h3 className="text-lg font-bold mb-6">Pricing History</h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead>
                                            <tr className="text-left border-b border-slate-200 dark:border-slate-700">
                                                <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase">Status</th>
                                                <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase">Effective Date</th>
                                                <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase text-right">In/Out (1M)</th>
                                                <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase text-right">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                                            {pricing.map(p => {
                                                const isActive = p.status === 'ACTIVE';
                                                return (
                                                    <tr key={p.id}>
                                                        <td className="py-4">
                                                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${isActive ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
                                                                }`}>
                                                                {p.status}
                                                            </span>
                                                        </td>
                                                        <td className="py-4">
                                                            <p className="text-sm font-medium">{new Date(p.effective_from).toLocaleDateString()}</p>
                                                            <p className="text-[10px] text-slate-400">{new Date(p.effective_from).toLocaleTimeString()}</p>
                                                        </td>
                                                        <td className="py-4 text-right">
                                                            <p className="text-sm font-bold text-slate-700 dark:text-slate-200">${p.price_in_per_1m} / ${p.price_out_per_1m}</p>
                                                            <p className="text-[10px] text-slate-400">Cached: ${p.price_cached_in_per_1m || 0}</p>
                                                        </td>
                                                        <td className="py-4 text-right">
                                                            {isActive && (
                                                                <button
                                                                    onClick={() => handleRetirePricing(p.id)}
                                                                    className="text-red-500 hover:underline text-xs"
                                                                >
                                                                    Retire
                                                                </button>
                                                            )}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            </div>
                        </div>
                    </fieldset>
                )}

                {tab === "economics" && (
                    <fieldset disabled={READ_ONLY} className={READ_ONLY ? "opacity-60" : ""}>
                        <div className="bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                        <h3 className="text-xl font-bold mb-8">Credit Economics</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                            <div className="space-y-4">
                                <label className="block text-xs font-bold text-slate-400 uppercase">1 Credit USD Value</label>
                                <div className="flex items-center gap-4">
                                    <input
                                        type="number"
                                        step="0.001"
                                        value={config.credit_value_usd}
                                        onChange={(e) => setConfig({ ...config, credit_value_usd: parseFloat(e.target.value) })}
                                        className="flex-1 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 text-xl font-bold focus:ring-2 focus:ring-primary outline-none"
                                    />
                                    <span className="text-slate-400">USD</span>
                                </div>
                                <p className="text-xs text-slate-400 mt-2">Default: 0.10. Users buying credits get this value. $5.99 = 60 credits.</p>
                            </div>
                            <div className="space-y-4">
                                <label className="block text-xs font-bold text-slate-400 uppercase">Min Charge Credits</label>
                                <input
                                    type="number"
                                    value={config.minimum_charge_credits}
                                    onChange={(e) => setConfig({ ...config, minimum_charge_credits: parseInt(e.target.value) })}
                                    className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 text-xl font-bold focus:ring-2 focus:ring-primary outline-none"
                                />
                                <p className="text-xs text-slate-400 mt-2">Minimum credits deducted per operation regardless of token count.</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div className="p-6 bg-slate-50 dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700">
                                <h4 className="font-bold mb-4 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-primary">fitness_center</span>
                                    Weight Multipliers
                                </h4>
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-medium">Legacy Plan: Standard</span>
                                        <input
                                            type="number"
                                            step="0.1"
                                            value={config.multipliers.STANDARD}
                                            onChange={(e) => setConfig({
                                                ...config,
                                                multipliers: { ...config.multipliers, STANDARD: parseFloat(e.target.value) }
                                            })}
                                            className="w-20 bg-white dark:bg-slate-800 p-2 rounded border text-center"
                                        />
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-medium">Legacy Plan: Research</span>
                                        <input
                                            type="number"
                                            step="0.1"
                                            value={config.multipliers.RESEARCH}
                                            onChange={(e) => setConfig({
                                                ...config,
                                                multipliers: { ...config.multipliers, RESEARCH: parseFloat(e.target.value) }
                                            })}
                                            className="w-20 bg-white dark:bg-slate-800 p-2 rounded border text-center"
                                        />
                                    </div>
                                </div>
                            </div>
                            <div className="p-6 bg-slate-50 dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700">
                                <h4 className="font-bold mb-4 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-primary">calculate</span>
                                    Fixed Credit Fees
                                </h4>
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-medium">OCR Extraction</span>
                                        <input
                                            type="number"
                                            step="1"
                                            value={config.fixed_fees.ocr}
                                            onChange={(e) => setConfig({
                                                ...config,
                                                fixed_fees: { ...config.fixed_fees, ocr: parseInt(e.target.value) }
                                            })}
                                            className="w-20 bg-white dark:bg-slate-800 p-2 rounded border text-center"
                                        />
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-medium">Voice Generation</span>
                                        <input
                                            type="number"
                                            step="1"
                                            value={config.fixed_fees.voice}
                                            onChange={(e) => setConfig({
                                                ...config,
                                                fixed_fees: { ...config.fixed_fees, voice: parseInt(e.target.value) }
                                            })}
                                            className="w-20 bg-white dark:bg-slate-800 p-2 rounded border text-center"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="mt-12 flex justify-end">
                            <button
                                onClick={() => handleUpdateConfig(config)}
                                className="px-8 py-4 bg-primary text-white rounded-xl font-bold shadow-lg shadow-primary/25 hover:bg-primary-hover transition-all"
                            >
                                Save Changes
                            </button>
                        </div>
                        </div>
                    </fieldset>
                )}

                {tab === "stripe" && (
                    <fieldset disabled={READ_ONLY} className={READ_ONLY ? "opacity-60" : ""}>
                        <div className="bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                        <h3 className="text-xl font-bold mb-8">Stripe Integration Status</h3>
                        <div className="flex gap-4 mb-12">
                            <div className="flex-1 p-6 bg-emerald-50 dark:bg-emerald-950/20 rounded-2xl border border-emerald-100 dark:border-emerald-900/50 flex flex-col items-center text-center">
                                <span className="material-symbols-outlined text-emerald-500 text-3xl mb-2">check_circle</span>
                                <h4 className="font-bold text-emerald-900 dark:text-emerald-100">API Key</h4>
                                <p className="text-xs text-emerald-600 dark:text-emerald-400">STRIPE_SECRET_KEY is present in environment.</p>
                            </div>
                            <div className="flex-1 p-6 bg-emerald-50 dark:bg-emerald-950/20 rounded-2xl border border-emerald-100 dark:border-emerald-900/50 flex flex-col items-center text-center">
                                <span className="material-symbols-outlined text-emerald-500 text-3xl mb-2">check_circle</span>
                                <h4 className="font-bold text-emerald-900 dark:text-emerald-100">Webhook Secret</h4>
                                <p className="text-xs text-emerald-600 dark:text-emerald-400">STRIPE_WEBHOOK_SECRET is present in environment.</p>
                            </div>
                        </div>

                        <h3 className="text-xl font-bold mb-6">Price ID Mappings</h3>
                        <p className="text-sm text-slate-500 mb-8">Map internal product/plan codes to Stripe Price IDs (e.g. `price_1P...`).</p>
                        <div className="space-y-4">
                            {["topup-60", "topup-300", "topup-1000", "plan-standard", "plan-research"].map(key => (
                                <div key={key} className="flex items-center gap-4 bg-slate-50 dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
                                    <div className="w-40 font-bold text-xs uppercase tracking-widest text-slate-400">{key}</div>
                                    <input
                                        type="text"
                                        placeholder="price_1P..."
                                        className="flex-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2 text-sm outline-none font-mono"
                                        value={config.stripe_mappings[key] || ""}
                                        onChange={(e) => {
                                            const newMaps = { ...config.stripe_mappings, [key]: e.target.value };
                                            setConfig({ ...config, stripe_mappings: newMaps });
                                        }}
                                    />
                                </div>
                            ))}
                        </div>
                        <div className="mt-12 flex justify-end">
                            <button
                                onClick={() => handleUpdateConfig(config)}
                                className="px-8 py-4 bg-primary text-white rounded-xl font-bold shadow-lg shadow-primary/25 hover:bg-primary-hover transition-all"
                            >
                                Sync Stripe Mappings
                            </button>
                        </div>
                        </div>
                    </fieldset>
                )}

                {tab === "invoice" && (
                    <fieldset disabled={READ_ONLY} className={READ_ONLY ? "opacity-60" : ""}>
                        <div className="bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                        <h3 className="text-xl font-bold mb-8">Invoice & Tax Policy</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                            <div className="space-y-6">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Tax Mode</label>
                                    <select
                                        value={config.tax_defaults.mode}
                                        onChange={(e) => setConfig({
                                            ...config,
                                            tax_defaults: { ...config.tax_defaults, mode: e.target.value }
                                        })}
                                        className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 font-bold outline-none"
                                    >
                                        <option value="NONE">No Tax (Internal Only)</option>
                                        <option value="ESTIMATED">Estimated At Payout</option>
                                        <option value="FINAL">Final (Audit Ready)</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Default Tax Rate (%)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={config.tax_defaults.rate}
                                        onChange={(e) => setConfig({
                                            ...config,
                                            tax_defaults: { ...config.tax_defaults, rate: parseFloat(e.target.value) }
                                        })}
                                        className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 font-bold outline-none"
                                    />
                                </div>
                            </div>
                            <div className="space-y-6">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Company Name (for Invoice)</label>
                                    <input
                                        type="text"
                                        value={config.invoice_settings.company_name}
                                        onChange={(e) => setConfig({
                                            ...config,
                                            invoice_settings: { ...config.invoice_settings, company_name: e.target.value }
                                        })}
                                        className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 font-medium outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Company Address</label>
                                    <textarea
                                        value={config.invoice_settings.company_address}
                                        onChange={(e) => setConfig({
                                            ...config,
                                            invoice_settings: { ...config.invoice_settings, company_address: e.target.value }
                                        })}
                                        className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 font-medium outline-none"
                                        rows={3}
                                    />
                                </div>
                            </div>
                        </div>
                        <div className="mt-12 flex justify-end">
                            <button
                                onClick={() => handleUpdateConfig(config)}
                                className="px-8 py-4 bg-primary text-white rounded-xl font-bold shadow-lg shadow-primary/25 hover:bg-primary-hover transition-all"
                            >
                                Save Tax & Branding
                            </button>
                        </div>
                        </div>
                    </fieldset>
                )}
            </div>
        </div>
    );
}
