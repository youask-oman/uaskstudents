"use client";

import { useEffect, useState } from "react";

interface MonitorEvent {
    direction: "in" | "out";
    type: string;
    from?: string;
    to?: string;
    text?: string;
    full_text?: string;
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

export default function WhatsAppMonitorPage() {
    const [data, setData] = useState<MonitorResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [phoneFilter, setPhoneFilter] = useState("");
    const [directionFilter, setDirectionFilter] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [selectedEvent, setSelectedEvent] = useState<MonitorEvent | null>(null);

    const fetchData = async () => {
        try {
            const params = new URLSearchParams({ limit: "80" });
            if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
            if (directionFilter) params.set("direction", directionFilter);
            const res = await fetch(`/api/admin/whatsapp/monitor?${params.toString()}`);
            if (!res.ok) {
                throw new Error("Failed to fetch monitor");
            }
            const json = await res.json();
            setData(json);
            setError(null);
        } catch (e: any) {
            setError(e?.message || "Failed to fetch monitor");
        }
    };

    useEffect(() => {
        fetchData();
        const id = setInterval(fetchData, 5000);
        return () => clearInterval(id);
    }, [phoneFilter, directionFilter]);

    useEffect(() => {
        if (!streaming) return;
        const es = new EventSource("/api/admin/whatsapp/monitor/stream");
        es.onmessage = (evt) => {
            try {
                const payload = JSON.parse(evt.data);
                setData(prev => {
                    const events = prev?.events ? [payload, ...prev.events].slice(0, 200) : [payload];
                    return prev ? { ...prev, events } : { bot_status: { status: "unknown" }, queue_length: null, events };
                });
            } catch (_e) {
                // ignore
            }
        };
        es.onerror = () => {
            es.close();
        };
        return () => es.close();
    }, [streaming]);

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white">WhatsApp Monitor</h1>
                    <p className="text-slate-600 dark:text-slate-400">Live inbound/outbound messages and queue depth.</p>
                </div>
                <div className="text-sm text-slate-500 dark:text-slate-400">
                    {data?.server_time ? `Server time: ${data.server_time}` : ""}
                </div>
            </div>

            {error && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
                    <p className="text-red-700 dark:text-red-300 text-sm">{error}</p>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Bot Status</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.bot_status?.status || "unknown"}</p>
                    {data?.bot_status?.phoneNumber && (
                        <p className="text-xs text-slate-500 mt-1">{data.bot_status.phoneNumber}</p>
                    )}
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Celery Queue</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.queue_length ?? "N/A"}</p>
                    <p className="text-xs text-slate-500 mt-1">WhatsApp: {data?.queue_length_whatsapp ?? "N/A"}</p>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500">Events</p>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{data?.events?.length || 0}</p>
                </div>
            </div>

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
                    <button
                        onClick={() => {
                            const params = new URLSearchParams({ limit: "200" });
                            if (phoneFilter.trim()) params.set("phone", phoneFilter.trim());
                            if (directionFilter) params.set("direction", directionFilter);
                            window.location.href = `/api/admin/whatsapp/monitor/export?${params.toString()}`;
                        }}
                        className="px-4 py-2 rounded bg-slate-900 text-white text-sm"
                    >
                        Export CSV
                    </button>
                    <button
                        onClick={() => setStreaming(!streaming)}
                        className="px-4 py-2 rounded border border-slate-200 dark:border-slate-700 text-sm"
                    >
                        {streaming ? "Stop Live" : "Start Live"}
                    </button>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Recent Events</h2>
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
                            <div className="mt-2">
                                <button
                                    type="button"
                                    onClick={() => setSelectedEvent(evt)}
                                    className="text-xs font-semibold text-primary"
                                >
                                    View details
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {selectedEvent && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 w-[90%] max-w-3xl">
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 dark:text-white">WhatsApp Event Detail</h3>
                                <p className="text-xs text-slate-500">{selectedEvent.timestamp || ""}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setSelectedEvent(null)}
                                className="text-sm px-3 py-1 rounded border border-slate-200 dark:border-slate-700"
                            >
                                Close
                            </button>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="text-sm text-slate-700 dark:text-slate-200">
                                <div className="text-xs text-slate-500 mb-1">Summary</div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`px-2 py-0.5 rounded text-xs ${selectedEvent.direction === "in" ? "bg-blue-100 text-blue-800" : "bg-green-100 text-green-800"}`}>
                                        {selectedEvent.direction}
                                    </span>
                                    <span className="text-xs text-slate-500">{selectedEvent.type}</span>
                                    {selectedEvent.ok === false && <span className="text-xs text-red-600">failed</span>}
                                    {selectedEvent.message_id && <span className="text-xs text-slate-500">msg: {selectedEvent.message_id}</span>}
                                    {selectedEvent.upload_id && <span className="text-xs text-slate-500">upload: {selectedEvent.upload_id}</span>}
                                </div>
                                <div className="mt-2 text-xs text-slate-500">
                                    {selectedEvent.from ? `from: ${selectedEvent.from}` : ""} {selectedEvent.to ? `to: ${selectedEvent.to}` : ""}
                                </div>
                            </div>
                            <div className="text-sm">
                                <div className="text-xs text-slate-500 mb-1">Full Text</div>
                                <pre className="whitespace-pre-wrap text-slate-800 dark:text-slate-100 bg-slate-50 dark:bg-slate-800 p-3 rounded border border-slate-200 dark:border-slate-700 text-xs">
{selectedEvent.full_text || selectedEvent.text || ""}
                                </pre>
                            </div>
                            {selectedEvent.error && (
                                <div className="text-sm">
                                    <div className="text-xs text-slate-500 mb-1">Error</div>
                                    <pre className="whitespace-pre-wrap text-red-600 bg-red-50 dark:bg-red-900/30 p-3 rounded border border-red-200 dark:border-red-800 text-xs">
{selectedEvent.error}
                                    </pre>
                                </div>
                            )}
                            <div className="text-sm">
                                <div className="text-xs text-slate-500 mb-1">Raw JSON</div>
                                <pre className="whitespace-pre-wrap text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-800 p-3 rounded border border-slate-200 dark:border-slate-700 text-[11px]">
{JSON.stringify(selectedEvent, null, 2)}
                                </pre>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
