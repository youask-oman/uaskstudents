"use client";

import Link from "next/link";

export default function AdminDashboardPage() {
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
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+12.3%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Daily Requests</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-cyan transition-colors">124.5k</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-emerald p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-emerald/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-emerald/10 text-accent-emerald rounded-lg material-symbols-outlined">document_scanner</span>
                            <span className="text-rose-500 text-xs font-bold bg-rose-500/10 px-2 py-1 rounded-full">-0.5%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">OCR Success Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-emerald transition-colors">98.2%</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-purple p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-purple/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-purple/10 text-accent-purple rounded-lg material-symbols-outlined">payments</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+5.2%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">LLM Cost Est.</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-purple transition-colors">$1,420.00</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-amber p-5 rounded-xl shadow-lg border-slate-800 border hover:border-accent-amber/50 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                            <span className="p-2 bg-accent-amber/10 text-accent-amber rounded-lg material-symbols-outlined">database</span>
                            <span className="text-accent-emerald text-xs font-bold bg-accent-emerald/10 px-2 py-1 rounded-full">+8.1%</span>
                        </div>
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Cache Hit Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-white group-hover:text-accent-amber transition-colors">42.5%</h3>
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
                                    <p className="text-[32px] font-bold tracking-tight text-accent-cyan">842,000</p>
                                    <p className="text-slate-400 text-sm font-medium flex items-center gap-1">
                                        Total Requests <span className="text-accent-emerald font-bold">+15.4%</span>
                                    </p>
                                </div>
                                <div className="w-px bg-slate-800 self-stretch"></div>
                                <div>
                                    <p className="text-[32px] font-bold tracking-tight text-accent-emerald">1.2s</p>
                                    <p className="text-slate-400 text-sm font-medium flex items-center gap-1">
                                        Avg Latency <span className="text-rose-500 font-bold">+4.2%</span>
                                    </p>
                                </div>
                            </div>
                            <div className="relative h-[240px] w-full flex flex-col justify-end bg-slate-800/10 rounded-lg p-2">
                                <svg className="absolute inset-0 w-full h-full opacity-10" height="100%" width="100%">
                                    <defs>
                                        <pattern height="40" id="grid" patternUnits="userSpaceOnUse" width="40">
                                            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="1"></path>
                                        </pattern>
                                    </defs>
                                    <rect fill="url(#grid)" height="100%" width="100%"></rect>
                                </svg>
                                <svg className="w-full relative z-10" fill="none" height="180" preserveAspectRatio="none" viewBox="-3 0 478 150" width="100%" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M0 109C18.1538 109 18.1538 21 36.3077 21C54.4615 21 54.4615 41 72.6154 41C90.7692 41 90.7692 93 108.923 93C127.077 93 127.077 33 145.231 33C163.385 33 163.385 101 181.538 101C199.692 101 199.692 61 217.846 61C236 61 236 45 254.154 45C272.308 45 272.308 121 290.462 121C308.615 121 308.615 149 326.769 149C344.923 149 344.923 11 363.077 11C381.231 11 381.231 81 399.385 81C417.538 81 417.538 129 435.692 129C453.846 129 453.846 25 472 25V149H326.769H0V109Z" fill="url(#chart_gradient)"></path>
                                    <path d="M0 109C18.1538 109 18.1538 21 36.3077 21C54.4615 21 54.4615 41 72.6154 41C90.7692 41 90.7692 93 108.923 93C127.077 93 127.077 33 145.231 33C163.385 33 163.385 101 181.538 101C199.692 101 199.692 61 217.846 61C236 61 236 45 254.154 45C272.308 45 272.308 121 290.462 121C308.615 121 308.615 149 326.769 149C344.923 149 344.923 11 363.077 11C381.231 11 381.231 81 399.385 81C417.538 81 417.538 129 435.692 129C453.846 129 453.846 25 472 25" stroke="#22d3ee" strokeLinecap="round" strokeWidth="3"></path>
                                    <defs>
                                        <linearGradient gradientUnits="userSpaceOnUse" id="chart_gradient" x1="236" x2="236" y1="1" y2="149">
                                            <stop stopColor="#22d3ee" stopOpacity="0.3"></stop>
                                            <stop offset="1" stopColor="#22d3ee" stopOpacity="0"></stop>
                                        </linearGradient>
                                    </defs>
                                </svg>
                                <div className="flex justify-between mt-4 px-2 relative z-10 w-full">
                                    <p className="text-slate-500 text-[11px] font-bold">Mon</p>
                                    <p className="text-slate-500 text-[11px] font-bold">Tue</p>
                                    <p className="text-slate-500 text-[11px] font-bold">Wed</p>
                                    <p className="text-slate-500 text-[11px] font-bold">Thu</p>
                                    <p className="text-slate-500 text-[11px] font-bold">Fri</p>
                                    <p className="text-slate-500 text-[11px] font-bold">Sat</p>
                                    <p className="text-slate-500 text-[11px] font-bold">Sun</p>
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
                            <div className="p-4 hover:bg-slate-800/50 transition-colors cursor-pointer group">
                                <div className="flex justify-between items-start mb-1">
                                    <span className="text-[10px] font-bold text-rose-500 uppercase flex items-center gap-1">
                                        <span className="material-symbols-outlined text-[12px] fill-current">error</span>
                                        Critical
                                    </span>
                                    <span className="text-slate-500 text-[10px]">2m ago</span>
                                </div>
                                <h5 className="text-sm font-bold text-slate-200 truncate">Claude-3 Context Overflow</h5>
                                <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">System failed to truncate input for request ID #8421. Resulted in 400 Bad Request.</p>
                                <div className="mt-3 flex gap-2">
                                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">ID: 400</span>
                                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">Route: Premium</span>
                                </div>
                            </div>
                            <div className="p-4 hover:bg-slate-800/50 transition-colors cursor-pointer group">
                                <div className="flex justify-between items-start mb-1">
                                    <span className="text-[10px] font-bold text-accent-amber uppercase flex items-center gap-1">
                                        <span className="material-symbols-outlined text-[12px] fill-current">warning</span>
                                        Warning
                                    </span>
                                    <span className="text-slate-500 text-[10px]">14m ago</span>
                                </div>
                                <h5 className="text-sm font-bold text-slate-200 truncate">GPT-4 High Latency Spike</h5>
                                <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">Response time exceeded 5000ms threshold for 8 consecutive requests.</p>
                                <div className="mt-3 flex gap-2">
                                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">ID: Latency</span>
                                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">Route: Standard</span>
                                </div>
                            </div>
                            <div className="p-4 hover:bg-slate-800/50 transition-colors cursor-pointer group">
                                <div className="flex justify-between items-start mb-1">
                                    <span className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-1">
                                        <span className="material-symbols-outlined text-[12px] fill-current">info</span>
                                        Notice
                                    </span>
                                    <span className="text-slate-500 text-[10px]">1h ago</span>
                                </div>
                                <h5 className="text-sm font-bold text-slate-200 truncate">Cache Invalidation Loop</h5>
                                <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">Frequent TTL resets detected on model embedding cache.</p>
                                <div className="mt-3 flex gap-2">
                                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">ID: 304</span>
                                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">Route: Internal</span>
                                </div>
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
