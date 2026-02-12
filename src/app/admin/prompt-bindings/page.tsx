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
    features?: Record<string, unknown> | null;
    multipliers?: Record<string, unknown> | null;
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

type BindingFeatures = {
    allow_research?: unknown;
    allow_verify?: unknown;
    allow_plot?: unknown;
    daily_credit_cap?: unknown;
    ocr_monthly_cap?: unknown;
    voice_monthly_cap?: unknown;
    generated_images_monthly_cap?: unknown;
    make_it_right_monthly_cap?: unknown;
};

type SolveTierCosts = {
    text?: unknown;
    snap_image?: unknown;
    snap_pdf?: unknown;
    voice?: unknown;
};

type BindingMultipliers = {
    credits?: {
        solve?: Record<string, SolveTierCosts | undefined>;
        verify?: Record<string, unknown>;
        plot_trigger?: unknown;
    };
};

const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";

const tierToPricingKey = (tier: string): "free" | "short" | "standard" | "research" => {
    const normalized = String(tier || "").toUpperCase();
    if (normalized === "FREE") return "free";
    if (normalized === "SHORT") return "short";
    if (normalized === "RESEARCH") return "research";
    return "standard";
};

const parseNum = (value: string, fallback = 0): number => {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
};

const parseOptionalInt = (value: string): number | null => (value === "" ? null : parseInt(value, 10));
const parseOptionalFloat = (value: string): number | null => (value === "" ? null : parseFloat(value));
const asFeatures = (value: Record<string, unknown> | null | undefined): BindingFeatures =>
    (value as BindingFeatures | undefined) || {};
const asMultipliers = (value: Record<string, unknown> | null | undefined): BindingMultipliers =>
    (value as BindingMultipliers | undefined) || {};

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
        allow_research: false,
        allow_verify: true,
        allow_plot: true,
        daily_credit_cap: "",
        ocr_monthly_cap: "",
        voice_monthly_cap: "",
        generated_images_monthly_cap: "",
        make_it_right_monthly_cap: "",
        solve_text_cost: "",
        solve_snap_image_cost: "",
        solve_snap_pdf_cost: "",
        solve_voice_cost: "",
        verify_cost: "",
        plot_trigger_cost: "",
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
            allow_research: Boolean(asFeatures(activeBinding?.features).allow_research ?? false),
            allow_verify: Boolean(asFeatures(activeBinding?.features).allow_verify ?? true),
            allow_plot: Boolean(asFeatures(activeBinding?.features).allow_plot ?? true),
            daily_credit_cap: String(asFeatures(activeBinding?.features).daily_credit_cap ?? ""),
            ocr_monthly_cap: String(asFeatures(activeBinding?.features).ocr_monthly_cap ?? ""),
            voice_monthly_cap: String(asFeatures(activeBinding?.features).voice_monthly_cap ?? ""),
            generated_images_monthly_cap: String(asFeatures(activeBinding?.features).generated_images_monthly_cap ?? ""),
            make_it_right_monthly_cap: String(asFeatures(activeBinding?.features).make_it_right_monthly_cap ?? ""),
            solve_text_cost: String(
                (
                    asMultipliers(activeBinding?.multipliers).credits?.solve?.[tierToPricingKey(nextTier)]?.text ?? ""
                ),
            ),
            solve_snap_image_cost: String(
                (
                    asMultipliers(activeBinding?.multipliers).credits?.solve?.[tierToPricingKey(nextTier)]?.snap_image ?? ""
                ),
            ),
            solve_snap_pdf_cost: String(
                (
                    asMultipliers(activeBinding?.multipliers).credits?.solve?.[tierToPricingKey(nextTier)]?.snap_pdf ?? ""
                ),
            ),
            solve_voice_cost: String(
                (
                    asMultipliers(activeBinding?.multipliers).credits?.solve?.[tierToPricingKey(nextTier)]?.voice ?? ""
                ),
            ),
            verify_cost: String(
                (asMultipliers(activeBinding?.multipliers).credits?.verify?.[tierToPricingKey(nextTier)] ?? ""),
            ),
            plot_trigger_cost: String((asMultipliers(activeBinding?.multipliers).credits?.plot_trigger ?? "")),
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
                    max_output_tokens: parseOptionalInt(form.max_output_tokens),
                    max_input_tokens: parseOptionalInt(form.max_input_tokens),
                    system_schema_budget_tokens: parseOptionalInt(form.system_schema_budget_tokens),
                    context_budget_tokens: parseOptionalInt(form.context_budget_tokens),
                    json_retry_max_output_tokens: parseOptionalInt(form.json_retry_max_output_tokens),
                    json_retry_max_attempts: parseOptionalInt(form.json_retry_max_attempts),
                    timeout_ms: parseOptionalInt(form.timeout_ms),
                    temperature: parseOptionalFloat(form.temperature),
                    top_p: parseOptionalFloat(form.top_p),
                    plot_points_cap: parseOptionalInt(form.plot_points_cap),
                    plot_traces_cap: parseOptionalInt(form.plot_traces_cap),
                    plot_annotations_cap: parseOptionalInt(form.plot_annotations_cap),
                    max_steps: parseOptionalInt(form.max_steps),
                    retry_cap_tokens: parseOptionalInt(form.retry_cap_tokens),
                    features: {
                        allow_research: form.allow_research,
                        allow_verify: form.allow_verify,
                        allow_plot: form.allow_plot,
                        daily_credit_cap: parseNum(form.daily_credit_cap, 0),
                        ocr_monthly_cap: parseNum(form.ocr_monthly_cap, 0),
                        voice_monthly_cap: parseNum(form.voice_monthly_cap, 0),
                        generated_images_monthly_cap: parseNum(form.generated_images_monthly_cap, 0),
                        make_it_right_monthly_cap: parseNum(form.make_it_right_monthly_cap, 0),
                    },
                    multipliers: {
                        version: 1,
                        credits: {
                            solve: {
                                [tierToPricingKey(form.tier)]: {
                                    text: parseNum(form.solve_text_cost, 0),
                                    snap_image: parseNum(form.solve_snap_image_cost, 0),
                                    snap_pdf: parseNum(form.solve_snap_pdf_cost, 0),
                                    voice: parseNum(form.solve_voice_cost, 0),
                                },
                            },
                            verify: {
                                [tierToPricingKey(form.tier)]: parseNum(form.verify_cost, 0),
                            },
                            plot_trigger: parseNum(form.plot_trigger_cost, 0),
                        },
                    },
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
            allow_research: Boolean(asFeatures(binding?.features).allow_research ?? false),
            allow_verify: Boolean(asFeatures(binding?.features).allow_verify ?? true),
            allow_plot: Boolean(asFeatures(binding?.features).allow_plot ?? true),
            daily_credit_cap: String(asFeatures(binding?.features).daily_credit_cap ?? ""),
            ocr_monthly_cap: String(asFeatures(binding?.features).ocr_monthly_cap ?? ""),
            voice_monthly_cap: String(asFeatures(binding?.features).voice_monthly_cap ?? ""),
            generated_images_monthly_cap: String(asFeatures(binding?.features).generated_images_monthly_cap ?? ""),
            make_it_right_monthly_cap: String(asFeatures(binding?.features).make_it_right_monthly_cap ?? ""),
            solve_text_cost: String(
                (
                    asMultipliers(binding?.multipliers).credits?.solve?.[tierToPricingKey(binding.tier)]?.text ?? ""
                ),
            ),
            solve_snap_image_cost: String(
                (
                    asMultipliers(binding?.multipliers).credits?.solve?.[tierToPricingKey(binding.tier)]?.snap_image ?? ""
                ),
            ),
            solve_snap_pdf_cost: String(
                (
                    asMultipliers(binding?.multipliers).credits?.solve?.[tierToPricingKey(binding.tier)]?.snap_pdf ?? ""
                ),
            ),
            solve_voice_cost: String(
                (
                    asMultipliers(binding?.multipliers).credits?.solve?.[tierToPricingKey(binding.tier)]?.voice ?? ""
                ),
            ),
            verify_cost: String(
                (asMultipliers(binding?.multipliers).credits?.verify?.[tierToPricingKey(binding.tier)] ?? ""),
            ),
            plot_trigger_cost: String((asMultipliers(binding?.multipliers).credits?.plot_trigger ?? "")),
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
        <div className="w-full p-6 xl:p-8 flex flex-col gap-6 max-w-[1920px] mx-auto">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400 font-semibold">Admin Panel</p>
                <div className="flex items-baseline justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">Prompt Bindings</h1>
                        <p className="text-sm text-slate-500 mt-1">Configure tier-specific runtime constraints and prompt linking.</p>
                    </div>
                </div>
            </header>

            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 px-4 py-3 text-sm font-medium flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                    {error}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">

                {/* --- Left Column: Configuration Form --- */}
                <div className="lg:col-span-5 space-y-6">

                    {/* section: Context Definition */}
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Core Context</h2>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Legacy Tier</label>
                                    <select
                                        className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                        value={form.tier}
                                        onChange={(e) => setForm((current) => normalizeFormSelection(e.target.value, current.mode, current))}
                                    >
                                        <option value="FREE">FREE</option>
                                        <option value="STANDARD">STANDARD</option>
                                        <option value="RESEARCH">RESEARCH</option>
                                        <option value="SHORT">SHORT</option>
                                    </select>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Execution Mode</label>
                                    <select
                                        className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                        value={form.mode}
                                        onChange={(e) => setForm((current) => normalizeFormSelection(current.tier, e.target.value, current))}
                                    >
                                        <option value="SOLVE">SOLVE</option>
                                        <option value="OCR_EXTRACT">OCR_EXTRACT</option>
                                        <option value="VERIFY">VERIFY</option>
                                        <option value="PLOT_TRIGGER">PLOT_TRIGGER</option>
                                        <option value="PLOT_SPEC">PLOT_SPEC</option>
                                    </select>
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">System Prompt</label>
                                <select
                                    className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-700 dark:text-slate-200"
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
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Developer Prompt</label>
                                <select
                                    className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-700 dark:text-slate-200"
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
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Output Schema</label>
                                <select
                                    className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-700 dark:text-slate-200"
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
                            </div>
                        </div>
                    </div>

                    {/* Section: Tokens & Limits */}
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Limits & Budgets</h2>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Max Input Tokens</label>
                                    <input type="number" placeholder="Auto" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.max_input_tokens} onChange={(e) => setForm({ ...form, max_input_tokens: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Max Output Tokens</label>
                                    <input type="number" placeholder="Auto" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.max_output_tokens} onChange={(e) => setForm({ ...form, max_output_tokens: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">System Budget</label>
                                    <input type="number" placeholder="Auto" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.system_schema_budget_tokens} onChange={(e) => setForm({ ...form, system_schema_budget_tokens: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Context Budget</label>
                                    <input type="number" placeholder="Auto" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.context_budget_tokens} onChange={(e) => setForm({ ...form, context_budget_tokens: e.target.value })} />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Section: Inference Parameters */}
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Inference Parameters</h2>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Temperature</label>
                                    <input type="number" step="0.1" placeholder="0.1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.temperature} onChange={(e) => setForm({ ...form, temperature: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Top P</label>
                                    <input type="number" step="0.1" placeholder="1.0" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.top_p} onChange={(e) => setForm({ ...form, top_p: e.target.value })} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Timeout (ms)</label>
                                    <input type="number" placeholder="60000" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.timeout_ms} onChange={(e) => setForm({ ...form, timeout_ms: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Trim Strategy</label>
                                    <select className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.trim_strategy} onChange={(e) => setForm({ ...form, trim_strategy: e.target.value })}>
                                        <option value="none">None</option>
                                        <option value="trim_context_first">Trim Context First</option>
                                        <option value="trim_user_first">Trim User First</option>
                                        <option value="summarize_context">Summarize Context</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Section: Retry & Plots (2 col for better spacing) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Retry Logic</h2>
                            </div>
                            <div className="p-4 space-y-3">
                                <div className="space-y-1">
                                    <label className="text-[11px] font-medium text-slate-400">JSON Retry Max Output</label>
                                    <input type="number" placeholder="Auto" className="w-full rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-sm" value={form.json_retry_max_output_tokens} onChange={(e) => setForm({ ...form, json_retry_max_output_tokens: e.target.value })} />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-medium text-slate-400">Retry Attempts</label>
                                    <input type="number" placeholder="1" className="w-full rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-sm" value={form.json_retry_max_attempts} onChange={(e) => setForm({ ...form, json_retry_max_attempts: e.target.value })} />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-medium text-slate-400">Max Steps</label>
                                    <input type="number" placeholder="Auto" className="w-full rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-sm" value={form.max_steps} onChange={(e) => setForm({ ...form, max_steps: e.target.value })} />
                                </div>
                            </div>
                        </div>

                        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Plotting</h2>
                            </div>
                            <div className="p-4 space-y-3">
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="space-y-1">
                                        <label className="text-[11px] font-medium text-slate-400">Points Cap</label>
                                        <input type="number" placeholder="25" className="w-full rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-sm" value={form.plot_points_cap} onChange={(e) => setForm({ ...form, plot_points_cap: e.target.value })} />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-[11px] font-medium text-slate-400">Traces Cap</label>
                                        <input type="number" placeholder="5" className="w-full rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-sm" value={form.plot_traces_cap} onChange={(e) => setForm({ ...form, plot_traces_cap: e.target.value })} />
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-medium text-slate-400">Annotations Cap</label>
                                    <input type="number" placeholder="5" className="w-full rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-2.5 py-1.5 text-sm" value={form.plot_annotations_cap} onChange={(e) => setForm({ ...form, plot_annotations_cap: e.target.value })} />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Credit Pricing</h2>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Solve Text Cost</label>
                                    <input type="number" step="1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.solve_text_cost} onChange={(e) => setForm({ ...form, solve_text_cost: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Solve Snap Image Cost</label>
                                    <input type="number" step="1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.solve_snap_image_cost} onChange={(e) => setForm({ ...form, solve_snap_image_cost: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Solve Snap PDF Cost</label>
                                    <input type="number" step="1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.solve_snap_pdf_cost} onChange={(e) => setForm({ ...form, solve_snap_pdf_cost: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Solve Voice Cost</label>
                                    <input type="number" step="1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.solve_voice_cost} onChange={(e) => setForm({ ...form, solve_voice_cost: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Verify Add-on Cost</label>
                                    <input type="number" step="1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.verify_cost} onChange={(e) => setForm({ ...form, verify_cost: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Plot Trigger Add-on Cost</label>
                                    <input type="number" step="1" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.plot_trigger_cost} onChange={(e) => setForm({ ...form, plot_trigger_cost: e.target.value })} />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">Feature Gates & Caps</h2>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                    <input type="checkbox" checked={form.allow_research} onChange={(e) => setForm({ ...form, allow_research: e.target.checked })} />
                                    Allow Research
                                </label>
                                <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                    <input type="checkbox" checked={form.allow_verify} onChange={(e) => setForm({ ...form, allow_verify: e.target.checked })} />
                                    Allow Verify
                                </label>
                                <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                    <input type="checkbox" checked={form.allow_plot} onChange={(e) => setForm({ ...form, allow_plot: e.target.checked })} />
                                    Allow Plot
                                </label>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Daily Credit Cap</label>
                                    <input type="number" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.daily_credit_cap} onChange={(e) => setForm({ ...form, daily_credit_cap: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">OCR Monthly Cap</label>
                                    <input type="number" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.ocr_monthly_cap} onChange={(e) => setForm({ ...form, ocr_monthly_cap: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Voice Monthly Cap</label>
                                    <input type="number" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.voice_monthly_cap} onChange={(e) => setForm({ ...form, voice_monthly_cap: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Generated Images Monthly Cap</label>
                                    <input type="number" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.generated_images_monthly_cap} onChange={(e) => setForm({ ...form, generated_images_monthly_cap: e.target.value })} />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-slate-500">Make It Right Monthly Cap</label>
                                    <input type="number" className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm" value={form.make_it_right_monthly_cap} onChange={(e) => setForm({ ...form, make_it_right_monthly_cap: e.target.value })} />
                                </div>
                            </div>
                        </div>
                    </div>


                    <div className="pt-4 flex gap-3">
                        <button
                            className="flex-1 px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            onClick={handleSubmit}
                            disabled={saving || !form.global_system_prompt_id || !form.developer_prompt_id || !form.output_schema_id}
                        >
                            {saving ? "Saving Changes..." : "Activate / Update Binding"}
                        </button>
                        <button
                            className="px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-semibold transition-colors disabled:opacity-50"
                            onClick={runTestPrompt}
                            disabled={testRunning || form.mode === "OCR_EXTRACT"}
                        >
                            {testRunning ? "Testing..." : "Test"}
                        </button>
                    </div>

                    {testResult && (
                        <div className="bg-slate-900 rounded-xl p-4 overflow-x-auto border border-slate-800">
                            <h4 className="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">Test Result</h4>
                            <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap leading-relaxed">{testResult}</pre>
                        </div>
                    )}

                </div>

                {/* --- Right Column: List --- */}
                <div className="lg:col-span-7 space-y-4">
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-[calc(100vh-140px)]">
                        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-950/50 rounded-t-xl">
                            <h2 className="font-semibold text-slate-800 dark:text-slate-100">Active Bindings</h2>
                            <span className="text-xs text-slate-500 bg-slate-200 dark:bg-slate-800 px-2 py-1 rounded-full">{bindings.length} configured</span>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                            {bindings.length === 0 && (
                                <div className="text-center py-12 text-slate-400 text-sm">No active bindings found. Configure one on the left.</div>
                            )}
                            {bindings.map((binding, index) => (
                                <div
                                    key={binding.id || `${binding.tier}-${binding.mode}-${index}`}
                                    className="group relative bg-white dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800 p-4 hover:border-blue-400 transition-colors"
                                >
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex items-center gap-3">
                                            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide ${binding.tier === 'FREE' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                                                binding.tier === 'STANDARD' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                                                    'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                                                }`}>
                                                {binding.tier}
                                            </span>
                                            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{binding.mode}</span>
                                        </div>
                                        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button onClick={() => handleEditBinding(binding)} className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors" title="Edit">
                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                            </button>
                                            <button onClick={() => handleDeleteBinding(binding)} disabled={deletingBindingId === binding.id} className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors" title="Delete">
                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                            </button>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 text-xs text-slate-600 dark:text-slate-400 mb-3">
                                        <div className="space-y-1">
                                            <div className="flex gap-2"><span className="text-slate-400 w-16">Global:</span> <span className="font-mono text-slate-700 dark:text-slate-300 truncate">{binding.global_system_prompt_id}</span></div>
                                            <div className="flex gap-2"><span className="text-slate-400 w-16">Dev:</span> <span className="font-mono text-slate-700 dark:text-slate-300 truncate">{binding.developer_prompt_id}</span></div>
                                            <div className="flex gap-2"><span className="text-slate-400 w-16">Schema:</span> <span className="font-mono text-slate-700 dark:text-slate-300 truncate">{binding.output_schema_id}</span></div>
                                        </div>
                                        <div className="space-y-1 border-l pl-4 border-slate-100 dark:border-slate-800">
                                            <div className="flex justify-between"><span>Out Tokens:</span> <span className="font-medium">{binding.max_output_tokens || 'Auto'}</span></div>
                                            <div className="flex justify-between"><span>Timeout:</span> <span className="font-medium">{binding.timeout_ms ? `${binding.timeout_ms}ms` : 'Default'}</span></div>
                                            <div className="flex justify-between"><span>Temp:</span> <span className="font-medium">{binding.temperature ?? '0.1'}</span></div>
                                        </div>
                                    </div>

                                    {/* Mini badges for active features */}
                                    <div className="flex gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                                        {binding.trim_strategy && binding.trim_strategy !== 'none' && <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">Trim: {binding.trim_strategy}</span>}
                                        {binding.plot_points_cap && <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">Plot Cap: {binding.plot_points_cap}</span>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );

}

