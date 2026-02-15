"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

export default function UserCreditInspectorPage() {
    const { pushToast } = useToast();
    const [query, setQuery] = useState("");
    type InspectorResult = {
        user: { id: number; email: string; role: string };
        credits: {
            available_credits: number;
            reserved_credits: number;
            lots_count: number;
            ledger_count: number;
        };
    };
    const [result, setResult] = useState<InspectorResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [reason, setReason] = useState("");
    const [role, setRole] = useState("");
    const canGrant = role === "superadmin" || role === "admin";

    useEffect(() => {
        if (typeof window !== "undefined") {
            setRole((localStorage.getItem("user_role") || "").toLowerCase());
        }
    }, []);

    const headers = useMemo<Record<string, string>>(() => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const out: Record<string, string> = { "Content-Type": "application/json" };
        if (token) out.Authorization = `Bearer ${token}`;
        return out;
    }, []);

    const search = async () => {
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await fetchApi(`/api/v1/admin/credits/user?query=${encodeURIComponent(query.trim())}`, { headers });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({ type: "error", title: "Search failed", message: err.message, requestId: err.requestId });
                setResult(null);
                return;
            }
            setResult(await res.json());
        } finally {
            setLoading(false);
        }
    };

    const grant = async () => {
        if (!canGrant) {
            pushToast({ type: "error", title: "Forbidden", message: "Only admin/superadmin can grant credits." });
            return;
        }
        if (!result?.user?.id) return;
        const creditsRaw = prompt("Grant credits amount", "50");
        if (!creditsRaw) return;
        const credits = Number(creditsRaw);
        if (!Number.isFinite(credits) || credits <= 0) return;
        if (!reason.trim()) {
            pushToast({ type: "error", title: "Reason required", message: "Provide reason before grant." });
            return;
        }
        const res = await fetchApi(`/api/v1/admin/credits/grant`, {
            method: "POST",
            headers: { ...headers, "Idempotency-Key": `grant_${result.user.id}_${Date.now()}` },
            body: JSON.stringify({ user_id: result.user.id, credits, reason }),
        });
        if (!res.ok) {
            const err = await parseApiError(res);
            pushToast({ type: "error", title: "Grant failed", message: err.message, requestId: err.requestId });
            return;
        }
        pushToast({ type: "success", title: "Credits granted", message: `${credits} credits granted.` });
        await search();
    };

    return (
        <div className="p-8 max-w-4xl mx-auto space-y-6">
            <h1 className="text-3xl font-black">User Credit Inspector</h1>
            <div className="flex gap-3">
                <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Email or user_id"
                    className="flex-1 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                />
                <button className="px-4 py-2 rounded bg-primary text-white text-sm font-semibold" onClick={() => void search()} disabled={loading}>
                    {loading ? "Searching..." : "Search"}
                </button>
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Audit Reason</label>
                <textarea
                    rows={2}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="w-full border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm"
                    placeholder="Reason for admin actions"
                />
            </div>
            {result && (
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="text-sm">
                        <div><strong>User:</strong> {result.user.email} (#{result.user.id})</div>
                        <div><strong>Role:</strong> {result.user.role}</div>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div><strong>Available:</strong> {result.credits.available_credits}</div>
                        <div><strong>Reserved:</strong> {result.credits.reserved_credits}</div>
                        <div><strong>Lots:</strong> {result.credits.lots_count}</div>
                        <div><strong>Ledger Rows:</strong> {result.credits.ledger_count}</div>
                    </div>
                    <div className="flex gap-2">
                        <button
                            className="px-3 py-2 rounded bg-emerald-600 text-white text-sm font-semibold disabled:opacity-50"
                            onClick={() => void grant()}
                            disabled={!canGrant}
                            title={!canGrant ? "Only admin/superadmin can grant credits." : undefined}
                        >
                            Grant Credits
                        </button>
                        <a className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-700 text-sm font-semibold" href={`/admin/billing/ledger?user_id=${result.user.id}`}>
                            View Ledger
                        </a>
                        <a className="px-3 py-2 rounded bg-slate-200 dark:bg-slate-700 text-sm font-semibold" href={`/admin/billing/holds?user_id=${result.user.id}`}>
                            View Holds
                        </a>
                    </div>
                </div>
            )}
        </div>
    );
}
