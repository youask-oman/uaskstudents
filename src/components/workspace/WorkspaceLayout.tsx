"use client";

import React from 'react';
import Link from 'next/link';
import MathRenderer from '../MathRenderer';
import MathRendererMJX from '../MathRendererMJX';
import { sanitizeLatex } from '../MathUtils';
import WorkspaceTabs from './WorkspaceTabs';

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

const isMathJaxEnabled = (process.env.NEXT_PUBLIC_MATH_RENDERER || "katex") === "mathjax";
const InlineRenderer = isMathJaxEnabled ? MathRendererMJX : MathRenderer;

interface WorkspaceLayoutProps {
    children: React.ReactNode;
    messages: WorkspaceMessage[];
    activeTab: "steps" | "verification" | "practice";
    onSelectTab: (tab: "steps" | "verification" | "practice") => void;
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
    };
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
    confidence = 99,
    sessionId,
    initialSaved = false,
    telemetry
}: WorkspaceLayoutProps) {
    const [isPlanOpen, setIsPlanOpen] = React.useState(true);
    const [isSaved, setIsSaved] = React.useState(initialSaved);
    const [isBookmarked, setIsBookmarked] = React.useState(false);
    const [isMetricsOpen, setIsMetricsOpen] = React.useState(false);

    const handleSave = async () => {
        // Optimistic toggle
        const newState = !isSaved;
        setIsSaved(newState);

        if (newState && sessionId) {
            try {
                // Call save endpoint
                await fetch(`/api/v1/sessions/${sessionId}/save`, { method: 'POST' });
            } catch (err) {
                console.error("Failed to save session", err);
                setIsSaved(!newState); // Revert on error
            }
        }
    };

    return (
        <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-background-light dark:bg-background-dark font-display text-[#111318] dark:text-white transition-colors duration-200">
            {/* ... (Header Omitted) ... */}
            <header className="sticky top-0 z-50 flex items-center justify-between whitespace-nowrap border-b border-solid border-[#e5e7eb] dark:border-[#2a303c] bg-white dark:bg-[#0d1117] px-6 lg:px-10 py-3">
                {/* Left: Logo + Nav */}
                <div className="flex items-center gap-8">
                    {/* Logo */}
                    <Link href="/dashboard" className="flex items-center gap-2">
                        <img src="/logo.png" alt="uask.ai" className="h-8 w-auto" />
                        <span className="text-lg font-bold tracking-tight text-[#111318] dark:text-white">uask.ai</span>
                    </Link>

                    {/* Navigation */}
                    <nav className="hidden md:flex items-center gap-1">
                        <Link
                            href="/dashboard"
                            className="px-4 py-2 text-sm font-medium text-[#616f89] dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                            Dashboard
                        </Link>
                        <Link
                            href="/solve"
                            className="px-4 py-2 text-sm font-bold text-primary bg-primary/5 rounded-lg"
                        >
                            New Solve
                        </Link>
                        <Link
                            href="/dashboard"
                            className="px-4 py-2 text-sm font-medium text-[#616f89] dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                            History
                        </Link>
                    </nav>
                </div>

                {/* Right: Theme Toggle, Notifications, Profile */}
                <div className="flex items-center gap-3">
                    {/* Dark/Light Mode Toggle */}
                    <button
                        onClick={() => {
                            const html = document.documentElement;
                            html.classList.toggle('dark');
                            localStorage.setItem('theme', html.classList.contains('dark') ? 'dark' : 'light');
                        }}
                        className="p-2 rounded-lg text-[#616f89] dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                        title="Toggle dark/light mode"
                    >
                        <span className="material-symbols-outlined text-[20px] dark:hidden">dark_mode</span>
                        <span className="material-symbols-outlined text-[20px] hidden dark:block">light_mode</span>
                    </button>

                    {/* Notifications (Placeholder) */}
                    <button
                        className="p-2 rounded-lg text-[#616f89] dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all relative"
                        title="Notifications (coming soon)"
                    >
                        <span className="material-symbols-outlined text-[20px]">notifications</span>
                        {/* Notification dot */}
                        <span className="absolute top-1.5 right-1.5 size-2 bg-red-500 rounded-full"></span>
                    </button>

                    {/* User Profile */}
                    <Link href="/profile" className="flex items-center gap-3 pl-3 border-l border-[#e5e7eb] dark:border-[#2a303c] hover:opacity-80 transition-opacity">
                        <div className="size-9 bg-gradient-to-br from-orange-400 to-orange-600 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-md">
                            NR
                        </div>
                        <span className="hidden lg:block text-sm font-medium text-[#111318] dark:text-white">Nathan Rivera</span>
                    </Link>
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
                <section className="bg-emerald-50 dark:bg-emerald-900/10 rounded-2xl p-6 mb-8 shadow-sm border border-emerald-200 dark:border-emerald-900/30 relative">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-100 dark:bg-emerald-800/20 rounded-full -translate-y-1/2 translate-x-1/2"></div>
                    <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">{problem?.topic || "Topic"}</span>
                                <span className="text-xs text-[#616f89] dark:text-slate-400">Workspace #{problem?.id?.slice(0, 4) || "64"}</span>
                            </div>
                            <h1 className="text-xl font-bold tracking-tight mb-2 text-[#111318] dark:text-white">{problem?.goal || "Solve"}</h1>
                            <div className="text-sm text-emerald-800 dark:text-emerald-300 font-medium leading-relaxed max-w-2xl">
                                <InlineRenderer content={problem?.input || "Expression"} inline />
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2 shrink-0 flex-wrap">
                            {/* Save to Library */}
                            <button
                                onClick={handleSave}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-xs shadow-md transition-all ${isSaved
                                    ? "bg-amber-100 text-amber-600 hover:bg-amber-200"
                                    : "bg-emerald-600 hover:bg-emerald-700 text-white"
                                    }`}
                            >
                                <span className={`material-symbols-outlined text-[16px] ${isSaved ? 'text-amber-500' : ''}`}>{isSaved ? 'bookmark_added' : 'bookmark_add'}</span>
                                {isSaved ? 'Saved' : 'Save'}
                            </button>

                            {/* Bookmark Toggle */}
                            <button
                                onClick={() => setIsBookmarked(!isBookmarked)}
                                className={`p-2 rounded-lg border transition-all ${isBookmarked
                                    ? "bg-amber-100 border-amber-300 text-amber-500"
                                    : "border-emerald-300 dark:border-emerald-700 hover:bg-emerald-100 dark:hover:bg-emerald-800/30 text-emerald-700 dark:text-emerald-400"
                                    }`}
                                title={isBookmarked ? "Remove Bookmark" : "Bookmark for later"}
                            >
                                <span className={`material-symbols-outlined text-[18px] ${isBookmarked ? 'fill-1 text-amber-500' : ''}`}>star</span>
                            </button>

                            {/* Share Dropdown */}
                            <div className="relative group">
                                <button
                                    className="p-2 rounded-lg border border-emerald-300 dark:border-emerald-700 hover:bg-emerald-100 dark:hover:bg-emerald-800/30 transition-all text-emerald-700 dark:text-emerald-400"
                                    title="Share solution"
                                >
                                    <span className="material-symbols-outlined text-[18px]">share</span>
                                </button>
                                {/* Dropdown Menu */}
                                <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-[#1e2634] rounded-lg shadow-xl border border-[#e5e7eb] dark:border-[#2a303c] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                                    <div className="p-2 space-y-1">
                                        <button onClick={() => window.open(`https://twitter.com/intent/tweet?text=Check out this math solution!&url=${encodeURIComponent(window.location.href)}`, '_blank')} className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition-all text-left">
                                            <span className="text-[#1DA1F2]">𝕏</span> Share on X/Twitter
                                        </button>
                                        <button onClick={() => window.open(`https://wa.me/?text=${encodeURIComponent('Check out this math solution: ' + window.location.href)}`, '_blank')} className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition-all text-left">
                                            <span className="text-[#25D366]">📱</span> Share on WhatsApp
                                        </button>
                                        <button onClick={() => window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.href)}`, '_blank')} className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition-all text-left">
                                            <span className="text-[#0A66C2]">in</span> Share on LinkedIn
                                        </button>
                                        <div className="h-px bg-slate-200 dark:bg-slate-600 my-1"></div>
                                        <button onClick={() => { navigator.clipboard.writeText(window.location.href); alert('Link copied!'); }} className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition-all text-left">
                                            <span className="material-symbols-outlined text-[14px]">link</span> Copy Link
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Print/PDF */}
                            <button
                                onClick={() => window.print()}
                                className="p-2 rounded-lg border border-emerald-300 dark:border-emerald-700 hover:bg-emerald-100 dark:hover:bg-emerald-800/30 transition-all text-emerald-700 dark:text-emerald-400"
                                title="Print or Save as PDF"
                            >
                                <span className="material-symbols-outlined text-[18px]">print</span>
                            </button>
                        </div>
                    </div>
                </section>

                {/* Quick Data Grid - 40/20/40 Layout */}
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
                    {/* GIVEN Card - 40% (col-span-2) - Warm tint */}
                    <div className="md:col-span-2 lg:col-span-2 bg-orange-50 dark:bg-orange-950/20 p-5 rounded-xl border border-orange-200 dark:border-orange-900/30 flex items-start gap-4">
                        <div className="size-10 rounded-lg bg-orange-100 dark:bg-orange-500/20 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
                            <span className="material-symbols-outlined">description</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-xs font-bold text-orange-700 dark:text-orange-400 uppercase mb-1">Given</p>
                            <div className="text-sm font-medium text-[#111318] dark:text-white whitespace-normal break-words" style={{ overflowWrap: 'break-word', wordBreak: 'normal', hyphens: 'auto' }}>
                                <InlineRenderer content={problem?.given_data?.join(", ") || problem?.input || "N/A"} inline />
                            </div>
                        </div>
                    </div>

                    {/* FIND Card - 20% (col-span-1) - Green tint */}
                    <div className="md:col-span-1 lg:col-span-1 bg-emerald-50 dark:bg-emerald-950/20 p-5 rounded-xl border border-emerald-200 dark:border-emerald-900/30 flex items-start gap-4">
                        <div className="size-10 rounded-lg bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                            <span className="material-symbols-outlined">target</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-xs font-bold text-emerald-700 dark:text-emerald-400 uppercase mb-1">Find</p>
                            <div className="text-base font-bold text-[#111318] dark:text-white whitespace-normal break-words">
                                <InlineRenderer content={problem?.unknowns?.join(", ") || problem?.goal || "x"} inline />
                            </div>
                        </div>
                    </div>

                    {/* ASSUMPTIONS Card - 40% (col-span-2) - Blue tint */}
                    <div className="md:col-span-3 lg:col-span-2 bg-blue-50 dark:bg-blue-950/20 p-5 rounded-xl border border-blue-200 dark:border-blue-900/30 flex items-start gap-4">
                        <div className="size-10 rounded-lg bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                            <span className="material-symbols-outlined">info</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-xs font-bold text-blue-700 dark:text-blue-400 uppercase mb-1">Assumptions</p>
                            <div className="text-sm font-medium text-[#111318] dark:text-white whitespace-normal break-words" style={{ overflowWrap: 'break-word', wordBreak: 'normal', hyphens: 'auto' }}>
                                <InlineRenderer content={problem?.assumptions?.join(", ") || "Standard"} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Final Answer Banner */}
                {finalAnswer && (
                    <div className="bg-primary text-white rounded-2xl p-6 mb-8 shadow-xl shadow-primary/20">
                        {/* Vertical Stack Layout */}
                        <div className="flex flex-col gap-4">

                            {/* Top Row - Refined Solution + Answer */}
                            <div className="flex items-start gap-4">
                                <div className="bg-white/20 p-3 rounded-full backdrop-blur-sm shrink-0">
                                    <span className="material-symbols-outlined text-[28px]">check_circle</span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center gap-2 mb-2">
                                        <span className="bg-white text-primary text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wide">Refined Solution</span>
                                        <span className="flex items-center gap-1 text-[11px] font-medium text-blue-100">
                                            <span className="material-symbols-outlined text-[14px]">verified</span>
                                            YouAsk AI Confidence {confidence}%
                                        </span>
                                    </div>
                                    {/* Smart rendering: split into Parabola/Line segments */}
                                    <div className="text-sm md:text-base font-bold tracking-tight whitespace-normal space-y-2" style={{ overflowWrap: 'break-word', wordBreak: 'normal', color: 'white' }}>
                                        {(() => {
                                            // Smart split: detect .textLine, textParabola, etc. and render as separate labeled sections
                                            const answer = finalAnswer || '';
                                            // Split by .textLine or textLine/textParabola patterns
                                            const segments = answer
                                                .replace(/\.textLine\s*:/gi, '\n**Line:** ')
                                                .replace(/\)textLine\s*:/gi, ')\n**Line:** ')
                                                .replace(/textLine\s*:/gi, '\n**Line:** ')
                                                .replace(/\.textParabola\s*:/gi, '\n**Parabola:** ')
                                                .replace(/textParabola\s*:/gi, '\n**Parabola:** ')
                                                .replace(/Parabola\s*:/gi, '**Parabola:** ')
                                                .split('\n')
                                                .map(s => s.trim())
                                                .filter(Boolean);

                                            return segments.map((segment, idx) => {
                                                // Check if segment starts with a label like **Line:** or **Parabola:**
                                                const labelMatch = segment.match(/^\*\*(Line|Parabola|Plot):\*\*\s*/i);
                                                if (labelMatch) {
                                                    const label = labelMatch[1];
                                                    const mathPart = segment.replace(labelMatch[0], '').trim();
                                                    return (
                                                        <div key={idx} className="flex flex-wrap items-baseline gap-2">
                                                            <span className="text-blue-200 font-bold">{label}:</span>
                                                            <span className="text-white">
                                                                <InlineRenderer content={mathPart} inline />
                                                            </span>
                                                        </div>
                                                    );
                                                }
                                                return (
                                                    <div key={idx}>
                                                        <InlineRenderer content={segment} inline />
                                                    </div>
                                                );
                                            });
                                        })()}
                                    </div>
                                </div>
                            </div>

                            {/* Bottom Row - Solution Set */}
                            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 pl-0 sm:pl-16">
                                <span className="text-xs font-bold text-blue-200 uppercase tracking-wider shrink-0">Solution Set:</span>
                                <div className="bg-white/15 backdrop-blur-sm px-4 py-2 rounded-xl border border-white/20 max-w-full">
                                    <div className="text-sm font-bold whitespace-normal break-words" style={{ color: '#86efac' }}>
                                        {(() => {
                                            // Clean the answer for Solution Set display
                                            const cleanedAnswer = (finalAnswer || '')
                                                .replace(/\.textLine\s*:/gi, '. Line: ')
                                                .replace(/\)textLine\s*:/gi, '). Line: ')
                                                .replace(/textLine\s*:/gi, 'Line: ')
                                                .replace(/\.textParabola\s*:/gi, '. Parabola: ')
                                                .replace(/textParabola\s*:/gi, 'Parabola: ');
                                            return <InlineRenderer content={cleanedAnswer} inline />;
                                        })()}
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>
                )}

                {/* Solution Plan (Horizontal List) */}
                <div className="mb-8 p-6 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-[20px]">format_list_numbered</span>
                            <h3 className="font-bold text-sm uppercase tracking-wide text-[#111318] dark:text-white">
                                Solution Plan {analysisPlan.length > 0 && `(${analysisPlan.length} Steps)`}
                            </h3>
                        </div>
                    </div>

                    {analysisPlan.length > 0 ? (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {analysisPlan.map((step, idx) => {
                                const stepNum = idx + 1;
                                const title = (step || "").trim();
                                if (!title) return null; // Skip truly empty ones if filter failed

                                const isRedundant =
                                    title.toLowerCase() === `step ${stepNum}` ||
                                    title.toLowerCase() === `step ${stepNum}:`;

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
                                        className="flex flex-col text-left w-full gap-1 bg-white dark:bg-[#1e2634] border border-[#e5e7eb] dark:border-[#2a303c] px-3 py-2 rounded-lg shadow-sm h-full hover:border-primary/50 hover:shadow-md transition-all active:scale-[0.98] group"
                                    >
                                        <div className="flex items-center justify-between w-full">
                                            <span className="text-primary font-black text-xs opacity-70">Step {String(stepNum).padStart(2, '0')}</span>
                                            <span className="material-symbols-outlined text-[14px] text-primary opacity-0 group-hover:opacity-100 transition-opacity">north_east</span>
                                        </div>
                                        {!isRedundant && (
                                            <div className="font-bold text-[#111318] dark:text-white text-xs leading-tight line-clamp-2" title={title}>
                                                <MathRenderer content={title} inline />
                                            </div>
                                        )}
                                        {isRedundant && (
                                            <div className="font-bold text-[#111318] dark:text-white text-xs leading-tight opacity-40">
                                                Analyzing...
                                            </div>
                                        )}
                                    </button>
                                );
                            })}
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
                    <WorkspaceTabs
                        activeTab={activeTab}
                        onSelectTab={onSelectTab}
                        stepsCount={stepsCount}
                    />

                    {/* Tab Content (Children) */}
                    <div>
                        {children}
                    </div>
                </div>

                {/* Metrics / Telemetry Block */}
                {telemetry && (
                    <div className="mt-8 border-t border-slate-200 dark:border-slate-700 pt-6">
                        <button
                            onClick={() => setIsMetricsOpen(!isMetricsOpen)}
                            className="flex items-center gap-2 text-xs font-mono text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 transition-colors w-full"
                        >
                            <span className="material-symbols-outlined text-[16px]">{isMetricsOpen ? 'expand_more' : 'chevron_right'}</span>
                            <span className="font-bold">METRICS</span>
                            <span className="ml-auto opacity-50">{telemetry.request_id}</span>
                        </button>

                        {isMetricsOpen && (
                            <div className="mt-2 p-4 bg-slate-100 dark:bg-slate-900 rounded-lg font-mono text-xs text-slate-700 dark:text-slate-400 overflow-x-auto">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2">
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Request ID:</span>
                                        <span className="font-bold select-all">{telemetry.request_id || '-'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Model:</span>
                                        <span className="font-bold">{telemetry.model || '-'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Goal:</span>
                                        <span className="font-bold uppercase text-xs pt-1">{telemetry.learning_mode || 'SOLVE'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Style:</span>
                                        <span className="font-bold uppercase text-xs pt-1">{telemetry.requested_mode || 'MINIMAL'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">OpenAI Latency:</span>
                                        <span className="font-bold">{telemetry.latency_ms_openai ?? '-'}ms</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Total Latency:</span>
                                        <span className="font-bold">{telemetry.latency_ms_total ?? '-'}ms</span>
                                    </div>
                                    <div className="col-span-1 md:col-span-2 border-t border-slate-200 dark:border-slate-800 my-1"></div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Input Tokens:</span>
                                        <span>{telemetry.input_tokens ?? '-'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Output Tokens:</span>
                                        <span>{telemetry.output_tokens ?? '-'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="opacity-70">Total Tokens:</span>
                                        <span className="font-bold text-primary">{telemetry.total_tokens ?? '-'}</span>
                                    </div>
                                    {typeof telemetry.cached_tokens === 'number' && (
                                        <div className="flex justify-between text-emerald-600 dark:text-emerald-400">
                                            <span className="opacity-70">Cached Tokens:</span>
                                            <span>{telemetry.cached_tokens}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

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
                        <p className="text-xs text-[#616f89] ml-4">© {new Date().getFullYear()} YouAsk AI LLM Math Solver Labs. All rights reserved.</p>
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
