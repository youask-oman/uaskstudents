"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type SystemConfigEntry = {
    key: string;
    value: string;
    description?: string | null;
};

type TokenPolicySnapshot = {
    text?: {
        input_max?: number;
        input_max_chars?: number;
        output_max?: {
            minimal?: { solve?: number; study?: number };
            detailed?: { solve?: number; study?: number };
        };
        output_retry_cap?: {
            detailed?: {
                solve?: number;
                study?: number;
            };
        };
    };
    request?: {
        system_and_schema_budget?: number;
        expected_output_budget?: number;
    };
    ocr_v5?: {
        output_max?: number;
    };
    ocr_image?: {
        extract_max?: number;
        input_max?: number;
        input_overhead?: number;
    };
    ocr_pdf?: {
        extract_max?: number;
        input_max?: number;
        input_overhead?: number;
    };
    voice?: {
        input_max?: number;
        input_overhead?: number;
    };
};

const DEFAULT_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";

export default function SystemConfigPanel({
    baseUrl = DEFAULT_BASE_URL,
    className = ""
}: {
    baseUrl?: string;
    className?: string;
}) {
    const [systemConfig, setSystemConfig] = useState<SystemConfigEntry[]>([]);
    const [configDraft, setConfigDraft] = useState<Record<string, string>>({});
    const [tokenPolicy, setTokenPolicy] = useState<TokenPolicySnapshot | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

    const sortedConfig = useMemo(
        () => [...systemConfig].sort((a, b) => a.key.localeCompare(b.key)),
        [systemConfig]
    );

    const tokenPolicyHighlights = useMemo(
        () => [
            { label: "Text input max", value: tokenPolicy?.text?.input_max },
            { label: "Minimal solve output max", value: tokenPolicy?.text?.output_max?.minimal?.solve },
            { label: "Detailed solve output max", value: tokenPolicy?.text?.output_max?.detailed?.solve },
            { label: "System + schema budget", value: tokenPolicy?.request?.system_and_schema_budget },
            { label: "Expected output budget", value: tokenPolicy?.request?.expected_output_budget },
            { label: "Voice input max", value: tokenPolicy?.voice?.input_max }
        ],
        [tokenPolicy]
    );

    const loadSettings = useCallback(
        async (signal?: AbortSignal) => {
            setIsLoading(true);
            setLoadError(null);
            try {
                const token = localStorage.getItem("token");
                const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
                const [policyRes, configRes] = await Promise.all([
                    fetch(`${baseUrl}/api/v1/config/token-policy`, { headers, signal }),
                    fetch(`${baseUrl}/api/v1/admin/system-config`, { headers, signal })
                ]);

                if (!policyRes.ok || !configRes.ok) {
                    throw new Error("Unable to load system configuration.");
                }

                const policyBody = await policyRes.json();
                const configBody = await configRes.json();
                setTokenPolicy(policyBody.policy ?? null);
                const entries = Array.isArray(configBody) ? configBody : [];
                setSystemConfig(entries);
                const draft: Record<string, string> = {};
                entries.forEach((entry) => {
                    draft[entry.key] = entry.value;
                });
                setConfigDraft(draft);
            } catch (err) {
                if ((err as Error).name !== "AbortError") {
                    setLoadError((err as Error).message ?? "Unable to load system settings.");
                }
            } finally {
                setIsLoading(false);
            }
        },
        [baseUrl]
    );

    useEffect(() => {
        const controller = new AbortController();
        loadSettings(controller.signal);
        return () => controller.abort();
    }, [loadSettings]);

    const handleFieldChange = (key: string, value: string) => {
        setConfigDraft((prev) => ({ ...prev, [key]: value }));
        setSaveError(null);
        setSaveSuccess(null);
    };

    const handleSave = async () => {
        if (systemConfig.length === 0) return;
        setIsSaving(true);
        setSaveError(null);
        setSaveSuccess(null);
        try {
            const token = localStorage.getItem("token");
            const headers: HeadersInit = {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {})
            };
            const payload = {
                entries: systemConfig.map((entry) => ({
                    key: entry.key,
                    value: configDraft[entry.key] ?? entry.value,
                    description: entry.description
                }))
            };

            const response = await fetch(`${baseUrl}/api/v1/admin/system-config`, {
                method: "POST",
                headers,
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error("Failed to save system configuration.");
            }

            await loadSettings();
            setSaveSuccess("System settings saved.");
        } catch (err) {
            setSaveError((err as Error).message ?? "Unable to save settings.");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <section className={`bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl ${className}`}>
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                    <h4 className="text-base font-bold text-slate-900 dark:text-white">System Configuration</h4>
                    <p className="text-sm text-slate-400 max-w-2xl">Token limits and other flags stored in SystemConfig.</p>
                </div>
                <button
                    className="px-4 py-2 text-sm font-semibold rounded-full bg-admin-primary text-white disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                    onClick={handleSave}
                    disabled={isSaving || isLoading || systemConfig.length === 0}
                >
                    {isSaving ? "Saving..." : "Save settings"}
                </button>
            </div>
            <div className="p-6 space-y-6">
                {loadError && <p className="text-sm text-rose-500">{loadError}</p>}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {tokenPolicyHighlights.map((item) => (
                        <div key={item.label} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-white/5 p-4">
                            <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">{item.label}</p>
                            <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">{item.value ?? "â€”"}</p>
                        </div>
                    ))}
                </div>
                {isLoading ? (
                    <p className="text-sm text-slate-400">Loading configuration entries...</p>
                ) : sortedConfig.length === 0 ? (
                    <p className="text-sm text-slate-400">No configuration entries available.</p>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {sortedConfig.map((entry) => (
                            <div key={entry.key} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-white/5 p-4 space-y-2">
                                <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">{entry.key}</p>
                                <input
                                    type="text"
                                    value={configDraft[entry.key] ?? entry.value ?? ""}
                                    onChange={(e) => handleFieldChange(entry.key, e.target.value)}
                                    className="w-full rounded-lg border border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-admin-primary transition-all"
                                />
                                <p className="text-[11px] text-slate-500">{entry.description ?? "System configuration entry"}</p>
                            </div>
                        ))}
                    </div>
                )}
                <div className="flex flex-wrap items-center gap-3">
                    {saveError && <span className="text-xs text-rose-500">{saveError}</span>}
                    {saveSuccess && <span className="text-xs text-emerald-500">{saveSuccess}</span>}
                </div>
            </div>
        </section>
    );
}

