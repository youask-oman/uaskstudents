"use client";

import React from "react";
import WorkspaceTabs from "./WorkspaceTabs";

interface SimilarExample {
    problem: string;
    key_idea: string;
    short_solution: string;
}

interface PracticeTabProps {
    similarExamples: SimilarExample[];
    progress: number;
    level: string;
    topic?: string;
    activeTab: "steps" | "verification" | "concepts" | "practice";
    onSelectTab: (tab: PracticeTabProps["activeTab"]) => void;
    stepsCount?: number;
}

const fallbackExamples: SimilarExample[] = [
    {
        problem: "Solve for x: 2x + 5 = 15",
        key_idea: "Isolate the variable by subtracting constants before dividing.",
        short_solution: "x = 5"
    },
    {
        problem: "Find the slope: y = 3x - 4",
        key_idea: "The slope is the coefficient of x in slope-intercept form.",
        short_solution: "m = 3"
    }
];

export default function PracticeTab({
    similarExamples,
    progress,
    level,
    topic,
    activeTab,
    onSelectTab,
    stepsCount = 0
}: PracticeTabProps) {
    const examples = similarExamples.length > 0 ? similarExamples : fallbackExamples;
    const masteryText = `You're doing great! Solve ${Math.max(1, 4 - examples.length)} more problems to reach ${level}.`;

    return (
        <div className="max-w-[900px] mx-auto flex flex-col gap-8">
            <WorkspaceTabs activeTab={activeTab} onSelectTab={onSelectTab} stepsCount={stepsCount} />

            <section className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white">
                        <span className="material-symbols-outlined text-primary dark:text-accent text-sm">school</span>
                        Topic Mastery: {topic || "Algebra"}
                    </div>
                    <span className="text-xs font-bold text-primary dark:text-accent">{progress}%</span>
                </div>
                <div className="h-2.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-primary dark:bg-accent rounded-full"
                        style={{ width: `${progress}%` }}
                    ></div>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-3">{masteryText}</p>
            </section>

            <section className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">Similar Examples</h2>
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                    <span className="px-2 py-1 rounded-full border border-slate-200 dark:border-border-dark">{topic || "Linear Equations"}</span>
                    <span className="px-2 py-1 rounded-full border border-slate-200 dark:border-border-dark">Difficulty: Medium</span>
                </div>
            </section>

            <section className="space-y-5">
                {examples.map((example, idx) => (
                    <div key={example.problem} className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl overflow-hidden shadow-sm">
                        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr]">
                            <div className="h-44 md:h-full bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700 flex items-center justify-center text-white">
                                <svg viewBox="0 0 200 140" className="w-full h-full opacity-70">
                                    <line x1="20" y1="120" x2="180" y2="20" stroke="white" strokeWidth="2" />
                                    <line x1="20" y1="120" x2="180" y2="80" stroke="white" strokeWidth="2" />
                                    <circle cx="80" cy="80" r="4" fill="white" />
                                </svg>
                            </div>
                            <div className="p-5 flex flex-col gap-4">
                                <div className="flex items-center justify-between">
                                    <div className="text-[10px] font-bold uppercase tracking-wide text-primary dark:text-accent">Problem {idx + 1}</div>
                                    <div className="flex items-center gap-3 text-slate-400 dark:text-slate-500">
                                        <span className="material-symbols-outlined text-sm">bookmark</span>
                                        <span className="material-symbols-outlined text-sm">share</span>
                                    </div>
                                </div>
                                <div>
                                    <p className="text-sm font-semibold math-font text-primary dark:text-white">{example.problem}</p>
                                </div>
                                <div className="bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-border-dark rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-xs font-bold text-primary dark:text-accent mb-2">
                                        <span className="material-symbols-outlined text-sm">lightbulb</span>
                                        Key Idea
                                    </div>
                                    <p className="text-xs text-slate-600 dark:text-slate-300">{example.key_idea}</p>
                                </div>
                                <div className="flex items-center justify-between text-xs text-primary dark:text-accent font-bold">
                                    <button className="flex items-center gap-1">
                                        Reveal Solution
                                        <span className="material-symbols-outlined text-sm">arrow_forward</span>
                                    </button>
                                    <span className="math-font text-primary dark:text-white">{example.short_solution}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </section>

            <section className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl p-4 flex items-center justify-between">
                <div>
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 dark:text-slate-500">Up Next</p>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">Quadratic Equations Introduction</p>
                </div>
                <button className="px-4 py-2 rounded-xl bg-primary dark:bg-accent text-white text-xs font-bold flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">auto_awesome</span>
                    Generate More Practice
                </button>
            </section>
        </div>
    );
}
