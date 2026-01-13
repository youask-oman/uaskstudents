"use client";

import React from "react";
import Image from "next/image";
import logoLight from "@/app/logo/logo-01.png";
import logoDark from "@/app/logo/logo-13.png";

interface WorkspaceProblem {
    input?: string;
    topic?: string;
    goal?: string;
    assumptions?: string[];
    given_data?: string[];
    unknowns?: string[];
}

interface WorkspaceMessage {
    role: string;
    content: unknown;
}

interface WorkspaceLayoutProps {
    children: React.ReactNode;
    messages: WorkspaceMessage[];
    problem?: WorkspaceProblem;
    analysisPlan?: string[];
    keyConcepts?: string[];
    stepsCount?: number;
    onSelectConcepts?: () => void;
    llmUsed?: string;
    totalTokensUsed?: number;
    questionTokensUsed?: number;
    totalProblemsSolved?: number;
    tokenUsage?: number;
}

export default function WorkspaceLayout({
    children,
    messages,
    problem,
    analysisPlan = [],
    keyConcepts = [],
    stepsCount = 0,
    onSelectConcepts,
    llmUsed,
    totalTokensUsed,
    questionTokensUsed,
    totalProblemsSolved,
    tokenUsage
}: WorkspaceLayoutProps) {
    const userMessage = messages.find(msg => msg.role === "user" && typeof msg.content === "string")?.content;
    const summaryLine = analysisPlan[0] ? `We'll start by ${analysisPlan[0].toLowerCase()}.` : "We'll work through the key steps together.";
    const summaryText = `I've broken this down into ${stepsCount || 0} steps. ${summaryLine}`;
    const rightTitle = keyConcepts[0] ? `The Goal of ${keyConcepts[0]}` : "Why this matters";
    const rightBody = problem?.goal
        ? `Focus on ${problem.goal.toLowerCase()} while keeping the core idea clear and reusable.`
        : "Focus on the underlying concept so you can apply it to similar problems.";

    return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark text-[#111318] dark:text-slate-100 font-display antialiased">
            <header className="sticky top-0 z-50 flex items-center justify-between border-b border-[#dbdfe6] dark:border-border-dark bg-white/80 dark:bg-background-dark/80 backdrop-blur-md px-6 py-3">
                <div className="flex items-center gap-3">
                    <Image src={logoLight} alt="uask.ai" className="h-8 w-auto dark:hidden" />
                    <Image src={logoDark} alt="uask.ai" className="h-8 w-auto hidden dark:block" />
                </div>
                <div className="hidden md:flex flex-1 items-center justify-center">
                    <nav className="flex items-center gap-8">
                        <a className="text-sm font-medium hover:text-primary dark:hover:text-accent transition-colors" href="/dashboard">Dashboard</a>
                        <a className="text-sm font-bold text-primary dark:text-accent border-b-2 border-primary dark:border-accent pb-1" href="#">Workspace</a>
                        <a className="text-sm font-medium hover:text-primary dark:hover:text-accent transition-colors" href="/library">Library</a>
                    </nav>
                </div>
                <div className="flex items-center gap-3">
                    <div className="hidden sm:flex items-center gap-2">
                        <div className="px-3 py-1.5 rounded-full bg-gray-100 dark:bg-slate-800 text-[10px] font-bold uppercase tracking-wide text-gray-600 dark:text-slate-300">
                            Total Problems
                            <span className="ml-2 text-gray-900 dark:text-white text-xs font-semibold">
                                {(totalProblemsSolved ?? 0).toLocaleString()}
                            </span>
                        </div>
                        <div className="px-3 py-1.5 rounded-full bg-gray-100 dark:bg-slate-800 text-[10px] font-bold uppercase tracking-wide text-gray-600 dark:text-slate-300">
                            Token Usage
                            <span className="ml-2 text-gray-900 dark:text-white text-xs font-semibold">
                                {(tokenUsage ?? 0).toLocaleString()}
                            </span>
                        </div>
                    </div>
                    <div className="bg-center bg-cover rounded-full size-9 border border-gray-200 dark:border-border-dark" style={{ backgroundImage: "url('/avatar.png')" }}></div>
                </div>
            </header>

            <div className="flex min-h-[calc(100vh-65px)]">
                <aside className="w-72 border-r border-[#dbdfe6] dark:border-border-dark bg-white dark:bg-background-dark flex-shrink-0 p-4 hidden lg:flex flex-col gap-6">
                    <div className="flex flex-col gap-4">
                        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Context</h3>
                        <div className="flex flex-col gap-2 p-3 rounded-xl bg-gray-50 dark:bg-slate-900/40 border border-gray-100 dark:border-border-dark">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="material-symbols-outlined text-sm">chat_bubble</span>
                                <span className="text-xs font-bold">You</span>
                            </div>
                            <p className="text-sm italic leading-relaxed text-gray-700 dark:text-slate-300">
                                {userMessage ? `"${userMessage}"` : "Your question will appear here."}
                            </p>
                        </div>
                        <div className="flex flex-col gap-2 p-3 rounded-xl bg-primary/5 border border-primary/20 dark:border-primary/30">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="material-symbols-outlined text-sm text-primary dark:text-accent">auto_awesome</span>
                                <span className="text-xs font-bold text-primary dark:text-accent">uask.ai</span>
                            </div>
                            <p className="text-xs leading-relaxed text-gray-800 dark:text-slate-300">
                                {summaryText}
                            </p>
                        </div>
                        <div className="flex flex-col gap-1 text-xs text-gray-700 dark:text-slate-300">
                            <div className="flex items-center justify-between">
                                <span className="font-semibold">LLM Used</span>
                                <span className="font-medium">{llmUsed || "Youask AI"}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="font-semibold">Tokens this question</span>
                                <span className="font-medium">
                                    {(questionTokensUsed ?? 0).toLocaleString()}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="font-semibold">Total tokens used</span>
                                <span className="font-medium">
                                    {(totalTokensUsed ?? 0).toLocaleString()}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div className="mt-auto pt-4 border-t border-gray-100 dark:border-border-dark">
                        <button className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 transition-colors">
                            <span className="text-xs font-medium">Session History</span>
                            <span className="material-symbols-outlined text-sm">history</span>
                        </button>
                    </div>
                </aside>

                <main className="flex-1 overflow-y-auto px-4 py-8 lg:px-12">
                    {children}
                </main>

                <aside className="w-80 border-l border-[#dbdfe6] dark:border-border-dark bg-white dark:bg-background-dark flex-shrink-0 p-4 hidden xl:flex flex-col gap-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Why this matters</h3>
                    <div className="p-5 bg-gray-50 dark:bg-slate-900/40 rounded-xl border border-gray-100 dark:border-border-dark">
                        <div className="size-10 bg-primary/10 text-primary dark:text-accent rounded-xl flex items-center justify-center mb-4">
                            <span className="material-symbols-outlined">psychology</span>
                        </div>
                        <h4 className="text-sm font-bold mb-2">{rightTitle}</h4>
                        <p className="text-xs text-gray-600 dark:text-slate-300 leading-relaxed">
                            {rightBody}
                        </p>
                        <button
                            type="button"
                            onClick={onSelectConcepts}
                            className="mt-4 text-xs font-bold text-primary dark:text-accent flex items-center gap-1"
                        >
                            Deep dive into concepts
                            <span className="material-symbols-outlined text-sm">arrow_forward</span>
                        </button>
                    </div>
                    <div className="p-5 border border-dashed border-gray-300 dark:border-border-dark rounded-xl">
                        <h4 className="text-xs font-bold text-gray-400 uppercase mb-3">Key Concepts</h4>
                        <div className="flex flex-wrap gap-2">
                            {(keyConcepts.length > 0 ? keyConcepts : ["Concepts"]).map((concept) => (
                                <span key={concept} className="px-2 py-1 bg-white dark:bg-surface-dark border border-gray-200 dark:border-border-dark rounded text-[10px] font-medium">
                                    {concept}
                                </span>
                            ))}
                        </div>
                    </div>
                    <div className="mt-auto p-4 bg-primary dark:bg-accent text-white rounded-xl">
                        <p className="text-xs font-bold mb-1">Stuck on this step?</p>
                        <p className="text-[10px] opacity-80 leading-normal mb-3">Ask me to visualize it differently or show another method.</p>
                        <button className="w-full bg-white dark:bg-surface-dark text-primary dark:text-accent py-2 rounded-lg text-xs font-bold hover:bg-gray-100 transition-colors">Ask AI Assistant</button>
                    </div>
                </aside>
            </div>
        </div>
    );
}
