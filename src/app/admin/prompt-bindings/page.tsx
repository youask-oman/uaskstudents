"use client";

import { useEffect, useMemo, useState } from "react";

interface BindingEntry {
    id: string;
    tier: string;
    mode: string;
    global_system_prompt_id: string;
    developer_prompt_id: string;
    output_schema_id: string;
    is_active: boolean;
    updated_at: string;
    updated_by?: string | null;
}

const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export default function AdminPromptBindingsPage() {
    const baseUrl = useMemo(() => DEFAULT_API_BASE_URL, []);
    const [bindings, setBindings] = useState<BindingEntry[]>([]);
    const [form, setForm] = useState({
        tier: "FREE",
        mode: "SOLVE",
        global_system_prompt_id: "",
        developer_prompt_id: "",
        output_schema_id: "",
    });
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [testRunning, setTestRunning] = useState(false);
    const [testResult, setTestResult] = useState<string | null>(null);

    const headers = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const h: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) (h as Record<string, string>)["Content-Type"] = "application/json";
        return h;
    };

    const loadBindings = async () => {
        try {
            setError(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/bindings`, { headers: headers() });
            if (!res.ok) throw new Error("Failed to load bindings");
            const data: BindingEntry[] = await res.json();
            setBindings(data);
        } catch {
            setError("Unable to load bindings.");
        }
    };

    useEffect(() => {
        loadBindings();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [baseUrl]);

    const handleSubmit = async () => {
        setSaving(true);
        try {
            setError(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/bindings/activate`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    ...form,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) throw new Error("Activate failed");
            await loadBindings();
        } catch {
            setError("Unable to activate binding.");
        } finally {
            setSaving(false);
        }
    };

    const runTestPrompt = async () => {
        setTestRunning(true);
        setTestResult(null);
        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/test`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    tier: form.tier,
                    mode: form.mode,
                    question_payload: { problem: "Solve x + 2 = 5" },
                    context_payload: { locale: "en-US" },
                    runtime_hints: { requested_mode: "minimal" },
                }),
            });
            const text = await res.text();
            setTestResult(text);
        } catch {
            setTestResult("Test failed.");
        } finally {
            setTestRunning(false);
        }
    };

    return (
        <div className="w-full p-6 xl:p-8 flex flex-col gap-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Prompt Bindings</h1>
                <p className="text-sm text-slate-500">Map tiers and modes to prompt + schema IDs.</p>
            </header>
            {error && <div className="rounded-lg border border-rose-200 bg-rose-50 text-rose-700 px-4 py-2 text-sm">{error}</div>}
            <div className="grid grid-cols-1 xl:grid-cols-[380px_minmax(0,1fr)] gap-6 w-full">
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                    <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Activate Binding</h2>
                    <select
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        value={form.tier}
                        onChange={(e) => setForm({ ...form, tier: e.target.value })}
                    >
                        <option value="FREE">FREE</option>
                        <option value="STANDARD">STANDARD</option>
                        <option value="RESEARCH">RESEARCH</option>
                    </select>
                    <select
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        value={form.mode}
                        onChange={(e) => setForm({ ...form, mode: e.target.value })}
                    >
                        <option value="SOLVE">SOLVE</option>
                        <option value="VERIFY">VERIFY</option>
                        <option value="PLOT_TRIGGER">PLOT_TRIGGER</option>
                        <option value="PLOT_SPEC">PLOT_SPEC</option>
                    </select>
                    <input
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        placeholder="global_system_prompt_id"
                        value={form.global_system_prompt_id}
                        onChange={(e) => setForm({ ...form, global_system_prompt_id: e.target.value })}
                    />
                    <input
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        placeholder="developer_prompt_id"
                        value={form.developer_prompt_id}
                        onChange={(e) => setForm({ ...form, developer_prompt_id: e.target.value })}
                    />
                    <input
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        placeholder="output_schema_id"
                        value={form.output_schema_id}
                        onChange={(e) => setForm({ ...form, output_schema_id: e.target.value })}
                    />
                    <button
                        className="w-full px-4 py-2 rounded-lg bg-admin-primary text-white text-xs font-semibold disabled:opacity-60"
                        onClick={handleSubmit}
                        disabled={saving}
                    >
                        {saving ? "Saving..." : "Activate Binding"}
                    </button>
                    <button
                        className="w-full px-4 py-2 rounded-lg bg-slate-700 text-white text-xs font-semibold disabled:opacity-60"
                        onClick={runTestPrompt}
                        disabled={testRunning}
                    >
                        {testRunning ? "Running..." : "Test Prompt"}
                    </button>
                    {testResult && (
                        <pre className="text-[10px] whitespace-pre-wrap break-words rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 p-2">{testResult}</pre>
                    )}
                </div>
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                    <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Active Bindings</h2>
                    <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
                        {bindings.map((binding, index) => (
                            <div
                                key={binding.id || `${binding.tier}-${binding.mode}-${binding.updated_at}-${index}`}
                                className="rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs text-slate-600 dark:text-slate-300"
                            >
                                <div className="font-semibold">{binding.tier} - {binding.mode}</div>
                                <div>global: {binding.global_system_prompt_id}</div>
                                <div>developer: {binding.developer_prompt_id}</div>
                                <div>schema: {binding.output_schema_id}</div>
                                <div className="text-[10px] text-slate-400">{binding.is_active ? "active" : "inactive"}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
