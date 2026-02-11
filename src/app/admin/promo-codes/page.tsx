"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type PromoCode = {
    id: number;
    code: string;
    discount_percent: number;
    valid_from?: string | null;
    valid_until?: string | null;
    is_active: boolean;
    max_uses?: number | null;
    current_uses?: number | null;
    created_at?: string | null;
};

export default function PromoCodesPage() {
    const { pushToast } = useToast();
    const [codes, setCodes] = useState<PromoCode[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editForm, setEditForm] = useState({
        discount_percent: 0,
        valid_until: "",
        max_uses: "",
        is_active: true,
    });
    const [form, setForm] = useState({
        code: "",
        discount_percent: 10,
        valid_until: "",
        max_uses: "",
        is_active: true,
    });

    const fetchCodes = async () => {
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const res = await fetch(`${API_BASE_URL}/api/admin/promo-codes`, {
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = await res.json();
            setCodes(Array.isArray(json) ? json : []);
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Failed to load promo codes",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

    useEffect(() => {
        fetchCodes();
    }, []);

    const startEdit = (code: PromoCode) => {
        setEditingId(code.id);
        setEditForm({
            discount_percent: code.discount_percent,
            valid_until: code.valid_until ? code.valid_until.slice(0, 10) : "",
            max_uses: code.max_uses ? String(code.max_uses) : "",
            is_active: code.is_active,
        });
    };

    const clearEdit = () => {
        setEditingId(null);
    };

    const updatePromo = async (promoId: number, updates: Record<string, unknown>) => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const res = await fetch(`${API_BASE_URL}/api/admin/promo-codes/${promoId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify(updates),
        });
        if (!res.ok) {
            const err = await parseApiError(res);
            throw new Error(err.message);
        }
    };

    const handleCreate = async () => {
        if (!form.code.trim()) {
            pushToast({ type: "error", title: "Missing code", message: "Promo code is required." });
            return;
        }
        setLoading(true);
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const payload: Record<string, unknown> = {
                code: form.code.trim(),
                discount_percent: Number(form.discount_percent),
                is_active: form.is_active,
            };
            if (form.valid_until) payload.valid_until = new Date(form.valid_until).toISOString();
            if (form.max_uses) payload.max_uses = Number(form.max_uses);
            const res = await fetch(`${API_BASE_URL}/api/admin/promo-codes`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify(payload),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            pushToast({ type: "success", title: "Promo created", message: "Promo code saved." });
            setForm({
                code: "",
                discount_percent: 10,
                valid_until: "",
                max_uses: "",
                is_active: true,
            });
            fetchCodes();
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Create failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Promo Codes</h1>
                <p className="text-slate-600 dark:text-slate-400">Create and manage discount promo codes.</p>
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded p-5 space-y-4">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Create Promo Code</h2>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                    <input
                        value={form.code}
                        onChange={(e) => setForm(prev => ({ ...prev, code: e.target.value.toUpperCase() }))}
                        placeholder="CODE10"
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <input
                        type="number"
                        value={form.discount_percent}
                        onChange={(e) => setForm(prev => ({ ...prev, discount_percent: Number(e.target.value) }))}
                        min={0}
                        max={100}
                        placeholder="Discount %"
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <input
                        type="date"
                        value={form.valid_until}
                        onChange={(e) => setForm(prev => ({ ...prev, valid_until: e.target.value }))}
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <input
                        type="number"
                        value={form.max_uses}
                        onChange={(e) => setForm(prev => ({ ...prev, max_uses: e.target.value }))}
                        placeholder="Max uses"
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                        <input
                            type="checkbox"
                            checked={form.is_active}
                            onChange={(e) => setForm(prev => ({ ...prev, is_active: e.target.checked }))}
                        />
                        Active
                    </label>
                </div>
                <button
                    onClick={handleCreate}
                    disabled={loading}
                    className="px-4 py-2 rounded bg-slate-900 text-white text-sm font-semibold disabled:opacity-50"
                >
                    {loading ? "Creating..." : "Create Promo"}
                </button>
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Existing Promo Codes</h2>
                </div>
                <div className="divide-y divide-slate-200 dark:divide-slate-700">
                    {codes.map(code => (
                        <div key={code.id} className="px-4 py-3 text-sm">
                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                                <div>
                                    <p className="font-semibold text-slate-900 dark:text-white">{code.code}</p>
                                    <p className="text-xs text-slate-500">
                                        {code.discount_percent}% off · uses {code.current_uses ?? 0}/{code.max_uses ?? "∞"}
                                    </p>
                                </div>
                                <div className="text-xs text-slate-500">
                                    {code.valid_until ? `Valid until ${new Date(code.valid_until).toLocaleDateString()}` : "No expiry"}
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className={`text-xs font-semibold ${code.is_active ? "text-green-600" : "text-slate-400"}`}>
                                        {code.is_active ? "Active" : "Inactive"}
                                    </div>
                                    <button
                                        onClick={async () => {
                                            try {
                                                await updatePromo(code.id, { is_active: !code.is_active });
                                                await fetchCodes();
                                            } catch (e: unknown) {
                                                pushToast({
                                                    type: "error",
                                                    title: "Update failed",
                                                    message: e instanceof Error ? e.message : "Unexpected error",
                                                });
                                            }
                                        }}
                                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs"
                                    >
                                        {code.is_active ? "Deactivate" : "Activate"}
                                    </button>
                                    <button
                                        onClick={() => startEdit(code)}
                                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs"
                                    >
                                        Edit
                                    </button>
                                </div>
                            </div>
                            {editingId === code.id && (
                                <div className="mt-3 grid grid-cols-1 md:grid-cols-5 gap-2">
                                    <input
                                        type="number"
                                        value={editForm.discount_percent}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, discount_percent: Number(e.target.value) }))}
                                        min={0}
                                        max={100}
                                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-xs"
                                    />
                                    <input
                                        type="date"
                                        value={editForm.valid_until}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, valid_until: e.target.value }))}
                                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-xs"
                                    />
                                    <input
                                        type="number"
                                        value={editForm.max_uses}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, max_uses: e.target.value }))}
                                        placeholder="Max uses"
                                        className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-xs"
                                    />
                                    <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                                        <input
                                            type="checkbox"
                                            checked={editForm.is_active}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, is_active: e.target.checked }))}
                                        />
                                        Active
                                    </label>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={async () => {
                                                try {
                                                    const updates: Record<string, unknown> = {
                                                        discount_percent: editForm.discount_percent,
                                                        is_active: editForm.is_active,
                                                    };
                                                    if (editForm.valid_until) {
                                                        updates.valid_until = new Date(editForm.valid_until).toISOString();
                                                    } else {
                                                        updates.valid_until = null;
                                                    }
                                                    updates.max_uses = editForm.max_uses ? Number(editForm.max_uses) : null;
                                                    await updatePromo(code.id, updates);
                                                    pushToast({
                                                        type: "success",
                                                        title: "Promo updated",
                                                        message: `Saved ${code.code}`,
                                                    });
                                                    clearEdit();
                                                    fetchCodes();
                                                } catch (e: unknown) {
                                                    pushToast({
                                                        type: "error",
                                                        title: "Update failed",
                                                        message: e instanceof Error ? e.message : "Unexpected error",
                                                    });
                                                }
                                            }}
                                            className="px-3 py-1 rounded bg-slate-900 text-white text-xs"
                                        >
                                            Save
                                        </button>
                                        <button
                                            onClick={clearEdit}
                                            className="px-3 py-1 rounded border border-slate-200 dark:border-slate-700 text-xs"
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                    {codes.length === 0 && (
                        <div className="px-4 py-4 text-sm text-slate-500">No promo codes created.</div>
                    )}
                </div>
            </div>
        </div>
    );
}
