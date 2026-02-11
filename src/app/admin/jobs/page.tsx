"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type QueueLengths = Record<string, number | null>;

type WorkerStatus = {
    name: string;
    ping: boolean;
    active: number;
    scheduled: number;
    reserved: number;
};

type BeatJob = {
    name: string;
    task: string;
    schedule: string;
    args?: unknown[];
    kwargs?: Record<string, unknown>;
};

type JobsStatus = {
    server_time?: string;
    queues: QueueLengths;
    workers: WorkerStatus[];
    beat_schedule: BeatJob[];
    inspect_error?: string | null;
};

type LogResponse = {
    path?: string | null;
    lines?: string[];
    note?: string;
};

const RUNNABLE_TASKS = new Set([
    "ocr_hold_release_job",
    "subscription_grant_job",
    "subscription_expiry_job",
]);

export default function AdminJobsPage() {
    const { pushToast } = useToast();
    const [data, setData] = useState<JobsStatus | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [runningTask, setRunningTask] = useState<string | null>(null);
    const [logType, setLogType] = useState<"worker" | "celery" | "whatsapp">("worker");
    const [logData, setLogData] = useState<LogResponse | null>(null);
    const [logLoading, setLogLoading] = useState(false);

    const fetchStatus = async () => {
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const res = await fetch(`${API_BASE_URL}/api/admin/jobs/status`, {
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = await res.json();
            setData(json);
            setError(null);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load jobs status");
        }
    };

    useEffect(() => {
        fetchStatus();
        const id = setInterval(fetchStatus, 5000);
        return () => clearInterval(id);
    }, []);

    const fetchLogs = async (typeOverride?: "worker" | "celery" | "whatsapp") => {
        const type = typeOverride || logType;
        setLogLoading(true);
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const res = await fetch(`${API_BASE_URL}/api/admin/jobs/logs?log_type=${type}&lines=400`, {
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = await res.json();
            setLogData(json);
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Failed to load logs",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setLogLoading(false);
        }
    };

    const queueCards = useMemo(() => {
        const queues = data?.queues || {};
        return Object.entries(queues).map(([name, length]) => ({
            name,
            length: length ?? null,
        }));
    }, [data?.queues]);

    const runTask = async (task: string) => {
        if (runningTask) return;
        setRunningTask(task);
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const res = await fetch(`${API_BASE_URL}/api/admin/jobs/run`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ task }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                throw new Error(err.message);
            }
            const json = await res.json();
            pushToast({
                type: "success",
                title: "Task queued",
                message: `${task} enqueued (${json?.task_id || "no id"})`,
            });
            fetchStatus();
        } catch (e: unknown) {
            pushToast({
                type: "error",
                title: "Failed to run task",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setRunningTask(null);
        }
    };

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-6">
            <div className="flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Jobs & Workers</h1>
                    <p className="text-slate-600 dark:text-slate-400">Live queue, worker, and scheduled job status.</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                        {data?.server_time ? `Server time: ${data.server_time}` : ""}
                    </div>
                    <button
                        onClick={() => runTask("ocr_hold_release_job")}
                        disabled={runningTask === "ocr_hold_release_job"}
                        className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs disabled:opacity-50"
                    >
                        {runningTask === "ocr_hold_release_job" ? "Releasing..." : "Run OCR Hold Release"}
                    </button>
                </div>
            </div>

            {error && (
                <div className="p-3 border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 rounded">
                    <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
                </div>
            )}

            {data?.inspect_error && (
                <div className="p-3 border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 rounded">
                    <p className="text-sm text-amber-700 dark:text-amber-300">
                        Worker inspect error: {data.inspect_error}
                    </p>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {queueCards.map((queue) => (
                    <div
                        key={queue.name}
                        className="p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded"
                    >
                        <p className="text-xs text-slate-500">Queue</p>
                        <p className="text-lg font-semibold text-slate-900 dark:text-white">{queue.name}</p>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                            {queue.length === null ? "N/A" : `${queue.length} pending`}
                        </p>
                    </div>
                ))}
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Workers</h2>
                </div>
                <div className="divide-y divide-slate-200 dark:divide-slate-700">
                    {(data?.workers || []).map((worker) => (
                        <div key={worker.name} className="px-4 py-3 text-sm flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                            <div>
                                <p className="font-semibold text-slate-900 dark:text-white">{worker.name}</p>
                                <p className="text-xs text-slate-500">{worker.ping ? "online" : "offline"}</p>
                            </div>
                            <div className="flex flex-wrap gap-3 text-xs text-slate-600 dark:text-slate-300">
                                <span>Active: {worker.active}</span>
                                <span>Scheduled: {worker.scheduled}</span>
                                <span>Reserved: {worker.reserved}</span>
                            </div>
                        </div>
                    ))}
                    {(!data?.workers || data.workers.length === 0) && (
                        <div className="px-4 py-4 text-sm text-slate-500">No workers detected.</div>
                    )}
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Scheduled Jobs</h2>
                </div>
                <div className="divide-y divide-slate-200 dark:divide-slate-700">
                    {(data?.beat_schedule || []).map((job) => (
                        <div key={job.name} className="px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3 text-sm">
                            <div>
                                <p className="font-semibold text-slate-900 dark:text-white">{job.name}</p>
                                <p className="text-xs text-slate-500">Task: {job.task}</p>
                                <p className="text-xs text-slate-500">Schedule: {job.schedule}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                {RUNNABLE_TASKS.has(job.task) ? (
                                    <button
                                        onClick={() => runTask(job.task)}
                                        disabled={runningTask === job.task}
                                        className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs disabled:opacity-50"
                                    >
                                        {runningTask === job.task ? "Running..." : "Run now"}
                                    </button>
                                ) : (
                                    <span className="text-xs text-slate-400">manual only</span>
                                )}
                            </div>
                        </div>
                    ))}
                    {(!data?.beat_schedule || data.beat_schedule.length === 0) && (
                        <div className="px-4 py-4 text-sm text-slate-500">No scheduled jobs configured.</div>
                    )}
                </div>
            </div>

            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded">
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                    <div>
                        <h2 className="font-semibold text-slate-900 dark:text-white">Worker Logs</h2>
                        <p className="text-xs text-slate-500">{logData?.path || logData?.note || "Select a log source"}</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <select
                            value={logType}
                            onChange={(e) => {
                                const next = e.target.value as "worker" | "celery" | "whatsapp";
                                setLogType(next);
                                fetchLogs(next);
                            }}
                            className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-700 bg-transparent text-xs"
                        >
                            <option value="worker">Worker</option>
                            <option value="celery">Celery</option>
                            <option value="whatsapp">WhatsApp</option>
                        </select>
                        <button
                            onClick={() => fetchLogs()}
                            className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-700 text-xs"
                            disabled={logLoading}
                        >
                            {logLoading ? "Refreshing..." : "Refresh"}
                        </button>
                    </div>
                </div>
                <div className="p-4 text-xs font-mono whitespace-pre-wrap text-slate-700 dark:text-slate-200 max-h-96 overflow-auto">
                    {(logData?.lines || []).length === 0 ? "No logs available." : (logData?.lines || []).join("\n")}
                </div>
            </div>
        </div>
    );
}
