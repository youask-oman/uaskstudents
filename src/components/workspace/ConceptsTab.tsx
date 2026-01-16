"use client";

import React from "react";
import WorkspaceTabs from "./WorkspaceTabs";
import VisualRenderer, { Visual } from "./VisualRenderer";

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

interface ConceptsTabProps {
    keyConcepts: string[];
    commonMistakes: string[];
    features?: Features;
    visuals?: Visual[];
    activeTab: "steps" | "verification" | "concepts" | "practice";
    onSelectTab: (tab: ConceptsTabProps["activeTab"]) => void;
    stepsCount?: number;
}

function formatPoint(point?: InterceptPoint | null): string {
    if (!point) return "N/A";
    return `(${point.x}, ${point.y})`;
}

function formatPoints(points?: InterceptPoint[]): string {
    if (!points || points.length === 0) return "N/A";
    return points.map(point => `(${point.x}, ${point.y})`).join(", ");
}

export default function ConceptsTab({
    keyConcepts,
    commonMistakes,
    features,
    visuals,
    activeTab,
    onSelectTab,
    stepsCount = 0
}: ConceptsTabProps) {
    const conceptCards = (keyConcepts.length > 0 ? keyConcepts : ["Core Concept"]).slice(0, 3);
    const mistakes = commonMistakes.length > 0 ? commonMistakes : ["Double-check signs and arithmetic."];
    const graphVisual = (visuals || [])[0];

    return (
        <div className="max-w-[900px] mx-auto flex flex-col gap-8">
            <div>
                <div className="text-xs text-slate-400 dark:text-slate-500 font-semibold uppercase tracking-wider">
                    Workspace / Concepts
                </div>
                <div className="mt-2">
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Concept Workspace</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Master the underlying principles behind the solution so you can solve similar problems with ease.
                    </p>
                </div>
            </div>



            <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-4">
                    <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white">
                        <span className="material-symbols-outlined text-primary dark:text-accent text-sm">menu_book</span>
                        Key Concepts
                    </div>

                    <div className="space-y-4">
                        {conceptCards.map((concept) => (
                            <div key={concept} className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl p-5 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-primary dark:text-accent bg-primary/10 px-2 py-1 rounded-full">
                                        Algebra Foundation
                                    </span>
                                    <button className="text-xs font-bold text-primary dark:text-accent flex items-center gap-1">
                                        Open Card
                                        <span className="material-symbols-outlined text-sm">arrow_forward</span>
                                    </button>
                                </div>
                                <h3 className="text-base font-bold text-slate-900 dark:text-white mt-3">{concept}</h3>
                                <p className="text-sm text-slate-600 dark:text-slate-300 mt-2">
                                    Focus on why this concept applies and how it shapes the final result.
                                </p>
                                <div className="mt-4 bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-border-dark rounded-lg px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                                    <span className="text-primary dark:text-accent font-bold">Rule:</span> Check the relationship between slope, intercepts, and the equation form.
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="space-y-4">
                    <div className="bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/50 rounded-2xl p-4">
                        <div className="flex items-center gap-2 text-sm font-bold text-red-600 dark:text-red-300">
                            <span className="material-symbols-outlined text-sm">error</span>
                            Common Mistakes
                        </div>
                        <div className="mt-3 space-y-3">
                            {mistakes.slice(0, 2).map((mistake) => (
                                <div key={mistake} className="border border-red-100 dark:border-red-900/50 bg-white/70 dark:bg-red-950/40 rounded-lg p-3">
                                    <p className="text-sm font-semibold text-red-600 dark:text-red-200">{mistake.split(":")[0]}</p>
                                    <p className="text-xs text-red-700 dark:text-red-300 mt-1">{mistake}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl p-4 shadow-sm">
                        <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white">
                            <span className="material-symbols-outlined text-primary dark:text-accent text-sm">calculate</span>
                            Math Facts
                        </div>
                        <div className="grid grid-cols-2 gap-3 mt-4">
                            <div className="border border-slate-200 dark:border-border-dark rounded-lg p-3 text-center">
                                <p className="text-[10px] uppercase text-slate-400 dark:text-slate-500">X-Intercept</p>
                                <p className="text-sm font-semibold math-font text-primary dark:text-white">{formatPoints(features?.intercepts?.x)}</p>
                            </div>
                            <div className="border border-slate-200 dark:border-border-dark rounded-lg p-3 text-center">
                                <p className="text-[10px] uppercase text-slate-400 dark:text-slate-500">Y-Intercept</p>
                                <p className="text-sm font-semibold math-font text-primary dark:text-white">{formatPoint(features?.intercepts?.y)}</p>
                            </div>
                            <div className="border border-slate-200 dark:border-border-dark rounded-lg p-3 text-center">
                                <p className="text-[10px] uppercase text-slate-400 dark:text-slate-500">Domain</p>
                                <p className="text-sm font-semibold math-font text-primary dark:text-white">{features?.domain || "N/A"}</p>
                            </div>
                            <div className="border border-slate-200 dark:border-border-dark rounded-lg p-3 text-center">
                                <p className="text-[10px] uppercase text-slate-400 dark:text-slate-500">Range</p>
                                <p className="text-sm font-semibold math-font text-primary dark:text-white">{features?.range || "N/A"}</p>
                            </div>
                        </div>
                        <div className="mt-4 border border-slate-200 dark:border-border-dark rounded-xl overflow-hidden">
                            {graphVisual ? (
                                <div className="bg-slate-50 dark:bg-slate-900/40 p-3">
                                    <VisualRenderer visual={graphVisual} />
                                </div>
                            ) : (
                                <div className="bg-slate-100 dark:bg-slate-900/40 h-32 flex items-center justify-center text-xs text-slate-500">
                                    Graph preview
                                </div>
                            )}
                            <div className="bg-white dark:bg-surface-dark border-t border-slate-200 dark:border-border-dark p-3 flex items-center justify-end">
                                <button className="text-xs font-bold text-primary dark:text-accent flex items-center gap-1">
                                    Expand Graph
                                    <span className="material-symbols-outlined text-sm">open_in_full</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
