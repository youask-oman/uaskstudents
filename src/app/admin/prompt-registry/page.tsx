"use client";

import { useEffect, useMemo, useState } from "react";

interface PromptEntry {
    prompt_id: string;
    tier: string | null;
    mode: string;
    role: string;
    version: number;
    is_active: boolean;
    content?: string | null;
    updated_at: string;
    updated_by?: string | null;
}

const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:9000";

export default function AdminPromptRegistryPage() {
    const baseUrl = useMemo(() => DEFAULT_API_BASE_URL, []);
    const [prompts, setPrompts] = useState<PromptEntry[]>([]);
    const [selected, setSelected] = useState<PromptEntry | null>(null);
    const [versions, setVersions] = useState<PromptEntry[]>([]);
    const [editedContent, setEditedContent] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [creating, setCreating] = useState(false);
    const [newPrompt, setNewPrompt] = useState({
        prompt_id: "",
        tier: "NONE",
        mode: "SOLVE",
        role: "DEVELOPER",
        content: "",
    });
    const [error, setError] = useState<string | null>(null);

    const headers = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const h: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) {
            (h as Record<string, string>)["Content-Type"] = "application/json";
        }
        return h;
    };

    const loadPromptVersions = async (promptId: string, signal?: AbortSignal) => {
        const res = await fetch(
            `${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(promptId)}/versions`,
            { headers: headers(), signal }
        );
        if (!res.ok) throw new Error("Failed to load versions");
        const data: PromptEntry[] = await res.json();
        return data;
    };

    const refreshPromptDetails = async (promptId: string) => {
        const data = await loadPromptVersions(promptId);
        setVersions(data);
        const active = data.find((v) => v.is_active) || data[0] || null;
        setSelected(active);
        setEditedContent(active?.content ?? "");
        if (active) {
            setPrompts((prev) => {
                const next = prev.map((p) => (p.prompt_id === active.prompt_id ? active : p));
                return next.some((p) => p.prompt_id === active.prompt_id) ? next : [...next, active];
            });
        }
    };

    useEffect(() => {
        const controller = new AbortController();
        const load = async () => {
            try {
                setError(null);
                const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts?include_inactive=true`, { headers: headers(), signal: controller.signal });
                if (!res.ok) throw new Error("Failed to load prompts");
                const data: PromptEntry[] = await res.json();
                setPrompts(data);
                setSelected(data[0] || null);
            } catch (err) {
                if ((err as Error).name !== "AbortError") {
                    setError("Unable to load prompts.");
                }
            } finally {
                setLoading(false);
            }
        };
        load();
        return () => controller.abort();
    }, [baseUrl]);

    useEffect(() => {
        if (!selected) return;
        const controller = new AbortController();
        const loadVersions = async () => {
            try {
                setError(null);
                const data = await loadPromptVersions(selected.prompt_id, controller.signal);
                setVersions(data);
                const active = data.find((v) => v.is_active) || data[0] || null;
                setSelected(active);
                setEditedContent(active?.content ?? "");
            } catch (err) {
                if ((err as Error).name !== "AbortError") {
                    setError("Unable to load prompt versions.");
                }
            }
        };
        loadVersions();
        return () => controller.abort();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selected?.prompt_id, baseUrl]);

    const handleSave = async () => {
        if (!selected) return;
        setSaving(true);
        try {
            setError(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(selected.prompt_id)}/update`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    content: editedContent,
                    tier: selected.tier,
                    mode: selected.mode,
                    role: selected.role,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Save failed");
            }
            await refreshPromptDetails(selected.prompt_id);
        } catch (err) {
            setError((err as Error)?.message || "Unable to save prompt.");
        } finally {
            setSaving(false);
        }
    };

    const activateVersion = async (version: number) => {
        if (!selected) return;
        try {
            setError(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(selected.prompt_id)}/rollback`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    version,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) throw new Error("Activate failed");
            await refreshPromptDetails(selected.prompt_id);
        } catch (err) {
            setError((err as Error)?.message || "Unable to activate version.");
        }
    };

    const handleDeletePrompt = async () => {
        if (!selected) return;
        const promptId = selected.prompt_id;
        const confirmed = window.confirm(
            `Delete prompt "${promptId}" and all its versions? This cannot be undone.`
        );
        if (!confirmed) return;

        setDeleting(true);
        try {
            setError(null);
            const updatedBy = localStorage.getItem("user_name") || "admin";
            const qs = updatedBy ? `?updated_by=${encodeURIComponent(updatedBy)}` : "";
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(promptId)}${qs}`, {
                method: "DELETE",
                headers: headers(),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Delete failed");
            }

            const remaining = prompts.filter((p) => p.prompt_id !== promptId);
            setPrompts(remaining);
            const nextSelected = remaining[0] || null;
            setSelected(nextSelected);
            if (!nextSelected) {
                setVersions([]);
                setEditedContent("");
            }
        } catch (err) {
            setError((err as Error)?.message || "Unable to delete prompt.");
        } finally {
            setDeleting(false);
        }
    };

    const handleCreatePrompt = async () => {
        const promptId = newPrompt.prompt_id.trim();
        if (!promptId) {
            setError("Prompt ID is required.");
            return;
        }
        if (prompts.some((p) => p.prompt_id === promptId)) {
            setError("Prompt ID already exists. Select it from the list to update.");
            return;
        }

        setCreating(true);
        try {
            setError(null);
            const tierValue = newPrompt.tier === "NONE" ? null : newPrompt.tier;
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(promptId)}/update`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    content: newPrompt.content,
                    tier: tierValue,
                    mode: newPrompt.mode,
                    role: newPrompt.role,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Create failed");
            }

            const data: PromptEntry = await res.json();
            setPrompts((prev) =>
                [...prev, data].sort((a, b) => a.prompt_id.localeCompare(b.prompt_id))
            );
            setSelected(data);
            setEditedContent(data.content ?? "");
            setVersions([data]);
            setNewPrompt({
                prompt_id: "",
                tier: "NONE",
                mode: "SOLVE",
                role: "DEVELOPER",
                content: "",
            });
        } catch (err) {
            setError((err as Error)?.message || "Unable to create prompt.");
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="w-full p-6 xl:p-8 flex flex-col gap-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Prompt Registry</h1>
                <p className="text-sm text-slate-500">Manage system and developer prompts stored in the database.</p>
            </header>
            {error && <div className="rounded-lg border border-rose-200 bg-rose-50 text-rose-700 px-4 py-2 text-sm">{error}</div>}
            <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6 w-full">
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                    <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 mb-4 space-y-2">
                        <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-200">Create Prompt</h3>
                        <input
                            className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs"
                            placeholder="prompt_id"
                            value={newPrompt.prompt_id}
                            onChange={(e) => setNewPrompt({ ...newPrompt, prompt_id: e.target.value })}
                        />
                        <div className="grid grid-cols-3 gap-2">
                            <select
                                className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-2 text-xs"
                                value={newPrompt.tier}
                                onChange={(e) => setNewPrompt({ ...newPrompt, tier: e.target.value })}
                            >
                                <option value="NONE">NO_TIER</option>
                                <option value="FREE">FREE</option>
                                <option value="STANDARD">STANDARD</option>
                                <option value="RESEARCH">RESEARCH</option>
                                <option value="SHORT">SHORT</option>
                            </select>
                            <select
                                className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-2 text-xs"
                                value={newPrompt.mode}
                                onChange={(e) => setNewPrompt({ ...newPrompt, mode: e.target.value })}
                            >
                                <option value="SOLVE">SOLVE</option>
                                <option value="OCR_EXTRACT">OCR_EXTRACT</option>
                                <option value="VERIFY">VERIFY</option>
                                <option value="PLOT_TRIGGER">PLOT_TRIGGER</option>
                                <option value="PLOT_SPEC">PLOT_SPEC</option>
                            </select>
                            <select
                                className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-2 text-xs"
                                value={newPrompt.role}
                                onChange={(e) => setNewPrompt({ ...newPrompt, role: e.target.value })}
                            >
                                <option value="SYSTEM">SYSTEM</option>
                                <option value="DEVELOPER">DEVELOPER</option>
                                <option value="USER">USER</option>
                                <option value="INTERNAL">INTERNAL</option>
                            </select>
                        </div>
                        <textarea
                            className="w-full min-h-[84px] rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs font-mono"
                            placeholder="Prompt content"
                            value={newPrompt.content}
                            onChange={(e) => setNewPrompt({ ...newPrompt, content: e.target.value })}
                        />
                        <button
                            className="w-full px-3 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold disabled:opacity-60"
                            onClick={handleCreatePrompt}
                            disabled={creating}
                        >
                            {creating ? "Creating..." : "Create Prompt"}
                        </button>
                    </div>
                    <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Prompts</h2>
                    {loading ? (
                        <p className="text-xs text-slate-500">Loading...</p>
                    ) : (
                        <ul className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
                            {prompts.map((prompt) => (
                                <li key={prompt.prompt_id}>
                                    <button
                                        className={`w-full text-left px-3 py-2 rounded-lg text-sm border ${selected?.prompt_id === prompt.prompt_id
                                            ? "border-admin-primary bg-admin-primary/10 text-admin-primary"
                                            : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300"
                                            }`}
                                        onClick={() => setSelected(prompt)}
                                    >
                                        <div className="font-medium">{prompt.prompt_id}</div>
                                        <div className="text-[11px] text-slate-400">{prompt.mode} - {prompt.is_active ? "active" : "inactive"}</div>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                    {selected ? (
                        <>
                            <div className="flex items-center justify-between">
                                <div>
                                    <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{selected.prompt_id}</h2>
                                    <p className="text-xs text-slate-500">Mode: {selected.mode} - Role: {selected.role}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        className="px-4 py-2 rounded-lg bg-rose-600 text-white text-xs font-semibold disabled:opacity-60"
                                        onClick={handleDeletePrompt}
                                        disabled={deleting || saving}
                                    >
                                        {deleting ? "Deleting..." : "Delete Prompt"}
                                    </button>
                                    <button
                                        className="px-4 py-2 rounded-lg bg-admin-primary text-white text-xs font-semibold disabled:opacity-60"
                                        onClick={handleSave}
                                        disabled={saving || deleting}
                                    >
                                        {saving ? "Saving..." : "Save New Version"}
                                    </button>
                                </div>
                            </div>
                            <div className="mt-3 grid grid-cols-3 gap-2">
                                <select
                                    className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-2 text-xs"
                                    value={selected.tier ?? "NONE"}
                                    onChange={(e) =>
                                        setSelected({
                                            ...selected,
                                            tier: e.target.value === "NONE" ? null : e.target.value,
                                        })
                                    }
                                >
                                    <option value="NONE">NO_TIER</option>
                                    <option value="FREE">FREE</option>
                                    <option value="STANDARD">STANDARD</option>
                                    <option value="RESEARCH">RESEARCH</option>
                                    <option value="SHORT">SHORT</option>
                                </select>
                                <select
                                    className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-2 text-xs"
                                    value={selected.mode}
                                    onChange={(e) => setSelected({ ...selected, mode: e.target.value })}
                                >
                                    <option value="SOLVE">SOLVE</option>
                                    <option value="OCR_EXTRACT">OCR_EXTRACT</option>
                                    <option value="VERIFY">VERIFY</option>
                                    <option value="PLOT_TRIGGER">PLOT_TRIGGER</option>
                                    <option value="PLOT_SPEC">PLOT_SPEC</option>
                                </select>
                                <select
                                    className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-2 text-xs"
                                    value={selected.role}
                                    onChange={(e) => setSelected({ ...selected, role: e.target.value })}
                                >
                                    <option value="SYSTEM">SYSTEM</option>
                                    <option value="DEVELOPER">DEVELOPER</option>
                                    <option value="USER">USER</option>
                                    <option value="INTERNAL">INTERNAL</option>
                                </select>
                            </div>
                            <textarea
                                className="mt-4 w-full min-h-[320px] rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 p-3 text-xs font-mono text-slate-800 dark:text-slate-200"
                                value={editedContent}
                                onChange={(e) => setEditedContent(e.target.value)}
                            />
                            <div className="mt-4">
                                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">Version History</h3>
                                <div className="space-y-2">
                                    {versions.map((v) => (
                                        <div key={`${v.prompt_id}-${v.version}`} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs">
                                            <div className="text-slate-600 dark:text-slate-300">
                                                v{v.version} {v.is_active ? "(active)" : ""}
                                            </div>
                                            {!v.is_active && (
                                                <button
                                                    className="px-3 py-1 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200"
                                                    onClick={() => activateVersion(v.version)}
                                                >
                                                    Activate
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    ) : (
                        <p className="text-sm text-slate-500">Select a prompt to edit.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
