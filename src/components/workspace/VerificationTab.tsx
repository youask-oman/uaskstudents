"use client";

import React from "react";
import WorkspaceTabs from "./WorkspaceTabs";

interface VerificationItem {
    method: string;
    why_it_works: string;
    steps: string[];
    conclusion: string;
}

interface InterceptPoint {
    x: number;
    y: number;
}

interface Features {
    intercepts?: {
        x?: InterceptPoint[];
        y?: InterceptPoint;
    };
    domain?: string;
    range?: string;
}

interface SimilarExample {
    problem: string;
    key_idea: string;
    short_solution: string;
}

interface VerificationTabProps {
    methods: VerificationItem[];
    activeTab: "steps" | "verification" | "concepts" | "practice";
    onSelectTab: (tab: VerificationTabProps["activeTab"]) => void;
    stepsCount?: number;
    problem?: {
        input?: string;
        topic?: string;
        goal?: string;
        assumptions?: string[];
        given_data?: string[];
        unknowns?: string[];
    };
    analysisPlan?: string[];
    finalAnswer?: string;
    confidence?: number;
    keyConcepts?: string[];
    features?: Features;
    commonMistakes?: string[];
    similarExamples?: SimilarExample[];
}

function formatPoint(point?: InterceptPoint | null): string {
    if (!point) return "N/A";
    return `(${point.x}, ${point.y})`;
}

function formatPoints(points?: InterceptPoint[]): string {
    if (!points || points.length === 0) return "N/A";
    return points.map(point => `(${point.x}, ${point.y})`).join(", ");
}

export default function VerificationTab({
    methods,
    activeTab,
    onSelectTab,
    stepsCount = 0,
    problem,
    analysisPlan = [],
    finalAnswer,
    confidence,
    keyConcepts = [],
    features,
    commonMistakes = [],
    similarExamples = []
}: VerificationTabProps) {
    const confidencePct = Math.round((confidence ?? 0) * 100);

    return (
        <div className="max-w-[800px] mx-auto flex flex-col gap-8">
            <section className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark overflow-hidden">
                <div className="p-6 border-b border-gray-50 dark:border-border-dark">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-xl font-bold">Solution Workspace</h1>
                            <p className="text-xs text-gray-500 dark:text-slate-400">Mathematical Analysis & Verification</p>
                        </div>
                        <button className="px-3 py-2 text-xs font-bold border border-gray-200 dark:border-border-dark rounded-lg flex items-center gap-2">
                            <span className="material-symbols-outlined text-sm">share</span>
                            Share Workspace
                        </button>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 divide-x divide-gray-100 dark:divide-border-dark">
                    <div className="p-4">
                        <p className="text-[10px] font-bold text-gray-400 dark:text-slate-500 uppercase mb-1">Given</p>
                        <p className="text-sm font-medium">{(problem?.given_data || []).join(", ") || "N/A"}</p>
                    </div>
                    <div className="p-4">
                        <p className="text-[10px] font-bold text-gray-400 dark:text-slate-500 uppercase mb-1">Find</p>
                        <p className="text-sm font-medium">{(problem?.unknowns || []).join(", ") || "N/A"}</p>
                    </div>
                    <div className="p-4">
                        <p className="text-[10px] font-bold text-gray-400 dark:text-slate-500 uppercase mb-1">Assumptions</p>
                        <p className="text-sm font-medium italic">{(problem?.assumptions || []).join(", ") || "N/A"}</p>
                    </div>
                </div>
                <div className="px-6 py-4 bg-gray-50 dark:bg-slate-900/40">
                    <details className="group">
                        <summary className="flex cursor-pointer items-center justify-between">
                            <span className="text-sm font-bold flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary dark:text-accent">lightbulb</span>
                                Solution Plan
                            </span>
                            <span className="material-symbols-outlined text-gray-400 dark:text-slate-500 group-open:rotate-180 transition-transform">expand_more</span>
                        </summary>
                        <div className="pt-3 text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                            {(analysisPlan.length > 0 ? analysisPlan : ["Verify the result step-by-step"]).map((line, idx) => (
                                <div key={idx}>{idx + 1}. {line}</div>
                            ))}
                        </div>
                    </details>
                </div>
            </section>

            <section className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-primary dark:text-accent">Final Result</span>
                    <p className="text-lg font-semibold mt-2 math-font text-primary dark:text-white">{finalAnswer || "Result ready"}</p>
                </div>
                <div className="flex items-center gap-3 bg-gray-50 dark:bg-slate-900/40 border border-gray-100 dark:border-border-dark rounded-xl px-4 py-3">
                    <div className="size-12 rounded-full border-4 border-primary/20 flex items-center justify-center text-primary dark:text-accent font-bold">
                        {confidencePct}%
                    </div>
                    <div>
                        <p className="text-xs font-bold">Confidence</p>
                        <p className="text-[10px] text-gray-500 dark:text-slate-400">Very High Accuracy</p>
                    </div>
                </div>
            </section>

            <WorkspaceTabs activeTab={activeTab} onSelectTab={onSelectTab} stepsCount={stepsCount} />

            <section className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark p-6">
                <div className="flex items-center gap-2 text-sm font-bold text-primary dark:text-accent mb-4">
                    <span className="material-symbols-outlined text-sm">verified</span>
                    Verification Methods
                </div>
                <div className="space-y-4">
                    {methods.map((method, idx) => (
                        <div key={idx} className="border border-gray-100 dark:border-border-dark rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="material-symbols-outlined text-primary dark:text-accent text-sm">check_circle</span>
                                <p className="text-sm font-bold">Method: {method.method}</p>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-slate-400 mb-3">{method.why_it_works}</p>
                            <ul className="space-y-2">
                                {method.steps.map((step, sIdx) => (
                                    <li key={sIdx} className="text-sm text-gray-700 dark:text-slate-200 flex items-start gap-2">
                                        <span className="material-symbols-outlined text-green-500 text-sm">check</span>
                                        <span>{step}</span>
                                    </li>
                                ))}
                            </ul>
                            <div className="mt-4 bg-gray-50 dark:bg-slate-900/40 border border-gray-100 dark:border-border-dark rounded-lg p-3">
                                <p className="text-[10px] uppercase text-gray-400 dark:text-slate-500 font-bold mb-1">Conclusion</p>
                                <p className="text-sm text-gray-700 dark:text-slate-200">{method.conclusion}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark p-4">
                    <div className="flex items-center gap-2 text-sm font-bold mb-3">
                        <span className="material-symbols-outlined text-primary dark:text-accent text-sm">insights</span>
                        Key Concepts
                    </div>
                    <div className="space-y-3">
                        {(keyConcepts.length > 0 ? keyConcepts : ["Core concept"])
                            .slice(0, 3)
                            .map((concept) => (
                                <div key={concept} className="border border-gray-100 dark:border-border-dark rounded-lg p-3">
                                    <p className="text-sm font-semibold">{concept}</p>
                                    <p className="text-xs text-gray-500 dark:text-slate-400">Applies directly in verification.</p>
                                </div>
                            ))}
                    </div>
                </div>
                <div className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark p-4">
                    <div className="flex items-center gap-2 text-sm font-bold mb-3">
                        <span className="material-symbols-outlined text-primary dark:text-accent text-sm">calculate</span>
                        Math Facts
                    </div>
                    <div className="space-y-2 text-sm text-gray-700 dark:text-slate-200">
                        <div className="flex items-center justify-between">
                            <span className="text-gray-500 dark:text-slate-400">Domain</span>
                            <span className="math-font text-primary dark:text-white">{features?.domain || "N/A"}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-500 dark:text-slate-400">Range</span>
                            <span className="math-font text-primary dark:text-white">{features?.range || "N/A"}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-500 dark:text-slate-400">X-Intercepts</span>
                            <span className="math-font text-primary dark:text-white">{formatPoints(features?.intercepts?.x)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-500 dark:text-slate-400">Y-Intercept</span>
                            <span className="math-font text-primary dark:text-white">{formatPoint(features?.intercepts?.y)}</span>
                        </div>
                    </div>
                    <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-3">Intercepts are computed from the verified equation.</p>
                </div>
            </section>

            <section className="bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/50 rounded-2xl p-4">
                <div className="flex items-center gap-2 text-sm font-bold text-red-600 dark:text-red-300 mb-2">
                    <span className="material-symbols-outlined text-sm">warning</span>
                    Common Mistakes
                </div>
                <ul className="text-sm text-red-700 dark:text-red-200 space-y-2">
                    {(commonMistakes.length > 0 ? commonMistakes : ["Double-check signs when subtracting negatives."]).map((mistake, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-sm">error</span>
                            <span>{mistake}</span>
                        </li>
                    ))}
                </ul>
            </section>

            <section className="space-y-3">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold">Similar Practice Problems</h3>
                    <button className="text-xs font-bold text-primary dark:text-accent flex items-center gap-1">
                        Generate More
                        <span className="material-symbols-outlined text-sm">arrow_forward</span>
                    </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {similarExamples.slice(0, 2).map((example, idx) => (
                        <div key={idx} className="bg-white dark:bg-surface-dark rounded-xl border border-gray-100 dark:border-border-dark p-4">
                            <p className="text-sm font-semibold mb-2">{example.problem}</p>
                            <p className="text-xs text-gray-500 dark:text-slate-400 mb-2">{example.key_idea}</p>
                            <button className="text-xs font-bold text-primary dark:text-accent flex items-center gap-1">
                                Show Solution
                                <span className="material-symbols-outlined text-sm">arrow_forward</span>
                            </button>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}
