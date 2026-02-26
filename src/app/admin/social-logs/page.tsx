"use client";

import { useCallback, useEffect, useState } from "react";
import { parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

interface MonitorEvent {
    direction: "in" | "out";
    type: string;
    from?: string;
    to?: string;
    text?: string;
    message_id?: string;
    upload_id?: string;
    ok?: boolean;
    error?: string;
    timestamp?: string;
    user_id?: number;
    user_email?: string;
}

interface MonitorResponse {
    bot_status: { status: string; phoneNumber?: string };
    queue_length: number | null;
    queue_length_whatsapp?: number | null;
    events: MonitorEvent[];
    total?: number;
    page?: number;
    page_size?: number;
    server_time?: string;
}

export default function SocialLogsPage() {
    const { pushToast } = useToast();
    const [data, setData] = useState<MonitorResponse | null>(null);
    const [phoneFilter, setPhoneFilter] = useState("");
    const [userEmailFilter, setUserEmailFilter] = useState("");
    const [userIdFilter, setUserIdFilter] = useState("");
    const [directionFilter, setDirectionFilter] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [page, setPage] = useState(1);
    const pageSize = 15;

    const fetchData = useCallback(async () => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
        if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
        if (userEmailFilter.trim()) params.set("user_email", userEmailFilter.trim());
        if (userIdFilter.trim()) params.set("user_id", userIdFilter.trim());
        if (directionFilter) params.set("direction", directionFilter);
        const res = await fetch(`/api/admin/whatsapp/monitor?${params.toString()}`, {
            headers,
        });
        if (!res.ok) {
            const err = await parseApiError(res);
            throw new Error(err.message);
        }
        const json = await res.json();
        setData(json);
    }, [directionFilter, page, phoneFilter, userEmailFilter, userIdFilter]);

    useEffect(() => {
        const loadData = async () => {
            await fetchData();
        };
        loadData();
        const id = setInterval(fetchData, 5000);
        return () => clearInterval(id);
    }, [fetchData]);

    useEffect(() => {
        if (!streaming) return;
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const params = new URLSearchParams();
        if (token) params.set("token", token);
        const es = new EventSource(`/api/admin/whatsapp/monitor/stream?${params.toString()}`);
        es.onmessage = () => {
            void fetchData();
        };
        es.onerror = () => {
            es.close();
        };
        return () => es.close();
    }, [fetchData, streaming]);

    const total = Number(data?.total || 0);
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const canPrev = page > 1;
    const canNext = page < totalPages;

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <header className="flex flex-col gap-2 mb-6">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Social Media Logs</h2>
                <p className="text-sm text-slate-400">WhatsApp activity stream. (Telegram/others can be added later.)</p>
            </header>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 p-4 mb-6">
                <div className="flex flex-col md:flex-row md:items-center gap-3">
                    <input
                        value={phoneFilter}
                        onChange={(e) => {
                            setPhoneFilter(e.target.value);
                            setPage(1);
                        }}
                        placeholder="Filter by phone (e.g. 12345@s.whatsapp.net)"
                        className="flex-1 px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <input
                        value={userEmailFilter}
                        onChange={(e) => {
                            setUserEmailFilter(e.target.value);
                            setPage(1);
                        }}
                        placeholder="Filter by user email"
                        className="flex-1 px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <input
                        value={userIdFilter}
                        onChange={(e) => {
                            setUserIdFilter(e.target.value);
                            setPage(1);
                        }}
                        placeholder="Filter by user id"
                        className="w-44 px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <select
                        value={directionFilter}
                        onChange={(e) => {
                            setDirectionFilter(e.target.value);
                            setPage(1);
                        }}
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    >
                        <option value="">All directions</option>
                        <option value="in">Inbound</option>
                        <option value="out">Outbound</option>
                    </select>
                    <button
                        type="button"
                        onClick={() => {
                            const params = new URLSearchParams({ limit: "200" });
                            if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
                            if (directionFilter) params.set("direction", directionFilter);
                            const token = localStorage.getItem("token");
                            if (token) params.set("token", token);
                            window.location.href = `/api/admin/whatsapp/monitor/export?${params.toString()}`;
                        }}
                        className="px-4 py-2 rounded bg-slate-900 text-white text-sm"
                    >
                        Export CSV
                    </button>
                    <button
                        type="button"
                        onClick={() => setStreaming((v) => !v)}
                        className="px-4 py-2 rounded border border-slate-200 dark:border-slate-700 text-sm"
                    >
                        {streaming ? "Stop Live" : "Start Live"}
                    </button>
                    <button
                        type="button"
                        onClick={async () => {
                            if (!confirm("Are you sure you want to clear the WhatsApp event monitor?")) return;
                            const token = localStorage.getItem("token");
                            const res = await fetch(`/api/admin/whatsapp/all`, {
                                method: "DELETE",
                                headers: token ? { Authorization: `Bearer ${token}` } : {},
                            });
                            if (!res.ok) {
                                const err = await parseApiError(res);
                                pushToast({
                                    type: "error",
                                    title: "Clear failed",
                                    message: err.message,
                                    requestId: err.requestId,
                                });
                                return;
                            }
                            setPage(1);
                            await fetchData();
                            pushToast({
                                type: "success",
                                title: "Monitor cleared",
                                message: "WhatsApp events cleared successfully.",
                            });
                        }}
                        className="px-4 py-2 rounded bg-rose-500 hover:bg-rose-600 text-white text-sm font-bold transition-all"
                    >
                        Clear Monitor
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Bot Status</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.bot_status?.status || "unknown"}</p>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Queue</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.queue_length ?? "N/A"}</p>
                    <p className="text-xs text-slate-500 mt-1">WhatsApp: {data?.queue_length_whatsapp ?? "N/A"}</p>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Events</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.events?.length || 0}</p>
                    <p className="text-xs text-slate-500 mt-1">total matched: {total}</p>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h3 className="font-semibold text-slate-900 dark:text-white">WhatsApp Events</h3>
                </div>
                <div className="divide-y divide-slate-200 dark:divide-slate-700">
                    {data?.events?.map((evt, idx) => (
                        <div key={idx} className="px-4 py-3 text-sm">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className={`px-2 py-0.5 rounded text-xs ${evt.direction === "in" ? "bg-blue-100 text-blue-800" : "bg-green-100 text-green-800"}`}>
                                        {evt.direction}
                                    </span>
                                    <span className="text-xs text-slate-500">{evt.type}</span>
                                    {evt.ok === false && <span className="text-xs text-red-600">failed</span>}
                                </div>
                                <span className="text-xs text-slate-400">{evt.timestamp || ""}</span>
                            </div>
                            <div className="mt-1 text-slate-700 dark:text-slate-200 break-words">
                                {evt.text || ""}
                            </div>
                            <div className="mt-1 text-xs text-slate-500">
                                {evt.from ? `from: ${evt.from}` : ""} {evt.to ? `to: ${evt.to}` : ""}
                            </div>
                            <div className="mt-1 text-xs text-slate-500">
                                {evt.user_id ? `user_id: ${evt.user_id}` : "user_id: n/a"}{" "}
                                {evt.user_email ? `| user_email: ${evt.user_email}` : "| user_email: n/a"}
                            </div>
                            {evt.error && <div className="mt-1 text-xs text-red-600">{evt.error}</div>}
                        </div>
                    ))}
                </div>
                <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <p className="text-xs text-slate-500">Page {page} of {totalPages} | 15 per page</p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            disabled={!canPrev}
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-700 text-sm disabled:opacity-50"
                        >
                            Prev
                        </button>
                        <button
                            type="button"
                            disabled={!canNext}
                            onClick={() => setPage((p) => p + 1)}
                            className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-700 text-sm disabled:opacity-50"
                        >
                            Next
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
