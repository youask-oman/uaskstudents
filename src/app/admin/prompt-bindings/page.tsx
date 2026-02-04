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

interface PromptEntry {
    prompt_id: string;
    tier: string | null;
    mode: string;
    role: string;
    version: number;
    is_active: boolean;
}

interface SchemaEntry {
    schema_id: string;
    version: number;
    is_active: boolean;
}

const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export default function AdminPromptBindingsPage() {
    const baseUrl = useMemo(() => DEFAULT_API_BASE_URL, []);
    const [bindings, setBindings] = useState<BindingEntry[]>([]);
    const [prompts, setPrompts] = useState<PromptEntry[]>([]);
    const [schemas, setSchemas] = useState<SchemaEntry[]>([]);
    const [form, setForm] = useState({
        tier: "FREE",
        mode: "SOLVE",
        global_system_prompt_id: "",
        developer_prompt_id: "",
        output_schema_id: "",
    });
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [deletingBindingId, setDeletingBindingId] = useState<string | null>(null);
    const [testRunning, setTestRunning] = useState(false);
    const [testResult, setTestResult] = useState<string | null>(null);

    const headers = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const h: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) (h as Record<string, string>)["Content-Type"] = "application/json";
        return h;
    };

    const loadBindings = async () => {
        const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/bindings`, { headers: headers() });
        if (!res.ok) throw new Error("Failed to load bindings");
        const data: BindingEntry[] = await res.json();
        setBindings(data);
    };

    const loadPrompts = async () => {
        const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts`, { headers: headers() });
        if (!res.ok) throw new Error("Failed to load prompts");
        const data: PromptEntry[] = await res.json();
        setPrompts(data);
    };

    const loadSchemas = async () => {
        const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/schemas`, { headers: headers() });
        if (!res.ok) throw new Error("Failed to load schemas");
        const data: SchemaEntry[] = await res.json();
        setSchemas(data);
    };

    const getGlobalPromptOptions = (tier: string, mode: string) =>
        prompts.filter((p) => {
            if (p.role !== "SYSTEM") return false;
            if (mode === "OCR_EXTRACT") return true;
            return p.mode === mode && (p.tier === null || p.tier === tier);
        });

    const getDeveloperPromptOptions = (tier: string, mode: string) =>
        prompts.filter((p) => {
            if (p.role !== "DEVELOPER") return false;
            if (mode === "OCR_EXTRACT") return true;
            return p.mode === mode && (p.tier === null || p.tier === tier);
        });

    const pickValidOption = (
        preferred: string,
        options: string[],
    ) => (preferred && options.includes(preferred) ? preferred : options[0] || "");

    const normalizeFormSelection = (nextTier: string, nextMode: string, currentForm: typeof form) => {
        const activeBinding = bindings.find((b) => b.is_active && b.tier === nextTier && b.mode === nextMode) || null;
        const globalOptions = getGlobalPromptOptions(nextTier, nextMode).map((p) => p.prompt_id);
        const developerOptions = getDeveloperPromptOptions(nextTier, nextMode).map((p) => p.prompt_id);
        const schemaOptions = schemas.map((s) => s.schema_id);

        return {
            tier: nextTier,
            mode: nextMode,
            global_system_prompt_id: pickValidOption(
                activeBinding?.global_system_prompt_id || currentForm.global_system_prompt_id,
                globalOptions,
            ),
            developer_prompt_id: pickValidOption(
                activeBinding?.developer_prompt_id || currentForm.developer_prompt_id,
                developerOptions,
            ),
            output_schema_id: pickValidOption(
                activeBinding?.output_schema_id || currentForm.output_schema_id,
                schemaOptions,
            ),
        };
    };

    useEffect(() => {
        const loadAll = async () => {
            try {
                setError(null);
                await Promise.all([loadBindings(), loadPrompts(), loadSchemas()]);
            } catch {
                setError("Unable to load binding options.");
            }
        };
        loadAll();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [baseUrl]);

    useEffect(() => {
        if (prompts.length === 0 && schemas.length === 0 && bindings.length === 0) return;
        setForm((current) => {
            const normalized = normalizeFormSelection(current.tier, current.mode, current);
            if (
                normalized.tier === current.tier &&
                normalized.mode === current.mode &&
                normalized.global_system_prompt_id === current.global_system_prompt_id &&
                normalized.developer_prompt_id === current.developer_prompt_id &&
                normalized.output_schema_id === current.output_schema_id
            ) {
                return current;
            }
            return normalized;
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [prompts, schemas, bindings]);

    const globalPromptOptions = useMemo(
        () => getGlobalPromptOptions(form.tier, form.mode),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [prompts, form.tier, form.mode],
    );
    const developerPromptOptions = useMemo(
        () => getDeveloperPromptOptions(form.tier, form.mode),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [prompts, form.tier, form.mode],
    );
    const schemaOptions = useMemo(() => schemas, [schemas]);

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
            await Promise.all([loadBindings(), loadPrompts(), loadSchemas()]);
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

    const handleDeleteBinding = async (binding: BindingEntry) => {
        const confirmed = window.confirm(
            `Delete binding "${binding.tier} - ${binding.mode}" from the table?`
        );
        if (!confirmed) return;

        setDeletingBindingId(binding.id);
        try {
            setError(null);
            const res = await fetch(
                `${baseUrl}/api/v1/admin/prompt-registry/bindings/${encodeURIComponent(binding.id)}`,
                {
                    method: "DELETE",
                    headers: headers(),
                }
            );
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Delete failed");
            }
            await loadBindings();
        } catch (err) {
            setError((err as Error)?.message || "Unable to delete binding.");
        } finally {
            setDeletingBindingId(null);
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
                        onChange={(e) => setForm((current) => normalizeFormSelection(e.target.value, current.mode, current))}
                    >
                        <option value="FREE">FREE</option>
                        <option value="STANDARD">STANDARD</option>
                        <option value="RESEARCH">RESEARCH</option>
                    </select>
                    <select
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        value={form.mode}
                        onChange={(e) => setForm((current) => normalizeFormSelection(current.tier, e.target.value, current))}
                    >
                        <option value="SOLVE">SOLVE</option>
                        <option value="OCR_EXTRACT">OCR_EXTRACT</option>
                        <option value="VERIFY">VERIFY</option>
                        <option value="PLOT_TRIGGER">PLOT_TRIGGER</option>
                        <option value="PLOT_SPEC">PLOT_SPEC</option>
                    </select>
                    <select
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        value={form.global_system_prompt_id}
                        onChange={(e) => setForm({ ...form, global_system_prompt_id: e.target.value })}
                    >
                        {globalPromptOptions.length === 0 && <option value="">No system prompts available</option>}
                        {globalPromptOptions.map((prompt) => (
                            <option key={`${prompt.prompt_id}-${prompt.version}`} value={prompt.prompt_id}>
                                {prompt.prompt_id} (v{prompt.version})
                            </option>
                        ))}
                    </select>
                    <select
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        value={form.developer_prompt_id}
                        onChange={(e) => setForm({ ...form, developer_prompt_id: e.target.value })}
                    >
                        {developerPromptOptions.length === 0 && <option value="">No developer prompts available</option>}
                        {developerPromptOptions.map((prompt) => (
                            <option key={`${prompt.prompt_id}-${prompt.version}`} value={prompt.prompt_id}>
                                {prompt.prompt_id} (v{prompt.version}{prompt.tier ? `, ${prompt.tier}` : ""})
                            </option>
                        ))}
                    </select>
                    <select
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                        value={form.output_schema_id}
                        onChange={(e) => setForm({ ...form, output_schema_id: e.target.value })}
                    >
                        {schemaOptions.length === 0 && <option value="">No schemas available</option>}
                        {schemaOptions.map((schema) => (
                            <option key={`${schema.schema_id}-${schema.version}`} value={schema.schema_id}>
                                {schema.schema_id} (v{schema.version})
                            </option>
                        ))}
                    </select>
                    <button
                        className="w-full px-4 py-2 rounded-lg bg-admin-primary text-white text-xs font-semibold disabled:opacity-60"
                        onClick={handleSubmit}
                        disabled={
                            saving ||
                            !form.global_system_prompt_id ||
                            !form.developer_prompt_id ||
                            !form.output_schema_id
                        }
                    >
                        {saving ? "Saving..." : "Activate Binding"}
                    </button>
                    <button
                        className="w-full px-4 py-2 rounded-lg bg-slate-700 text-white text-xs font-semibold disabled:opacity-60"
                        onClick={runTestPrompt}
                        disabled={testRunning || form.mode === "OCR_EXTRACT"}
                    >
                        {testRunning ? "Running..." : form.mode === "OCR_EXTRACT" ? "Test Not Available (OCR_EXTRACT)" : "Test Prompt"}
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
                                <div className="flex items-center justify-between gap-2">
                                    <div className="font-semibold">{binding.tier} - {binding.mode}</div>
                                    <button
                                        className="px-2 py-1 rounded bg-rose-600 text-white text-[10px] font-semibold disabled:opacity-60"
                                        onClick={() => handleDeleteBinding(binding)}
                                        disabled={deletingBindingId === binding.id}
                                    >
                                        {deletingBindingId === binding.id ? "Deleting..." : "Delete"}
                                    </button>
                                </div>
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
