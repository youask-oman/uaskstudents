"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type Overview = {
    total_credits_issued: number;
    total_credits_consumed: number;
    active_holds_count: number;
    active_holds_reserved: number;
    insufficient_credits_count: number;
    provider_failures_count: number;
    last_ledger_entry_at?: string | null;
};

export default function AdminCreditsOverviewPage() {
    const { pushToast } = useToast();
    const [data, setData] = useState<Overview | null>(null);
    const [loading, setLoading] = useState(true);

    const headers = useMemo<Record<string, string>>(() => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const out: Record<string, string> = {};
        if (token) out.Authorization = `Bearer ${token}`;
        return out;
    }, []);

    useEffect(() => {
        const run = async () => {
            setLoading(true);
            try {
                const res = await fetchApi(`/api/v1/admin/credits/overview`, { headers });
                if (!res.ok) {
                    const err = await parseApiError(res);
                    pushToast({ type: "error", title: "Failed to load overview", message: err.message, requestId: err.requestId });
                    return;
                }
                setData(await res.json());
            } catch (e) {
                pushToast({ type: "error", title: "Failed to load overview", message: e instanceof Error ? e.message : "Unexpected error" });
            } finally {
                setLoading(false);
            }
        };
        void run();
    }, [headers, pushToast]);

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-6">
            <h1 className="text-3xl font-black">Credits & Billing Overview</h1>
            {loading && <div className="text-sm text-slate-500">Loading...</div>}
            {data && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card title="Total Issued" value={data.total_credits_issued} />
                    <Card title="Total Consumed" value={data.total_credits_consumed} />
                    <Card title="Active Holds" value={data.active_holds_count} />
                    <Card title="Reserved In Holds" value={data.active_holds_reserved} />
                    <Card title="Insufficient Credit Errors" value={data.insufficient_credits_count} />
                    <Card title="Provider Failures" value={data.provider_failures_count} />
                </div>
            )}
            {data?.last_ledger_entry_at && (
                <p className="text-sm text-slate-500">
                    Last ledger entry: {new Date(data.last_ledger_entry_at).toLocaleString()}
                </p>
            )}
        </div>
    );
}

function Card({ title, value }: { title: string; value: number }) {
    return (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">{title}</p>
            <p className="text-2xl font-black mt-1">{Number(value || 0).toLocaleString()}</p>
        </div>
    );
}
