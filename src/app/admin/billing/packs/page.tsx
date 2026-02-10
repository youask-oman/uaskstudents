"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

const PAGE_TITLE = "Credit Packs";

type Pack = {
    id: number;
    code: string;
    name: string;
    credits: number;
    price_usd: number;
    is_active: boolean;
    description?: string | null;
    metadata_json?: Record<string, unknown> | null;
};

type PackResponse = {
    items: Pack[];
    total: number;
    limit: number;
    offset: number;
};

type PackForm = {
    code: string;
    name: string;
    credits: number;
    price_usd: number;
    is_active: boolean;
    description: string;
};

const emptyForm: PackForm = {
    code: "",
    name: "",
    credits: 0,
    price_usd: 0,
    is_active: true,
    description: "",
};

const makeIdempotencyKey = (prefix: string) => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return `${prefix}_${crypto.randomUUID()}`;
    }
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
};

export default function CreditPacksPage() {
    const { pushToast } = useToast();
    const [packs, setPacks] = useState<Pack[]>([]);
    const [total, setTotal] = useState(0);
    const [limit] = useState(50);
    const [offset] = useState(0);
    const [statusFilter, setStatusFilter] = useState("all");
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingPack, setEditingPack] = useState<Pack | null>(null);
    const [form, setForm] = useState<PackForm>(emptyForm);
    const [reason, setReason] = useState("");

    const headers = useMemo(() => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        return token ? { Authorization: `Bearer ${token}` } : {};
    }, []);

    const fetchPacks = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                limit: limit.toString(),
                offset: offset.toString(),
            });
            if (statusFilter !== "all") params.set("status", statusFilter);

            const res = await fetch(`${API_BASE_URL}/api/admin/billing/packs?${params.toString()}`,
                {
                    headers,
                }
            );
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Failed to load credit packs",
                    message: err.message,
                    requestId: err.requestId,
                });
                return;
            }
            const data = (await res.json()) as PackResponse;
            setPacks(data.items || []);
            setTotal(data.total || 0);
        } catch (error) {
            pushToast({
                type: "error",
                title: "Failed to load credit packs",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        } finally {
            setLoading(false);
        }
    }, [headers, limit, offset, statusFilter, pushToast]);

    useEffect(() => {
        fetchPacks();
    }, [fetchPacks]);

    const openCreate = () => {
        setEditingPack(null);
        setForm(emptyForm);
        setShowForm(true);
    };

    const openEdit = (pack: Pack) => {
        setEditingPack(pack);
        setForm({
            code: pack.code,
            name: pack.name,
            credits: pack.credits,
            price_usd: pack.price_usd,
            is_active: pack.is_active,
            description: pack.description || "",
        });
        setShowForm(true);
    };

    const handleSave = async () => {
        if (!reason.trim()) {
            pushToast({
                type: "error",
                title: "Reason required",
                message: "Provide a reason for audit logging.",
            });
            return;
        }
        if (!form.name.trim() || (!editingPack && !form.code.trim())) {
            pushToast({
                type: "error",
                title: "Missing fields",
                message: "Name and code are required.",
            });
            return;
        }

        const payload = {
            name: form.name.trim(),
            credits: Number(form.credits),
            price_usd: Number(form.price_usd),
            is_active: form.is_active,
            description: form.description.trim() || null,
            reason: reason.trim(),
            idempotency_key: makeIdempotencyKey(editingPack ? "pack_update" : "pack_create"),
        } as Record<string, unknown>;

        if (!editingPack) {
            payload.code = form.code.trim();
        }

        const url = editingPack
            ? `${API_BASE_URL}/api/admin/billing/packs/${editingPack.id}`
            : `${API_BASE_URL}/api/admin/billing/packs`;
        const method = editingPack ? "PUT" : "POST";

        const res = await fetch(url, {
            method,
            headers: {
                "Content-Type": "application/json",
                ...headers,
            },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const err = await parseApiError(res);
            pushToast({
                type: "error",
                title: editingPack ? "Update failed" : "Create failed",
                message: err.message,
                requestId: err.requestId,
            });
            return;
        }

        pushToast({
            type: "success",
            title: editingPack ? "Pack updated" : "Pack created",
            message: "Catalog updated successfully.",
        });
        setShowForm(false);
        setReason("");
        fetchPacks();
    };

    const handleDeactivate = async (pack: Pack) => {
        if (!reason.trim()) {
            pushToast({
                type: "error",
                title: "Reason required",
                message: "Provide a reason for audit logging.",
            });
            return;
        }
        if (!confirm(`Deactivate ${pack.name}?`)) return;

        const res = await fetch(`${API_BASE_URL}/api/admin/billing/packs/${pack.id}`,
            {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    ...headers,
                },
                body: JSON.stringify({
                    reason: reason.trim(),
                    idempotency_key: makeIdempotencyKey("pack_deactivate"),
                }),
            }
        );

        if (!res.ok) {
            const err = await parseApiError(res);
            pushToast({
                type: "error",
                title: "Deactivate failed",
                message: err.message,
                requestId: err.requestId,
            });
            return;
        }

        pushToast({
            type: "success",
            title: "Pack deactivated",
            message: `${pack.name} is now inactive.`,
        });
        setReason("");
        fetchPacks();
    };

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-6">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500 border border-emerald-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">inventory_2</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">{PAGE_TITLE}</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Manage top-up products available for user purchases. These are real catalog entries stored in `topupproduct`.
                    </p>
                </div>
                <div className="flex gap-4 flex-wrap">
                    <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-sm bg-white dark:bg-slate-900"
                    >
                        <option value="all">All</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                    </select>
                    <button
                        onClick={openCreate}
                        className="flex items-center gap-2 px-6 py-3 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        Create Pack
                    </button>
                </div>
            </header>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Reason for Changes (Audit Required)</label>
                <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={2}
                    placeholder="Provide a reason for catalog updates"
                    className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                />
            </div>

            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full text-left">
                        <thead className="bg-slate-50 dark:bg-slate-900/50">
                            <tr>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Code</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Name</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Credits</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Price (USD)</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Status</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Description</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                            {loading ? (
                                <tr>
                                    <td colSpan={7} className="px-4 py-6 text-center text-sm text-slate-500">
                                        Loading packs...
                                    </td>
                                </tr>
                            ) : packs.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="px-4 py-6 text-center text-sm text-slate-500">
                                        No packs found.
                                    </td>
                                </tr>
                            ) : (
                                packs.map((pack) => (
                                    <tr key={pack.id} className="hover:bg-slate-100 dark:hover:bg-slate-800/40 transition-colors">
                                        <td className="px-4 py-3 text-xs font-mono text-slate-600 dark:text-slate-300">{pack.code}</td>
                                        <td className="px-4 py-3 text-sm font-semibold text-slate-900 dark:text-white">{pack.name}</td>
                                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">{pack.credits.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">${pack.price_usd.toFixed(2)}</td>
                                        <td className="px-4 py-3 text-xs">
                                            <span className={`px-2 py-1 rounded-full ${pack.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                                                {pack.is_active ? "ACTIVE" : "INACTIVE"}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-xs text-slate-500">{pack.description || "--"}</td>
                                        <td className="px-4 py-3 text-right">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    onClick={() => openEdit(pack)}
                                                    className="text-slate-600 dark:text-slate-300 hover:text-admin-primary text-xs font-semibold"
                                                >
                                                    Edit
                                                </button>
                                                {pack.is_active && (
                                                    <button
                                                        onClick={() => handleDeactivate(pack)}
                                                        className="text-rose-600 hover:text-rose-700 text-xs font-semibold"
                                                    >
                                                        Deactivate
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {showForm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 w-full max-w-xl border border-slate-200 dark:border-slate-700">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold">
                                {editingPack ? "Edit Pack" : "Create Pack"}
                            </h2>
                            <button onClick={() => setShowForm(false)}>
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="md:col-span-2">
                                <label className="text-xs font-semibold text-slate-500">Code</label>
                                <input
                                    value={form.code}
                                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                                    disabled={!!editingPack}
                                    className="w-full mt-1 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                            <div className="md:col-span-2">
                                <label className="text-xs font-semibold text-slate-500">Name</label>
                                <input
                                    value={form.name}
                                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                                    className="w-full mt-1 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-slate-500">Credits</label>
                                <input
                                    type="number"
                                    value={form.credits}
                                    onChange={(e) => setForm({ ...form, credits: Number(e.target.value) })}
                                    className="w-full mt-1 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-slate-500">Price (USD)</label>
                                <input
                                    type="number"
                                    step="0.01"
                                    value={form.price_usd}
                                    onChange={(e) => setForm({ ...form, price_usd: Number(e.target.value) })}
                                    className="w-full mt-1 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                            <div className="md:col-span-2">
                                <label className="text-xs font-semibold text-slate-500">Description</label>
                                <textarea
                                    value={form.description}
                                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                                    rows={3}
                                    className="w-full mt-1 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                                />
                            </div>
                            <div className="md:col-span-2 flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={form.is_active}
                                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                                />
                                <span className="text-xs text-slate-500">Active</span>
                            </div>
                        </div>
                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                onClick={() => setShowForm(false)}
                                className="px-4 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSave}
                                className="px-4 py-2 text-sm bg-admin-primary text-white rounded-lg"
                            >
                                {editingPack ? "Save Changes" : "Create Pack"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="text-xs text-slate-500">
                Showing {packs.length} of {total} packs.
            </div>
        </div>
    );
}

