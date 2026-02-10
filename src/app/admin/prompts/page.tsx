"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type RegistryPromptItem = {
    prompt_id: string;
    tier: string | null;
    mode: string;
    role: string;
    version: number;
    is_active: boolean;
    content?: string | null;
    updated_at: string;
    updated_by?: string | null;
};

export default function AdminPromptsPage() {
    const { pushToast } = useToast();
    const baseUrl = useMemo(() => API_BASE_URL, []);
    const [prompts, setPrompts] = useState<RegistryPromptItem[]>([]);
    const [selectedPromptId, setSelectedPromptId] = useState<string>("");
    const [versions, setVersions] = useState<RegistryPromptItem[]>([]);
    const [selectedVersion, setSelectedVersion] = useState<RegistryPromptItem | null>(null);
    const [editedContent, setEditedContent] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const getAuthHeaders = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) {
            (headers as Record<string, string>)["Content-Type"] = "application/json";
        }
        return headers;
    };

    useEffect(() => {
        const controller = new AbortController();
        const loadPrompts = async () => {
            try {
                setErrorMessage(null);
                const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts`, {
                    headers: getAuthHeaders(),
                    signal: controller.signal,
                });
                if (!res.ok) throw new Error("Unable to load prompt registry entries.");
                const data = await res.json();
                const parsed: RegistryPromptItem[] = Array.isArray(data) ? data : [];
                setPrompts(parsed);
                if (parsed.length > 0) {
                    setSelectedPromptId(parsed[0].prompt_id);
                }
            } catch (err) {
                if ((err as Error).name === "AbortError") return;
                console.error(err);
                setErrorMessage("Unable to load prompt registry entries. Please refresh.");
            } finally {
                setIsLoading(false);
            }
        };

        loadPrompts();
        return () => controller.abort();
    }, [baseUrl]);

    useEffect(() => {
        if (!selectedPromptId) return;

        const controller = new AbortController();
        const loadVersions = async () => {
            try {
                setErrorMessage(null);
                const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(selectedPromptId)}/versions`, {
                    headers: getAuthHeaders(),
                    signal: controller.signal,
                });
                if (!res.ok) throw new Error("Unable to load prompt versions.");
                const data = await res.json();
                const parsed: RegistryPromptItem[] = Array.isArray(data) ? data : [];
                setVersions(parsed);
                const active = parsed.find((v) => v.is_active) || parsed[0] || null;
                setSelectedVersion(active);
                setEditedContent(active?.content || "");
            } catch (err) {
                if ((err as Error).name === "AbortError") return;
                console.error(err);
                setErrorMessage("Unable to load prompt versions. Please refresh.");
            }
        };

        loadVersions();
        return () => controller.abort();
    }, [selectedPromptId, baseUrl]);

    const refreshVersions = async () => {
        if (!selectedPromptId) return;
        const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(selectedPromptId)}/versions`, {
            headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error("Unable to refresh prompt versions.");
        const parsed = (await res.json()) as RegistryPromptItem[];
        setVersions(parsed);
        const active = parsed.find((v) => v.is_active) || parsed[0] || null;
        setSelectedVersion(active);
        setEditedContent(active?.content || "");
    };

    const handleSaveVersion = async () => {
        if (!selectedPromptId || !selectedVersion) return;
        setIsSaving(true);
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(selectedPromptId)}/update`, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    content: editedContent,
                    tier: selectedVersion.tier,
                    mode: selectedVersion.mode,
                    role: selectedVersion.role,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Save failed",
                    message: err.message,
                    requestId: err.requestId,
                });
                throw new Error("Failed to save prompt version.");
            }
            await refreshVersions();
            pushToast({
                type: "success",
                title: "Prompt version saved",
                message: "New version stored successfully.",
            });
        } catch (err) {
            console.error(err);
            setErrorMessage("Failed to save prompt version.");
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeploy = async () => {
        if (!selectedPromptId || !selectedVersion) return;
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/prompts/${encodeURIComponent(selectedPromptId)}/rollback`, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    version: selectedVersion.version,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Activation failed",
                    message: err.message,
                    requestId: err.requestId,
                });
                throw new Error("Failed to activate selected version.");
            }
            await refreshVersions();
            pushToast({
                type: "success",
                title: "Prompt activated",
                message: "Selected version is now active.",
            });
        } catch (err) {
            console.error(err);
            setErrorMessage("Failed to activate selected version.");
        }
    };

    if (isLoading) return <div className="p-8 text-slate-400">Loading prompt registry...</div>;

    return (
        <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white dark:bg-[#101622]">
            <aside className="w-72 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-[#101622] flex flex-col">
                <div className="p-4 border-b border-slate-200 dark:border-slate-800">
                    <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Prompt Registry</h3>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1 no-scrollbar">
                    {prompts.map((p) => (
                        <button
                            key={`${p.prompt_id}-${p.mode}-${p.role}`}
                            onClick={() => setSelectedPromptId(p.prompt_id)}
                            className={`w-full text-left px-3 py-2 rounded-lg transition ${selectedPromptId === p.prompt_id ? "bg-admin-primary/20 text-slate-900 dark:text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"}`}
                        >
                            <div className="text-xs font-black tracking-wide">{p.prompt_id}</div>
                            <div className="text-[10px] uppercase opacity-70">{p.role} | {p.mode} {p.tier ? `| ${p.tier}` : ""}</div>
                        </button>
                    ))}
                </div>
            </aside>

            <main className="flex-1 flex flex-col bg-slate-50 dark:bg-[#1a1f29]">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                    {errorMessage && <div className="mb-3 rounded-lg border border-rose-400/30 bg-rose-500/10 px-4 py-2 text-xs text-rose-300">{errorMessage}</div>}
                    <div className="flex items-end justify-between gap-4">
                        <div>
                            <h1 className="text-2xl font-black text-slate-900 dark:text-white">{selectedPromptId || "Prompt"}</h1>
                            <p className="text-xs text-slate-500">Registry-backed prompts only</p>
                        </div>
                        <div className="flex gap-2">
                            <select
                                className="h-9 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-bold px-3"
                                value={selectedVersion?.version || ""}
                                onChange={(e) => {
                                    const v = versions.find((x) => x.version === Number(e.target.value)) || null;
                                    setSelectedVersion(v);
                                    setEditedContent(v?.content || "");
                                }}
                            >
                                {versions.map((v) => (
                                    <option key={`${v.prompt_id}-${v.version}`} value={v.version}>
                                        v{v.version}{v.is_active ? " (ACTIVE)" : ""}
                                    </option>
                                ))}
                            </select>
                            <button onClick={handleSaveVersion} disabled={isSaving} className="h-9 px-4 rounded-lg bg-slate-800 text-white text-xs font-bold disabled:opacity-50">
                                {isSaving ? "Saving..." : "Save New Version"}
                            </button>
                            <button onClick={handleDeploy} className="h-9 px-4 rounded-lg bg-admin-primary text-white text-xs font-bold">
                                Activate Selected
                            </button>
                        </div>
                    </div>
                </div>

                <div className="flex-1 p-6">
                    <textarea
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        className="w-full h-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl p-4 font-mono text-sm text-slate-900 dark:text-slate-200"
                        placeholder="Prompt content"
                    />
                </div>
            </main>
        </div>
    );
}
