"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import SystemConfigPanel from "@/components/admin/SystemConfigPanel";
import { API_BASE_URL } from "@/lib/api";

type FilterState = {
    mode: string;
    model: string;
    provider: string;
    route: string;
};

const defaultFilters: FilterState = {
    mode: "",
    model: "",
    provider: "",
    route: ""
};

const buildQuery = (params: Record<string, string | number | undefined>) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === "") {
            return;
        }
        query.set(key, String(value));
    });
    return query.toString();
};

const formatNumber = (value: number | null | undefined, fallback = "0") => {
    if (!Number.isFinite(Number(value))) return fallback;
    return Number(value).toLocaleString();
};

const formatPercent = (value: number | null | undefined) => {
    if (!Number.isFinite(Number(value))) return "0.0%";
    return `${Number(value).toFixed(1)}%`;
};

const formatCurrency = (value: number | null | undefined) => {
    if (!Number.isFinite(Number(value))) return "$0.00";
    return `$${Number(value).toFixed(4)}`;
};

type DashboardStats = {
    daily_requests?: number;
    ocr_success_rate?: number;
    llm_cost_est?: number;
    cache_hit_rate?: number;
};

type RoutingSeriesEntry = {
    day?: string;
    volume?: number;
};

type RoutingData = {
    series?: RoutingSeriesEntry[];
};

type KPIEntry = {
    value?: number;
    delta_pct?: number;
};

type TrendItem = {
    total?: number;
    p95?: number;
};

type BreakdownItem = {
    subject?: string;
    grade?: string;
    count?: number;
    model?: string;
    share?: number;
};

type OverviewBreakdowns = {
    subjects?: BreakdownItem[];
    grades?: BreakdownItem[];
    model_routing?: BreakdownItem[];
};

type OverviewQuality = {
    verified_rate?: number;
    schema_violation_rate?: number;
};

type OverviewHealth = {
    providers?: Array<{ provider?: string; error_rate?: number }>;
    streaming?: { disconnect_rate?: number; truncated_rate?: number };
};

type DashboardOverview = {
    kpis?: Record<string, KPIEntry>;
    trends?: {
        questions?: TrendItem[];
        cost?: TrendItem[];
        latency?: TrendItem[];
    };
    breakdowns?: OverviewBreakdowns;
    quality?: OverviewQuality;
    health?: OverviewHealth;
};

type SolveTraceEntry = {
    request_id?: string;
    user_id?: number;
    ui_goal?: string;
    ui_style?: string;
    resolved_profile_key?: string;
    input_tokens?: number;
    output_tokens?: number;
    deduct_committed?: boolean;
};

type ErrorEntry = {
    request_id?: string;
    error_type?: string;
    endpoint?: string;
};

type AnomalyData = {
    top_cost_users?: Array<{ user_id?: number; cost_usd?: number }>;
    token_spike_requests?: Array<{ request_id?: string; tokens_total?: number }>;
    ocr_failures?: Array<{ reason?: string; count?: number }>;
};

const TrendBars = ({ series, color }: { series: number[]; color: string }) => {
    const max = Math.max(...series, 1);
    return (
        <div className="flex items-end gap-1 h-14">
            {series.map((value, idx) => (
                <div
                    key={idx}
                    className="flex-1 rounded-sm"
                    style={{ height: `${(value / max) * 100}%`, backgroundColor: color }}
                    title={String(value)}
                />
            ))}
        </div>
    );
};

export default function AdminDashboardPage() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [routing, setRouting] = useState<RoutingData | null>(null);
    const [solveTraces, setSolveTraces] = useState<SolveTraceEntry[]>([]);
    const [selectedTrace, setSelectedTrace] = useState<SolveTraceEntry | null>(null);
    const [overview, setOverview] = useState<DashboardOverview | null>(null);
    const [errors, setErrors] = useState<ErrorEntry[]>([]);
    const [anomalies, setAnomalies] = useState<AnomalyData | null>(null);
    const [range, setRange] = useState("7d");
    const [filters, setFilters] = useState<FilterState>(defaultFilters);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const baseUrl = API_BASE_URL;
    const router = useRouter();
    const settingsPanelRef = useRef<HTMLDivElement | null>(null);
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);

    const adminFeatureLinks = [
        { label: "Overview", href: "/admin/dashboard" },
        { label: "Users", href: "/admin/users" },
        { label: "Quotas", href: "/admin/quotas" },
        { label: "Legacy Subscriptions", href: "/admin/legacy/subscriptions" },
        { label: "Prompt Registry", href: "/admin/prompt-registry" },
        { label: "Prompt Bindings", href: "/admin/prompt-bindings" },
        { label: "Logs", href: "/admin/logs" },
        { label: "LLM Usage", href: "/admin/observability/llm-usage" },
        { label: "Canonical Cache", href: "/admin/cache/canonical" },
        { label: "Question Identity", href: "/admin/cache/question-identity" },
        { label: "Content", href: "/admin/content" },
        { label: "Data", href: "/admin/data" },
    ];

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (settingsPanelRef.current && !settingsPanelRef.current.contains(event.target as Node)) {
                setIsSettingsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const clearSessionData = () => {
        if (typeof window === "undefined") return;
        localStorage.removeItem("token");
        localStorage.removeItem("user_id");
        localStorage.removeItem("user_name");
        localStorage.removeItem("user_avatar");
        localStorage.removeItem("user_role");
        localStorage.removeItem("session_token");
        localStorage.removeItem("user");
        localStorage.removeItem("subscription_cache");
        localStorage.clear();
        sessionStorage.clear();
    };

    const handleAdminLogout = () => {
        clearSessionData();
        setIsSettingsOpen(false);
        router.push("/login");
    };


    useEffect(() => {
        const controller = new AbortController();
        const fetchData = async () => {
            const token = localStorage.getItem("token");
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
                setStats(await statsRes.json() as DashboardStats);
                setRouting(await routingRes.json() as RoutingData);
                const tracesData = await tracesRes.json();
                setSolveTraces(Array.isArray(tracesData) ? (tracesData as SolveTraceEntry[]) : []);
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
    }, [baseUrl]);

    useEffect(() => {
        const controller = new AbortController();
        const fetchAnalytics = async () => {
            const token = localStorage.getItem("token");
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
            const query = buildQuery({ range, ...filters });
            try {
                const [overviewRes, errorsRes, anomaliesRes] = await Promise.all([
                    fetch(`${baseUrl}/api/v1/admin/analytics/overview?${query}`, { headers, signal: controller.signal }),
                    fetch(`${baseUrl}/api/v1/admin/analytics/errors?${buildQuery({ range, ...filters })}`, { headers, signal: controller.signal }),
                    fetch(`${baseUrl}/api/v1/admin/analytics/anomalies?${buildQuery({ range, ...filters })}`, { headers, signal: controller.signal })
                ]);
                if (!overviewRes.ok || !errorsRes.ok || !anomaliesRes.ok) {
                    throw new Error("Failed to load analytics data.");
                }
                setOverview(await overviewRes.json() as DashboardOverview);
                setErrors(await errorsRes.json() as ErrorEntry[]);
                setAnomalies(await anomaliesRes.json() as AnomalyData);
            } catch (err) {
                if ((err as Error).name === "AbortError") {
                    return;
                }
                console.error("Failed to fetch analytics data:", err);
            }
        };
        fetchAnalytics();
        return () => controller.abort();
    }, [baseUrl, range, filters]);

    const routingSeries = Array.isArray(routing?.series) ? routing.series : [];
    const maxVolume = routingSeries.length > 0
        ? Math.max(...routingSeries.map((x) => x.volume ?? 0), 1)
        : 1;

    const questionTrendSeries = useMemo(() => {
        const trend = overview?.trends?.questions ?? [];
        return trend.map((item) => item.total ?? 0);
    }, [overview]);

    const costTrendSeries = useMemo(() => {
        const trend = overview?.trends?.cost ?? [];
        return trend.map((item) => item.total ?? 0);
    }, [overview]);

    const latencyTrendSeries = useMemo(() => {
        const trend = overview?.trends?.latency ?? [];
        return trend.map((item) => item.p95 ?? 0);
    }, [overview]);

    if (isLoading) {
        return <div className="p-8 text-slate-400">Loading dashboard metrics...</div>;
    }

    if (errorMessage) {
        return <div className="p-8 text-rose-400">{errorMessage}</div>;
    }

    const kpis = overview?.kpis || {};

    return (
        <>
            <header className="sticky top-0 z-10 flex items-center justify-between bg-white/80 dark:bg-[#0F172A]/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-8 py-3 w-full">
                <div className="flex items-center gap-6">
                    <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">Analytics Dashboard</h2>
                    <div className="relative group">
                        <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
                            <span className="material-symbols-outlined text-lg">search</span>
                        </span>
                        <input className="bg-slate-800 border-none rounded-lg py-2 pl-10 pr-4 text-sm w-64 focus:ring-2 focus:ring-admin-primary text-slate-900 dark:text-white placeholder-slate-500 transition-all" placeholder="Search metrics or models..." type="text" />
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors relative">
                        <span className="material-symbols-outlined">notifications</span>
                        <span className="absolute top-2 right-2.5 size-2 bg-rose-500 rounded-full border-2 border-slate-200 dark:border-[#0F172A]"></span>
                    </button>
                    <button
                        onClick={handleAdminLogout}
                        className="px-3 py-2 rounded-lg bg-red-600/10 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/40 hover:bg-red-600/20 transition-colors text-xs font-bold uppercase tracking-widest"
                        aria-label="Logout and clear cache"
                    >
                        Logout
                    </button>
                    <div className="relative" ref={settingsPanelRef}>
                        <button
                            onClick={() => setIsSettingsOpen((prev) => !prev)}
                            className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors flex items-center gap-1"
                            aria-expanded={isSettingsOpen}
                            aria-label="Settings and session actions"
                        >
                            <span className="material-symbols-outlined">settings</span>
                            <span className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Menu</span>
                        </button>
                        {isSettingsOpen && (
                            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl shadow-black/20 ring-1 ring-black/5 z-50">
                                <div className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800">
                                    <div className="p-3">
                                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Quick Links</p>
                                        <div className="flex flex-col gap-1">
                                            {adminFeatureLinks.map((item) => (
                                                <Link
                                                    key={item.href}
                                                    href={item.href}
                                                    onClick={() => setIsSettingsOpen(false)}
                                                    className="text-sm text-slate-700 dark:text-slate-200 hover:text-admin-primary hover:font-semibold transition-colors"
                                                >
                                                    {item.label}
                                                </Link>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="p-3">
                                        <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-slate-400 mb-1">
                                            Dangerous
                                        </p>
                                        <button
                                            onClick={handleAdminLogout}
                                            className="w-full text-left rounded-lg px-3 py-2 text-sm font-bold text-red-600 bg-red-50 dark:bg-red-900/30 hover:bg-red-100 dark:hover:bg-red-800 transition-colors"
                                        >
                                            Full Sign Out (clears cache)
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                    <button className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined">light_mode</span>
                    </button>
                </div>
            </header>

            <div className="p-8 max-w-[1400px] mx-auto w-full flex flex-col gap-8">
                <section className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-5">
                    <div className="flex flex-wrap items-center gap-4 text-sm text-slate-300">
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500 uppercase text-xs tracking-widest">Range</span>
                            <select
                                value={range}
                                onChange={(e) => setRange(e.target.value)}
                                className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
                            >
                                <option value="7d">7 days</option>
                                <option value="30d">30 days</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500 uppercase text-xs tracking-widest">Mode</span>
                            <select
                                value={filters.mode}
                                onChange={(e) => setFilters((prev) => ({ ...prev, mode: e.target.value }))}
                                className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
                            >
                                <option value="">All</option>
                                <option value="minimal">Quick</option>
                                <option value="detailed">Detailed</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500 uppercase text-xs tracking-widest">Provider</span>
                            <input
                                value={filters.provider}
                                onChange={(e) => setFilters((prev) => ({ ...prev, provider: e.target.value }))}
                                placeholder="openai"
                                className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500 uppercase text-xs tracking-widest">Model</span>
                            <input
                                value={filters.model}
                                onChange={(e) => setFilters((prev) => ({ ...prev, model: e.target.value }))}
                                placeholder="gpt-5-mini"
                                className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500 uppercase text-xs tracking-widest">Route</span>
                            <input
                                value={filters.route}
                                onChange={(e) => setFilters((prev) => ({ ...prev, route: e.target.value }))}
                                placeholder="solve_v3"
                                className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
                            />
                        </div>
                    </div>
                </section>

                <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="kpi-card border-l-4 border-accent-cyan p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Total Students</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.total_students?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.total_students?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-emerald p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Active Students Today</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.active_students_today?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.active_students_today?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-amber p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Online Now</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.online_now?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.online_now?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-purple p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">New Users Today</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.new_users_today?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.new_users_today?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-cyan p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Questions Today</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.questions_today?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.questions_today?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-emerald p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Avg Qs / Active</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.avg_questions_per_active?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.avg_questions_per_active?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-amber p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Tokens Today</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">
                            {formatNumber(kpis?.tokens_in_today?.value)} / {formatNumber(kpis?.tokens_out_today?.value)}
                        </h3>
                        <p className="text-[11px] text-slate-500 mt-1">Delta {formatPercent(kpis?.tokens_in_today?.delta_pct)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-purple p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">LLM Cost Today</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatCurrency(kpis?.llm_cost_today?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Cost / Q {formatCurrency(kpis?.cost_per_question?.value)}</p>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-cyan p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Credit Deductions</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(kpis?.credit_deductions_today?.value)}</h3>
                        <p className="text-[11px] text-slate-500 mt-1">Failures {formatNumber(kpis?.deduction_failures_today?.value)}</p>
                    </div>
                </section>

                <section className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Questions Trend</h4>
                        <p className="text-xs text-slate-400 mb-3">Quick vs Study vs Solve</p>
                        <TrendBars series={questionTrendSeries} color="#38BDF8" />
                    </div>
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Cost Trend</h4>
                        <p className="text-xs text-slate-400 mb-3">Total cost per day</p>
                        <TrendBars series={costTrendSeries} color="#A855F7" />
                    </div>
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Latency Trend</h4>
                        <p className="text-xs text-slate-400 mb-3">p95 latency (ms)</p>
                        <TrendBars series={latencyTrendSeries} color="#34D399" />
                    </div>
                </section>

                <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Breakdowns</h4>
                        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-slate-300">
                            <div>
                                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Top Subjects</p>
                                {(overview?.breakdowns?.subjects ?? []).map((item, index) => (
                                    <div key={`${item.subject ?? "subject"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 py-1">
                                        <span>{item.subject}</span>
                                        <span className="text-slate-400">{item.count}</span>
                                    </div>
                                ))}
                            </div>
                            <div>
                                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Grades</p>
                                {(overview?.breakdowns?.grades ?? []).map((item, index) => (
                                    <div key={`${item.grade ?? "grade"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 py-1">
                                        <span>{item.grade}</span>
                                        <span className="text-slate-400">{item.count}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Model Routing Share</h4>
                        <div className="mt-4 space-y-2 text-sm text-slate-300">
                            {(overview?.breakdowns?.model_routing ?? []).slice(0, 6).map((item, index) => (
                                <div key={`${item.model ?? "model"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-1">
                                    <span>{item.model}</span>
                                    <span className="text-slate-400">{item.share}%</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Quality & Safety</h4>
                        <div className="mt-4 text-sm text-slate-300 space-y-2">
                            <div className="flex items-center justify-between">
                                <span>Verified pass rate</span>
                                <span>{formatPercent(overview?.quality?.verified_rate)}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span>Schema violations</span>
                                <span>{formatPercent(overview?.quality?.schema_violation_rate)}</span>
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Operational Health</h4>
                        <div className="mt-4 text-sm text-slate-300 space-y-2">
                            {(overview?.health?.providers ?? []).map((item, index) => (
                                <div key={`${item.provider ?? "provider"}-${index}`} className="flex items-center justify-between">
                                    <span>{item.provider}</span>
                                    <span>{formatPercent(item.error_rate)}</span>
                                </div>
                            ))}
                            <div className="flex items-center justify-between">
                                <span>Stream disconnects</span>
                                <span>{formatPercent(overview?.health?.streaming?.disconnect_rate)}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span>Stream truncations</span>
                                <span>{formatPercent(overview?.health?.streaming?.truncated_rate)}</span>
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Recent Errors Inbox</h4>
                        <div className="mt-4 text-xs text-slate-400 space-y-2">
                            {errors.length === 0 && <div>No errors in the selected window.</div>}
                            {errors.slice(0, 6).map((item, index) => (
                                <div key={`${item.request_id ?? "error"}-${item.error_type ?? "type"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-1">
                                    <span>{item.error_type}</span>
                                    <span className="text-slate-500">{item.endpoint || "unknown"}</span>
                                </div>
                            ))}
                        </div>
                        <button className="mt-4 text-xs font-bold text-admin-primary">View All Logs</button>
                    </div>
                </section>

                <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">Anomalies</h4>
                        <div className="mt-4 text-sm text-slate-300 space-y-4">
                            <div>
                                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Top Cost Users</p>
                                {(anomalies?.top_cost_users ?? []).map((item, index) => (
                                    <div key={`${item.user_id ?? "user"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 py-1">
                                        <span>User {item.user_id}</span>
                                        <span className="text-slate-400">{formatCurrency(item.cost_usd)}</span>
                                    </div>
                                ))}
                            </div>
                            <div>
                                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Token Spike Requests</p>
                                {(anomalies?.token_spike_requests ?? []).map((item, index) => (
                                    <div key={`${item.request_id ?? "token"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 py-1">
                                        <span>{item.request_id?.slice(0, 6)}</span>
                                        <span className="text-slate-400">{formatNumber(item.tokens_total)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-6">
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">OCR Failure Reasons</h4>
                        <div className="mt-4 text-sm text-slate-300 space-y-2">
                            {(anomalies?.ocr_failures ?? []).map((item, index) => (
                                <div key={`${item.reason ?? "reason"}-${index}`} className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 py-1">
                                    <span>{item.reason}</span>
                                    <span className="text-slate-400">{item.count}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="kpi-card border-l-4 border-accent-cyan p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Daily Requests</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(stats?.daily_requests)}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-emerald p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">OCR Success Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatPercent(stats?.ocr_success_rate)}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-purple p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">LLM Cost Est.</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatCurrency(stats?.llm_cost_est)}</h3>
                    </div>
                    <div className="kpi-card border-l-4 border-accent-amber p-5 rounded-xl shadow-lg border-slate-200 dark:border-slate-800 border">
                        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Cache Hit Rate</p>
                        <h3 className="text-2xl font-bold mt-1 tracking-tight text-slate-900 dark:text-white">{formatNumber(stats?.cache_hit_rate)}%</h3>
                    </div>
                </section>

                <section className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xl">
                    <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-800/20">
                        <div>
                            <h4 className="text-base font-bold text-slate-900 dark:text-white">Model Routing Volume</h4>
                            <p className="text-sm text-slate-400">Requests distributed across major models</p>
                        </div>
                    </div>
                    <div className="p-6">
                        <div className="relative h-[240px] w-full flex flex-col justify-end bg-slate-800/10 rounded-lg p-2">
                            <div className="flex items-end justify-between h-48 px-4 gap-2">
                                {routingSeries.map((s, index) => {
                                    const h = (Number(s.volume ?? 0) / maxVolume) * 100;
                                    return (
                                        <div key={`${s.day ?? "day"}-${index}`} className="flex-1 flex flex-col items-center gap-2 group">
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

                <SystemConfigPanel baseUrl={baseUrl} />

                <section className="bg-white dark:bg-panel-dark border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl">
                    <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-800/20">
                        <div>
                            <h4 className="text-base font-bold text-slate-900 dark:text-white">Solve Request Traces</h4>
                            <p className="text-sm text-slate-400">Latest streamed solve requests (JSONL)</p>
                        </div>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Last 120</span>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-3">
                        <div className="lg:col-span-2 border-r border-slate-200 dark:border-slate-800">
                            <div className="max-h-[420px] overflow-y-auto divide-y divide-slate-800">
                                {solveTraces.length === 0 && (
                                    <div className="p-6 text-slate-500 text-sm italic">No trace logs available.</div>
                                )}
                                {solveTraces.map((entry, index) => (
                                    <button
                                        key={`${entry.request_id ?? "trace"}-${entry.user_id ?? "user"}-${index}`}
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
                            <div className="mt-3 bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg p-4 max-h-[360px] overflow-y-auto">
                                {selectedTrace ? (
                                    <pre className="text-[11px] text-slate-300 whitespace-pre-wrap">{JSON.stringify(selectedTrace, null, 2)}</pre>
                                ) : (
                                    <p className="text-sm text-slate-500">Pick a trace entry to inspect the OpenAI payload and metering.</p>
                                )}
                            </div>
                        </div>
                    </div>
                </section>

                <footer className="mt-auto pt-8 flex items-center justify-between text-slate-500 text-[11px] font-medium border-t border-slate-200 dark:border-slate-800">
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
