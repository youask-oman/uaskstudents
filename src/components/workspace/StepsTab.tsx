"use client";

import React from 'react';
import 'katex/dist/katex.min.css';

import VisualRenderer, { Visual } from './VisualRenderer';
import MathRenderer from '../MathRenderer';

interface V3Checkpoint {
    question: string;
    expected_answer: string;
}

interface Step {
    index: number;
    title: string;
    explanation?: string; // V2 or V3 fallback
    work?: string[];
    rules_used?: string[];
    result?: string;
    checkpoint?: V3Checkpoint;
    visual_refs?: string[];
}

interface StepsTabProps {
    title: string;
    steps: Step[];
    visuals?: Visual[];
    problemLatex?: string;
    problem?: any;
    // Props passed by parent but handled in WorkspaceLayout now, 
    // keeping them optional or ignored to avoid errors if passed
    analysisPlan?: string[];
    finalAnswer?: string;
    activeTab?: string;
    onSelectTab?: any;
}

// Helper to process and split math work lines for the 'Card' format
const processWorkLines = (work: string[]): string[] => {
    if (!work || work.length === 0) return [];

    const splitLines: string[] = [];

    work.forEach(rawLine => {
        let content = rawLine.trim();
        // Split by standard separators used in the solver output: \Rightarrow, \rightarrow, ->, or \quad enclosed variations
        // Also handle explicit newlines if any
        const parts = content.split(/\\quad\\Rightarrow\\quad|\\Rightarrow|\\rightarrow|->/g);

        parts.forEach(part => {
            const cleanPart = part.trim();
            if (cleanPart) {
                splitLines.push(cleanPart);
            }
        });
    });

    return splitLines;
};

// Helper to cleaning outer math delimiters if present (fixes connected words issue)
const cleanExplanation = (text?: string): string => {
    if (!text) return "Follow the procedure on the right.";
    // Remove wrapping $$ or $
    let cleaned = text.trim();
    if (cleaned.startsWith('$$') && cleaned.endsWith('$$')) {
        cleaned = cleaned.slice(2, -2);
    } else if (cleaned.startsWith('$') && cleaned.endsWith('$')) {
        cleaned = cleaned.slice(1, -1);
    }
    return cleaned;
};

export default function StepsTab({
    steps,
    visuals,
}: StepsTabProps) {

    return (
        <div className="flex flex-col gap-8">

            {/* Global Tips (Once, at the top) */}
            <div className="bg-amber-50 dark:bg-amber-900/10 rounded-xl border border-amber-200 dark:border-amber-900/50 p-4 flex flex-col md:flex-row items-start md:items-center gap-4 text-xs">
                <div className="flex items-center gap-2 text-amber-700 dark:text-amber-500 font-bold uppercase tracking-wider shrink-0">
                    <span className="material-symbols-outlined text-[18px]">warning</span>
                    <span>Common Tips</span>
                </div>
                <div className="h-px w-full md:w-px md:h-8 bg-amber-200 dark:bg-amber-900/50"></div>
                <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <span className="font-bold text-amber-900 dark:text-amber-100">Verify Step-by-Step: </span>
                        <span className="text-amber-800/80 dark:text-amber-400/80">Always check your arithmetic at each stage to avoid errors.</span>
                    </div>
                    <div>
                        <span className="font-bold text-amber-900 dark:text-amber-100">Units: </span>
                        <span className="text-amber-800/80 dark:text-amber-400/80">Ensure consistency throughout the problem.</span>
                    </div>
                </div>
            </div>

            {/* Steps Content */}
            <div className="space-y-8">
                {steps.map((step, index) => {
                    const cardLines = processWorkLines(step.work || []);
                    const explanationText = cleanExplanation(step.explanation);

                    return (
                        <div key={index} className="relative pl-8 border-l-2 border-primary/20">
                            {/* Step Dot */}
                            <div className="absolute -left-[9px] top-0 size-4 rounded-full bg-primary border-4 border-white dark:border-[#101622]"></div>

                            {/* Step Container */}
                            <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
                                {/* Left Content: Steps (70% width) */}
                                <div className="lg:col-span-7 space-y-4">
                                    <div>
                                        <div className="flex items-center gap-3 mb-2">
                                            <h4 className="text-xl font-bold text-[#111318] dark:text-white">
                                                Step {index + 1}:
                                            </h4>
                                        </div>
                                        <div className="text-lg font-bold text-[#111318] dark:text-white mb-2 leading-snug">
                                            <MathRenderer content={step.title} />
                                        </div>
                                        <div className="text-sm text-[#616f89] dark:text-slate-400 mb-4 leading-relaxed">
                                            <MathRenderer content={explanationText} />
                                            {step.rules_used && step.rules_used.length > 0 && (
                                                <span className="block mt-2 italic text-xs">
                                                    Using: {step.rules_used.join(", ")}
                                                </span>
                                            )}
                                        </div>

                                        {/* Checkpoint Quiz */}
                                        {step.checkpoint && (
                                            <div className="bg-primary/5 dark:bg-primary/10 border border-primary/20 rounded-xl p-4">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className="material-symbols-outlined text-primary text-[16px]">quiz</span>
                                                    <span className="text-xs font-bold text-primary uppercase">Checkpoint</span>
                                                </div>
                                                <div className="text-xs font-medium mb-3 text-[#111318] dark:text-white">
                                                    <MathRenderer content={step.checkpoint.question} />
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    <button className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-primary/20 rounded-lg text-[11px] hover:bg-primary hover:text-white transition-all text-[#616f89] dark:text-slate-300">
                                                        <MathRenderer content={step.checkpoint.expected_answer} inline />
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Middle Content: Math Work Box (30% width) */}
                                <div className="lg:col-span-3">
                                    {cardLines.length > 0 && (
                                        <div className="w-full h-full bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex flex-col items-center justify-center shadow-sm overflow-hidden">
                                            <div className="text-center space-y-2 w-full overflow-x-auto">
                                                {cardLines.map((line, idx) => {
                                                    const isLastLine = idx === cardLines.length - 1;

                                                    const hasExplicitLatex = line.includes('\\');
                                                    const hasMathSymbols = line.includes('=') || line.includes('^') || line.includes('{');
                                                    // Aggressive check: If it's long (>30 chars) and NO backslash, assume Text/Mixed, even if it has math symbols.
                                                    const isLongMixed = line.length > 30 && !hasExplicitLatex;

                                                    // Heuristic: If it has spaces, treat as Text (mixed content) so we don't force-wrap in $$
                                                    // The new smart MathRenderer will inject $ for specific math symbols.
                                                    const spaceCount = (line.match(/\s/g) || []).length;
                                                    const isText = spaceCount >= 3;

                                                    // Style logic: Last line is Primary Blue Bold ONLY if it's not a text sentence
                                                    const textClass = (isLastLine && !isText)
                                                        ? "text-base font-bold text-primary" // Reduced from text-lg
                                                        : "text-[10px] text-[#111318] dark:text-white font-medium"; // Reduced from text-xs

                                                    return (
                                                        <div key={idx} className="flex flex-col items-center w-full">
                                                            <div className={`break-words whitespace-normal max-w-full px-1 ${textClass}`}>
                                                                <MathRenderer content={line} forceMath={!isText} />
                                                            </div>
                                                            {idx < cardLines.length - 1 && (
                                                                <div className="h-px w-full bg-slate-300 dark:bg-slate-700 my-2"></div>
                                                            )}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Visualizations Section (At the end) */}
            {visuals && visuals.length > 0 && (
                <div className="mt-8 space-y-8 border-t border-[#e5e7eb] dark:border-[#2a303c] pt-8">
                    <h3 className="font-bold text-xl text-[#111318] dark:text-white">Visualizations</h3>
                    {visuals.map(visual => (
                        <div key={visual.id} className="bg-white dark:bg-[#1e2634] rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] overflow-hidden p-4 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h4 className="font-bold text-sm text-[#111318] dark:text-white">
                                    <MathRenderer content={visual.title || "Graph"} inline />
                                </h4>
                                <span className="material-symbols-outlined text-primary text-[24px]">monitoring</span>
                            </div>
                            <div className="w-full h-[400px]">
                                <VisualRenderer visual={visual} height={400} />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
