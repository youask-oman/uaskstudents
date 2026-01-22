"use client";

import { useEffect, useMemo, useState } from "react";

export default function AdminLogsPage() {
    const [traces, setTraces] = useState<any[]>([]);
    const [selectedTrace, setSelectedTrace] = useState<any | null>(null);
    const [relatedUserData, setRelatedUserData] = useState<any | null>(null);
    const [isLoadingUserData, setIsLoadingUserData] = useState(false);
    const [filter, setFilter] = useState("");
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const controller = new AbortController();
        const fetchTraces = async () => {
            const token = localStorage.getItem("token");
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
            try {
                const res = await fetch(`${baseUrl}/api/v1/admin/solve-traces?limit=500`, { headers, signal: controller.signal });
                if (!res.ok) {
                    throw new Error("Failed to load solve traces.");
                }
                const data = await res.json();
                setTraces(Array.isArray(data) ? data : []);
            } catch (err) {
                if ((err as Error).name === "AbortError") return;
                console.error("Failed to fetch solve traces:", err);
                setErrorMessage("Unable to load solve traces.");
            } finally {
                setIsLoading(false);
            }
        };
        fetchTraces();
        return () => controller.abort();
    }, []);

    const filteredTraces = useMemo(() => {
        if (!filter.trim()) return traces;
        const needle = filter.trim().toLowerCase();
        return traces.filter((trace) =>
            JSON.stringify(trace).toLowerCase().includes(needle)
        );
    }, [filter, traces]);

    useEffect(() => {
        if (!selectedTrace?.user_id) {
            setRelatedUserData(null);
            return;
        }
        const controller = new AbortController();
        const fetchUserData = async () => {
            const token = localStorage.getItem("token");
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
            setIsLoadingUserData(true);
            try {
                const res = await fetch(`${baseUrl}/api/v1/admin/users/${selectedTrace.user_id}/full`, { headers, signal: controller.signal });
                if (!res.ok) {
                    throw new Error("Failed to load related user data.");
                }
                const data = await res.json();
                setRelatedUserData(data);
            } catch (err) {
                if ((err as Error).name === "AbortError") return;
                console.error("Failed to fetch related user data:", err);
            } finally {
                setIsLoadingUserData(false);
            }
        };
        fetchUserData();
        return () => controller.abort();
    }, [selectedTrace]);

    if (isLoading) {
        return <div className="p-8 text-slate-400">Loading logs...</div>;
    }

    if (errorMessage) {
        return <div className="p-8 text-rose-400">{errorMessage}</div>;
    }

    return (
        <div className="p-8 max-w-[1400px] mx-auto w-full flex flex-col gap-6">
            <header className="flex flex-col gap-2">
                <h2 className="text-xl font-bold text-white">Solve Request Logs</h2>
                <p className="text-sm text-slate-400">Full trace log for each request, including OpenAI payload metadata.</p>
            </header>
            <div className="flex items-center gap-3">
                <input
                    className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-600 focus:ring-admin-primary"
                    placeholder="Search request_id, user_id, schema, model..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                />
                <span className="text-xs text-slate-500">{filteredTraces.length} results</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <section className="lg:col-span-2 bg-[#111827] border border-slate-800 rounded-2xl overflow-hidden">
                    <div className="max-h-[640px] overflow-y-auto divide-y divide-slate-800">
                        {filteredTraces.length === 0 && (
                            <div className="p-6 text-slate-500 text-sm italic">No trace logs available.</div>
                        )}
                                {filteredTraces.map((entry, index) => (
                                    <button
                                        key={entry.request_id || index}
                                        onClick={() => setSelectedTrace(entry)}
                                        className="w-full text-left px-6 py-4 hover:bg-slate-800/50 transition-colors"
                                    >
                                        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
                                            <span className="font-mono text-slate-200">{entry.request_id?.slice(0, 10) || "unknown"}</span>
                                            <span>User {entry.user_id ?? "n/a"}</span>
                                            <span>{entry.ui_goal || "solve"} / {entry.ui_style || "minimal"}</span>
                                            <span>{entry.schema_name || "schema"}</span>
                                            <span>{entry.input_tokens ?? 0}/{entry.output_tokens ?? 0} tok</span>
                                            <span className={entry.deduct_committed ? "text-emerald-400" : "text-rose-400"}>
                                                {entry.deduct_committed ? "debited" : "no debit"}
                                            </span>
                                        </div>
                                        {entry.problem_text && (
                                            <p className="mt-2 text-[11px] text-slate-500 line-clamp-2">
                                                {entry.problem_text}
                                            </p>
                                        )}
                                    </button>
                                ))}
                    </div>
                </section>
                <section className="bg-[#111827] border border-slate-800 rounded-2xl p-6 flex flex-col gap-4">
                    <div>
                        <h4 className="text-sm font-bold text-white mb-2">Selected Trace</h4>
                        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 max-h-[300px] overflow-y-auto">
                            {selectedTrace ? (
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">{JSON.stringify(selectedTrace, null, 2)}</pre>
                            ) : (
                                <p className="text-sm text-slate-500">Pick a trace entry to inspect details.</p>
                            )}
                        </div>
                    </div>
                    <div>
                        <h4 className="text-sm font-bold text-white mb-2">Related User Data (Full)</h4>
                        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 max-h-[300px] overflow-y-auto">
                            {isLoadingUserData && <p className="text-sm text-slate-500">Loading user data...</p>}
                            {!isLoadingUserData && relatedUserData ? (
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">{JSON.stringify(relatedUserData, null, 2)}</pre>
                            ) : null}
                            {!isLoadingUserData && !relatedUserData && (
                                <p className="text-sm text-slate-500">No user data loaded.</p>
                            )}
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
}
