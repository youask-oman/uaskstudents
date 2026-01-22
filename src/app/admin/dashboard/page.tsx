"use client";

import { useEffect, useState } from "react";

export default function AdminDashboardPage() {
    const [stats, setStats] = useState<any>(null);
    const [routing, setRouting] = useState<any>(null);
    const [solveTraces, setSolveTraces] = useState<any[]>([]);
    const [selectedTrace, setSelectedTrace] = useState<any | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        const fetchData = async () => {
            const token = localStorage.getItem("token");
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
            try {
                const [statsRes, routingRes, tracesRes] = await Promise.all([
                    fetch(`${baseUrl}/api/v1/admin/stats/dashboard`, { headers, signal: controller.signal }),
                    fetch(`${baseUrl}/api/v1/admin/stats/model-routing`, { headers, signal: controller.signal }),
                    fetch(`${baseUrl}/api/v1/admin/solve-traces?limit=120`, { headers, signal: controller.signal })
                ]);
                if (!statsRes.ok || !routingRes.ok || !tracesRes.ok) {
                    throw new Error("Failed to load admin metrics.");
                }
                const statsData = await statsRes.json();
                const routingData = await routingRes.json();
                const tracesData = await tracesRes.json();
                setStats(statsData);
                setRouting(routingData);
                setSolveTraces(Array.isArray(tracesData) ? tracesData : []);
            } catch (err) {
                if ((err as Error).name === "AbortError") {
                    return;
                }
                console.error("Failed to fetch dashboard data:", err);
                setErrorMessage("Unable to load admin metrics. Please refresh or check your connection.");
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
        return () => controller.abort();
    }, []);

    if (isLoading) {
        return <div className="p-8 text-slate-400">Loading dashboard metrics...</div>;
    }

    if (errorMessage) {
        return <div className="p-8 text-rose-400">{errorMessage}</div>;
    }

    const safeNumber = (value: number | null | undefined, fallback = 0) =>
        Number.isFinite(value) ? Number(value) : fallback;
    const formatPercent = (value: number | null | undefined, fallback = "0.0%") =>
        Number.isFinite(value) ? `${Number(value).toFixed(1)}%` : fallback;
    const formatCurrency = (value: number | null | undefined, fallback = "$0.00") =>
        Number.isFinite(value) ? `$${Number(value).toFixed(2)}` : fallback;
    const routingSeries = Array.isArray(routing?.series) ? routing.series : [];
    const maxVolume = routingSeries.length > 0
        ? Math.max(...routingSeries.map((x: any) => x.volume || 0), 1)
        : 1;

    return (
        <>
            <header className="sticky top-0 z-10 flex items-center justify-between bg-[#0F172A]/80 backdrop-blur-md border-b border-slate-800 px-8 py-3 w-full">
                <div className="flex items-center gap-6">
                    <h2 className="text-lg font-bold tracking-tight text-white">Analytics Dashboard</h2>
                    <div className="relative group">
                        <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
                            <span className="material-symbols-outlined text-lg">search</span>
                        </span>
                        <input className="bg-slate-800 border-none rounded-lg py-2 pl-10 pr-4 text-sm w-64 focus:ring-2 focus:ring-admin-primary text-white placeholder-slate-500 transition-all" placeholder="Search metrics or models..." type="text" />
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors relative">
                        <span className="material-symbols-outlined">notifications</span>
                        <span className="absolute top-2 right-2.5 size-2 bg-rose-500 rounded-full border-2 border-[#0F172A]"></span>
                    </button>
                    <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined">settings</span>
                    </button>
                    <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined">light_mode</span>
                    </button>
                </div>
            </header>

            <div className="p-8 max-w-[1400px] mx-auto w-full flex flex-col gap-8">
                <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="kpi-card border-l-4 border-accent-cyan p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-cyan/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-cyan/10 text-accent-cyan rounded-lg material-symbols-outlined">bolt</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+{safeNumber(stats?.requests_growth).toFixed(1)}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Daily Requests</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-cyan transition-colors">{safeNumber(stats?.daily_requests).toLocaleString()}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-emerald p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-emerald/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-emerald/10 text-accent-emerald rounded-lg material-symbols-outlined">document_scanner</span>
                            <span className="text-rose-500 text-xs font-bold bg-rose-500/10 px-2 py-1 rounded-full">{safeNumber(stats?.success_rate_change)}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">OCR Success Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-emerald transition-colors">{formatPercent(stats?.ocr_success_rate)}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-purple p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-purple/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-purple/10 text-accent-purple rounded-lg material-symbols-outlined">payments</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+{safeNumber(stats?.cost_change)}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">LLM Cost Est.</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-purple transition-colors">{formatCurrency(stats?.llm_cost_est)}</h3>
                        <p className="text-[10px] text-slate-500 mt-2">
                            Monthly tokens in/out: {safeNumber(stats?.llm_tokens_in_monthly).toLocaleString()} / {safeNumber(stats?.llm_tokens_out_monthly).toLocaleString()}
                        </p>
                        <p className="text-[10px] text-slate-500">
                            Daily tokens in/out: {safeNumber(stats?.llm_tokens_in_daily).toLocaleString()} / {safeNumber(stats?.llm_tokens_out_daily).toLocaleString()}
                        </p>
                        <p className="text-[10px] text-slate-500">
                            Total requests (M/D): {safeNumber(stats?.llm_total_requests_monthly).toLocaleString()} / {safeNumber(stats?.llm_total_requests_daily).toLocaleString()}
                        </p>
                        <p className="text-[10px] text-slate-500">
                            Total spend (M/D): {formatCurrency(stats?.llm_total_spend_monthly)} / {formatCurrency(stats?.llm_total_spend_daily)}
                        </p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-amber p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-amber/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-amber/10 text-accent-amber rounded-lg material-symbols-outlined">database</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+{safeNumber(stats?.cache_hit_change)}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Cache Hit Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-amber transition-colors">{safeNumber(stats?.cache_hit_rate)}%</h3>
                    </div>
                </section>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <section className="lg:col-span-2 bg-panel-dark border border-slate-800 rounded-xl overflow-hidden shadow-xl">
                        <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-800/20">
                            <div>
                                <h4 className="text-base font-bold text-white">Model Routing Volume</h4>
                                <p className="text-sm text-slate-400">Requests distributed across GPT-4, Claude-3, and Llama-3</p>
                            </div>
                            <div className="flex gap-2">
                                <button className="px-3 py-1.5 text-xs font-bold bg-admin-primary text-white rounded-lg">7 Days</button>
                                <button className="px-3 py-1.5 text-xs font-bold bg-slate-800 text-slate-400 rounded-lg hover:text-white transition-colors">30 Days</button>
                            </div>
                        </div>
                        <div className="p-6">
                            <div className="mb-6 flex gap-8">
                                <div>
                                    <p className="text-[32px] font-bold tracking-tight text-accent-cyan">{safeNumber(routing?.total_requests).toLocaleString()}</p>
                                    <p className="text-slate-400 text-sm font-medium flex items-center gap-1">
                                        Total Requests <span className="text-accent-emerald font-bold">+{safeNumber(routing?.requests_growth)}%</span>
                                    </p>
                                </div>
                                <div className="w-px bg-slate-800 self-stretch"></div>
                                <div>
                                    <p className="text-[32px] font-bold tracking-tight text-accent-emerald">{safeNumber(routing?.avg_latency).toFixed(1)}s</p>
                                    <p className="text-slate-400 text-sm font-medium flex items-center gap-1">
                                        Avg Latency <span className="text-rose-500 font-bold">+{safeNumber(routing?.latency_change)}%</span>
                                    </p>
                                </div>
                            </div>
                            <div className="relative h-[240px] w-full flex flex-col justify-end bg-slate-800/10 rounded-lg p-2">
                                {/* SVG Grid and Path would remain similar but ideally mapped to routing.series */}
                                <div className="flex items-end justify-between h-48 px-4 gap-2">
                                    {routingSeries.map((s: any) => {
                                        const h = (safeNumber(s.volume) / maxVolume) * 100;
                                        return (
                                            <div key={s.day} className="flex-1 flex flex-col items-center gap-2 group">
                                                <div
                                                    className="w-full bg-accent-cyan/20 border-t-2 border-accent-cyan rounded-t-sm transition-all group-hover:bg-accent-cyan/40"
                                                    style={{ height: `${h}%` }}
                                                    title={`${s.volume} requests`}
                                                ></div>
                                                <p className="text-slate-500 text-[11px] font-bold">{s.day}</p>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </section>
                    <section className="bg-panel-dark border border-slate-800 rounded-xl flex flex-col shadow-xl">
                        <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-800/20">
                            <h4 className="text-base font-bold text-white">Recent Errors Inbox</h4>
                            <span className="bg-rose-500/10 text-rose-500 text-[10px] font-bold px-2 py-0.5 rounded uppercase flex items-center gap-1">
                                <span className="size-1.5 bg-rose-500 rounded-full"></span> Live
                            </span>
                        </div>
                        <div className="flex-1 overflow-y-auto max-h-[460px] divide-y divide-slate-800">
                            {/* Empty state or real errors if endpoint added later */}
                            <div className="p-8 text-center text-slate-500 text-sm italic">
                                No critical system errors in the last 24 hours.
                            </div>
                        </div>
                        <div className="p-4 border-t border-slate-800 bg-slate-800/10">
                            <button className="w-full py-2 text-xs font-bold text-admin-primary hover:text-admin-primary/80 transition-colors">View All Logs</button>
                        </div>
                    </section>
                </div>

                <section className="bg-panel-dark border border-slate-800 rounded-xl shadow-xl">
                    <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-800/20">
                        <div>
                            <h4 className="text-base font-bold text-white">Solve Request Traces</h4>
                            <p className="text-sm text-slate-400">Latest streamed solve requests (JSONL)</p>
                        </div>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Last 120</span>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-3">
                        <div className="lg:col-span-2 border-r border-slate-800">
                            <div className="max-h-[420px] overflow-y-auto divide-y divide-slate-800">
                                {solveTraces.length === 0 && (
                                    <div className="p-6 text-slate-500 text-sm italic">No trace logs available.</div>
                                )}
                                {solveTraces.map((entry, index) => (
                                    <button
                                        key={entry.request_id || index}
                                        onClick={() => setSelectedTrace(entry)}
                                        className="w-full text-left px-6 py-3 hover:bg-slate-800/50 transition-colors"
                                    >
                                        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
                                            <span className="font-mono text-slate-200">{entry.request_id?.slice(0, 8) || "unknown"}</span>
                                            <span>User {entry.user_id ?? "n/a"}</span>
                                            <span>{entry.ui_goal || "solve"} / {entry.ui_style || "minimal"}</span>
                                            <span>{entry.resolved_profile_key || "profile"}</span>
                                            <span>{entry.input_tokens ?? 0}/{entry.output_tokens ?? 0} tok</span>
                                            <span className={entry.deduct_committed ? "text-emerald-400" : "text-rose-400"}>
                                                {entry.deduct_committed ? "debited" : "no debit"}
                                            </span>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className="p-6">
                            <h5 className="text-xs font-bold uppercase tracking-widest text-slate-500">Selected Trace</h5>
                            <div className="mt-3 bg-slate-900/60 border border-slate-800 rounded-lg p-4 max-h-[360px] overflow-y-auto">
                                {selectedTrace ? (
                                    <pre className="text-[11px] text-slate-300 whitespace-pre-wrap">{JSON.stringify(selectedTrace, null, 2)}</pre>
                                ) : (
                                    <p className="text-sm text-slate-500">Pick a trace entry to inspect the OpenAI payload and metering.</p>
                                )}
                            </div>
                        </div>
                    </div>
                </section>

                <footer className="mt-auto pt-8 flex items-center justify-between text-slate-500 text-[11px] font-medium border-t border-slate-800">
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1.5">
                            <span className="size-2 bg-accent-emerald rounded-full"></span>
                            <span className="text-slate-400">All systems operational</span>
                        </div>
                        <div className="h-4 w-px bg-slate-800"></div>
                        <span>API v2.4.1</span>
                    </div>
                    <div>
                        (c) 2024 uask.ai Admin Console
                    </div>
                </footer>
            </div>
        </>
    );
}
