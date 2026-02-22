"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type Binding = {
    id: string;
    tier: string;
    mode: string;
    provider: string;
    global_system_prompt_id: string;
    developer_prompt_id: string;
    output_schema_id: string;
    features: Record<string, unknown>;
    multipliers: Record<string, unknown>;
    is_active: boolean;
    max_questions_allowed: number | null;
    timeout_ms: number | null;
    max_input_tokens: number | null;
    max_output_tokens: number | null;
    system_schema_budget_tokens: number | null;
    context_budget_tokens: number | null;
    json_retry_max_output_tokens: number | null;
    json_retry_max_attempts: number | null;
    plot_points_cap: number | null;
    plot_traces_cap: number | null;
    plot_annotations_cap: number | null;
    temperature: number | null;
    top_p: number | null;
    trim_strategy: string | null;
    max_steps: number | null;
    retry_cap_tokens: number | null;
    solve_text_cost: number;
    solve_snap_image_cost: number;
    solve_snap_pdf_cost: number;
    solve_voice_cost: number;
    verify_addon_cost: number;
    plot_addon_cost: number;
    attempt_fee: number;
    updated_at: string;
    updated_by?: string;
};

type PromptRegistryEntry = {
    prompt_id: string;
    tier?: string | null;
    mode?: string | null;
    role?: string | null;
    version?: number;
    is_active?: boolean;
};

type SchemaRegistryEntry = {
    schema_id: string;
    version?: number;
    is_active?: boolean;
};

type DraftBinding = Omit<Binding, "features" | "multipliers"> & {
    features_obj: Record<string, unknown>;
    multipliers_obj: Record<string, unknown>;
};

const modeOptions = ["SOLVE", "VERIFY", "PLOT_TRIGGER", "PLOT_SPEC", "OCR_EXTRACT"];
const trimStrategyOptions = [
    "",
    "none",
    "trim_context_first",
    "trim_user_first",
    "summarize_context",
    "trim_everything_except_plot_plan",
];

const numericKeys: Array<keyof Binding> = [
    "max_questions_allowed",
    "timeout_ms",
    "max_input_tokens",
    "max_output_tokens",
    "system_schema_budget_tokens",
    "context_budget_tokens",
    "json_retry_max_output_tokens",
    "json_retry_max_attempts",
    "plot_points_cap",
    "plot_traces_cap",
    "plot_annotations_cap",
    "temperature",
    "top_p",
    "max_steps",
    "retry_cap_tokens",
    "solve_text_cost",
    "solve_snap_image_cost",
    "solve_snap_pdf_cost",
    "solve_voice_cost",
    "verify_addon_cost",
    "plot_addon_cost",
    "attempt_fee",
];

const intKeys = new Set<keyof Binding>([
    "max_questions_allowed",
    "timeout_ms",
    "max_input_tokens",
    "max_output_tokens",
    "system_schema_budget_tokens",
    "context_budget_tokens",
    "json_retry_max_output_tokens",
    "json_retry_max_attempts",
    "plot_points_cap",
    "plot_traces_cap",
    "plot_annotations_cap",
    "max_steps",
    "retry_cap_tokens",
]);

const bindingTones = [
    { badge: "bg-rose-100 border-rose-200 text-rose-800", badgeActive: "bg-rose-200 border-rose-300 text-rose-900 ring-rose-300", section: "border-rose-200", sectionHeader: "bg-rose-50 border-rose-200", sectionTitle: "text-rose-800" },
    { badge: "bg-amber-100 border-amber-200 text-amber-800", badgeActive: "bg-amber-200 border-amber-300 text-amber-900 ring-amber-300", section: "border-amber-200", sectionHeader: "bg-amber-50 border-amber-200", sectionTitle: "text-amber-800" },
    { badge: "bg-emerald-100 border-emerald-200 text-emerald-800", badgeActive: "bg-emerald-200 border-emerald-300 text-emerald-900 ring-emerald-300", section: "border-emerald-200", sectionHeader: "bg-emerald-50 border-emerald-200", sectionTitle: "text-emerald-800" },
    { badge: "bg-sky-100 border-sky-200 text-sky-800", badgeActive: "bg-sky-200 border-sky-300 text-sky-900 ring-sky-300", section: "border-sky-200", sectionHeader: "bg-sky-50 border-sky-200", sectionTitle: "text-sky-800" },
    { badge: "bg-indigo-100 border-indigo-200 text-indigo-800", badgeActive: "bg-indigo-200 border-indigo-300 text-indigo-900 ring-indigo-300", section: "border-indigo-200", sectionHeader: "bg-indigo-50 border-indigo-200", sectionTitle: "text-indigo-800" },
    { badge: "bg-fuchsia-100 border-fuchsia-200 text-fuchsia-800", badgeActive: "bg-fuchsia-200 border-fuchsia-300 text-fuchsia-900 ring-fuchsia-300", section: "border-fuchsia-200", sectionHeader: "bg-fuchsia-50 border-fuchsia-200", sectionTitle: "text-fuchsia-800" },
    { badge: "bg-teal-100 border-teal-200 text-teal-800", badgeActive: "bg-teal-200 border-teal-300 text-teal-900 ring-teal-300", section: "border-teal-200", sectionHeader: "bg-teal-50 border-teal-200", sectionTitle: "text-teal-800" },
    { badge: "bg-orange-100 border-orange-200 text-orange-800", badgeActive: "bg-orange-200 border-orange-300 text-orange-900 ring-orange-300", section: "border-orange-200", sectionHeader: "bg-orange-50 border-orange-200", sectionTitle: "text-orange-800" },
];

function toDraft(b: Binding): DraftBinding {
    return {
        ...b,
        features_obj: JSON.parse(JSON.stringify(b.features || {})),
        multipliers_obj: JSON.parse(JSON.stringify(b.multipliers || {})),
    };
}

function asRecord(v: unknown): Record<string, unknown> {
    return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

function asInput(v: string | number | null | undefined): string {
    if (v === null || v === undefined) return "";
    return String(v);
}

function parseNullableNumber(v: string): number | null {
    if (v.trim() === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
}

function stableHash(value: string): number {
    let hash = 0;
    for (let i = 0; i < value.length; i += 1) {
        hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
    }
    return hash;
}

function toneForBinding(binding: Pick<Binding, "id" | "tier" | "mode"> | null | undefined) {
    if (!binding) return bindingTones[0];
    const normalizedTier = String(binding.tier || "").trim().toUpperCase();
    if (normalizedTier === "STANDARD") return bindingTones[0];
    if (normalizedTier === "RESEARCH") return bindingTones[4];
    if (normalizedTier === "FINAL") return bindingTones[6];
    if (normalizedTier === "SHORT_STEPS") return bindingTones[5];
    const key = `${binding.id}|${binding.mode}|${(binding as any).provider || ""}`;
    return bindingTones[stableHash(key) % bindingTones.length];
}

function tierKey(tier: string): "short_steps" | "standard" | "research" | "final" {
    const t = (tier || "").toUpperCase();
    if (t === "SHORT_STEPS") return "short_steps";
    if (t === "RESEARCH") return "research";
    if (t === "FINAL") return "final";
    return "standard";
}

function parseNumberMaybe(v: string | number | null | undefined, integer: boolean): number | null {
    if (v === null || v === undefined || v === "") return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    return integer ? Math.trunc(n) : n;
}

function normalizeRoleValue(value: unknown): string {
    return String(value || "")
        .trim()
        .toLowerCase()
        .replace(/[\s-]+/g, "_");
}

function Section({
    title,
    children,
    tone,
}: {
    title: string;
    children: React.ReactNode;
    tone?: { section?: string; sectionHeader?: string; sectionTitle?: string };
}) {
    return (
        <section className={`rounded-2xl border bg-white shadow-sm overflow-hidden ${tone?.section || "border-slate-200"}`}>
            <header className={`px-6 py-4 border-b ${tone?.sectionHeader || "border-slate-200 bg-slate-50"}`}>
                <h3 className={`text-base tracking-[0.08em] font-extrabold uppercase ${tone?.sectionTitle || "text-slate-700"}`}>{title}</h3>
            </header>
            <div className="p-6">{children}</div>
        </section>
    );
}

function Field({
    label,
    children,
}: {
    label: string;
    children: React.ReactNode;
}) {
    return (
        <label className="block">
            <div className="text-sm font-bold text-slate-600 dark:text-slate-300 mb-2">{label}</div>
            {children}
        </label>
    );
}

export default function PromptBindingsPage() {
    const { pushToast } = useToast();
    const [items, setItems] = useState<Binding[]>([]);
    const [drafts, setDrafts] = useState<Record<string, DraftBinding>>({});
    const [selectedId, setSelectedId] = useState<string>("");
    const [reason, setReason] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [role, setRole] = useState("");
    const [promptOptions, setPromptOptions] = useState<PromptRegistryEntry[]>([]);
    const [schemaOptions, setSchemaOptions] = useState<SchemaRegistryEntry[]>([]);

    const normalizedRole = useMemo(() => normalizeRoleValue(role), [role]);
    const canEdit = !normalizedRole || normalizedRole === "admin" || normalizedRole === "superadmin" || normalizedRole === "super_admin";

    useEffect(() => {
        if (typeof window !== "undefined") {
            const rawRole = normalizeRoleValue(localStorage.getItem("user_role") || "");
            if (rawRole) {
                setRole(rawRole);
                return;
            }
            const token = localStorage.getItem("token") || "";
            if (token.includes(".")) {
                try {
                    const payload = JSON.parse(atob(token.split(".")[1] || ""));
                    const roleCandidates: unknown[] = [
                        payload?.role,
                        payload?.user_role,
                        payload?.user?.role,
                        Array.isArray(payload?.roles) ? payload.roles[0] : undefined,
                    ];
                    const tokenRole = roleCandidates
                        .map((v) => normalizeRoleValue(v))
                        .find((v) => Boolean(v)) || "";
                    if (tokenRole) {
                        setRole(tokenRole);
                        return;
                    }
                } catch {
                    // ignore malformed token payload
                }
            }
            setRole("");
        }
    }, []);

    const headers = useMemo(() => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const h: Record<string, string> = { "Content-Type": "application/json" };
        if (token) h.Authorization = `Bearer ${token}`;
        return h;
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [res, promptRes, schemaRes] = await Promise.all([
                fetchApi("/api/v1/admin/prompt_bindings?scope=all", { headers }),
                fetchApi("/api/v1/admin/prompt-registry/prompts?include_inactive=true", { headers }),
                fetchApi("/api/v1/admin/prompt-registry/schemas?include_inactive=true", { headers }),
            ]);

            if (!res.ok) throw new Error((await parseApiError(res)).message);
            if (!promptRes.ok) throw new Error((await parseApiError(promptRes)).message);
            if (!schemaRes.ok) throw new Error((await parseApiError(schemaRes)).message);

            const data = await res.json();
            const promptData: PromptRegistryEntry[] = await promptRes.json();
            const schemaData: SchemaRegistryEntry[] = await schemaRes.json();
            const rowsRaw: Binding[] = Array.isArray(data?.items) ? data.items : [];
            const rows: Binding[] = rowsRaw.map((row) => ({
                ...row,
                id: String(row.id),
                tier: String(row.tier || ""),
                mode: String(row.mode || ""),
                provider: String(row.provider || "openai"),
            }));
            setItems(rows);
            setDrafts(Object.fromEntries(rows.map((r) => [r.id, toDraft(r)])));
            const promptMap = new Map<string, PromptRegistryEntry>();
            for (const item of promptData || []) {
                if (!item?.prompt_id) continue;
                const prev = promptMap.get(item.prompt_id);
                if (!prev || Boolean(item.is_active) || Number(item.version || 0) > Number(prev.version || 0)) {
                    promptMap.set(item.prompt_id, item);
                }
            }
            const schemaMap = new Map<string, SchemaRegistryEntry>();
            for (const item of schemaData || []) {
                if (!item?.schema_id) continue;
                const prev = schemaMap.get(item.schema_id);
                if (!prev || Boolean(item.is_active) || Number(item.version || 0) > Number(prev.version || 0)) {
                    schemaMap.set(item.schema_id, item);
                }
            }
            setPromptOptions(Array.from(promptMap.values()).sort((a, b) => a.prompt_id.localeCompare(b.prompt_id)));
            setSchemaOptions(Array.from(schemaMap.values()).sort((a, b) => a.schema_id.localeCompare(b.schema_id)));
            if (rows.length > 0) {
                setSelectedId((prev) => (prev && rows.some((x) => String(x.id) === String(prev)) ? String(prev) : String(rows[0].id)));
            }
        } catch (err) {
            pushToast({ type: "error", title: "Failed to load", message: err instanceof Error ? err.message : "Unexpected error" });
        } finally {
            setLoading(false);
        }
    }, [headers, pushToast]);

    useEffect(() => {
        void load();
    }, [load]);

    const selected = items.find((x) => String(x.id) === String(selectedId)) || null;
    const draft = selected ? drafts[selected.id] : null;
    const activeCount = useMemo(() => items.filter((x) => Boolean(x.is_active)).length, [items]);
    const activeTone = toneForBinding(selected);
    const systemPromptOptions = useMemo(() => {
        const opts = promptOptions.filter((p) => String(p.role || "").toUpperCase() === "SYSTEM");
        return opts.length > 0 ? opts : promptOptions;
    }, [promptOptions]);

    const developerPromptOptions = useMemo(() => {
        const opts = promptOptions.filter((p) => String(p.role || "").toUpperCase() === "DEVELOPER");
        return opts.length > 0 ? opts : promptOptions;
    }, [promptOptions]);

    const updateDraft = (key: keyof DraftBinding, value: string | number | boolean | null) => {
        if (!draft) return;
        setDrafts((prev) => ({ ...prev, [draft.id]: { ...prev[draft.id], [key]: value } }));
    };

    const setFeature = (key: string, value: unknown) => {
        if (!draft) return;
        setDrafts((prev) => ({
            ...prev,
            [draft.id]: {
                ...prev[draft.id],
                features_obj: { ...asRecord(prev[draft.id].features_obj), [key]: value },
            },
        }));
    };

    const setMultiplier = (path: string[], value: unknown) => {
        if (!draft) return;
        setDrafts((prev) => {
            const curr = asRecord(prev[draft.id].multipliers_obj);
            const root = { ...curr };
            let cursor: Record<string, unknown> = root;
            for (let i = 0; i < path.length - 1; i += 1) {
                const step = path[i];
                const next = asRecord(cursor[step]);
                cursor[step] = { ...next };
                cursor = cursor[step] as Record<string, unknown>;
            }
            cursor[path[path.length - 1]] = value;
            return { ...prev, [draft.id]: { ...prev[draft.id], multipliers_obj: root } };
        });
    };

    const resetCurrent = () => {
        if (!selected) return;
        setDrafts((prev) => ({ ...prev, [selected.id]: toDraft(selected) }));
    };

    const saveCurrent = async () => {
        if (!selected || !draft) return;
        if (!canEdit) {
            pushToast({ type: "error", title: "Forbidden", message: "Only admin/superadmin can edit prompt bindings." });
            return;
        }
        if (!reason.trim()) {
            pushToast({ type: "error", title: "Reason required", message: "Please provide an audit reason." });
            return;
        }

        const payload: Record<string, unknown> = { reason: reason.trim() };

        const scalarKeys: Array<keyof Binding> = [
            "tier",
            "mode",
            "provider",
            "global_system_prompt_id",
            "developer_prompt_id",
            "output_schema_id",
            "is_active",
            "trim_strategy",
            ...numericKeys,
        ];

        for (const key of scalarKeys) {
            const prevVal = selected[key];
            const nextVal = draft[key as keyof DraftBinding];

            if (typeof prevVal === "boolean") {
                if (Boolean(nextVal) !== prevVal) payload[key] = Boolean(nextVal);
                continue;
            }

            if (numericKeys.includes(key)) {
                const prevNum = parseNumberMaybe(prevVal as number | null, intKeys.has(key));
                const nextNum = parseNumberMaybe(nextVal as string | number | null, intKeys.has(key));
                if (prevNum !== nextNum) payload[key] = nextNum;
                continue;
            }

            const prevStr = String(prevVal ?? "").trim();
            const nextStr = String(nextVal ?? "").trim();
            if (prevStr !== nextStr && nextStr !== "") payload[key] = nextStr;
        }

        if (JSON.stringify(draft.features_obj || {}) !== JSON.stringify(selected.features || {})) {
            payload.features = draft.features_obj || {};
        }
        if (JSON.stringify(draft.multipliers_obj || {}) !== JSON.stringify(selected.multipliers || {})) {
            payload.multipliers = draft.multipliers_obj || {};
        }

        if (Object.keys(payload).length === 1) {
            pushToast({ type: "info", title: "No changes", message: "No fields changed." });
            return;
        }

        setSaving(true);
        try {
            const res = await fetchApi(`/api/v1/admin/prompt_bindings/${selected.id}`, {
                method: "PATCH",
                headers,
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error((await parseApiError(res)).message);
            pushToast({ type: "success", title: "Saved", message: `${draft.tier} / ${draft.mode} updated.` });
            await load();
        } catch (err) {
            pushToast({ type: "error", title: "Save failed", message: err instanceof Error ? err.message : "Unexpected error" });
        } finally {
            setSaving(false);
        }
    };

    const features = draft ? asRecord(draft.features_obj) : {};
    const multipliers = draft ? asRecord(draft.multipliers_obj) : {};
    const credits = asRecord(multipliers.credits);
    const tKey = draft ? tierKey(draft.tier) : "standard";
    const solveTier = asRecord(asRecord(credits.solve)[tKey]);
    const verifyTier = asRecord(credits.verify);
    const attemptTier = asRecord(credits.attempt_fee);

    if (loading) {
        return <div className="p-8 text-slate-500">Loading prompt bindings...</div>;
    }

    return (
        <div className="p-6 max-w-6xl mx-auto space-y-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-xl font-bold text-slate-900 dark:text-white">Prompt Bindings</h1>
                <p className="text-sm text-slate-500">Configure prompt binding runtime, pricing, and feature gates for each tier.</p>
            </header>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                {activeCount === 0 && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                        No active prompt bindings detected. Solves may fail until at least one binding per tier is active.
                    </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="Binding">
                        <select
                            value={selectedId}
                            onChange={(e) => setSelectedId(e.target.value)}
                            className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100"
                        >
                            {items.map((b) => (
                                <option key={b.id} value={b.id}>
                                    {b.tier} / {b.mode} ({b.provider})
                                </option>
                            ))}
                        </select>
                    </Field>
                    <Field label="Audit Reason">
                        <input
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100"
                            placeholder="Reason is required before save"
                        />
                    </Field>
                </div>
                <div className="flex items-center justify-between">
                    <div className="text-xs text-slate-500">
                        Role: <span className="font-semibold uppercase">{normalizedRole || "unknown"}</span> · Last updated by {selected?.updated_by || "unknown"} · {items.length} bindings loaded
                        {!canEdit ? " · read-only" : ""}
                    </div>
                    <div className="flex gap-3">
                        <button onClick={resetCurrent} disabled={saving} className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-semibold">Reset</button>
                        <button onClick={() => void saveCurrent()} disabled={saving || !canEdit} className="px-5 py-2 rounded-lg bg-admin-primary text-white text-sm font-bold disabled:opacity-60">
                            {saving ? "Saving..." : "Save Changes"}
                        </button>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                    {items.map((b) => {
                        const tone = toneForBinding(b);
                        const isActive = String(b.id) === String(selectedId);
                        return (
                            <button
                                key={b.id}
                                type="button"
                                onClick={() => setSelectedId(String(b.id))}
                                className={`px-3 py-1 rounded-full border text-xs font-semibold transition ring-2 ${isActive ? tone.badgeActive : `${tone.badge} ring-transparent opacity-80 hover:opacity-100`}`}
                            >
                                {b.tier} / {b.mode} ({b.provider})
                            </button>
                        );
                    })}
                </div>
            </section>

            {!draft ? (
                <div className="text-slate-500 text-sm">No binding selected.</div>
            ) : (
                <>
                    <Section title="Binding Identity" tone={activeTone}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Field label="Tier">
                                <select value={draft.tier} onChange={(e) => updateDraft("tier", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    <option value="SHORT_STEPS">SHORT_STEPS</option>
                                    <option value="STANDARD">STANDARD</option>
                                    <option value="RESEARCH">RESEARCH</option>
                                    <option value="FINAL">FINAL</option>
                                </select>
                            </Field>
                            <Field label="Mode">
                                <select value={draft.mode} onChange={(e) => updateDraft("mode", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    {modeOptions.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                </select>
                            </Field>
                            <Field label="Provider">
                                <select value={draft.provider} onChange={(e) => updateDraft("provider", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    <option value="openai">OpenAI</option>
                                    <option value="ollama">Ollama</option>
                                </select>
                            </Field>
                            <Field label="Global System Prompt ID">
                                <select value={draft.global_system_prompt_id || ""} onChange={(e) => updateDraft("global_system_prompt_id", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    {!!draft.global_system_prompt_id && !systemPromptOptions.some((p) => p.prompt_id === draft.global_system_prompt_id) && (
                                        <option value={draft.global_system_prompt_id}>{draft.global_system_prompt_id} (current)</option>
                                    )}
                                    {systemPromptOptions.map((p) => (
                                        <option key={p.prompt_id} value={p.prompt_id}>
                                            {p.prompt_id} · v{p.version ?? 1}{p.is_active ? "" : " · inactive"}
                                        </option>
                                    ))}
                                </select>
                            </Field>
                            <Field label="Developer Prompt ID">
                                <select value={draft.developer_prompt_id || ""} onChange={(e) => updateDraft("developer_prompt_id", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    {!!draft.developer_prompt_id && !developerPromptOptions.some((p) => p.prompt_id === draft.developer_prompt_id) && (
                                        <option value={draft.developer_prompt_id}>{draft.developer_prompt_id} (current)</option>
                                    )}
                                    {developerPromptOptions.map((p) => (
                                        <option key={p.prompt_id} value={p.prompt_id}>
                                            {p.prompt_id} · v{p.version ?? 1}{p.is_active ? "" : " · inactive"}
                                        </option>
                                    ))}
                                </select>
                            </Field>
                            <Field label="Output Schema ID">
                                <select value={draft.output_schema_id || ""} onChange={(e) => updateDraft("output_schema_id", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    {!!draft.output_schema_id && !schemaOptions.some((s) => s.schema_id === draft.output_schema_id) && (
                                        <option value={draft.output_schema_id}>{draft.output_schema_id} (current)</option>
                                    )}
                                    {schemaOptions.map((s) => (
                                        <option key={s.schema_id} value={s.schema_id}>
                                            {s.schema_id} · v{s.version ?? 1}{s.is_active ? "" : " · inactive"}
                                        </option>
                                    ))}
                                </select>
                            </Field>
                            <Field label="Binding ID">
                                <input value={draft.id} disabled className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-slate-50 text-slate-600" />
                            </Field>
                            <Field label="Active">
                                <label className="inline-flex items-center gap-3 rounded-xl border border-slate-300 px-4 py-3 bg-white">
                                    <input type="checkbox" checked={Boolean(draft.is_active)} onChange={(e) => updateDraft("is_active", e.target.checked)} disabled={!canEdit} className="size-4" />
                                    <span className="text-sm font-semibold text-slate-700">{draft.is_active ? "Enabled" : "Disabled"}</span>
                                </label>
                            </Field>
                        </div>
                    </Section>

                    <Section title="Limits & Budgets" tone={activeTone}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Field label="Max Questions Allowed"><input value={asInput(draft.max_questions_allowed)} onChange={(e) => updateDraft("max_questions_allowed", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Required" /></Field>
                            <Field label="Max Input Tokens"><input value={asInput(draft.max_input_tokens)} onChange={(e) => updateDraft("max_input_tokens", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Auto" /></Field>
                            <Field label="Max Output Tokens"><input value={asInput(draft.max_output_tokens)} onChange={(e) => updateDraft("max_output_tokens", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Auto" /></Field>
                            <Field label="System Budget"><input value={asInput(draft.system_schema_budget_tokens)} onChange={(e) => updateDraft("system_schema_budget_tokens", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Auto" /></Field>
                            <Field label="Context Budget"><input value={asInput(draft.context_budget_tokens)} onChange={(e) => updateDraft("context_budget_tokens", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Auto" /></Field>
                        </div>
                    </Section>

                    <Section title="Inference Parameters" tone={activeTone}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Field label="Temperature"><input value={asInput(draft.temperature)} onChange={(e) => updateDraft("temperature", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Top P"><input value={asInput(draft.top_p)} onChange={(e) => updateDraft("top_p", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Timeout (ms)"><input value={asInput(draft.timeout_ms)} onChange={(e) => updateDraft("timeout_ms", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Trim Strategy">
                                <select value={draft.trim_strategy || ""} onChange={(e) => updateDraft("trim_strategy", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    {trimStrategyOptions.map((opt, i) => <option key={`trim-${i}-${opt || "null"}`} value={opt}>{opt || "(null)"}</option>)}
                                </select>
                            </Field>
                        </div>
                    </Section>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <Section title="Retry Logic" tone={activeTone}>
                            <div className="space-y-6">
                                <Field label="JSON Retry Max Output"><input value={asInput(draft.json_retry_max_output_tokens)} onChange={(e) => updateDraft("json_retry_max_output_tokens", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Auto" /></Field>
                                <Field label="Retry Attempts"><input value={asInput(draft.json_retry_max_attempts)} onChange={(e) => updateDraft("json_retry_max_attempts", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                                <Field label="Max Steps"><input value={asInput(draft.max_steps)} onChange={(e) => updateDraft("max_steps", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" placeholder="Auto" /></Field>
                            </div>
                        </Section>
                        <Section title="Plotting" tone={activeTone}>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <Field label="Points Cap"><input value={asInput(draft.plot_points_cap)} onChange={(e) => updateDraft("plot_points_cap", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                                <Field label="Traces Cap"><input value={asInput(draft.plot_traces_cap)} onChange={(e) => updateDraft("plot_traces_cap", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                                <Field label="Annotations Cap"><input value={asInput(draft.plot_annotations_cap)} onChange={(e) => updateDraft("plot_annotations_cap", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            </div>
                        </Section>
                    </div>

                    <Section title="Credit Pricing" tone={activeTone}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Field label="Solve Text Cost"><input value={asInput(draft.solve_text_cost)} onChange={(e) => updateDraft("solve_text_cost", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Solve Snap Image Cost"><input value={asInput(draft.solve_snap_image_cost)} onChange={(e) => updateDraft("solve_snap_image_cost", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Solve Snap PDF Cost"><input value={asInput(draft.solve_snap_pdf_cost)} onChange={(e) => updateDraft("solve_snap_pdf_cost", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Solve Voice Cost"><input value={asInput(draft.solve_voice_cost)} onChange={(e) => updateDraft("solve_voice_cost", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Verify Add-on Cost"><input value={asInput(draft.verify_addon_cost)} onChange={(e) => updateDraft("verify_addon_cost", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Plot Trigger Add-on Cost"><input value={asInput(draft.plot_addon_cost)} onChange={(e) => updateDraft("plot_addon_cost", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                        </div>
                    </Section>

                    <Section title="Feature Gates & Caps" tone={activeTone}>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                            <label className="flex items-center gap-3 text-base font-semibold text-slate-700"><input type="checkbox" checked={Boolean(features.allow_research)} onChange={(e) => setFeature("allow_research", e.target.checked)} disabled={!canEdit} className="size-4" />Allow Research</label>
                            <label className="flex items-center gap-3 text-base font-semibold text-slate-700"><input type="checkbox" checked={Boolean(features.allow_verify ?? true)} onChange={(e) => setFeature("allow_verify", e.target.checked)} disabled={!canEdit} className="size-4" />Allow Verify</label>
                            <label className="flex items-center gap-3 text-base font-semibold text-slate-700"><input type="checkbox" checked={Boolean(features.allow_plot ?? true)} onChange={(e) => setFeature("allow_plot", e.target.checked)} disabled={!canEdit} className="size-4" />Allow Plot</label>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Field label="Daily Credit Cap"><input value={asInput(features.daily_credit_cap as number | null)} onChange={(e) => setFeature("daily_credit_cap", parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="OCR Monthly Cap"><input value={asInput(features.ocr_monthly_cap as number | null)} onChange={(e) => setFeature("ocr_monthly_cap", parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Voice Monthly Cap"><input value={asInput(features.voice_monthly_cap as number | null)} onChange={(e) => setFeature("voice_monthly_cap", parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Generated Images Monthly Cap"><input value={asInput(features.generated_images_monthly_cap as number | null)} onChange={(e) => setFeature("generated_images_monthly_cap", parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Make It Right Monthly Cap"><input value={asInput(features.make_it_right_monthly_cap as number | null)} onChange={(e) => setFeature("make_it_right_monthly_cap", parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                        </div>
                    </Section>

                    <Section title="Multiplier Overrides" tone={activeTone}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Field label="Multiplier Text"><input value={asInput(solveTier.text as number | null)} onChange={(e) => setMultiplier(["credits", "solve", tKey, "text"], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Multiplier Snap Image"><input value={asInput(solveTier.snap_image as number | null)} onChange={(e) => setMultiplier(["credits", "solve", tKey, "snap_image"], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Multiplier Snap PDF"><input value={asInput(solveTier.snap_pdf as number | null)} onChange={(e) => setMultiplier(["credits", "solve", tKey, "snap_pdf"], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Multiplier Voice"><input value={asInput(solveTier.voice as number | null)} onChange={(e) => setMultiplier(["credits", "solve", tKey, "voice"], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Multiplier Verify"><input value={asInput(verifyTier[tKey] as number | null)} onChange={(e) => setMultiplier(["credits", "verify", tKey], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Plot Trigger Multiplier"><input value={asInput(credits.plot_trigger as number | null)} onChange={(e) => setMultiplier(["credits", "plot_trigger"], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Attempt Fee Multiplier"><input value={asInput(attemptTier[tKey] as number | null)} onChange={(e) => setMultiplier(["credits", "attempt_fee", tKey], parseNullableNumber(e.target.value))} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100" /></Field>
                            <Field label="Current Binding Mode">
                                <select value={draft.mode} onChange={(e) => updateDraft("mode", e.target.value)} disabled={!canEdit} className="w-full rounded-xl border border-slate-300 px-4 py-3 bg-white text-slate-900 placeholder-slate-400 disabled:text-slate-500 disabled:bg-slate-100">
                                    {modeOptions.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                </select>
                            </Field>
                        </div>
                    </Section>
                </>
            )}
        </div>
    );
}



