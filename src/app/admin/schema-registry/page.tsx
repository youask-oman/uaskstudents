"use client";

import { useEffect, useMemo, useState } from "react";

interface SchemaEntry {
    schema_id: string;
    version: number;
    is_active: boolean;
    updated_at: string;
    updated_by?: string | null;
    content?: Record<string, unknown>;
}

const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export default function AdminSchemaRegistryPage() {
    const baseUrl = useMemo(() => DEFAULT_API_BASE_URL, []);
    const [schemas, setSchemas] = useState<SchemaEntry[]>([]);
    const [selected, setSelected] = useState<SchemaEntry | null>(null);
    const [versions, setVersions] = useState<SchemaEntry[]>([]);
    const [editedContent, setEditedContent] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [creating, setCreating] = useState(false);
    const [newSchemaId, setNewSchemaId] = useState("");
    const [newSchemaContent, setNewSchemaContent] = useState('{\n  "type": "object",\n  "properties": {}\n}');
    const [error, setError] = useState<string | null>(null);

    const headers = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const h: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) (h as Record<string, string>)["Content-Type"] = "application/json";
        return h;
    };

    const loadSchemaVersions = async (schemaId: string, signal?: AbortSignal) => {
        const res = await fetch(
            `${baseUrl}/api/v1/admin/prompt-registry/schemas/${encodeURIComponent(schemaId)}/versions`,
            { headers: headers(), signal }
        );
        if (!res.ok) throw new Error("Failed to load versions");
        const data: SchemaEntry[] = await res.json();
        return data;
    };

    const refreshSchemaDetails = async (schemaId: string) => {
        const data = await loadSchemaVersions(schemaId);
        setVersions(data);
        const active = data.find((v) => v.is_active) || data[0] || null;
        setSelected(active);
        setEditedContent(active?.content ? JSON.stringify(active.content, null, 2) : "");
        if (active) {
            setSchemas((prev) => {
                const next = prev.map((s) => (s.schema_id === active.schema_id ? active : s));
                return next.some((s) => s.schema_id === active.schema_id) ? next : [...next, active];
            });
        }
    };

    useEffect(() => {
        const controller = new AbortController();
        const load = async () => {
            try {
                setError(null);
                const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/schemas?include_inactive=true`, { headers: headers(), signal: controller.signal });
                if (!res.ok) throw new Error("Failed to load schemas");
                const data: SchemaEntry[] = await res.json();
                setSchemas(data);
                setSelected(data[0] || null);
            } catch (err) {
                if ((err as Error).name !== "AbortError") setError("Unable to load schemas.");
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
                const data = await loadSchemaVersions(selected.schema_id, controller.signal);
                setVersions(data);
                const active = data.find((v) => v.is_active) || data[0] || null;
                setSelected(active);
                setEditedContent(active?.content ? JSON.stringify(active.content, null, 2) : "");
            } catch (err) {
                if ((err as Error).name !== "AbortError") setError("Unable to load schema versions.");
            }
        };
        loadVersions();
        return () => controller.abort();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selected?.schema_id, baseUrl]);

    const handleSave = async () => {
        if (!selected) return;
        setSaving(true);
        try {
            setError(null);
            const parsed = JSON.parse(editedContent);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/schemas/${encodeURIComponent(selected.schema_id)}/update`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    content: parsed,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Save failed");
            }
            await refreshSchemaDetails(selected.schema_id);
        } catch (err) {
            setError((err as Error)?.message || "Unable to save schema. Ensure the JSON is valid Draft 2020-12.");
        } finally {
            setSaving(false);
        }
    };

    const activateVersion = async (version: number) => {
        if (!selected) return;
        try {
            setError(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/schemas/${encodeURIComponent(selected.schema_id)}/rollback`, {
                method: "POST",
                headers: headers(true),
                body: JSON.stringify({
                    version,
                    updated_by: localStorage.getItem("user_name") || "admin",
                }),
            });
            if (!res.ok) throw new Error("Activate failed");
            await refreshSchemaDetails(selected.schema_id);
        } catch (err) {
            setError((err as Error)?.message || "Unable to activate schema version.");
        }
    };

    const handleDeleteSchema = async () => {
        if (!selected) return;
        const schemaId = selected.schema_id;
        const confirmed = window.confirm(
            `Delete schema "${schemaId}" and all its versions? This cannot be undone.`
        );
        if (!confirmed) return;

        setDeleting(true);
        try {
            setError(null);
            const updatedBy = localStorage.getItem("user_name") || "admin";
            const qs = updatedBy ? `?updated_by=${encodeURIComponent(updatedBy)}` : "";
            const res = await fetch(`${baseUrl}/api/v1/admin/prompt-registry/schemas/${encodeURIComponent(schemaId)}${qs}`, {
                method: "DELETE",
                headers: headers(),
            });
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Delete failed");
            }

            const remaining = schemas.filter((schema) => schema.schema_id !== schemaId);
            setSchemas(remaining);
            const nextSelected = remaining[0] || null;
            setSelected(nextSelected);
            if (!nextSelected) {
                setVersions([]);
                setEditedContent("");
            }
        } catch (err) {
            setError((err as Error)?.message || "Unable to delete schema.");
        } finally {
            setDeleting(false);
        }
    };

    const handleCreateSchema = async () => {
        const schemaId = newSchemaId.trim();
        if (!schemaId) {
            setError("Schema ID is required.");
            return;
        }
        if (schemas.some((s) => s.schema_id === schemaId)) {
            setError("Schema ID already exists. Select it from the list to update.");
            return;
        }

        setCreating(true);
        try {
            setError(null);
            const parsed = JSON.parse(newSchemaContent);
            const res = await fetch(
                `${baseUrl}/api/v1/admin/prompt-registry/schemas/${encodeURIComponent(schemaId)}/update`,
                {
                    method: "POST",
                    headers: headers(true),
                    body: JSON.stringify({
                        content: parsed,
                        updated_by: localStorage.getItem("user_name") || "admin",
                    }),
                }
            );
            if (!res.ok) {
                const payload = await res.json().catch(() => null);
                throw new Error(payload?.detail || "Create failed");
            }

            const data: SchemaEntry = await res.json();
            setSchemas((prev) => [...prev, data].sort((a, b) => a.schema_id.localeCompare(b.schema_id)));
            setSelected(data);
            setVersions([data]);
            setEditedContent(data.content ? JSON.stringify(data.content, null, 2) : "");
            setNewSchemaId("");
            setNewSchemaContent('{\n  "type": "object",\n  "properties": {}\n}');
        } catch (err) {
            setError((err as Error)?.message || "Unable to create schema.");
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="w-full p-6 xl:p-8 flex flex-col gap-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Schema Registry</h1>
                <p className="text-sm text-slate-500">Manage JSON schemas stored in the database.</p>
            </header>
            {error && <div className="rounded-lg border border-rose-200 bg-rose-50 text-rose-700 px-4 py-2 text-sm">{error}</div>}
            <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6 w-full">
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                    <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 mb-4 space-y-2">
                        <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-200">Create Schema</h3>
                        <input
                            className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs"
                            placeholder="schema_id"
                            value={newSchemaId}
                            onChange={(e) => setNewSchemaId(e.target.value)}
                        />
                        <textarea
                            className="w-full min-h-[100px] rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs font-mono"
                            placeholder="Schema JSON"
                            value={newSchemaContent}
                            onChange={(e) => setNewSchemaContent(e.target.value)}
                        />
                        <button
                            className="w-full px-3 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold disabled:opacity-60"
                            onClick={handleCreateSchema}
                            disabled={creating}
                        >
                            {creating ? "Creating..." : "Create Schema"}
                        </button>
                    </div>
                    <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Schemas</h2>
                    {loading ? (
                        <p className="text-xs text-slate-500">Loading...</p>
                    ) : (
                        <ul className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
                            {schemas.map((schema) => (
                                <li key={schema.schema_id}>
                                    <button
                                        className={`w-full text-left px-3 py-2 rounded-lg text-sm border ${selected?.schema_id === schema.schema_id
                                                ? "border-admin-primary bg-admin-primary/10 text-admin-primary"
                                                : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300"
                                            }`}
                                        onClick={() => setSelected(schema)}
                                    >
                                        <div className="font-medium">{schema.schema_id}</div>
                                        <div className="text-[11px] text-slate-400">{schema.is_active ? "active" : "inactive"}</div>
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
                                    <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{selected.schema_id}</h2>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        className="px-4 py-2 rounded-lg bg-rose-600 text-white text-xs font-semibold disabled:opacity-60"
                                        onClick={handleDeleteSchema}
                                        disabled={deleting || saving}
                                    >
                                        {deleting ? "Deleting..." : "Delete Schema"}
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
                            <textarea
                                className="mt-4 w-full min-h-[320px] rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 p-3 text-xs font-mono text-slate-800 dark:text-slate-200"
                                value={editedContent}
                                onChange={(e) => setEditedContent(e.target.value)}
                            />
                            <div className="mt-4">
                                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">Version History</h3>
                                <div className="space-y-2">
                                    {versions.map((v) => (
                                        <div key={`${v.schema_id}-${v.version}`} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs">
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
                        <p className="text-sm text-slate-500">Select a schema to edit.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
