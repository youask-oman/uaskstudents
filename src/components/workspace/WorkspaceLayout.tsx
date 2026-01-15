"use client";

import React from 'react';
import Link from 'next/link';
import MathRenderer from '../MathRenderer';

interface WorkspaceMessage {
    role: string;
    content: unknown;
}

interface WorkspaceProblem {
    id?: string;
    topic?: string;
    subtopic?: string;
    difficulty?: string;
    goal?: string;
    visual_type?: string;
    knowns?: string[];
    unknowns?: string[];
    constraints?: string[];
    relevant_formulas?: string[];
    input?: string; // The raw latex or query
    original_text?: string;
    assumptions?: string[];
    given_data?: string[];
}

interface WorkspaceLayoutProps {
    children: React.ReactNode;
    messages: WorkspaceMessage[];
    activeTab: "steps" | "verification" | "concepts" | "practice";
    onSelectTab: (tab: "steps" | "verification" | "concepts" | "practice") => void;
    problem?: WorkspaceProblem;
    stepsCount?: number;
    analysisPlan?: string[];
    finalAnswer?: string;
    confidence?: number;
    // Unused but kept for interface compatibility if needed
    llmUsed?: string;
    totalTokensUsed?: number;
    questionTokensUsed?: number;
    totalProblemsSolved?: number;
    tokenUsage?: number;
}

export default function WorkspaceLayout({
    children,
    messages,
    activeTab,
    onSelectTab,
    problem,
    stepsCount,
    analysisPlan = [],
    finalAnswer,
    confidence = 99
}: WorkspaceLayoutProps) {
    const [isPlanOpen, setIsPlanOpen] = React.useState(true);

    return (
        <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-background-light dark:bg-background-dark font-display text-[#111318] dark:text-white transition-colors duration-200">
            {/* Top Header */}
            <header className="sticky top-0 z-50 flex items-center justify-between whitespace-nowrap border-b border-solid border-[#e5e7eb] dark:border-[#2a303c] bg-white/80 dark:bg-background-dark/80 backdrop-blur-md px-10 py-3">
                <div className="flex items-center gap-8">
                    <div className="flex items-center gap-3">
                        <div className="size-6 text-primary">
                            <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                                <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z"></path>
                            </svg>
                        </div>
                        <h2 className="text-lg font-bold tracking-tight">uask.ai</h2>
                    </div>
                    <nav className="hidden md:flex items-center gap-6">
                        <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Dashboard</a>
                        <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Courses</a>
                        <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Library</a>
                        <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Settings</a>
                    </nav>
                </div>
                <div className="flex flex-1 justify-end gap-4 items-center">
                    <div className="hidden sm:flex items-center bg-[#f0f2f4] dark:bg-[#1e2634] rounded-xl px-3 h-10 w-64 border border-transparent focus-within:border-primary/50 transition-all">
                        <span className="material-symbols-outlined text-[#616f89] text-[20px]">search</span>
                        <input className="bg-transparent border-none focus:ring-0 text-sm w-full placeholder:text-[#616f89] outline-none" placeholder="Search problem sets..." type="text" />
                    </div>
                    <div className="bg-center bg-no-repeat aspect-square bg-cover rounded-full size-9 border border-[#e5e7eb] dark:border-[#2a303c] bg-slate-200" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuBT8Vr3uT5sB9YqSpfa1iQvokQxs6dCmTPslq4xIF0j5j8EvvuHnpbvGhj1-XQuiM0tPzWzIrFy-rQFuAqTwD-bOYYuGDjPv0e4Dmzh-qLYWGkiHoephNflXAyQZ4a2Z1bit4kT3bkxgu8ygJ-U2k8rOe5j_2TmqMW8160inxraHyJkr6nXNw4sIJ4KA2i2_FWzdN-W7s_mc4LHtlL0l-eexFHvpspMGDbpxnuX0tpVZBHfY8bqVMtLWZIZAGZvCdFAasKpvhuqbPv1")' }}></div>
                </div>
            </header>

            <main className="flex-1 max-w-[1200px] mx-auto w-full px-6 py-8">
                {/* Breadcrumbs */}
                <nav className="flex items-center gap-2 mb-6 text-sm text-[#616f89] dark:text-slate-400">
                    <a className="hover:text-primary" href="#">Home</a>
                    <span className="material-symbols-outlined text-xs">chevron_right</span>
                    <a className="hover:text-primary" href="#">{problem?.topic || "Algebra"}</a>
                    <span className="material-symbols-outlined text-xs">chevron_right</span>
                    <span className="text-[#111318] dark:text-white font-medium">{problem?.topic || "Linear Equations"} Workspace</span>
                </nav>

                {/* Problem Summary Hero */}
                <section className="bg-white dark:bg-[#1e2634] rounded-2xl p-8 mb-8 shadow-sm border border-[#e5e7eb] dark:border-[#2a303c] relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                    <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                        <div>
                            <div className="flex items-center gap-2 mb-2">
                                <span className="bg-primary/10 text-primary text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">{problem?.topic || "Topic"}</span>
                                <span className="text-xs text-[#616f89] dark:text-slate-400">Workspace #{problem?.id?.slice(0, 4) || "64"}</span>
                            </div>
                            <h1 className="text-3xl font-black tracking-tight mb-2">{problem?.goal || "Problem Goal"}</h1>
                            <div className="text-2xl text-primary font-medium tracking-wide">
                                <MathRenderer content={problem?.input || "Expression"} inline />
                            </div>
                        </div>
                        <div className="flex gap-3">
                            <button className="flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md hover:bg-blue-700 transition-all">
                                <span className="material-symbols-outlined text-[18px]">bookmark</span>
                                Save to Library
                            </button>
                            <button className="p-2.5 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] hover:bg-[#f0f2f4] dark:hover:bg-slate-700 transition-all text-[#616f89]">
                                <span className="material-symbols-outlined text-[20px]">share</span>
                            </button>
                        </div>
                    </div>
                </section>

                {/* Quick Data Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                    <div className="bg-white dark:bg-[#1e2634] p-5 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex items-center gap-4">
                        <div className="size-10 rounded-lg bg-orange-100 dark:bg-orange-500/20 text-orange-600 dark:text-orange-400 flex items-center justify-center">
                            <span className="material-symbols-outlined">description</span>
                        </div>
                        <div className="overflow-hidden">
                            <p className="text-xs font-bold text-[#616f89] dark:text-slate-400 uppercase">Given</p>
                            <div className="text-lg truncate text-[#111318] dark:text-white">
                                <MathRenderer content={problem?.given_data?.join(", ") || problem?.input || "N/A"} inline />
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-[#1e2634] p-5 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex items-center gap-4">
                        <div className="size-10 rounded-lg bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400 flex items-center justify-center">
                            <span className="material-symbols-outlined">target</span>
                        </div>
                        <div>
                            <p className="text-xs font-bold text-[#616f89] dark:text-slate-400 uppercase">Find</p>
                            <div className="text-lg text-[#111318] dark:text-white">
                                <MathRenderer content={problem?.unknowns?.join(", ") || problem?.goal || "x"} inline />
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-[#1e2634] p-5 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex items-center gap-4">
                        <div className="size-10 rounded-lg bg-blue-100 dark:bg-blue-500/20 text-primary flex items-center justify-center">
                            <span className="material-symbols-outlined">info</span>
                        </div>
                        <div>
                            <p className="text-xs font-bold text-[#616f89] dark:text-slate-400 uppercase">Assumptions</p>
                            <div className="text-sm font-medium text-[#111318] dark:text-white">
                                <MathRenderer content={problem?.assumptions?.join(", ") || "Standard"} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Final Answer Banner */}
                {finalAnswer && (
                    <div className="bg-primary text-white rounded-2xl p-6 mb-8 shadow-xl shadow-primary/20 flex flex-col md:flex-row items-center justify-between gap-6 overflow-hidden">
                        <div className="flex items-center gap-4 overflow-hidden w-full">
                            <div className="bg-white/20 p-3 rounded-full backdrop-blur-sm shrink-0">
                                <span className="material-symbols-outlined text-[32px]">check_circle</span>
                            </div>
                            <div className="overflow-hidden w-full">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="bg-white text-primary text-[10px] font-black px-2 py-0.5 rounded-full uppercase">Refined Solution</span>
                                    <span className="flex items-center gap-1 text-[11px] font-medium text-blue-100">
                                        <span className="material-symbols-outlined text-[12px] fill-current">verified</span>
                                        {confidence}% Confidence
                                    </span>
                                </div>
                                <div className="text-2xl md:text-3xl font-black tracking-tight break-all">
                                    {/* Force white color using LaTeX since backend might send blue */}
                                    <MathRenderer content={`\\color{white} {${finalAnswer}}`} forceMath inline />
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                            <span className="text-sm font-medium text-blue-100">Solution Set:</span>
                            <span className="bg-white/20 px-4 py-1.5 rounded-full font-bold">
                                <MathRenderer content={`\\color{#86efac} \\{${finalAnswer}\\}`} forceMath inline />
                            </span>
                        </div>
                    </div>
                )}

                {/* Solution Plan (Horizontal List) */}
                <div className="mb-8 p-6 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-[20px]">format_list_numbered</span>
                            <h3 className="font-bold text-sm uppercase tracking-wide text-[#111318] dark:text-white">Solution Plan ({analysisPlan.length > 0 ? analysisPlan.length : 3} Steps)</h3>
                        </div>
                    </div>

                    {analysisPlan.length > 0 ? (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {analysisPlan.map((step, idx) => (
                                <div key={idx} className="flex flex-col gap-1 bg-white dark:bg-[#1e2634] border border-[#e5e7eb] dark:border-[#2a303c] px-3 py-2 rounded-lg shadow-sm h-full">
                                    <span className="text-primary font-black text-xs opacity-70">Step {String(idx + 1).padStart(2, '0')}</span>
                                    <div className="font-bold text-[#111318] dark:text-white text-xs leading-tight line-clamp-2" title={step}>
                                        <MathRenderer content={step} inline />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 opacity-50">
                            {[1, 2, 3, 4].map((i) => (
                                <div key={i} className="flex flex-col gap-1 bg-white dark:bg-[#1e2634] border border-[#e5e7eb] dark:border-[#2a303c] px-3 py-2 rounded-lg shadow-sm">
                                    <span className="text-primary font-black text-xs opacity-70">Step 0{i}</span>
                                    <span className="font-bold text-[#111318] dark:text-white text-xs">Waiting for plan...</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Tabbed Interface Headers */}
                <div className="flex flex-col gap-6">
                    <div className="flex border-b border-[#e5e7eb] dark:border-[#2a303c] gap-8">
                        <button
                            onClick={() => onSelectTab("steps")}
                            className={`pb-3 border-b-2 font-bold text-sm transition-colors ${activeTab === "steps" ? "border-primary text-primary" : "border-transparent text-[#616f89] dark:text-slate-400 hover:text-primary"}`}
                        >
                            Steps
                        </button>
                        <button
                            onClick={() => onSelectTab("verification")}
                            className={`pb-3 border-b-2 font-bold text-sm transition-colors ${activeTab === "verification" ? "border-primary text-primary" : "border-transparent text-[#616f89] dark:text-slate-400 hover:text-primary"}`}
                        >
                            Verification
                        </button>
                        <button
                            onClick={() => onSelectTab("concepts")}
                            className={`pb-3 border-b-2 font-bold text-sm transition-colors ${activeTab === "concepts" ? "border-primary text-primary" : "border-transparent text-[#616f89] dark:text-slate-400 hover:text-primary"}`}
                        >
                            Concepts
                        </button>
                        <button
                            onClick={() => onSelectTab("practice")}
                            className={`pb-3 border-b-2 font-bold text-sm transition-colors ${activeTab === "practice" ? "border-primary text-primary" : "border-transparent text-[#616f89] dark:text-slate-400 hover:text-primary"}`}
                        >
                            Practice
                        </button>
                    </div>

                    {/* Tab Content (Children) */}
                    <div>
                        {children}
                    </div>
                </div>

            </main>

            <footer className="bg-white dark:bg-[#1e2634] border-t border-[#e5e7eb] dark:border-[#2a303c] py-12 mt-12 text-[#111318] dark:text-white">
                <div className="max-w-[1200px] mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-8">
                    <div className="flex items-center gap-3">
                        <div className="size-5 text-primary">
                            <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                                <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z"></path>
                            </svg>
                        </div>
                        <h2 className="text-md font-bold">uask.ai</h2>
                        <p className="text-xs text-[#616f89] ml-4">© 2024 Math Solver Labs. All rights reserved.</p>
                    </div>
                    <div className="flex gap-6">
                        <a className="text-xs text-[#616f89] hover:text-primary" href="#">Terms</a>
                        <a className="text-xs text-[#616f89] hover:text-primary" href="#">Privacy</a>
                        <a className="text-xs text-[#616f89] hover:text-primary" href="#">Help Center</a>
                    </div>
                </div>
            </footer>
        </div>
    );
}
