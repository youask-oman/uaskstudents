"use client";

import { useEffect, useState } from "react";

export default function AdminDashboardPage() {
    const [stats, setStats] = useState<any>(null);
    const [routing, setRouting] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, routingRes] = await Promise.all([
                    fetch("http://127.0.0.1:8000/api/v1/admin/stats/dashboard"),
                    fetch("http://127.0.0.1:8000/api/v1/admin/stats/model-routing")
                ]);
                const statsData = await statsRes.json();
                const routingData = await routingRes.json();
                setStats(statsData);
                setRouting(routingData);
            } catch (err) {
                console.error("Failed to fetch dashboard data:", err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, []);

    if (isLoading) {
        return <div className="p-8 text-slate-400">Loading dashboard metrics...</div>;
    }

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
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+{stats?.requests_growth.toFixed(1)}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Daily Requests</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-cyan transition-colors">{stats?.daily_requests}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-emerald p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-emerald/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-emerald/10 text-accent-emerald rounded-lg material-symbols-outlined">document_scanner</span>
                            <span className="text-rose-500 text-xs font-bold bg-rose-500/10 px-2 py-1 rounded-full">{stats?.success_rate_change}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">OCR Success Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-emerald transition-colors">{stats?.ocr_success_rate.toFixed(1)}%</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-purple p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-purple/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-purple/10 text-accent-purple rounded-lg material-symbols-outlined">payments</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+{stats?.cost_change}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">LLM Cost Est.</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-purple transition-colors">${stats?.llm_cost_est.toFixed(2)}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-amber p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-amber/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-amber/10 text-accent-amber rounded-lg material-symbols-outlined">database</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+{stats?.cache_hit_change}%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Cache Hit Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-amber transition-colors">{stats?.cache_hit_rate}%</h3>
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
                                    <p className="text-[32px] font-bold tracking-tight text-accent-cyan">{routing?.total_requests.toLocaleString()}</p>
                                    <p className="text-slate-400 text-sm font-medium flex items-center gap-1">
                                        Total Requests <span className="text-accent-emerald font-bold">+{routing?.requests_growth}%</span>
                                    </p>
                                </div>
                                <div className="w-px bg-slate-800 self-stretch"></div>
                                <div>
                                    <p className="text-[32px] font-bold tracking-tight text-accent-emerald">{routing?.avg_latency}s</p>
                                    <p className="text-slate-400 text-sm font-medium flex items-center gap-1">
                                        Avg Latency <span className="text-rose-500 font-bold">+{routing?.latency_change}%</span>
                                    </p>
                                </div>
                            </div>
                            <div className="relative h-[240px] w-full flex flex-col justify-end bg-slate-800/10 rounded-lg p-2">
                                {/* SVG Grid and Path would remain similar but ideally mapped to routing.series */}
                                <div className="flex items-end justify-between h-48 px-4 gap-2">
                                    {routing?.series.map((s: any) => {
                                        const h = (s.volume / Math.max(...routing.series.map((x: any) => x.volume))) * 100;
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
                        © 2024 uask.ai Admin Console
                    </div>
                </footer>
            </div>
        </>
    );
}
