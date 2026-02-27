'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

type PromptEntry = {
    id: string;
    key: string;
    version: number;
    updated_at: string | null;
    mode?: string;
    role?: string;
};

type SchemaEntry = {
    id: string;
    key: string;
    version: number;
    updated_at: string | null;
    name?: string | null;
};

type OcrConfig = {
    local_engine_enabled: boolean;
    openai_engine_enabled: boolean;
    glm_ocr_engine_enabled: boolean;
    glm_ocr_model: string;
    openai_model: string;
    openai_system_prompt_key: string;
    openai_schema_key: string;
    dedupe_window_hours: number;
    ocr_hold_ttl_minutes: number;
    rate_limit_extract_per_min: number;
    local_ocr_credit: number;
    openai_ocr_credit: number;
    glm_ocr_credit: number;
    solve_credit: number;
};

type ConfigMeta = {
    version_id: number | null;
    version: number | null;
    updated_at: string | null;
    updated_by_user_id: number | null;
};

type ConfigHistory = {
    id: number;
    version: number;
    created_at: string;
    created_by: number;
    change_msg: string;
};

export default function AdminOcrConfigurationPage() {
    const { token } = useAuth();
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000';

    const [config, setConfig] = useState<OcrConfig | null>(null);
    const [initialConfig, setInitialConfig] = useState<OcrConfig | null>(null);
    const [meta, setMeta] = useState<ConfigMeta | null>(null);
    const [history, setHistory] = useState<ConfigHistory[]>([]);
    const [prompts, setPrompts] = useState<PromptEntry[]>([]);
    const [schemas, setSchemas] = useState<SchemaEntry[]>([]);
    const [resolvedPrompt, setResolvedPrompt] = useState<PromptEntry | null>(null);
    const [resolvedSchema, setResolvedSchema] = useState<SchemaEntry | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [reason, setReason] = useState('');

    const getErrorMessage = (err: unknown, fallback: string) => {
        if (err instanceof Error) return err.message;
        return fallback;
    };

    const fetchConfig = useCallback(async () => {
        if (!token) return;
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/admin/ocr-configuration`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data?.detail || 'Failed to load OCR configuration');
            }
            const data = await res.json();
            setConfig(data.config);
            setInitialConfig(data.config);
            setMeta(data.meta);
            setHistory(data.history || []);
            setPrompts(data.prompt_templates || []);
            setSchemas(data.json_schemas || []);
            setResolvedPrompt(data.resolved?.prompt_template || null);
            setResolvedSchema(data.resolved?.json_schema || null);
        } catch (err: unknown) {
            setError(getErrorMessage(err, 'Failed to load OCR configuration'));
        } finally {
            setLoading(false);
        }
    }, [API_BASE, token]);

    useEffect(() => {
        fetchConfig();
    }, [fetchConfig]);

    const updateField = <K extends keyof OcrConfig>(key: K, value: OcrConfig[K]) => {
        setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
    };

    const validPromptKeys = useMemo(() => new Set(prompts.map((p) => p.key)), [prompts]);
    const validSchemaKeys = useMemo(() => new Set(schemas.map((s) => s.key)), [schemas]);
    const promptKeyValid = useMemo(
        () => !config?.openai_engine_enabled || (Boolean(config?.openai_system_prompt_key) && validPromptKeys.has(config?.openai_system_prompt_key || "")),
        [config, validPromptKeys]
    );
    const schemaKeyValid = useMemo(
        () => !config?.openai_engine_enabled || (Boolean(config?.openai_schema_key) && validSchemaKeys.has(config?.openai_schema_key || "")),
        [config, validSchemaKeys]
    );
    const hasChanges = useMemo(() => {
        if (!config || !initialConfig) return false;
        return JSON.stringify(config) !== JSON.stringify(initialConfig);
    }, [config, initialConfig]);

    const openAiRelevantChanged = useMemo(() => {
        if (!config || !initialConfig) return false;
        return (
            config.openai_engine_enabled !== initialConfig.openai_engine_enabled ||
            config.openai_model !== initialConfig.openai_model ||
            config.openai_system_prompt_key !== initialConfig.openai_system_prompt_key ||
            config.openai_schema_key !== initialConfig.openai_schema_key
        );
    }, [config, initialConfig]);

    const requiresOpenAiKeyValidation = useMemo(
        () => Boolean(config?.openai_engine_enabled) && openAiRelevantChanged,
        [config, openAiRelevantChanged]
    );

    const canSave = useMemo(
        () =>
            Boolean(reason.trim()) &&
            Boolean(config) &&
            hasChanges &&
            (!requiresOpenAiKeyValidation || (promptKeyValid && schemaKeyValid)),
        [reason, config, hasChanges, requiresOpenAiKeyValidation, promptKeyValid, schemaKeyValid]
    );

    const handleSave = async () => {
        if (!config) return;
        if (!reason.trim()) {
            setError('Reason is required to save changes.');
            return;
        }
        setSaving(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/admin/ocr-configuration`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ ...config, reason }),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data?.detail || 'Failed to update configuration');
            }
            setReason('');
            await fetchConfig();
        } catch (err: unknown) {
            setError(getErrorMessage(err, 'Failed to update configuration'));
        } finally {
            setSaving(false);
        }
    };

    const handleActivate = async (versionId: number) => {
        if (!reason.trim()) {
            setError('Reason is required to activate a configuration.');
            return;
        }
        setSaving(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/admin/ocr-configuration/activate/${versionId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ reason }),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data?.detail || 'Failed to activate configuration');
            }
            setReason('');
            await fetchConfig();
        } catch (err: unknown) {
            setError(getErrorMessage(err, 'Failed to activate configuration'));
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    if (!config) {
        return <div className="p-8 text-red-600">Failed to load OCR configuration.</div>;
    }

    return (
        <div className="p-8 max-w-5xl mx-auto space-y-8">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">OCR Configuration</h1>
                <p className="text-sm text-slate-500">Manage OCR engines, prompts, schemas, and billing rules.</p>
            </header>

            {error && (
                <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-semibold">Active Configuration</h2>
                        <p className="text-sm text-slate-500">
                            Version {meta?.version ?? '-'} {meta?.updated_at ? `Â· Updated ${new Date(meta.updated_at).toLocaleString()}` : ''}
                        </p>
                    </div>
                    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">ACTIVE</span>
                </div>
                {(!promptKeyValid || !schemaKeyValid) && (
                    <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                        OCR prompt/schema keys are not valid against active registry options. Pick valid keys before saving.
                    </div>
                )}
            </section>

            <section className="grid gap-6 md:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    <h3 className="text-base font-semibold">Engines</h3>
                    <label className="flex items-center justify-between">
                        <span className="text-sm text-slate-600">Local Pix2Text Enabled</span>
                        <input
                            type="checkbox"
                            checked={config.local_engine_enabled}
                            onChange={(e) => updateField('local_engine_enabled', e.target.checked)}
                        />
                    </label>
                    <label className="flex items-center justify-between">
                        <span className="text-sm text-slate-600">OpenAI OCR Enabled</span>
                        <input
                            type="checkbox"
                            checked={config.openai_engine_enabled}
                            onChange={(e) => updateField('openai_engine_enabled', e.target.checked)}
                        />
                    </label>
                    <label className="flex items-center justify-between">
                        <span className="text-sm text-slate-600">GLM OCR (Ollama) Enabled</span>
                        <input
                            type="checkbox"
                            checked={config.glm_ocr_engine_enabled}
                            onChange={(e) => updateField('glm_ocr_engine_enabled', e.target.checked)}
                        />
                    </label>
                    <div className="space-y-2">
                        <label className="text-sm text-slate-600">GLM OCR Model</label>
                        <input
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.glm_ocr_model}
                            onChange={(e) => updateField('glm_ocr_model', e.target.value)}
                        />
                    </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    <h3 className="text-base font-semibold">OpenAI Settings</h3>
                    <div className="space-y-2">
                        <label className="text-sm text-slate-600">Model</label>
                        <input
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.openai_model}
                            onChange={(e) => updateField('openai_model', e.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm text-slate-600">System Prompt</label>
                        <select
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.openai_system_prompt_key}
                            onChange={(e) => updateField('openai_system_prompt_key', e.target.value)}
                        >
                            {prompts.map((prompt) => (
                                <option key={prompt.id} value={prompt.key}>
                                    {prompt.key} (v{prompt.version})
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm text-slate-600">Schema</label>
                        <select
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.openai_schema_key}
                            onChange={(e) => updateField('openai_schema_key', e.target.value)}
                        >
                            {schemas.map((schema) => (
                                <option key={schema.id} value={schema.key}>
                                    {schema.key} {schema.name ? `(${schema.name})` : ''} (v{schema.version})
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    <h3 className="text-base font-semibold">Billing Credits</h3>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">Local OCR Credits</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.local_ocr_credit}
                            onChange={(e) => updateField('local_ocr_credit', Number(e.target.value))}
                        />
                    </label>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">OpenAI OCR Credits</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.openai_ocr_credit}
                            onChange={(e) => updateField('openai_ocr_credit', Number(e.target.value))}
                        />
                    </label>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">GLM OCR Credits</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.glm_ocr_credit}
                            onChange={(e) => updateField('glm_ocr_credit', Number(e.target.value))}
                        />
                    </label>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">Solve Credits</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.solve_credit}
                            onChange={(e) => updateField('solve_credit', Number(e.target.value))}
                        />
                    </label>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    <h3 className="text-base font-semibold">Anti-Abuse</h3>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">Dedup Window (hours)</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.dedupe_window_hours}
                            onChange={(e) => updateField('dedupe_window_hours', Number(e.target.value))}
                        />
                    </label>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">OCR Hold TTL (minutes)</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.ocr_hold_ttl_minutes}
                            onChange={(e) => updateField('ocr_hold_ttl_minutes', Number(e.target.value))}
                        />
                    </label>
                    <label className="space-y-1 block">
                        <span className="text-sm text-slate-600">Extract Rate Limit / min</span>
                        <input
                            type="number"
                            min={1}
                            className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                            value={config.rate_limit_extract_per_min}
                            onChange={(e) => updateField('rate_limit_extract_per_min', Number(e.target.value))}
                        />
                    </label>
                </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <h3 className="text-base font-semibold">Resolved Prompt / Schema</h3>
                <div className="grid gap-4 md:grid-cols-2 text-sm">
                    <div>
                        <p className="text-slate-500">Prompt</p>
                        <p className="font-medium">{resolvedPrompt?.key || 'Not resolved'}</p>
                        <p className="text-xs text-slate-400">v{resolvedPrompt?.version ?? '-'}</p>
                    </div>
                    <div>
                        <p className="text-slate-500">Schema</p>
                        <p className="font-medium">{resolvedSchema?.key || 'Not resolved'}</p>
                        <p className="text-xs text-slate-400">v{resolvedSchema?.version ?? '-'}</p>
                    </div>
                </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <h3 className="text-base font-semibold">Save / Activate</h3>
                <div className="space-y-2">
                    <label className="text-sm text-slate-600">Reason (required)</label>
                    <input
                        className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Why are you changing OCR settings?"
                    />
                </div>
                <div className="flex gap-3">
                    <button
                        className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                        onClick={handleSave}
                        disabled={!canSave || saving}
                    >
                        {saving ? 'Saving...' : 'Save Configuration'}
                    </button>
                </div>
                {!canSave && config && (
                    <p className="text-xs text-slate-500">
                        Save is disabled until you provide a reason and make at least one change. OpenAI prompt/schema keys are only required when changing OpenAI settings while OpenAI OCR is enabled.
                    </p>
                )}
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <h3 className="text-base font-semibold">History</h3>
                <div className="space-y-3">
                    {history.length === 0 && <p className="text-sm text-slate-500">No history yet.</p>}
                    {history.map((entry) => (
                        <div key={entry.id} className="flex items-center justify-between border-b border-slate-100 pb-3">
                            <div>
                                <p className="text-sm font-medium">Version {entry.version}</p>
                                <p className="text-xs text-slate-500">{entry.change_msg}</p>
                                <p className="text-xs text-slate-400">{new Date(entry.created_at).toLocaleString()}</p>
                            </div>
                            <button
                                className="rounded border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 disabled:opacity-50"
                                onClick={() => handleActivate(entry.id)}
                                disabled={saving}
                            >
                                Activate
                            </button>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}

