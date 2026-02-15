"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type TopUpProduct = {
    id: number;
    code: string;
    name: string;
    credits: number;
    price_usd: number;
    is_active: boolean;
    metadata_json?: Record<string, unknown> | null;
};

type Draft = {
    name: string;
    credits: string;
    price_usd: string;
    is_active: boolean;
};

function toDraft(item: TopUpProduct): Draft {
    return {
        name: item.name || "",
        credits: String(item.credits ?? 0),
        price_usd: String(item.price_usd ?? 0),
        is_active: Boolean(item.is_active),
    };
}

export default function TopUpProductsPage() {
    const { pushToast } = useToast();
    const [items, setItems] = useState<TopUpProduct[]>([]);
    const [drafts, setDrafts] = useState<Record<number, Draft>>({});
    const [loading, setLoading] = useState(true);
    const [savingId, setSavingId] = useState<number | null>(null);
    const [creating, setCreating] = useState(false);
    const [reason, setReason] = useState("");
    const [role, setRole] = useState("");
    const [newPack, setNewPack] = useState({
        code: "",
        name: "",
        credits: "",
        price_usd: "",
    });

    const canEdit = role === "superadmin";

    useEffect(() => {
        if (typeof window !== "undefined") {
            setRole((localStorage.getItem("user_role") || "").toLowerCase());
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
            const res = await fetchApi("/api/admin/payments/pricing", { headers });
            if (!res.ok) throw new Error((await parseApiError(res)).message);
            const data = await res.json();
            const rows: TopUpProduct[] = Array.isArray(data?.topup_packs) ? data.topup_packs : [];
            rows.sort((a, b) => Number(a.price_usd || 0) - Number(b.price_usd || 0));
            setItems(rows);
            setDrafts(Object.fromEntries(rows.map((row) => [row.id, toDraft(row)])));
        } catch (err) {
            pushToast({ type: "error", title: "Failed to load Top-Up products", message: err instanceof Error ? err.message : "Unexpected error" });
        } finally {
            setLoading(false);
        }
    }, [headers, pushToast]);

    useEffect(() => {
        void load();
    }, [load]);

    const updateDraft = (id: number, patch: Partial<Draft>) => {
        setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
    };

    const mutate = async (payload: Record<string, unknown>) => {
        const res = await fetchApi("/api/admin/payments/pricing", {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await parseApiError(res);
            throw new Error(err.message);
        }
    };

    const savePack = async (item: TopUpProduct) => {
        if (!canEdit) {
            pushToast({ type: "error", title: "Forbidden", message: "Only superadmin can update Top-Up products." });
            return;
        }
        if (!reason.trim()) {
            pushToast({ type: "error", title: "Reason required", message: "Provide an audit reason before saving." });
            return;
        }
        const d = drafts[item.id];
        const credits = Number(d?.credits);
        const price = Number(d?.price_usd);
        if (!Number.isFinite(credits) || credits <= 0) {
            pushToast({ type: "error", title: "Invalid credits", message: "Credits must be a positive number." });
            return;
        }
        if (!Number.isFinite(price) || price <= 0) {
            pushToast({ type: "error", title: "Invalid price", message: "Price must be a positive number." });
            return;
        }

        setSavingId(item.id);
        try {
            await mutate({
                kind: "TOPUP_PACK",
                action: "update",
                reason: reason.trim(),
                data: {
                    id: item.id,
                    name: d.name.trim(),
                    credits: Math.trunc(credits),
                    price_usd: price,
                    is_active: d.is_active,
                },
            });
            pushToast({ type: "success", title: "Saved", message: `${item.code} updated.` });
            await load();
        } catch (err) {
            pushToast({ type: "error", title: "Save failed", message: err instanceof Error ? err.message : "Unexpected error" });
        } finally {
            setSavingId(null);
        }
    };

    const deactivatePack = async (item: TopUpProduct) => {
        if (!canEdit) {
            pushToast({ type: "error", title: "Forbidden", message: "Only superadmin can deactivate Top-Up products." });
            return;
        }
        if (!reason.trim()) {
            pushToast({ type: "error", title: "Reason required", message: "Provide an audit reason before deactivation." });
            return;
        }
        setSavingId(item.id);
        try {
            await mutate({
                kind: "TOPUP_PACK",
                action: "deactivate",
                reason: reason.trim(),
                data: { id: item.id },
            });
            pushToast({ type: "success", title: "Deactivated", message: `${item.code} deactivated.` });
            await load();
        } catch (err) {
            pushToast({ type: "error", title: "Deactivation failed", message: err instanceof Error ? err.message : "Unexpected error" });
        } finally {
            setSavingId(null);
        }
    };

    const createPack = async () => {
        if (!canEdit) {
            pushToast({ type: "error", title: "Forbidden", message: "Only superadmin can create Top-Up products." });
            return;
        }
        if (!reason.trim()) {
            pushToast({ type: "error", title: "Reason required", message: "Provide an audit reason before creating." });
            return;
        }
        const code = newPack.code.trim();
        const name = newPack.name.trim();
        const credits = Number(newPack.credits);
        const price = Number(newPack.price_usd);
        if (!code || !name) {
            pushToast({ type: "error", title: "Missing fields", message: "Code and name are required." });
            return;
        }
        if (!Number.isFinite(credits) || credits <= 0 || !Number.isFinite(price) || price <= 0) {
            pushToast({ type: "error", title: "Invalid values", message: "Credits and price must be positive numbers." });
            return;
        }

        setCreating(true);
        try {
            await mutate({
                kind: "TOPUP_PACK",
                action: "create",
                reason: reason.trim(),
                data: {
                    code,
                    name,
                    credits: Math.trunc(credits),
                    price_usd: price,
                    is_active: true,
                },
            });
            pushToast({ type: "success", title: "Created", message: `${code} created.` });
            setNewPack({ code: "", name: "", credits: "", price_usd: "" });
            await load();
        } catch (err) {
            pushToast({ type: "error", title: "Create failed", message: err instanceof Error ? err.message : "Unexpected error" });
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Top-Up Products</h1>
                <p className="text-sm text-slate-500">Manage TopUpProduct entries used by homepage credit packs (`/api/v1/topups/products`).</p>
            </header>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <label className="block">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Audit Reason</div>
                    <textarea
                        rows={2}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Required for create/update/deactivate"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                </label>
                <p className="text-xs text-slate-500">Role: <span className="font-semibold uppercase">{role || "unknown"}</span> · {items.length} products loaded</p>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <h2 className="text-base font-bold text-slate-800">Create Top-Up Product</h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input value={newPack.code} onChange={(e) => setNewPack((p) => ({ ...p, code: e.target.value }))} placeholder="code (e.g. topup_15)" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                    <input value={newPack.name} onChange={(e) => setNewPack((p) => ({ ...p, name: e.target.value }))} placeholder="name (e.g. $15 Pack)" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                    <input value={newPack.credits} onChange={(e) => setNewPack((p) => ({ ...p, credits: e.target.value }))} placeholder="credits" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                    <input value={newPack.price_usd} onChange={(e) => setNewPack((p) => ({ ...p, price_usd: e.target.value }))} placeholder="price_usd" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <button onClick={() => void createPack()} disabled={creating || !canEdit} className="px-4 py-2 rounded-lg bg-admin-primary text-white text-sm font-bold disabled:opacity-60">
                    {creating ? "Creating..." : "Create Product"}
                </button>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="text-base font-bold text-slate-800 mb-4">Existing Products</h2>
                {loading ? (
                    <div className="text-slate-500 text-sm">Loading...</div>
                ) : items.length === 0 ? (
                    <div className="text-slate-500 text-sm">No Top-Up products found.</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                            <thead>
                                <tr className="text-left border-b border-slate-200">
                                    <th className="px-3 py-2">Code</th>
                                    <th className="px-3 py-2">Name</th>
                                    <th className="px-3 py-2">Credits</th>
                                    <th className="px-3 py-2">Price USD</th>
                                    <th className="px-3 py-2">Active</th>
                                    <th className="px-3 py-2 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item) => {
                                    const d = drafts[item.id] || toDraft(item);
                                    const busy = savingId === item.id;
                                    return (
                                        <tr key={item.id} className="border-b border-slate-100">
                                            <td className="px-3 py-2 font-mono text-xs">{item.code}</td>
                                            <td className="px-3 py-2"><input value={d.name} onChange={(e) => updateDraft(item.id, { name: e.target.value })} disabled={!canEdit || busy} className="w-full rounded border border-slate-300 px-2 py-1" /></td>
                                            <td className="px-3 py-2"><input value={d.credits} onChange={(e) => updateDraft(item.id, { credits: e.target.value })} disabled={!canEdit || busy} className="w-28 rounded border border-slate-300 px-2 py-1" /></td>
                                            <td className="px-3 py-2"><input value={d.price_usd} onChange={(e) => updateDraft(item.id, { price_usd: e.target.value })} disabled={!canEdit || busy} className="w-28 rounded border border-slate-300 px-2 py-1" /></td>
                                            <td className="px-3 py-2">
                                                <label className="inline-flex items-center gap-2">
                                                    <input type="checkbox" checked={d.is_active} onChange={(e) => updateDraft(item.id, { is_active: e.target.checked })} disabled={!canEdit || busy} />
                                                    <span>{d.is_active ? "Yes" : "No"}</span>
                                                </label>
                                            </td>
                                            <td className="px-3 py-2 text-right">
                                                <div className="inline-flex gap-2">
                                                    <button onClick={() => void savePack(item)} disabled={!canEdit || busy} className="px-3 py-1 rounded border border-slate-300 text-xs font-semibold disabled:opacity-50">{busy ? "Saving..." : "Save"}</button>
                                                    <button onClick={() => void deactivatePack(item)} disabled={!canEdit || busy || !d.is_active} className="px-3 py-1 rounded border border-rose-300 text-rose-700 text-xs font-semibold disabled:opacity-50">Deactivate</button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </div>
    );
}

