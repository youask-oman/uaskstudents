"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

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
}

interface MonitorResponse {
    bot_status: { status: string; phoneNumber?: string };
    queue_length: number | null;
    queue_length_whatsapp?: number | null;
    events: MonitorEvent[];
    server_time?: string;
}

export default function SocialLogsPage() {
    const [data, setData] = useState<MonitorResponse | null>(null);
    const [phoneFilter, setPhoneFilter] = useState("");
    const [directionFilter, setDirectionFilter] = useState("");

    const fetchData = useCallback(async () => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const params = new URLSearchParams({ limit: "80" });
        if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
        if (directionFilter) params.set("direction", directionFilter);
        const res = await fetch(`${API_BASE_URL}/api/admin/whatsapp/monitor?${params.toString()}`, {
            headers,
        });
        const json = await res.json();
        setData(json);
    }, [phoneFilter, directionFilter]);

    useEffect(() => {
        const loadData = async () => {
            await fetchData();
        };
        loadData();
        const id = setInterval(fetchData, 5000);
        return () => clearInterval(id);
    }, [fetchData]);

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
                        onChange={(e) => setPhoneFilter(e.target.value)}
                        placeholder="Filter by phone (e.g. 12345@s.whatsapp.net)"
                        className="flex-1 px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    />
                    <select
                        value={directionFilter}
                        onChange={(e) => setDirectionFilter(e.target.value)}
                        className="px-3 py-2 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
                    >
                        <option value="">All directions</option>
                        <option value="in">Inbound</option>
                        <option value="out">Outbound</option>
                    </select>
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
                            {evt.error && <div className="mt-1 text-xs text-red-600">{evt.error}</div>}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
