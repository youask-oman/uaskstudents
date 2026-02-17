"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import StudentLayout from "@/components/layout/StudentLayout";
import MathRenderer from "@/components/math/MathJaxRenderer";
import ShareSolutionModal from "@/components/share/ShareSolutionModal";
import { useToast } from "@/components/ui/ToastProvider";
import {
    fetchWalletLedger,
    fetchWalletPrograms,
    fetchWalletSummary,
    updateWalletTier,
    WalletLedgerEntry,
    WalletProgramEnrollment,
    WalletSummary,
    WalletTier,
} from "@/lib/wallet";

interface ChatSession {
    id: number;
    attempt_id?: string | null;
    request_id?: string | null;
    title: string;
    subject?: string;
    topic?: string;
    grade_level?: string;
    difficulty?: string;
    topics?: string[];
    input?: string;
    created_at: string;
    is_saved?: boolean;
    credits_charged_total?: number;
    credits_balance_after?: number | null;
    per_question_charges?: Array<{
        question_id?: string | null;
        question_index?: number | null;
        credits_charged?: number;
        balance_after?: number | null;
        created_at?: string | null;
    }>;
    telemetry?: {
        latency_ms_total?: number;
        total_tokens?: number;
        model?: string;
        tier_effective?: string;
        effective_tier?: string;
        tier_requested?: string;
        tier?: string;
    };
}

interface UserUsage {
    questions_count: number;
    scans_count: number;
}

interface UserProfile {
    full_name?: string;
    usage?: UserUsage;
    is_public?: boolean;
    learning_interests?: string[];
}

interface StatCard {
    label: string;
    value: string;
    icon: string;
    color: string;
    trend: string;
}

type ProfileUpdate = {
    is_public?: boolean;
    learning_interests?: string[];
};

function DashboardContent() {
    const { pushToast } = useToast();
    const initialStats: StatCard[] = [
        { label: "Problems Solved", value: "...", icon: "analytics", color: "blue", trend: "..." },
        { label: "Token Usage", value: "...", icon: "offline_bolt", color: "amber", trend: "Monthly" },
        { label: "Scans", value: "...", icon: "document_scanner", color: "purple", trend: "Total" },
    ];
    const [stats, setStats] = useState<StatCard[]>(initialStats);
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [loading, setLoading] = useState(true);
    const [user, setUser] = useState<UserProfile | null>(null);
    const [activeTab, setActiveTab] = useState("history"); // history, bookmarked
    const router = useRouter();
    const searchParams = useSearchParams();
    const tabParam = searchParams.get('tab');
    const [walletSummary, setWalletSummary] = useState<WalletSummary | null>(null);
    const [walletPrograms, setWalletPrograms] = useState<WalletProgramEnrollment[]>([]);
    const [walletLedger, setWalletLedger] = useState<WalletLedgerEntry[]>([]);
    const [walletLoading, setWalletLoading] = useState(true);
    const [walletError, setWalletError] = useState<string | null>(null);
    const [solveAsTier, setSolveAsTier] = useState<WalletTier>("STANDARD");
    const [tierSaving, setTierSaving] = useState(false);
    const resolveHistorySessionRoute = (session: ChatSession) => {
        const telemetry = session?.telemetry;
        const rawTier =
            telemetry?.tier_effective ||
            telemetry?.effective_tier ||
            telemetry?.tier_requested ||
            telemetry?.tier ||
            "";
        return String(rawTier).trim().toUpperCase() === "FINAL"
            ? `/chat_final/${session.id}`
            : `/chat/${session.id}`;
    };

    useEffect(() => {
        if (tabParam && ['history', 'bookmarked'].includes(tabParam)) {
            setActiveTab(tabParam);
        }
    }, [tabParam]);

    const [isPublic, setIsPublic] = useState(false);
    const [interests, setInterests] = useState<string[]>([]);
    const [newInterest, setNewInterest] = useState("");
    const [historyPage, setHistoryPage] = useState(1);
    const historyPerPage = 10;
    const [historySearch, setHistorySearch] = useState("");
    const [shareModalOpen, setShareModalOpen] = useState(false);
    const [shareAttemptId, setShareAttemptId] = useState<string | null>(null);
    const [shareSessionId, setShareSessionId] = useState<number | null>(null);

    const updateProfile = async (updates: ProfileUpdate) => {
        const userId = localStorage.getItem("user_id");
        if (!userId) return;
        try {
            await fetch(`/api/v1/user/profile?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
        } catch (e) {
            console.error("Failed to update profile", e);
        }
    };

    const togglePublic = () => {
        const newVal = !isPublic;
        setIsPublic(newVal);
        updateProfile({ is_public: newVal });
    };

    const addInterest = () => {
        if (!newInterest.trim()) return;
        if (interests.includes(newInterest.trim())) return;
        const updated = [...interests, newInterest.trim()];
        setInterests(updated);
        setNewInterest("");
        updateProfile({ learning_interests: updated });
    };

    const removeInterest = (tag: string) => {
        const updated = interests.filter(i => i !== tag);
        setInterests(updated);
        updateProfile({ learning_interests: updated });
    };

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) {
            router.push("/login");
            return;
        }

        const storedUser = localStorage.getItem("user");
        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser) as UserProfile);
            } catch (e) {
                console.error("Error parsing user data", e);
            }
        }

        const fetchData = async () => {
            try {
                let fetchedHistory: ChatSession[] = [];
                // Fetch History (ALL sessions)
                const historyRes = await fetch(`/api/v1/history?user_id=${userId}&saved_only=false`);
                if (historyRes.ok) {
                    const data = await historyRes.json();
                    fetchedHistory = Array.isArray(data) ? data : [];
                    setHistory(fetchedHistory);
                }

                // Fetch Profile Stats
                const profileRes = await fetch(`/api/v1/user/profile?user_id=${userId}`);
                if (profileRes.ok) {
                    const profile = (await profileRes.json()) as UserProfile;
                    setIsPublic(Boolean(profile.is_public));
                    setInterests(profile.learning_interests || []);
                    const usage = profile.usage ?? { questions_count: 0, scans_count: 0 };
                    const problemsValue = usage.questions_count.toString();
                    const scansValue = usage.scans_count.toString();
                    const creditsUsedTotal = fetchedHistory.reduce(
                        (sum, row) => sum + Number(row.credits_charged_total || 0),
                        0,
                    );
                    setStats([
                        {
                            label: "Problems Solved",
                            value: problemsValue,
                            icon: "analytics",
                            color: "blue",
                            trend: "Total"
                        },
                        {
                            label: "Credits Used",
                            value: creditsUsedTotal.toFixed(2),
                            icon: "offline_bolt",
                            color: "amber",
                            trend: "Total"
                        },
                        {
                            label: "Scans",
                            value: scansValue,
                            icon: "document_scanner",
                            color: "purple",
                            trend: "Total"
                        },
                    ]);
                }

            } catch (error) {
                console.error("Failed to fetch dashboard data:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [router]);

    useEffect(() => {
        let active = true;
        const loadWallet = async () => {
            try {
                const [summary, ledgerResp, programsResp] = await Promise.all([
                    fetchWalletSummary(),
                    fetchWalletLedger(6, 0),
                    fetchWalletPrograms(10, 0),
                ]);
                if (!active) return;
                setWalletSummary(summary);
                setWalletLedger(ledgerResp.items || []);
                setWalletPrograms(programsResp.items || []);
                const nextTier = (summary.effective_tier || "STANDARD") as WalletTier;
                setSolveAsTier(nextTier);
                setWalletError(null);
            } catch (err) {
                if (!active) return;
                const message = err instanceof Error ? err.message : "Unable to load wallet data";
                const requestId = err && typeof err === "object" && "requestId" in err ? (err as { requestId?: string }).requestId : undefined;
                setWalletError(message);
                pushToast({
                    type: "error",
                    title: "Wallet unavailable",
                    message,
                    requestId,
                });
            } finally {
                if (active) setWalletLoading(false);
            }
        };
        void loadWallet();
        return () => {
            active = false;
        };
    }, [pushToast]);

    const handleSolveAsChange = async (nextTier: WalletTier) => {
        setSolveAsTier(nextTier);
        setTierSaving(true);
        try {
            await updateWalletTier(nextTier);
            const refreshed = await fetchWalletSummary();
            setWalletSummary(refreshed);
            const effective = (refreshed.effective_tier || nextTier) as WalletTier;
            setSolveAsTier(effective);
            localStorage.setItem("uask.solveTier", effective);
            pushToast({
                type: "success",
                title: "Solve tier updated",
                message: `Default Solve as is now ${effective}.`,
            });
        } catch (err) {
            const message = err instanceof Error ? err.message : "Unable to update solve tier";
            const requestId = err && typeof err === "object" && "requestId" in err ? (err as { requestId?: string }).requestId : undefined;
            pushToast({
                type: "error",
                title: "Tier update failed",
                message,
                requestId,
            });
        } finally {
            setTierSaving(false);
        }
    };

    useEffect(() => {
        if (activeTab === "history") {
            setHistoryPage(1);
        }
    }, [activeTab, history.length, historySearch]);

    const normalizedHistorySearch = historySearch.trim().toLowerCase();
    const filteredHistory = normalizedHistorySearch
        ? history.filter(session => [session.title, session.subject, session.topic, session.input]
            .filter(Boolean)
            .some(value => value!.toLowerCase().includes(normalizedHistorySearch)))
        : history;
    const totalHistoryPages = Math.max(1, Math.ceil(filteredHistory.length / historyPerPage));
    const historyStart = (historyPage - 1) * historyPerPage;
    const pagedHistory = filteredHistory.slice(historyStart, historyStart + historyPerPage);

    return (
        <StudentLayout>
            <section className="p-8">
                <div className="max-w-5xl mx-auto space-y-8">
                    {/* Hero/Welcome Section */}
                    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-amber-200 to-yellow-400 p-10 text-slate-800 shadow-xl">
                        <div className="relative z-10">
                            <h1 className="text-4xl font-bold mb-4 tracking-tight leading-tight">
                                Welcome back, {user?.full_name?.split(' ')[0] || "Alex"}. <br />Ready to solve?
                            </h1>
                            <div className="text-slate-800/90 max-w-md mb-8 text-sm">
                                {history.length > 0 ? (
                                    <div className="flex flex-col gap-1">
                                        <span>Your last problem:</span>
                                        <div className="font-bold bg-white/40 px-3 py-2 rounded-lg backdrop-blur-sm inline-block">
                                            <MathRenderer content={history[0].title} mode="prose" />
                                        </div>
                                        <span>is ready for review.</span>
                                    </div>
                                ) : (
                                    "Start your first problem solving session today!"
                                )}
                            </div>
                            <div className="flex gap-4">
                                <button
                                    onClick={() => router.push('/solve')}
                                    className="bg-white text-amber-700 px-6 py-3 rounded-lg font-bold text-sm shadow-lg hover:shadow-xl transition-all flex items-center gap-2"
                                >
                                    <span className="material-symbols-outlined text-sm">add_circle</span>
                                    New Solve
                                </button>
                                {history.length > 0 && (
                                    <button
                                        onClick={() => router.push(resolveHistorySessionRoute(history[0]))}
                                        className="bg-amber-600/20 text-slate-800 border border-amber-600/30 px-6 py-3 rounded-lg font-bold text-sm shadow-sm hover:bg-amber-600/30 transition-all flex items-center gap-2"
                                    >
                                        <span className="material-symbols-outlined text-sm">history</span>
                                        Continue Last
                                    </button>
                                )}
                            </div>
                        </div>
                        {/* Abstract Geometric Shapes */}
                        <div className="absolute -right-20 -top-20 w-80 h-80 bg-white/10 rounded-full blur-3xl"></div>
                        <div className="absolute right-10 bottom-10 opacity-20">
                            <span className="material-symbols-outlined text-[120px]" style={{ fontVariationSettings: "'wght' 200" }}>calculate</span>
                        </div>
                    </div>

                    {/* Statistics Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {stats.map((stat, idx) => (
                            <div key={idx} className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                                <div className="flex items-center justify-between mb-4">
                                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${stat.color === 'blue' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' :
                                        stat.color === 'purple' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400' :
                                            'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
                                        }`}>
                                        <span className="material-symbols-outlined">{stat.icon}</span>
                                    </div>
                                    <span className={`text-xs font-bold ${stat.color === 'amber' ? 'text-amber-500' : stat.color === 'blue' ? 'text-green-500' : 'text-slate-400'}`}>
                                        {stat.trend}
                                    </span>
                                </div>
                                <h3 className="text-slate-500 text-sm font-medium">{stat.label}</h3>
                                <p className="text-2xl font-bold mt-1 tracking-tight">{stat.value}</p>
                            </div>
                        ))}
                    </div>

                    {/* Wallet Snapshot */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-sm font-bold">Wallet Snapshot</h3>
                                    <p className="text-xs text-slate-500">Computed balance and active tier</p>
                                </div>
                                <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded-full bg-primary/10 text-primary">
                                    {walletSummary?.effective_tier || "SHORT_STEPS"}
                                </span>
                            </div>
                            <div className="text-3xl font-black">
                                {walletSummary ? walletSummary.spendable_balance.toFixed(2) : "--"} credits
                            </div>
                            <div className="space-y-2">
                                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                                    Solve as
                                </label>
                                <select
                                    value={solveAsTier}
                                    onChange={(e) => handleSolveAsChange(e.target.value as WalletTier)}
                                    disabled={tierSaving || walletLoading}
                                    className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm font-semibold"
                                >
                                    <option value="SHORT_STEPS">Short Steps</option>
                                    <option value="FINAL">Final Answer</option>
                                    <option value="STANDARD">Standard</option>
                                    <option value="RESEARCH">Research</option>
                                </select>
                                <p className="text-[11px] text-slate-500">
                                    This sets your default Solve tier across pages.
                                </p>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-xs text-slate-500">
                                <div>
                                    <p className="font-semibold">Pending Holds</p>
                                    <p>{walletSummary ? walletSummary.pending_hold_credits.toFixed(2) : "--"} credits</p>
                                </div>
                                <div>
                                    <p className="font-semibold">Expiring Soon</p>
                                    <p>{walletSummary ? walletSummary.expiring_soon_credits.toFixed(2) : "--"} credits</p>
                                </div>
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button
                                    onClick={() => router.push("/billing")}
                                    className="flex-1 bg-primary text-white text-xs font-bold px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors"
                                >
                                    Open Wallet
                                </button>
                                <button
                                    onClick={() => router.push("/billing/payment")}
                                    className="flex-1 bg-slate-100 dark:bg-slate-800 text-xs font-bold px-4 py-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                                >
                                    Top Up
                                </button>
                            </div>
                            {walletLoading && (
                                <p className="text-xs text-slate-400">Loading wallet snapshot...</p>
                            )}
                            {walletError && (
                                <p className="text-xs text-rose-500">Wallet data unavailable.</p>
                            )}
                        </div>

                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-bold">Recent Usage</h3>
                                <span className="text-[10px] text-slate-400 uppercase tracking-widest">Ledger</span>
                            </div>
                            {walletLoading ? (
                                <p className="text-sm text-slate-400">Loading usage...</p>
                            ) : walletLedger.length === 0 ? (
                                <p className="text-sm text-slate-500">No recent credit activity.</p>
                            ) : (
                                <ul className="space-y-3">
                                    {walletLedger.slice(0, 5).map((entry) => (
                                        <li key={entry.id} className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-300">
                                            <div>
                                                <p className="font-semibold">{entry.event_type.replace(/_/g, " ")}</p>
                                                <p className="text-[10px] text-slate-400">
                                                    {new Date(entry.created_at).toLocaleString()}
                                                </p>
                                            </div>
                                            <span className={`font-bold ${entry.credits_delta >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                                                {entry.credits_delta >= 0 ? "+" : ""}{entry.credits_delta.toFixed(2)}
                                            </span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>

                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-bold">Active Programs</h3>
                                <span className="text-[10px] text-slate-400 uppercase tracking-widest">Enrollments</span>
                            </div>
                            {walletLoading ? (
                                <p className="text-sm text-slate-400">Loading programs...</p>
                            ) : walletPrograms.length === 0 ? (
                                <p className="text-sm text-slate-500">No active credit programs.</p>
                            ) : (
                                <ul className="space-y-2">
                                    {walletPrograms.map((program) => (
                                        <li key={program.id} className="text-xs text-slate-600 dark:text-slate-300">
                                            <p className="font-semibold">{program.program_name || program.program_slug}</p>
                                            {program.next_grant_date && (
                                                <p className="text-[10px] text-slate-400">
                                                    Next grant: {new Date(program.next_grant_date).toLocaleDateString()}
                                                </p>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </div>

                    {/* Profile & Interests Section */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Public Profile Card */}
                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
                            <div>
                                <div className="flex items-center gap-3 mb-2">
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isPublic ? 'bg-green-100 text-green-600' : 'bg-slate-100 text-slate-500'}`}>
                                        <span className="material-symbols-outlined text-lg">public</span>
                                    </div>
                                    <h3 className="font-bold text-sm">Public Profile</h3>
                                </div>
                                <p className="text-xs text-slate-500 mb-4">
                                    Allow other students to see you online and view your shared solutions relative to your university.
                                </p>
                            </div>
                            <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl">
                                <span className={`text-xs font-bold ${isPublic ? 'text-green-600' : 'text-slate-500'}`}>
                                    {isPublic ? "Visible" : "Hidden"}
                                </span>
                                <button
                                    onClick={togglePublic}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isPublic ? 'bg-green-500' : 'bg-slate-300'}`}
                                >
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isPublic ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                            </div>
                        </div>

                        {/* Learning Interests Card */}
                        <div className="md:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-600 flex items-center justify-center">
                                    <span className="material-symbols-outlined text-lg">school</span>
                                </div>
                                <h3 className="font-bold text-sm">Learning Interests</h3>
                            </div>

                            <div className="flex flex-wrap gap-2 mb-4">
                                {interests.map((tag, idx) => (
                                    <div key={idx} className="flex items-center gap-1 pl-3 pr-1 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                                        <span>{tag}</span>
                                        <button onClick={() => removeInterest(tag)} className="w-5 h-5 flex items-center justify-center rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-red-500 transition-colors">
                                            <span className="material-symbols-outlined text-[14px]">close</span>
                                        </button>
                                    </div>
                                ))}
                                {interests.length === 0 && (
                                    <span className="text-xs text-slate-400 italic py-1">No interests added yet.</span>
                                )}
                            </div>

                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={newInterest}
                                    onChange={(e) => setNewInterest(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && addInterest()}
                                    placeholder="Add a topic (e.g. Calculus, Physics)..."
                                    className="flex-1 bg-slate-50 dark:bg-slate-800 border-none rounded-lg text-sm px-4 py-2 focus:ring-2 focus:ring-primary/50 outline-none"
                                />
                                <button
                                    onClick={addInterest}
                                    disabled={!newInterest.trim()}
                                    className="bg-primary text-white px-4 py-2 rounded-lg text-sm font-bold shadow-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                >
                                    Add
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Recent Solutions Section */}
                    {/* Recent Solutions Section */}
                    {/* Main Content Areas with Tabs */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden min-h-[400px]">
                        {/* Tabs Header */}
                        <div className="px-6 border-b border-slate-100 dark:border-slate-800 flex items-center gap-8">
                            {["history", "bookmarked"].map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    className={`py-4 text-sm font-bold capitalize transition-colors relative ${activeTab === tab
                                        ? 'text-primary dark:text-white'
                                        : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                                        }`}
                                >
                                    {tab}
                                    {activeTab === tab && (
                                        <div className="absolute bottom-0 left-0 w-full h-0.5 bg-primary dark:bg-white rounded-t-full"></div>
                                    )}
                                </button>
                            ))}
                        </div>

                        {/* Content */}
                        <div className="divide-y divide-slate-100 dark:divide-slate-800">
                            {loading ? (
                                <div className="p-12 flex justify-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                </div>
                            ) : (
                                <>
                                    {activeTab === 'history' && (
                                        filteredHistory.length === 0 ? (
                                            <div className="p-12 text-center text-slate-500 italic">No history found.</div>
                                        ) : (
                                            <>
                                                <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                                    <div className="text-xs font-semibold text-slate-500">History</div>
                                                    <div className="relative w-full md:w-64">
                                                        <span className="material-symbols-outlined text-sm text-slate-400 absolute left-3 top-1/2 -translate-y-1/2">search</span>
                                                        <input
                                                            type="text"
                                                            value={historySearch}
                                                            onChange={(e) => setHistorySearch(e.target.value)}
                                                            placeholder="Search history..."
                                                            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/30"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="px-6 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 grid grid-cols-[2fr_1fr_1.2fr_0.8fr] gap-4">
                                                    <div>Input</div>
                                                    <div>Topic</div>
                                                    <div>Billing</div>
                                                    <div className="text-right">Date</div>
                                                </div>
                                                {pagedHistory.map((session) => (
                                                    <div
                                                        key={session.id}
                                                        onClick={() => router.push(resolveHistorySessionRoute(session))}
                                                        className="p-4 flex items-center hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group px-6"
                                                    >
                                                        <div className="grid grid-cols-[2fr_1fr_1.2fr_0.8fr] gap-4 items-center w-full">
                                                            <div className="flex items-center gap-3 min-w-0">
                                                                <div className="w-9 h-9 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 group-hover:bg-primary/10 group-hover:text-primary transition-colors flex-shrink-0">
                                                                    <span className="material-symbols-outlined">
                                                                        {session.subject === 'Physics' ? 'science' : 'functions'}
                                                                    </span>
                                                                </div>
                                                                <div className="min-w-0 flex-1">
                                                                    <div className="text-sm font-semibold text-slate-700 dark:text-slate-200" title={session.input}>
                                                                        <MathRenderer content={session.input && session.input.length > 100 ? session.input.substring(0, 100) + "..." : (session.input || "No input")} mode="prose" />
                                                                    </div>
                                                                    {session.is_saved && (
                                                                        <span className="mt-1 inline-flex px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-[10px] font-bold rounded">Saved</span>
                                                                    )}
                                                                </div>
                                                            </div>

                                                            <div className="flex flex-col gap-1 min-w-0 pr-2">
                                                                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 truncate">
                                                                    {session.subject || "Math"}
                                                                </div>
                                                                <div className="flex flex-wrap gap-1">
                                                                    {session.topic && (
                                                                        <span className="text-[10px] text-slate-500 truncate max-w-full">
                                                                            {session.topic}
                                                                        </span>
                                                                    )}
                                                                    {session.grade_level && (
                                                                        <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] text-slate-500 border border-slate-200 dark:border-slate-700 whitespace-nowrap">
                                                                            {session.grade_level}
                                                                        </span>
                                                                    )}
                                                                    {session.difficulty && (
                                                                        <span className={`px-1.5 py-0.5 rounded text-[10px] border whitespace-nowrap ${session.difficulty.toLowerCase().includes('hard') ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-900/30' :
                                                                            session.difficulty.toLowerCase().includes('medium') ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-100 dark:border-amber-900/30' :
                                                                                'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-900/30'
                                                                            }`}>
                                                                            {session.difficulty}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>

                                                            <div className="text-[11px] text-slate-600 dark:text-slate-300 space-y-1">
                                                                <div className="font-semibold">
                                                                    Charged:{" "}
                                                                    <span className="text-rose-600 dark:text-rose-400">
                                                                        -{Number(session.credits_charged_total || 0).toFixed(2)} cr
                                                                    </span>
                                                                </div>
                                                                {typeof session.credits_balance_after === "number" && (
                                                                    <div>
                                                                        Left after:{" "}
                                                                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                                                                            {Number(session.credits_balance_after || 0).toFixed(2)} cr
                                                                        </span>
                                                                    </div>
                                                                )}
                                                                {Array.isArray(session.per_question_charges) && session.per_question_charges.length > 1 && (
                                                                    <div className="text-[10px] text-slate-500 dark:text-slate-400 space-y-0.5">
                                                                        {session.per_question_charges.slice(0, 3).map((item, idx) => (
                                                                            <div key={`${session.id}:q:${idx}`}>
                                                                                {(item.question_id || `q${item.question_index ?? idx + 1}`)}: -{Number(item.credits_charged || 0).toFixed(2)}
                                                                                {typeof item.balance_after === "number" ? ` -> ${Number(item.balance_after || 0).toFixed(2)}` : ""}
                                                                            </div>
                                                                        ))}
                                                                        {session.per_question_charges.length > 3 && (
                                                                            <div>+{session.per_question_charges.length - 3} more</div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>

                                                            <div className="text-xs text-slate-500 text-right">
                                                                <div>{new Date(session.created_at).toLocaleDateString()}</div>
                                                                <button
                                                                    type="button"
                                                                    onClick={(event) => {
                                                                        event.stopPropagation();
                                                                        setShareAttemptId(session.attempt_id || null);
                                                                        setShareSessionId(session.id);
                                                                        setShareModalOpen(true);
                                                                    }}
                                                                    className="mt-1 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-slate-500 hover:text-primary"
                                                                    title="Share solution"
                                                                >
                                                                    <span className="material-symbols-outlined text-sm">share</span>
                                                                    Share
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ))}
                                                {totalHistoryPages > 1 && (
                                                    <div className="px-6 py-4 flex items-center justify-between border-t border-slate-100 dark:border-slate-800">
                                                        <button
                                                            type="button"
                                                            onClick={() => setHistoryPage(page => Math.max(1, page - 1))}
                                                            disabled={historyPage === 1}
                                                            className="text-xs font-bold text-slate-500 disabled:opacity-40 flex items-center gap-1"
                                                        >
                                                            <span className="material-symbols-outlined text-sm">chevron_left</span>
                                                            Prev
                                                        </button>
                                                        <div className="text-xs font-semibold text-slate-500">
                                                            Page {historyPage} of {totalHistoryPages}
                                                        </div>
                                                        <button
                                                            type="button"
                                                            onClick={() => setHistoryPage(page => Math.min(totalHistoryPages, page + 1))}
                                                            disabled={historyPage === totalHistoryPages}
                                                            className="text-xs font-bold text-slate-500 disabled:opacity-40 flex items-center gap-1"
                                                        >
                                                            Next
                                                            <span className="material-symbols-outlined text-sm">chevron_right</span>
                                                        </button>
                                                    </div>
                                                )}
                                            </>
                                        )
                                    )}

                                    {activeTab === 'bookmarked' && (
                                        history.filter(h => h.is_saved && h.title !== "Debug Seeded Session").length === 0 ? (
                                            <div className="p-12 text-center text-slate-500 italic">No saved solutions yet.</div>
                                        ) : (
                                            history.filter(h => h.is_saved && h.title !== "Debug Seeded Session").map((session) => (
                                                <div
                                                    key={session.id}
                                                    onClick={() => router.push(resolveHistorySessionRoute(session))}
                                                    className="p-4 flex items-center gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group px-6"
                                                >
                                                    <div className="w-10 h-10 rounded bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center text-amber-600 dark:text-amber-500">
                                                        <span className="material-symbols-outlined">bookmark</span>
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <h4 className="text-sm font-semibold truncate">
                                                            <MathRenderer content={session.title} mode="prose" />
                                                        </h4>
                                                        <p className="text-xs text-slate-500 capitalize">
                                                            {session.subject || "Math"} • {new Date(session.created_at).toLocaleDateString()}
                                                        </p>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button
                                                            type="button"
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                setShareAttemptId(session.attempt_id || null);
                                                                setShareSessionId(session.id);
                                                                setShareModalOpen(true);
                                                            }}
                                                            className="material-symbols-outlined text-slate-400 hover:text-primary transition-colors"
                                                            title="Share solution"
                                                        >
                                                            share
                                                        </button>
                                                        <button className="material-symbols-outlined text-slate-400 hover:text-red-500 transition-colors">delete</button>
                                                    </div>
                                                </div>
                                            ))
                                        )
                                    )}

                                    {/* Concepts tab removed */}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </section>
            <ShareSolutionModal
                open={shareModalOpen}
                attemptId={shareAttemptId}
                sessionId={shareSessionId}
                onClose={() => {
                    setShareModalOpen(false);
                    setShareAttemptId(null);
                    setShareSessionId(null);
                }}
            />
        </StudentLayout>
    );
}

export default function DashboardPage() {
    return (
        <Suspense fallback={<div>Loading dashboard...</div>}>
            <DashboardContent />
        </Suspense>
    );
}

