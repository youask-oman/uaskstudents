"use client";

import React from 'react';
import Image from "next/image";
import Link from 'next/link';
import MathRenderer from '../math/MathRendererSwitch';
import WorkspaceTabs from './WorkspaceTabs';
import ContextualChatPanel from './ContextualChatPanel';
import VisualRenderer, { Visual } from './VisualRenderer';

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
    input?: string;
    original_text?: string;
    assumptions?: string[];
    given_data?: string[];
}

interface PlotSpec {
    plot_id?: string;
    plot_type?: string;
    title?: string;
    x_label?: string;
    y_label?: string;
    x_min?: number;
    x_max?: number;
    y_min?: number;
    y_max?: number;
    series?: Array<{
        name?: string;
        kind?: string;
        expression_latex?: string;
        points?: Array<{ x: number; y: number; label?: string }>;
    }>;
    key_points?: Array<{ x: number; y: number; label: string }>;
    annotations?: Array<{ text: string; x: number; y: number }>;
}

interface VisualsData {
    should_visualize?: boolean;
    decision_reason?: string;
    plots?: PlotSpec[];
    alternative_visual?: {
        kind?: string;
        description?: string;
        data?: Array<{ label: string; x?: number; y?: number }>;
    };
}

interface Classification {
    grade_band?: string;
    domain?: string;
    topic?: string;
    difficulty?: string;
}

interface WorkspaceLayoutProps {
    children: React.ReactNode;
    messages: WorkspaceMessage[];
    activeTab: "steps";
    onSelectTab: (tab: "steps") => void;
    problem?: WorkspaceProblem;
    stepsCount?: number;
    analysisPlan?: string[];
    finalAnswer?: string;
    finalAnswerMode?: "inline" | "prose";
    confidence?: number;
    llmUsed?: string;
    totalTokensUsed?: number;
    questionTokensUsed?: number;
    totalProblemsSolved?: number;
    tokenUsage?: number;
    sessionId?: string | number;
    initialSaved?: boolean;
    telemetry?: {
        request_id?: string;
        model?: string;
        total_tokens?: number;
        input_tokens?: number;
        output_tokens?: number;
        latency_ms_openai?: number;
        latency_ms_total?: number;
        cached_tokens?: number;
        learning_mode?: string;
        requested_mode?: string;
        solve_tier?: string;
        openai_payload?: {
            full_input?: any[];
            full_output?: any;
        };
    };
    // NEW: Classification data
    classification?: Classification;
    // NEW: Quality insights
    commonMistakes?: string[];
    // NEW: Visuals/Plots
    visuals?: VisualsData;
    // NEW: For chat context
    originalProblemText?: string;
    // NEW: Steps for chat context
    steps?: Array<{ title: string; index: number }>;
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
    finalAnswerMode = "prose",
    confidence = 99,
    sessionId,
    initialSaved = false,
    telemetry,
    classification,
    commonMistakes,
    visuals,
    originalProblemText,
    steps = []
}: WorkspaceLayoutProps) {
    const [isSaved, setIsSaved] = React.useState(initialSaved);
    const [isBookmarked, setIsBookmarked] = React.useState(false);
    const [isMetricsOpen, setIsMetricsOpen] = React.useState(false);
    const [isChatOpen, setIsChatOpen] = React.useState(true);
    const messageCount = messages.length;

    const handleSave = async () => {
        const newState = !isSaved;
        setIsSaved(newState);

        if (newState && sessionId) {
            try {
                await fetch(`/api/v1/sessions/${sessionId}/save`, { method: 'POST' });
            } catch (err) {
                console.error("Failed to save session", err);
                setIsSaved(!newState);
            }
        }
    };

    // Helper to get difficulty color
    const getDifficultyStyles = (difficulty?: string) => {
        switch (difficulty?.toLowerCase()) {
            case 'easy':
                return 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/30';
            case 'challenging':
            case 'hard':
                return 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/30';
            default:
                return 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/30';
        }
    };

    // Map visuals for VisualRenderer
    const mappedVisuals: Visual[] = React.useMemo(() => {
        if (!visuals?.plots || visuals.plots.length === 0) return [];
        return visuals.plots.map((plot, idx) => ({
            id: plot.plot_id || `plot-${idx}`,
            type: (plot.plot_type as Visual['type']) || 'function_plot',
            title: plot.title,
            axes: {
                x_label: plot.x_label,
                y_label: plot.y_label
            },
            domain: plot.x_min !== undefined && plot.x_max !== undefined ? {
                x_min_latex: String(plot.x_min),
                x_max_latex: String(plot.x_max)
            } : undefined,
            series: plot.series?.map(s => ({
                label: s.name || '',
                points: (s.points || []).map(p => ({ x: p.x, y: p.y }))
            })),
            markers: plot.key_points?.map(kp => ({
                label: kp.label || '',
                x: kp.x ?? 0,
                y: kp.y ?? 0
            }))
        }));
    }, [visuals]);


    return (
        <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-gradient-to-br from-slate-50 via-white to-emerald-50/30 dark:from-slate-950 dark:via-slate-900 dark:to-emerald-950/20 font-display text-[#111318] dark:text-white transition-colors duration-200">

            {/* Header */}
            <header data-message-count={messageCount} className="sticky top-0 z-50 flex items-center justify-between whitespace-nowrap border-b border-slate-200/80 dark:border-slate-800/80 bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl px-6 lg:px-10 py-3 shadow-sm">
                {/* Left: Logo + Nav */}
                <div className="flex items-center gap-8">
                    <Link href="/dashboard" className="flex items-center gap-2 group">
                        <Image src="/logo.png" alt="uask.ai" width={160} height={40} className="h-8 w-auto transition-transform group-hover:scale-105" priority />
                        <span className="text-lg font-bold tracking-tight text-[#111318] dark:text-white">uask.ai</span>
                    </Link>

                    <nav className="hidden md:flex items-center gap-1">
                        <Link
                            href="/dashboard"
                            className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                            Dashboard
                        </Link>
                        <Link
                            href="/solve"
                            className="px-4 py-2 text-sm font-bold text-primary bg-primary/10 rounded-lg"
                        >
                            New Solve
                        </Link>
                        <Link
                            href="/dashboard?tab=history"
                            className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                            History
                        </Link>
                    </nav>
                </div>

                {/* Right: Controls */}
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => {
                            const html = document.documentElement;
                            html.classList.toggle('dark');
                            localStorage.setItem('theme', html.classList.contains('dark') ? 'dark' : 'light');
                        }}
                        className="p-2 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                        title="Toggle dark/light mode"
                    >
                        <span className="material-symbols-outlined text-[20px] dark:hidden">dark_mode</span>
                        <span className="material-symbols-outlined text-[20px] hidden dark:block">light_mode</span>
                    </button>

                    <button className="p-2 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all relative">
                        <span className="material-symbols-outlined text-[20px]">notifications</span>
                        <span className="absolute top-1.5 right-1.5 size-2 bg-red-500 rounded-full"></span>
                    </button>

                    <Link href="/profile" className="flex items-center gap-3 pl-3 border-l border-slate-200 dark:border-slate-700 hover:opacity-80 transition-opacity">
                        <div className="size-9 bg-gradient-to-br from-orange-400 to-orange-600 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-md">
                            NR
                        </div>
                        <span className="hidden lg:block text-sm font-medium text-slate-900 dark:text-white">Nathan Rivera</span>
                    </Link>
                </div>
            </header>

            {/* Main Content - 70/30 Split */}
            <div className="flex-1 flex">
                {/* Solution Panel - 70% */}
                <main className={`${isChatOpen ? 'w-full lg:w-[70%]' : 'w-full'} overflow-y-auto transition-all duration-300`}>
                    <div className="max-w-[1000px] mx-auto px-6 py-8">

                        {/* Breadcrumbs + Classification Badges */}
                        <div className="mb-6">
                            <nav className="flex items-center gap-2 mb-3 text-sm text-slate-500 dark:text-slate-400">
                                <a className="hover:text-primary transition-colors" href="/dashboard">Home</a>
                                <span className="material-symbols-outlined text-xs">chevron_right</span>
                                <a className="hover:text-primary transition-colors" href="#">{classification?.domain || problem?.topic || "Math"}</a>
                                <span className="material-symbols-outlined text-xs">chevron_right</span>
                                <span className="text-slate-900 dark:text-white font-medium">Solution</span>
                            </nav>

                            {/* Classification Badges */}
                            {classification && (
                                <div className="flex flex-wrap items-center gap-2">
                                    {classification.domain && (
                                        <span className="px-3 py-1.5 bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300 text-xs font-bold rounded-full uppercase tracking-wide border border-blue-200 dark:border-blue-500/30 shadow-sm">
                                            {classification.domain}
                                        </span>
                                    )}
                                    {classification.grade_band && (
                                        <span className="px-3 py-1.5 bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 text-xs font-bold rounded-full border border-purple-200 dark:border-purple-500/30 shadow-sm">
                                            📚 Grade {classification.grade_band}
                                        </span>
                                    )}
                                    {classification.difficulty && (
                                        <span className={`px-3 py-1.5 text-xs font-bold rounded-full border shadow-sm capitalize ${getDifficultyStyles(classification.difficulty)}`}>
                                            {classification.difficulty === 'easy' ? '🟢' : classification.difficulty === 'challenging' ? '🔴' : '🟡'} {classification.difficulty}
                                        </span>
                                    )}
                                    {classification.topic && (
                                        <span className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-medium rounded-full border border-slate-200 dark:border-slate-700 shadow-sm">
                                            {classification.topic}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Problem Statement Card */}
                        <section className="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 rounded-2xl p-6 mb-6 shadow-lg shadow-emerald-500/5 border border-emerald-200/50 dark:border-emerald-800/50 relative overflow-hidden">
                            <div className="absolute top-0 right-0 w-48 h-48 bg-gradient-to-bl from-emerald-200/30 to-transparent dark:from-emerald-500/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>

                            <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                                            {problem?.goal || "Solve"}
                                        </span>
                                    </div>
                                    <div className="text-lg font-bold text-slate-900 dark:text-white leading-relaxed">
                                        <MathRenderer content={problem?.input || originalProblemText || "Problem"} mode="inline" />
                                    </div>
                                </div>

                                {/* Action Buttons */}
                                <div className="flex items-center gap-2 shrink-0">
                                    <button
                                        onClick={handleSave}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs shadow-lg transition-all hover:scale-105 ${isSaved
                                            ? "bg-amber-100 text-amber-600 hover:bg-amber-200 shadow-amber-500/20"
                                            : "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white shadow-emerald-500/30"
                                            }`}
                                    >
                                        <span className="material-symbols-outlined text-[16px]">{isSaved ? 'bookmark_added' : 'bookmark_add'}</span>
                                        {isSaved ? 'Saved' : 'Save'}
                                    </button>

                                    <button
                                        onClick={() => setIsBookmarked(!isBookmarked)}
                                        className={`p-2 rounded-xl border transition-all hover:scale-105 ${isBookmarked
                                            ? "bg-amber-100 border-amber-300 text-amber-500 shadow-lg shadow-amber-500/20"
                                            : "border-emerald-300 dark:border-emerald-700 hover:bg-emerald-100 dark:hover:bg-emerald-800/30 text-emerald-700 dark:text-emerald-400"
                                            }`}
                                    >
                                        <span className={`material-symbols-outlined text-[18px] ${isBookmarked ? 'fill-1' : ''}`}>star</span>
                                    </button>

                                    <button
                                        onClick={() => window.print()}
                                        className="p-2 rounded-xl border border-emerald-300 dark:border-emerald-700 hover:bg-emerald-100 dark:hover:bg-emerald-800/30 transition-all text-emerald-700 dark:text-emerald-400"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">print</span>
                                    </button>
                                </div>
                            </div>
                        </section>

                        {/* Final Answer Banner */}
                        {finalAnswer && (
                            <section className="bg-gradient-to-r from-primary via-emerald-500 to-teal-500 text-white rounded-2xl p-6 mb-6 shadow-xl shadow-primary/30 relative overflow-hidden">
                                <div className="absolute inset-0 bg-[url('/grid-pattern.svg')] opacity-10"></div>

                                <div className="relative z-10 flex flex-col gap-4">
                                    <div className="flex items-start gap-4">
                                        <div className="bg-white/20 p-3 rounded-full backdrop-blur-sm shrink-0 shadow-lg">
                                            <span className="material-symbols-outlined text-[28px]">check_circle</span>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex flex-wrap items-center gap-2 mb-2">
                                                <span className="bg-white text-primary text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wide shadow-md">
                                                    ✓ Verified Solution
                                                </span>
                                                <span className="flex items-center gap-1 text-[11px] font-medium text-white/90">
                                                    <span className="material-symbols-outlined text-[14px]">verified</span>
                                                    AI Confidence: {confidence}%
                                                </span>
                                            </div>
                                            <div className="text-xl md:text-2xl font-bold tracking-tight">
                                                <MathRenderer content={finalAnswer} mode={finalAnswerMode} />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </section>
                        )}

                        {/* Graph/Visualization Section */}
                        {visuals?.should_visualize && mappedVisuals.length > 0 && (
                            <section className="mb-6">
                                <div className="flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined text-primary text-[24px]">monitoring</span>
                                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">Visualization</h2>
                                </div>
                                <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 p-6 shadow-lg">
                                    {mappedVisuals.map((visual) => (
                                        <VisualRenderer key={visual.id} visual={visual} />
                                    ))}
                                </div>
                            </section>
                        )}

                        {/* Solution Plan (Compact) */}
                        {analysisPlan.length > 0 && (
                            <section className="mb-6 p-5 bg-white dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-lg">
                                <div className="flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined text-primary text-[20px]">route</span>
                                    <h3 className="font-bold text-sm uppercase tracking-wide text-slate-900 dark:text-white">
                                        Solution Plan ({analysisPlan.length} Steps)
                                    </h3>
                                </div>

                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                    {analysisPlan.map((step, idx) => {
                                        const stepNum = idx + 1;
                                        const title = (step || "").trim();
                                        if (!title) return null;

                                        const isRedundant = title.toLowerCase() === `step ${stepNum}` || title.toLowerCase() === `step ${stepNum}:`;

                                        return (
                                            <button
                                                key={idx}
                                                onClick={() => {
                                                    onSelectTab("steps");
                                                    setTimeout(() => {
                                                        const el = document.getElementById(`step-${stepNum}`);
                                                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                                    }, 100);
                                                }}
                                                className="flex flex-col text-left w-full gap-1 bg-gradient-to-br from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 border border-slate-200 dark:border-slate-700 px-3 py-2.5 rounded-xl shadow-sm hover:shadow-lg hover:border-primary/50 transition-all active:scale-[0.98] group"
                                            >
                                                <div className="flex items-center justify-between w-full">
                                                    <span className="text-primary font-black text-xs">Step {String(stepNum).padStart(2, '0')}</span>
                                                    <span className="material-symbols-outlined text-[14px] text-primary opacity-0 group-hover:opacity-100 transition-opacity">north_east</span>
                                                </div>
                                                {!isRedundant && (
                                                    <div className="font-bold text-slate-800 dark:text-white text-xs leading-tight line-clamp-2">
                                                        <MathRenderer content={title} mode="prose" />
                                                    </div>
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            </section>
                        )}

                        {/* Steps Tab Content */}
                        <section className="mb-6">
                            <WorkspaceTabs activeTab={activeTab} onSelectTab={onSelectTab} stepsCount={stepsCount} />
                            <div className="mt-6">{children}</div>
                        </section>

                        {/* Common Mistakes Section */}
                        {commonMistakes && commonMistakes.length > 0 && (
                            <section className="mb-6 p-5 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/30 rounded-2xl border border-amber-200 dark:border-amber-800/50 shadow-lg">
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="size-10 rounded-xl bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-amber-600 dark:text-amber-400 text-[22px]">warning</span>
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-sm text-amber-800 dark:text-amber-300 uppercase tracking-wide">
                                            Common Mistakes to Avoid
                                        </h3>
                                        <p className="text-xs text-amber-600 dark:text-amber-400/80">Watch out for these errors</p>
                                    </div>
                                </div>
                                <ul className="space-y-3">
                                    {commonMistakes.map((mistake, i) => (
                                        <li key={i} className="flex gap-3 text-sm text-amber-900 dark:text-amber-200 bg-white/50 dark:bg-amber-500/10 p-3 rounded-xl border border-amber-200/50 dark:border-amber-500/20">
                                            <span className="text-amber-500 shrink-0 font-bold">⚠</span>
                                            <span>{mistake}</span>
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}

                        {/* Metrics / Telemetry Block */}
                        {telemetry && (
                            <section className="border-t border-slate-200 dark:border-slate-700 pt-6">
                                <button
                                    onClick={() => setIsMetricsOpen(!isMetricsOpen)}
                                    className="flex items-center gap-2 text-xs font-mono text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 transition-colors w-full"
                                >
                                    <span className="material-symbols-outlined text-[16px]">{isMetricsOpen ? 'expand_more' : 'chevron_right'}</span>
                                    <span className="font-bold">METRICS</span>
                                    <span className="ml-auto opacity-50 text-[10px]">{telemetry.request_id}</span>
                                </button>

                                {isMetricsOpen && (
                                    <div className="mt-3 p-4 bg-slate-100 dark:bg-slate-900 rounded-xl font-mono text-xs text-slate-700 dark:text-slate-400">
                                        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2">
                                            <div className="flex justify-between"><span className="opacity-70">Model:</span><span className="font-bold">{telemetry.model || '-'}</span></div>
                                            <div className="flex justify-between"><span className="opacity-70">Goal:</span><span className="font-bold uppercase">{telemetry.learning_mode || 'SOLVE'}</span></div>
                                            <div className="flex justify-between"><span className="opacity-70">Style:</span><span className="font-bold uppercase">{telemetry.requested_mode || 'MINIMAL'}</span></div>
                                            <div className="flex justify-between"><span className="opacity-70">Latency:</span><span className="font-bold">{telemetry.latency_ms_openai ?? '-'}ms</span></div>
                                            <div className="flex justify-between"><span className="opacity-70">Input Tokens:</span><span>{telemetry.input_tokens ?? '-'}</span></div>
                                            <div className="flex justify-between"><span className="opacity-70">Output Tokens:</span><span>{telemetry.output_tokens ?? '-'}</span></div>
                                            <div className="flex justify-between"><span className="opacity-70">Total:</span><span className="font-bold text-primary">{telemetry.total_tokens ?? '-'}</span></div>
                                            {typeof telemetry.cached_tokens === 'number' && (
                                                <div className="flex justify-between text-emerald-600"><span className="opacity-70">Cached:</span><span>{telemetry.cached_tokens}</span></div>
                                            )}
                                        </div>

                                        {/* OpenAI Raw Payload Debugger */}
                                        {telemetry.openai_payload && (
                                            <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-800">
                                                <h4 className="text-[10px] font-black uppercase text-slate-400 mb-3 tracking-widest">Debug: Raw OpenAI Interaction</h4>

                                                <div className="space-y-4">
                                                    <div>
                                                        <div className="text-[10px] text-emerald-600 mb-1 font-bold">RAW INPUT (PROMPTS)</div>
                                                        <pre className="p-3 bg-white dark:bg-black rounded-lg border border-slate-200 dark:border-slate-800 overflow-x-auto whitespace-pre-wrap max-h-60 overflow-y-auto custom-scrollbar">
                                                            {JSON.stringify(telemetry.openai_payload.full_input, null, 2)}
                                                        </pre>
                                                    </div>

                                                    <div>
                                                        <div className="text-[10px] text-blue-600 mb-1 font-bold">RAW OUTPUT (JSON)</div>
                                                        <pre className="p-3 bg-white dark:bg-black rounded-lg border border-slate-200 dark:border-slate-800 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto custom-scrollbar">
                                                            {JSON.stringify(telemetry.openai_payload.full_output, null, 2)}
                                                        </pre>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </section>
                        )}
                    </div>
                </main>

                {/* Chat Panel - 30% */}
                <aside className={`hidden lg:block ${isChatOpen ? 'w-[30%]' : 'w-0'} border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 transition-all duration-300 overflow-hidden`}>
                    {isChatOpen && (
                        <div className="h-[calc(100vh-65px)] sticky top-[65px]">
                            <ContextualChatPanel
                                sessionId={String(sessionId || '')}
                                originalProblem={originalProblemText || problem?.input || ''}
                                finalAnswer={finalAnswer}
                                steps={steps}
                                classification={classification}
                            />
                        </div>
                    )}
                </aside>

                {/* Mobile Chat Toggle */}
                <button
                    onClick={() => setIsChatOpen(!isChatOpen)}
                    className="lg:hidden fixed bottom-6 right-6 size-14 bg-gradient-to-r from-primary to-emerald-500 text-white rounded-full shadow-xl shadow-primary/40 flex items-center justify-center z-50 hover:scale-110 transition-transform"
                >
                    <span className="material-symbols-outlined text-[24px]">{isChatOpen ? 'close' : 'chat'}</span>
                </button>
            </div>

            {/* Footer */}
            <footer className="bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 py-8 text-slate-900 dark:text-white">
                <div className="max-w-[1200px] mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
                    <div className="flex items-center gap-3">
                        <div className="size-5 text-primary">
                            <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                                <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z"></path>
                            </svg>
                        </div>
                        <span className="text-md font-bold">uask.ai</span>
                        <span className="text-xs text-slate-500 ml-4">© {new Date().getFullYear()} YouAsk AI. All rights reserved.</span>
                    </div>
                    <div className="flex gap-6">
                        <a className="text-xs text-slate-500 hover:text-primary transition-colors" href="#">Terms</a>
                        <a className="text-xs text-slate-500 hover:text-primary transition-colors" href="#">Privacy</a>
                        <a className="text-xs text-slate-500 hover:text-primary transition-colors" href="#">Help</a>
                    </div>
                </div>
            </footer>
        </div>
    );
}
