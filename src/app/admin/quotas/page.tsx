"use client";
import { useEffect, useState } from "react";

export default function AdminQuotasPage() {
    const [data, setData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedUser, setSelectedUser] = useState<any>(null);
    const [overrideTokens, setOverrideTokens] = useState(1000000);
    const [overrideConcurrency, setOverrideConcurrency] = useState(10);
    const [overrideDuration, setOverrideDuration] = useState<number | null>(24);
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const fetchData = async (signal?: AbortSignal) => {
        setIsLoading(true);
        const token = localStorage.getItem("token");
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/quotas`, { headers, signal });
            if (!res.ok) {
                throw new Error("Failed to load quotas.");
            }
            const json = await res.json();
            setData(json);
        } catch (err) {
            if ((err as Error).name === "AbortError") {
                return;
            }
            console.error(err);
            setErrorMessage("Unable to load quotas. Please refresh.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        const controller = new AbortController();
        fetchData(controller.signal);
        return () => controller.abort();
    }, []);

    const handleApplyOverride = async () => {
        if (!selectedUser) return;
        setIsSaving(true);
        const token = localStorage.getItem("token");
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
        const headers: HeadersInit = {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {})
        };
        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/quotas/override`, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    user_id: selectedUser.id,
                    token_limit: overrideTokens,
                    ocr_concurrency: overrideConcurrency,
                    duration_hours: overrideDuration
                })
            });
            if (res.ok) {
                alert("Override applied successfully");
                fetchData();
                setSelectedUser(null);
            } else {
                throw new Error("Failed to apply override.");
            }
        } catch (err) {
            console.error(err);
            setErrorMessage("Failed to apply override.");
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading && !data) {
        return <div className="p-8 text-slate-400">Loading quota details...</div>;
    }

    if (errorMessage && !data) {
        return <div className="p-8 text-rose-400">{errorMessage}</div>;
    }

    return (
        <div className="flex flex-col gap-8 p-8 max-w-[1400px] mx-auto w-full">
            <header className="flex flex-wrap justify-between items-end gap-3 mb-4">
                <div className="flex flex-col gap-2">
                    <h1 className="text-white text-4xl font-black leading-tight tracking-tight">Usage & Quotas</h1>
                    <p className="text-slate-400 text-base font-normal leading-normal">Monitor resource consumption and manage manual overrides.</p>
                </div>
                <div className="flex gap-3">
                    <button className="flex items-center gap-2 bg-slate-800 border border-slate-700 px-4 py-2 rounded-lg text-sm font-semibold text-white hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined text-lg">download</span> Export Report
                    </button>
                    <button className="bg-admin-primary text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-admin-primary/90 transition-colors">
                        Global Quota Update
                    </button>
                </div>
            </header>
            {errorMessage && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs font-bold uppercase tracking-widest text-rose-300">
                    {errorMessage}
                </div>
            )}

            {/* Global Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="flex flex-col gap-4 rounded-xl p-6 bg-panel-dark border border-slate-800 shadow-xl group hover:border-admin-primary/50 transition-all">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-slate-400 text-sm font-medium">Global API Consumption</p>
                            <p className="text-3xl font-bold mt-1 text-white">{data?.global_consumption}%</p>
                        </div>
                        <div className="p-2 bg-admin-primary/10 rounded-lg text-admin-primary group-hover:scale-110 transition-transform">
                            <span className="material-symbols-outlined">data_usage</span>
                        </div>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-admin-primary h-full transition-all duration-1000" style={{ width: `${data?.global_consumption}%` }}></div>
                    </div>
                    <p className="text-accent-emerald text-sm font-medium flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">trending_up</span> +5.2% from last hour
                    </p>
                </div>

                <div className="flex flex-col gap-4 rounded-xl p-6 bg-panel-dark border border-slate-800 shadow-xl group hover:border-accent-emerald/50 transition-all">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-slate-400 text-sm font-medium">Daily Active Quota Holders</p>
                            <p className="text-3xl font-bold mt-1 text-white">{data?.daily_active_holders.toLocaleString()}</p>
                        </div>
                        <div className="p-2 bg-accent-emerald/10 rounded-lg text-accent-emerald group-hover:scale-110 transition-transform">
                            <span className="material-symbols-outlined">group</span>
                        </div>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-accent-emerald h-full" style={{ width: '48%' }}></div>
                    </div>
                    <p className="text-accent-emerald text-sm font-medium flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">trending_up</span> +1.8% vs yesterday
                    </p>
                </div>

                <div className="flex flex-col gap-4 rounded-xl p-6 bg-panel-dark border border-slate-800 shadow-xl group hover:border-accent-amber/50 transition-all">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-slate-400 text-sm font-medium">Tokens Burned (24h)</p>
                            <p className="text-3xl font-bold mt-1 text-white">{data?.tokens_burned_24h}</p>
                        </div>
                        <div className="p-2 bg-accent-amber/10 rounded-lg text-accent-amber group-hover:scale-110 transition-transform">
                            <span className="material-symbols-outlined">toll</span>
                        </div>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-accent-amber h-full" style={{ width: '85%' }}></div>
                    </div>
                    <p className="text-rose-500 text-sm font-medium flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">trending_down</span> -0.4% from peak
                    </p>
                </div>
            </div>

            <div className="flex gap-8 items-start">
                {/* User Table */}
                <div className="flex-1 overflow-hidden rounded-xl border border-slate-800 bg-panel-dark shadow-2xl">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-800/50 border-b border-slate-800">
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">User ID</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Plan</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 w-64">Daily Usage %</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Last Active</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {data?.users.map((u: any) => (
                                <tr key={u.id}
                                    onClick={() => setSelectedUser(u)}
                                    className={`hover:bg-slate-800/50 cursor-pointer transition-colors group ${selectedUser?.id === u.id ? 'bg-admin-primary/10 border-l-2 border-admin-primary' : ''}`}>
                                    <td className="px-6 py-5 font-medium text-slate-200">{u.full_id}</td>
                                    <td className="px-6 py-5">
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${u.plan === 'Pro' ? 'bg-admin-primary/10 text-admin-primary' : 'bg-slate-800 text-slate-400'}`}>
                                            {u.plan}
                                        </span>
                                    </td>
                                    <td className="px-6 py-5">
                                        <div className="flex items-center gap-3">
                                            <div className="flex-1 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                                <div className={`h-full ${u.usage_percent > 80 ? 'bg-rose-500' : 'bg-admin-primary'}`} style={{ width: `${u.usage_percent}%` }}></div>
                                            </div>
                                            <span className={`text-sm font-bold w-8 text-right ${u.usage_percent > 80 ? 'text-rose-500' : 'text-slate-300'}`}>{u.usage_percent}%</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-slate-400 text-sm">{u.last_active}</td>
                                    <td className="px-6 py-5 text-right">
                                        <button className="text-rose-500 font-bold text-xs uppercase tracking-widest hover:underline decoration-2 underline-offset-4">
                                            {u.is_banned ? "Unban" : "Ban"}
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Side Override Panel */}
                {selectedUser && (
                    <div className="w-[400px] shrink-0 bg-panel-dark border border-slate-800 rounded-xl shadow-2xl p-6 flex flex-col gap-6 sticky top-8 animate-in slide-in-from-right duration-300">
                        <div className="flex items-center justify-between">
                            <h3 className="text-xl font-bold text-white tracking-tight">Limit Override</h3>
                            <button onClick={() => setSelectedUser(null)} className="text-slate-500 hover:text-white transition-colors">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>

                        <div className="flex items-center gap-4 bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                            <div className="size-12 rounded-full bg-admin-primary/20 text-admin-primary flex items-center justify-center font-bold text-xl ring-2 ring-admin-primary/20">
                                {selectedUser.full_id[4]}
                            </div>
                            <div>
                                <p className="font-bold text-white text-lg leading-tight">{selectedUser.full_id}</p>
                                <p className="text-xs text-slate-500 uppercase tracking-widest font-bold">{selectedUser.plan} Account</p>
                            </div>
                        </div>

                        <div className="space-y-6">
                            <div className="flex flex-col gap-2">
                                <label className="text-sm font-bold text-slate-300">Daily Token Limit</label>
                                <div className="flex items-center gap-2">
                                    <input
                                        className="flex-1 rounded-lg border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:ring-admin-primary focus:border-admin-primary"
                                        type="number"
                                        value={overrideTokens}
                                        onChange={(e) => setOverrideTokens(parseInt(e.target.value))}
                                    />
                                    <span className="text-sm font-medium text-slate-500">Tokens</span>
                                </div>
                            </div>

                            <div className="flex flex-col gap-2">
                                <label className="text-sm font-bold text-slate-300">OCR Job Concurrency</label>
                                <select
                                    className="rounded-lg border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:ring-admin-primary focus:border-admin-primary w-full"
                                    value={overrideConcurrency}
                                    onChange={(e) => setOverrideConcurrency(parseInt(e.target.value))}
                                >
                                    <option value={5}>Default (5)</option>
                                    <option value={10}>High Priority (10)</option>
                                    <option value={25}>Extreme Override (25)</option>
                                    <option value={100}>Unlimited (100)</option>
                                </select>
                            </div>

                            <div className="flex flex-col gap-3">
                                <label className="text-sm font-bold text-slate-300">Override Duration</label>
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        onClick={() => setOverrideDuration(24)}
                                        className={`py-2 text-xs font-bold rounded-lg border-2 transition-all ${overrideDuration === 24 ? 'border-admin-primary bg-admin-primary/10 text-admin-primary' : 'border-slate-800 bg-slate-800/50 text-slate-400'}`}>
                                        24 Hours
                                    </button>
                                    <button
                                        onClick={() => setOverrideDuration(null)}
                                        className={`py-2 text-xs font-bold rounded-lg border-2 transition-all ${overrideDuration === null ? 'border-admin-primary bg-admin-primary/10 text-admin-primary' : 'border-slate-800 bg-slate-800/50 text-slate-400'}`}>
                                        Permanent
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="pt-6 border-t border-slate-800 mt-auto flex flex-col gap-3">
                            <button
                                onClick={handleApplyOverride}
                                disabled={isSaving}
                                className="w-full bg-admin-primary text-white py-3 rounded-lg font-bold hover:bg-admin-primary/90 transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-admin-primary/20">
                                {isSaving ? "Applying..." : "Apply Override"}
                            </button>
                            <button className="w-full bg-slate-900 text-rose-500 border border-rose-500/20 py-3 rounded-lg font-bold hover:bg-rose-500/10 transition-colors">
                                Reset to Plan Defaults
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
