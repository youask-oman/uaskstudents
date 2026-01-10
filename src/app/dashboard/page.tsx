"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import StudentLayout from "@/components/layout/StudentLayout";

interface ChatSession {
    id: number;
    title: string;
    subject?: string;
    created_at: string;
    is_saved?: boolean;
}

export default function DashboardPage() {
    const [stats, setStats] = useState([
        { label: "Problems Solved", value: "...", icon: "analytics", color: "blue", trend: "..." },
        { label: "Token Usage", value: "...", icon: "offline_bolt", color: "amber", trend: "Monthly" },
        { label: "Scans", value: "...", icon: "document_scanner", color: "purple", trend: "Total" },
    ]);
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [loading, setLoading] = useState(true);
    const [user, setUser] = useState<any>(null);
    const [activeTab, setActiveTab] = useState("history"); // history, saved, concepts
    const router = useRouter();

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) {
            router.push("/login");
            return;
        }

        const storedUser = localStorage.getItem("user");
        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser));
            } catch (e) {
                console.error("Error parsing user data");
            }
        }

        const fetchData = async () => {
            try {
                // Fetch History (ALL sessions)
                const historyRes = await fetch(`http://localhost:8000/api/v1/history?user_id=${userId}&saved_only=false`);
                if (historyRes.ok) {
                    const data = await historyRes.json();
                    setHistory(data);
                }

                // Fetch Profile Stats
                const profileRes = await fetch(`http://localhost:8000/api/v1/user/profile?user_id=${userId}`);
                if (profileRes.ok) {
                    const profile = await profileRes.json();
                    setStats([
                        {
                            label: "Problems Solved",
                            value: profile.usage.questions_count.toString(),
                            icon: "analytics",
                            color: "blue",
                            trend: "Total"
                        },
                        {
                            label: "Token Usage",
                            value: `${(profile.usage.questions_count * 500 / 1000).toFixed(1)}k`, // Approximate or fetch real token metric if in profile
                            icon: "offline_bolt",
                            color: "amber",
                            trend: "Monthly"
                        },
                        {
                            label: "Scans",
                            value: profile.usage.scans_count.toString(),
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

    return (
        <StudentLayout>
            <section className="p-8">
                <div className="max-w-5xl mx-auto space-y-8">
                    {/* Hero/Welcome Section */}
                    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary to-[#06399c] p-10 text-white shadow-xl">
                        <div className="relative z-10">
                            <h1 className="text-4xl font-bold mb-4 tracking-tight leading-tight">
                                Welcome back, {user?.full_name?.split(' ')[0] || "Alex"}. <br />Ready to solve?
                            </h1>
                            <p className="text-blue-100/80 max-w-md mb-8">
                                {history.length > 0
                                    ? `Your last problem "${history[0].title}" is ready for review.`
                                    : "Start your first problem solving session today!"}
                            </p>
                            <button
                                onClick={() => history[0] ? router.push(`/chat/${history[0].id}`) : router.push('/chat/new')}
                                className="bg-white text-primary px-6 py-3 rounded-lg font-bold text-sm shadow-lg hover:shadow-xl transition-all"
                            >
                                {history.length > 0 ? "Continue Last Session" : "Start New Session"}
                            </button>
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

                    {/* Recent Solutions Section */}
                    {/* Recent Solutions Section */}
                    {/* Main Content Areas with Tabs */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden min-h-[400px]">
                        {/* Tabs Header */}
                        <div className="px-6 border-b border-slate-100 dark:border-slate-800 flex items-center gap-8">
                            {["history", "saved", "concepts"].map((tab) => (
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
                                        history.length === 0 ? (
                                            <div className="p-12 text-center text-slate-500 italic">No history found.</div>
                                        ) : (
                                            history.map((session) => (
                                                <div
                                                    key={session.id}
                                                    onClick={() => router.push(`/chat/${session.id}`)}
                                                    className="p-4 flex items-center gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group px-6"
                                                >
                                                    <div className="w-10 h-10 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                                                        <span className="material-symbols-outlined">
                                                            {session.subject === 'Physics' ? 'science' : 'functions'}
                                                        </span>
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <h4 className="text-sm font-semibold truncate">{session.title}</h4>
                                                        <p className="text-xs text-slate-500 capitalize">
                                                            {session.subject || "Math"} • {new Date(session.created_at).toLocaleDateString()}
                                                        </p>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        {session.is_saved && (
                                                            <span className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-[10px] font-bold rounded">Saved</span>
                                                        )}
                                                        <span className="material-symbols-outlined text-slate-300">chevron_right</span>
                                                    </div>
                                                </div>
                                            ))
                                        )
                                    )}

                                    {activeTab === 'saved' && (
                                        history.filter(h => h.is_saved).length === 0 ? (
                                            <div className="p-12 text-center text-slate-500 italic">No saved solutions yet.</div>
                                        ) : (
                                            history.filter(h => h.is_saved).map((session) => (
                                                <div
                                                    key={session.id}
                                                    onClick={() => router.push(`/chat/${session.id}`)}
                                                    className="p-4 flex items-center gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group px-6"
                                                >
                                                    <div className="w-10 h-10 rounded bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center text-amber-600 dark:text-amber-500">
                                                        <span className="material-symbols-outlined">bookmark</span>
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <h4 className="text-sm font-semibold truncate">{session.title}</h4>
                                                        <p className="text-xs text-slate-500 capitalize">
                                                            {session.subject || "Math"} • {new Date(session.created_at).toLocaleDateString()}
                                                        </p>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button className="material-symbols-outlined text-slate-400 hover:text-red-500 transition-colors">delete</button>
                                                    </div>
                                                </div>
                                            ))
                                        )
                                    )}

                                    {activeTab === 'concepts' && (
                                        <div className="p-12 text-center text-slate-500">
                                            <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                                                <span className="material-symbols-outlined text-3xl">lightbulb</span>
                                            </div>
                                            <p>Concepts aggregation coming soon!</p>
                                            <p className="text-xs mt-2">Solve more problems to build your knowledge graph.</p>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </section>
        </StudentLayout>
    );
}
