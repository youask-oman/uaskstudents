"use client";
import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

interface QuotaUser {
    id: number;
    full_name?: string;
    email?: string;
    full_id?: string;
    plan?: string;
    usage_percent?: number;
    daily_tokens_used?: number;
    daily_credit_cap?: number;
    last_active?: string;
    is_banned?: boolean;
    override_token_limit?: number;
    override_ocr_concurrency?: number;
    override_expires_at?: string | null;
    credits_balance?: number;
    credits_used_this_period?: number;
    [key: string]: unknown;
}

interface QuotaData {
    users?: QuotaUser[];
    global_consumption?: number;
    daily_active_holders?: number;
    tokens_burned_24h?: number;
    [key: string]: unknown;
}

export default function AdminQuotasPage() {
    const { pushToast } = useToast();
    const [data, setData] = useState<QuotaData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedUser, setSelectedUser] = useState<QuotaUser | null>(null);
    const [overrideTokens, setOverrideTokens] = useState(1000000);
    const [overrideConcurrency, setOverrideConcurrency] = useState(10);
    const [overrideDuration, setOverrideDuration] = useState<number | null>(24);
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [pageIndex, setPageIndex] = useState(0);
    const pageSize = 15;
    const baseUrl = API_BASE_URL;
    const fallbackUrl = process.env.NEXT_PUBLIC_API_FALLBACK_URL || API_BASE_URL || "http://127.0.0.1:9000";

    const fetchData = useCallback(
        async (signal?: AbortSignal) => {
            setIsLoading(true);
            const token = localStorage.getItem("token");
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

            try {
                const attemptFetch = async (urlBase: string) => {
                    const res = await fetch(`${urlBase}/api/v1/admin/quotas`, { headers, signal });
                    if (!res.ok) {
                        throw new Error("Failed to load quotas.");
                    }
                    return res.json();
                };

                try {
                    const json = await attemptFetch(baseUrl);
                    setData(json as QuotaData);
                } catch (err) {
                    if (baseUrl !== fallbackUrl) {
                        const json = await attemptFetch(fallbackUrl);
                        setData(json as QuotaData);
                    } else {
                        throw err;
                    }
                }
            } catch (err) {
                if ((err as Error).name === "AbortError") {
                    return;
                }
                console.error(err);
                setErrorMessage("Unable to load quotas. Please refresh.");
            } finally {
                setIsLoading(false);
            }
        },
        [baseUrl, fallbackUrl]
    );

    useEffect(() => {
        const controller = new AbortController();
        fetchData(controller.signal);
        return () => controller.abort();
    }, [fetchData]);

    useEffect(() => {
        if (!selectedUser) {
            setOverrideTokens(1000000);
            setOverrideConcurrency(10);
            setOverrideDuration(24);
            return;
        }
        if (selectedUser.override_token_limit) setOverrideTokens(selectedUser.override_token_limit);
        if (selectedUser.override_ocr_concurrency) setOverrideConcurrency(selectedUser.override_ocr_concurrency);
        if (selectedUser.override_expires_at) {
            setOverrideDuration(null);
        }
    }, [selectedUser]);

    useEffect(() => {
        if (!data?.users) return;
        setPageIndex(0);
    }, [data?.users]);

    const totalUsers = data?.users?.length ?? 0;
    const totalPages = Math.max(1, Math.ceil(totalUsers / pageSize));
    const startIndex = pageIndex * pageSize;
    const endIndex = Math.min(totalUsers, startIndex + pageSize);
    const pagedUsers = data?.users?.slice(startIndex, endIndex) ?? [];

    const handleApplyOverride = useCallback(async () => {
        if (!selectedUser) return;
        setIsSaving(true);
        const token = localStorage.getItem("token");
        const headers: HeadersInit = {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/quotas/override`, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    user_id: selectedUser.id,
                    token_limit: overrideTokens,
                    ocr_concurrency: overrideConcurrency,
                    duration_hours: overrideDuration,
                }),
            });
            if (res.ok) {
                pushToast({
                    type: "success",
                    title: "Override applied",
                    message: "User quota override saved.",
                });
                await fetchData();
                setSelectedUser(null);
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Override failed",
                    message: err.message,
                    requestId: err.requestId,
                });
                throw new Error("Failed to apply override.");
            }
        } catch (err) {
            console.error(err);
            setErrorMessage("Failed to apply override.");
        } finally {
            setIsSaving(false);
        }
    }, [baseUrl, fetchData, overrideConcurrency, overrideDuration, overrideTokens, selectedUser, pushToast]);

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
                    <h1 className="text-slate-900 dark:text-white text-4xl font-black leading-tight tracking-tight">Usage & Quotas</h1>
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
                <div className="flex flex-col gap-4 rounded-xl p-6 bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 shadow-xl group hover:border-admin-primary/50 transition-all">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-slate-400 text-sm font-medium">Global API Consumption</p>
                            <p className="text-3xl font-bold mt-1 text-slate-900 dark:text-white">
                                {data?.global_consumption ?? 0}%
                            </p>
                        </div>
                        <div className="p-2 bg-admin-primary/10 rounded-lg text-admin-primary group-hover:scale-110 transition-transform">
                            <span className="material-symbols-outlined">data_usage</span>
                        </div>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                            className="bg-admin-primary h-full transition-all duration-1000"
                            style={{ width: `${data?.global_consumption ?? 0}%` }}
                        ></div>
                    </div>
                    <p className="text-slate-500 text-xs font-medium">Change data not available.</p>
                </div>

                <div className="flex flex-col gap-4 rounded-xl p-6 bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 shadow-xl group hover:border-accent-emerald/50 transition-all">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-slate-400 text-sm font-medium">Daily Active Quota Holders</p>
                            <p className="text-3xl font-bold mt-1 text-slate-900 dark:text-white">
                                {(data?.daily_active_holders ?? 0).toLocaleString()}
                            </p>
                        </div>
                        <div className="p-2 bg-accent-emerald/10 rounded-lg text-accent-emerald group-hover:scale-110 transition-transform">
                            <span className="material-symbols-outlined">group</span>
                        </div>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-accent-emerald h-full" style={{ width: "100%" }}></div>
                    </div>
                    <p className="text-slate-500 text-xs font-medium">Change data not available.</p>
                </div>

                <div className="flex flex-col gap-4 rounded-xl p-6 bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 shadow-xl group hover:border-accent-amber/50 transition-all">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-slate-400 text-sm font-medium">Tokens Burned (24h)</p>
                            <p className="text-3xl font-bold mt-1 text-slate-900 dark:text-white">
                                {data?.tokens_burned_24h ?? 0}
                            </p>
                        </div>
                        <div className="p-2 bg-accent-amber/10 rounded-lg text-accent-amber group-hover:scale-110 transition-transform">
                            <span className="material-symbols-outlined">toll</span>
                        </div>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-accent-amber h-full" style={{ width: "100%" }}></div>
                    </div>
                    <p className="text-slate-500 text-xs font-medium">Change data not available.</p>
                </div>
            </div>

            <div className="flex gap-8 items-start">
                {/* User Table */}
                <div className="flex-1 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-panel-dark shadow-2xl">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-100 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">User</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Legacy Plan</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 w-64">Daily Usage %</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Daily Usage</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Last Active</th>
                                <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {pagedUsers.map((u) => (
                                <tr
                                    key={u.id}
                                    onClick={() => setSelectedUser(u)}
                                    className={`hover:bg-slate-100 dark:hover:bg-slate-800/50 cursor-pointer transition-colors group ${
                                        selectedUser?.id === u.id ? "bg-admin-primary/10 border-l-2 border-admin-primary" : ""
                                    }`}
                                >
                                    <td className="px-6 py-5">
                                        <div className="flex flex-col">
                                            <span className="text-sm font-bold text-slate-900 dark:text-slate-200">{u.full_name}</span>
                                            <span className="text-xs text-slate-500">{u.email}</span>
                                            <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">{u.full_id}</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-5">
                                        <span
                                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                                u.plan === "Pro" ? "bg-admin-primary/10 text-admin-primary" : "bg-slate-800 text-slate-400"
                                            }`}
                                        >
                                            {u.plan}
                                        </span>
                                    </td>
                                    <td className="px-6 py-5">
                                        <div className="flex items-center gap-3">
                                            <div className="flex-1 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full ${u.usage_percent && u.usage_percent > 80 ? "bg-rose-500" : "bg-admin-primary"}`}
                                                    style={{ width: `${u.usage_percent ?? 0}%` }}
                                                ></div>
                                            </div>
                                            <span
                                                className={`text-sm font-bold w-8 text-right ${
                                                    u.usage_percent && u.usage_percent > 80 ? "text-rose-500" : "text-slate-600 dark:text-slate-300"
                                                }`}
                                            >
                                                {u.usage_percent ?? 0}%
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-slate-400 text-xs">
                                        {u.daily_tokens_used?.toLocaleString() ?? 0} tok / {u.daily_credit_cap ? `${u.daily_credit_cap} cr` : "n/a"}
                                    </td>
                                    <td className="px-6 py-5 text-slate-400 text-sm">{u.last_active}</td>
                                    <td className="px-6 py-5 text-right">
                                        <div className="flex items-center justify-end gap-3">
                                            <button
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    window.location.href = `/admin/users/${u.id}`;
                                                }}
                                                className="text-admin-primary font-bold text-xs uppercase tracking-widest hover:underline decoration-2 underline-offset-4"
                                            >
                                                View
                                            </button>
                                            <button className="text-rose-500 font-bold text-xs uppercase tracking-widest hover:underline decoration-2 underline-offset-4">
                                                {u.is_banned ? "Unban" : "Ban"}
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40">
                        <span className="text-xs text-slate-500">
                            {totalUsers === 0 ? "No users to display" : `Showing ${startIndex + 1}-${endIndex} of ${totalUsers}`}
                        </span>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setPageIndex((prev) => Math.max(prev - 1, 0))}
                                disabled={pageIndex === 0}
                                className="px-3 py-1.5 text-xs font-bold rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                            >
                                Prev
                            </button>
                            <span className="text-xs text-slate-500">
                                Page {totalPages === 0 ? 0 : pageIndex + 1} of {totalPages}
                            </span>
                            <button
                                onClick={() => setPageIndex((prev) => Math.min(prev + 1, totalPages - 1))}
                                disabled={pageIndex >= totalPages - 1}
                                className="px-3 py-1.5 text-xs font-bold rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </div>

                {/* Side Override Panel */}
                {selectedUser && (
                    <div className="w-[400px] shrink-0 bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl p-6 flex flex-col gap-6 sticky top-8 animate-in slide-in-from-right duration-300">
                        <div className="flex items-center justify-between">
                            <h3 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">Limit Override</h3>
                            <button onClick={() => setSelectedUser(null)} className="text-slate-500 hover:text-white transition-colors">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>

                        <div className="flex items-center gap-4 bg-slate-50 dark:bg-slate-900/50 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
                            <div className="size-12 rounded-full bg-admin-primary/20 text-admin-primary flex items-center justify-center font-bold text-xl ring-2 ring-admin-primary/20">
                                {(selectedUser.full_name || selectedUser.full_id || "U").slice(0, 1)}
                            </div>
                            <div>
                                <p className="font-bold text-slate-900 dark:text-white text-lg leading-tight">{selectedUser.full_name}</p>
                                <p className="text-xs text-slate-500">{selectedUser.email}</p>
                                <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">
                                    {selectedUser.full_id} · {selectedUser.plan} Legacy Account
                                </p>
                                <p className="text-[10px] text-slate-500 mt-1">
                                    Credits: {selectedUser.credits_balance ?? "n/a"} used {selectedUser.credits_used_this_period ?? "n/a"}
                                </p>
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
                                        onChange={(e) => setOverrideTokens(Number.parseInt(e.target.value, 10))}
                                    />
                                    <span className="text-sm font-medium text-slate-500">Tokens</span>
                                </div>
                            </div>

                            <div className="flex flex-col gap-2">
                                <label className="text-sm font-bold text-slate-300">OCR Job Concurrency</label>
                                <select
                                    className="rounded-lg border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:ring-admin-primary focus:border-admin-primary w-full"
                                    value={overrideConcurrency}
                                    onChange={(e) => setOverrideConcurrency(Number.parseInt(e.target.value, 10))}
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
                                        className={`py-2 text-xs font-bold rounded-lg border-2 transition-all ${
                                            overrideDuration === 24
                                                ? "border-admin-primary bg-admin-primary/10 text-admin-primary"
                                                : "border-slate-800 bg-slate-800/50 text-slate-400"
                                        }`}
                                    >
                                        24 Hours
                                    </button>
                                    <button
                                        onClick={() => setOverrideDuration(null)}
                                        className={`py-2 text-xs font-bold rounded-lg border-2 transition-all ${
                                            overrideDuration === null
                                                ? "border-admin-primary bg-admin-primary/10 text-admin-primary"
                                                : "border-slate-800 bg-slate-800/50 text-slate-400"
                                        }`}
                                    >
                                        Permanent
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="pt-6 border-t border-slate-800 mt-auto flex flex-col gap-3">
                            <button
                                onClick={handleApplyOverride}
                                disabled={isSaving}
                                className="w-full bg-admin-primary text-white py-3 rounded-lg font-bold hover:bg-admin-primary/90 transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-admin-primary/20"
                            >
                                {isSaving ? "Applying..." : "Apply Override"}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
