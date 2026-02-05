"use client";

import { useEffect, useMemo, useState } from "react";

interface BindingEntry {
    id: string;
    tier: string;
    mode: string;
    global_system_prompt_id: string;
    developer_prompt_id: string;
    output_schema_id: string;
    max_output_tokens?: number | null;
    max_input_tokens?: number | null;
    system_schema_budget_tokens?: number | null;
    context_budget_tokens?: number | null;
    json_retry_max_output_tokens?: number | null;
    json_retry_max_attempts?: number | null;
    timeout_ms?: number | null;
    temperature?: number | null;
    top_p?: number | null;
    plot_points_cap?: number | null;
    plot_traces_cap?: number | null;
    plot_annotations_cap?: number | null;
    trim_strategy?: string | null;
    max_steps?: number | null;
    retry_cap_tokens?: number | null;
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
        max_output_tokens: "",
        max_input_tokens: "",
        system_schema_budget_tokens: "",
        context_budget_tokens: "",
        json_retry_max_output_tokens: "",
        json_retry_max_attempts: "",
        timeout_ms: "",
        temperature: "",
        top_p: "",
        plot_points_cap: "",
        plot_traces_cap: "",
        plot_annotations_cap: "",
        trim_strategy: "trim_context_first",
        max_steps: "",
        retry_cap_tokens: "",
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
            max_output_tokens: activeBinding?.max_output_tokens?.toString() || "",
            max_input_tokens: activeBinding?.max_input_tokens?.toString() || "",
            system_schema_budget_tokens: activeBinding?.system_schema_budget_tokens?.toString() || "",
            context_budget_tokens: activeBinding?.context_budget_tokens?.toString() || "",
            json_retry_max_output_tokens: activeBinding?.json_retry_max_output_tokens?.toString() || "",
            json_retry_max_attempts: activeBinding?.json_retry_max_attempts?.toString() || "",
            timeout_ms: activeBinding?.timeout_ms?.toString() || "",
            temperature: activeBinding?.temperature?.toString() || "",
            top_p: activeBinding?.top_p?.toString() || "",
            plot_points_cap: activeBinding?.plot_points_cap?.toString() || "",
            plot_traces_cap: activeBinding?.plot_traces_cap?.toString() || "",
            plot_annotations_cap: activeBinding?.plot_annotations_cap?.toString() || "",
            trim_strategy: activeBinding?.trim_strategy || "trim_context_first",
            max_steps: activeBinding?.max_steps?.toString() || "",
            retry_cap_tokens: activeBinding?.retry_cap_tokens?.toString() || "",
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
                    max_output_tokens: form.max_output_tokens === "" ? null : parseInt(form.max_output_tokens),
                    max_input_tokens: form.max_input_tokens === "" ? null : parseInt(form.max_input_tokens),
                    system_schema_budget_tokens: form.system_schema_budget_tokens === "" ? null : parseInt(form.system_schema_budget_tokens),
                    context_budget_tokens: form.context_budget_tokens === "" ? null : parseInt(form.context_budget_tokens),
                    json_retry_max_output_tokens: form.json_retry_max_output_tokens === "" ? null : parseInt(form.json_retry_max_output_tokens),
                    json_retry_max_attempts: form.json_retry_max_attempts === "" ? null : parseInt(form.json_retry_max_attempts),
                    timeout_ms: form.timeout_ms === "" ? null : parseInt(form.timeout_ms),
                    temperature: form.temperature === "" ? null : parseFloat(form.temperature),
                    top_p: form.top_p === "" ? null : parseFloat(form.top_p),
                    plot_points_cap: form.plot_points_cap === "" ? null : parseInt(form.plot_points_cap),
                    plot_traces_cap: form.plot_traces_cap === "" ? null : parseInt(form.plot_traces_cap),
                    plot_annotations_cap: form.plot_annotations_cap === "" ? null : parseInt(form.plot_annotations_cap),
                    max_steps: form.max_steps === "" ? null : parseInt(form.max_steps),
                    retry_cap_tokens: form.retry_cap_tokens === "" ? null : parseInt(form.retry_cap_tokens),
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

    const handleEditBinding = (binding: BindingEntry) => {
        setForm({
            tier: binding.tier,
            mode: binding.mode,
            global_system_prompt_id: binding.global_system_prompt_id,
            developer_prompt_id: binding.developer_prompt_id,
            output_schema_id: binding.output_schema_id,
            max_output_tokens: binding.max_output_tokens?.toString() || "",
            max_input_tokens: binding.max_input_tokens?.toString() || "",
            system_schema_budget_tokens: binding.system_schema_budget_tokens?.toString() || "",
            context_budget_tokens: binding.context_budget_tokens?.toString() || "",
            json_retry_max_output_tokens: binding.json_retry_max_output_tokens?.toString() || "",
            json_retry_max_attempts: binding.json_retry_max_attempts?.toString() || "",
            timeout_ms: binding.timeout_ms?.toString() || "",
            temperature: binding.temperature?.toString() || "",
            top_p: binding.top_p?.toString() || "",
            plot_points_cap: binding.plot_points_cap?.toString() || "",
            plot_traces_cap: binding.plot_traces_cap?.toString() || "",
            plot_annotations_cap: binding.plot_annotations_cap?.toString() || "",
            trim_strategy: binding.trim_strategy || "trim_context_first",
            max_steps: binding.max_steps?.toString() || "",
            retry_cap_tokens: binding.retry_cap_tokens?.toString() || "",
        });
        window.scrollTo({ top: 0, behavior: "smooth" });
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

                    <div className="grid grid-cols-2 gap-2 mt-2">
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Max Input Tokens</label>
                            <input
                                type="number"
                                placeholder="Auto"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.max_input_tokens}
                                onChange={(e) => setForm({ ...form, max_input_tokens: e.target.value })}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Trim Strategy</label>
                            <select
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.trim_strategy}
                                onChange={(e) => setForm({ ...form, trim_strategy: e.target.value })}
                            >
                                <option value="none">none</option>
                                <option value="trim_context_first">trim_context_first</option>
                                <option value="trim_user_first">trim_user_first</option>
                                <option value="summarize_context">summarize_context</option>
                            </select>
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Max Out</label>
                            <input
                                type="number"
                                placeholder="Auto"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.max_output_tokens}
                                onChange={(e) => setForm({ ...form, max_output_tokens: e.target.value })}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Temp</label>
                            <input
                                type="number"
                                step="0.1"
                                placeholder="0.1"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.temperature}
                                onChange={(e) => setForm({ ...form, temperature: e.target.value })}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Timeout</label>
                            <input
                                type="number"
                                placeholder="60000"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.timeout_ms}
                                onChange={(e) => setForm({ ...form, timeout_ms: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Retry Max Tokens</label>
                            <input
                                type="number"
                                placeholder="Auto"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.json_retry_max_output_tokens}
                                onChange={(e) => setForm({ ...form, json_retry_max_output_tokens: e.target.value })}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Retry Attempts</label>
                            <input
                                type="number"
                                placeholder="1"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.json_retry_max_attempts}
                                onChange={(e) => setForm({ ...form, json_retry_max_attempts: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                        <label className="text-[10px] font-bold text-slate-500 block mb-1 uppercase tracking-wider">Plot Pipeline Caps</label>
                        <div className="grid grid-cols-3 gap-2">
                            <div className="space-y-1">
                                <label className="text-[10px] text-slate-400">Pts</label>
                                <input
                                    type="number"
                                    placeholder="25"
                                    className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                    value={form.plot_points_cap}
                                    onChange={(e) => setForm({ ...form, plot_points_cap: e.target.value })}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] text-slate-400">Traces</label>
                                <input
                                    type="number"
                                    placeholder="5"
                                    className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                    value={form.plot_traces_cap}
                                    onChange={(e) => setForm({ ...form, plot_traces_cap: e.target.value })}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] text-slate-400">Anno</label>
                                <input
                                    type="number"
                                    placeholder="5"
                                    className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                    value={form.plot_annotations_cap}
                                    onChange={(e) => setForm({ ...form, plot_annotations_cap: e.target.value })}
                                />
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Max Steps</label>
                            <input
                                type="number"
                                placeholder="Auto"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.max_steps}
                                onChange={(e) => setForm({ ...form, max_steps: e.target.value })}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">Retry Cap (Legacy)</label>
                            <input
                                type="number"
                                placeholder="Auto"
                                className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-sm"
                                value={form.retry_cap_tokens}
                                onChange={(e) => setForm({ ...form, retry_cap_tokens: e.target.value })}
                            />
                        </div>
                    </div>
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
                                    <div className="flex gap-2">
                                        <button
                                            className="px-2 py-1 rounded bg-admin-primary text-white text-[10px] font-semibold"
                                            onClick={() => handleEditBinding(binding)}
                                        >
                                            Edit
                                        </button>
                                        <button
                                            className="px-2 py-1 rounded bg-rose-600 text-white text-[10px] font-semibold disabled:opacity-60"
                                            onClick={() => handleDeleteBinding(binding)}
                                            disabled={deletingBindingId === binding.id}
                                        >
                                            {deletingBindingId === binding.id ? "Deleting..." : "Delete"}
                                        </button>
                                    </div>
                                </div>
                                <div>global: {binding.global_system_prompt_id}</div>
                                <div>developer: {binding.developer_prompt_id}</div>
                                <div>schema: {binding.output_schema_id}</div>
                                <div className="flex flex-wrap gap-2 text-[10px] text-slate-400 mt-1">
                                    {binding.max_output_tokens && <span>Out: {binding.max_output_tokens}</span>}
                                    {binding.max_input_tokens && <span>In: {binding.max_input_tokens}</span>}
                                    {binding.temperature && <span>T: {binding.temperature}</span>}
                                    {binding.plot_points_cap && <span>Pts: {binding.plot_points_cap}</span>}
                                    {binding.trim_strategy && <span>Trim: {binding.trim_strategy}</span>}
                                    {binding.max_steps && <span>Steps: {binding.max_steps}</span>}
                                </div>
                                <div className="text-[10px] text-slate-400">{binding.is_active ? "active" : "inactive"}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
