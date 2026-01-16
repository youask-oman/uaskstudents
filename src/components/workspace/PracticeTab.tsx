"use client";

import React, { useState } from "react";
import MathRenderer from "../MathRenderer";
import VisualRenderer, { Visual } from "./VisualRenderer";

interface SimilarExample {
    problem: string;
    key_idea: string;
    short_solution: string;
    visual?: Visual;
}

interface PracticeTabProps {
    similarExamples: SimilarExample[];
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
    level,
    topic,
}: PracticeTabProps) {
    const [revealed, setRevealed] = useState<Set<number>>(new Set());
    const [completed, setCompleted] = useState<Set<number>>(new Set());

    const examples = similarExamples.length > 0 ? similarExamples : fallbackExamples;

    // Progress starts at 0 and increases based on completed questions
    const currentProgress = Math.round((completed.size / examples.length) * 100);
    const problemsLeft = examples.length - completed.size;
    const masteryText = problemsLeft > 0
        ? `You're doing great! Solve ${problemsLeft} more problems to reach standard.`
        : "Excellent! You've completed all practice problems for this set.";

    const toggleReveal = (idx: number) => {
        const next = new Set(revealed);
        if (next.has(idx)) next.delete(idx);
        else next.add(idx);
        setRevealed(next);
    };

    const handleSolve = (problem: string, idx: number) => {
        // Mark as completed
        const next = new Set(completed);
        next.add(idx);
        setCompleted(next);

        // Open in new tab to allow user to see progress bar update here
        window.open(`/?q=${encodeURIComponent(problem)}&autoSolve=true`, '_blank');
    };

    return (
        <div className="max-w-[900px] mx-auto flex flex-col gap-8">
            <section className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-white">
                        <span className="material-symbols-outlined text-primary dark:text-accent text-sm">school</span>
                        Topic Mastery: {topic || "Algebra"}
                    </div>
                    <span className="text-xs font-bold text-primary dark:text-accent">{currentProgress}%</span>
                </div>
                <div className="h-2.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-primary dark:bg-accent rounded-full"
                        style={{ width: `${currentProgress}%` }}
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
                {examples.map((example, idx) => {
                    const hasVisual = !!example.visual;
                    const isRevealed = revealed.has(idx);

                    return (
                        <div key={idx} className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl overflow-hidden shadow-sm transition-all hover:shadow-md">
                            <div className={`grid ${hasVisual ? 'grid-cols-1 md:grid-cols-[220px_1fr]' : 'grid-cols-1'}`}>
                                {hasVisual && (
                                    <div className="h-44 md:h-full bg-slate-50 dark:bg-black/20 flex items-center justify-center border-r border-slate-100 dark:border-border-dark p-4">
                                        <VisualRenderer visual={example.visual!} />
                                    </div>
                                )}

                                <div className="p-5 flex flex-col gap-4">
                                    <div className="flex items-center justify-between">
                                        <div className="text-[10px] font-bold uppercase tracking-wide text-primary dark:text-accent">Problem {idx + 1}</div>
                                        <div className="flex items-center gap-3 text-slate-400 dark:text-slate-500">
                                            <span className="material-symbols-outlined text-sm cursor-pointer hover:text-primary transition-colors">bookmark</span>
                                            <span className="material-symbols-outlined text-sm cursor-pointer hover:text-primary transition-colors">share</span>
                                        </div>
                                    </div>
                                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                                        <MathRenderer content={example.problem} />
                                    </div>

                                    {example.key_idea && (
                                        <div className="bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-border-dark rounded-xl p-4">
                                            <div className="flex items-center gap-2 text-xs font-bold text-primary dark:text-accent mb-2">
                                                <span className="material-symbols-outlined text-sm">lightbulb</span>
                                                Key Idea
                                            </div>
                                            <p className="text-xs text-slate-600 dark:text-slate-300">{example.key_idea}</p>
                                        </div>
                                    )}

                                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100 dark:border-white/5">
                                        <div className="flex items-center gap-4">
                                            {example.short_solution && example.short_solution !== "Tap to solve" && (
                                                <>
                                                    <button
                                                        onClick={() => toggleReveal(idx)}
                                                        className="text-xs font-bold text-primary dark:text-accent flex items-center gap-1 hover:underline outline-none"
                                                    >
                                                        {isRevealed ? "Hide Solution" : "Reveal Solution"}
                                                        <span className="material-symbols-outlined text-sm">{isRevealed ? "visibility_off" : "visibility"}</span>
                                                    </button>

                                                    {isRevealed && (
                                                        <div className="animate-in fade-in slide-in-from-left-2 duration-300">
                                                            <span className="text-sm font-bold text-slate-800 dark:text-white px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-lg">
                                                                <MathRenderer content={example.short_solution} />
                                                            </span>
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                        </div>

                                        {/* Tap to solve hidden for now 
                                        <button 
                                            onClick={() => handleSolve(example.problem, idx)}
                                            className="text-xs font-bold text-slate-400 dark:text-slate-500 hover:text-primary dark:hover:text-white transition-colors flex items-center gap-1"
                                        >
                                            Tap to solve
                                            <span className="material-symbols-outlined text-sm">arrow_forward</span>
                                        </button>
                                        */}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </section>

            <section className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-2xl p-4 flex items-center justify-between">
                <div>
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 dark:text-slate-500">Up Next</p>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">Quadratic Equations Introduction</p>
                </div>
                <button className="px-4 py-2 rounded-xl bg-primary dark:bg-accent text-white text-xs font-bold flex items-center gap-2 hover:opacity-90 transition-opacity">
                    <span className="material-symbols-outlined text-sm">auto_awesome</span>
                    Generate More Practice
                </button>
            </section>
        </div>
    );
}
