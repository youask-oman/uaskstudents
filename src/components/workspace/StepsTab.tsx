"use client";

import React from 'react';
import MathRenderer from '../math/MathRendererSwitch';
import VisualRenderer, { Visual } from './VisualRenderer';

interface Checkpoint {
    question: string;
    answer?: string;           // V3 schema field
    expected_answer?: string;  // Legacy fallback
    options?: string[];
}

interface Step {
    index?: number;
    title: string;
    explanation: string;
    work?: string[];           // Legacy field
    math_latex?: string | string[];       // V3 schema field
    checkpoint?: Checkpoint;
    rules_used?: string[];
}

interface StepsTabProps {
    steps: Step[];
    visuals: Visual[];
    problemLatex?: string;
    problem?: {
        goal?: string;
        given_data?: string[];
        assumptions?: string[];
    };
    analysisPlan?: string[];
    finalAnswer?: string;
    decisionReason?: string;
    activeTab?: "steps" | "verification" | "practice";
    onSelectTab?: (tab: "steps" | "verification" | "practice") => void;
}

const ExplanationRenderer = MathRenderer;

// Helper to get math content from step
const getMathContent = (step: Step): string => {
    // Prefer math_latex (V3 schema)
    if (step.math_latex) {
        if (Array.isArray(step.math_latex)) {
            return step.math_latex.join(' \\\\ ');
        }
        return String(step.math_latex);
    }
    // Fallback to work array (legacy)
    if (step.work && Array.isArray(step.work) && step.work.length > 0) {
        return step.work.join(' \\\\ ');
    }
    return '';
};

// Helper to clean explanation text
const cleanExplanation = (text?: any): string => {
    if (!text) return "Follow the procedure on the right.";
    if (typeof text !== "string") return JSON.stringify(text);
    let cleaned = text.trim();
    if (cleaned.startsWith('$$') && cleaned.endsWith('$$')) {
        cleaned = cleaned.slice(2, -2);
    } else if (cleaned.startsWith('$') && cleaned.endsWith('$')) {
        cleaned = cleaned.slice(1, -1);
    }
    return cleaned;
};

// Get checkpoint answer with fallback
const getCheckpointAnswer = (checkpoint?: Checkpoint): string => {
    if (!checkpoint) return '';
    return checkpoint.answer || checkpoint.expected_answer || '';
};

// Format rule name for display
const formatRuleName = (rule: string): string => {
    return rule
        .replace(/_/g, ' ')
        .replace(/\b\w/g, char => char.toUpperCase());
};

// Checkpoint Interaction Component
function CheckpointInteraction({ question, answer }: { question: string; answer: string }) {
    const [isRevealed, setIsRevealed] = React.useState(false);
    const [userAnswer, setUserAnswer] = React.useState('');
    const [showInput, setShowInput] = React.useState(false);

    return (
        <div className="bg-gradient-to-br from-primary/5 to-emerald-500/5 dark:from-primary/10 dark:to-emerald-500/10 border border-primary/20 rounded-2xl p-5 transition-all shadow-lg shadow-primary/5">
            <div className="flex items-center gap-2 mb-3">
                <div className="size-8 rounded-lg bg-primary/10 dark:bg-primary/20 flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary text-[18px]">quiz</span>
                </div>
                <span className="text-xs font-bold text-primary uppercase tracking-wide">Checkpoint</span>
            </div>

            <div className="text-sm font-medium mb-4 text-slate-800 dark:text-white leading-relaxed">
                <ExplanationRenderer content={question} mode="prose" />
            </div>

            {isRevealed ? (
                <div className="animate-in fade-in zoom-in-95 duration-300">
                    <div className="px-4 py-3 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/30 dark:to-teal-900/30 border border-emerald-400/30 rounded-xl text-sm font-bold flex items-start gap-3 text-emerald-800 dark:text-emerald-300 shadow-lg shadow-emerald-500/10">
                        <div className="size-8 rounded-lg bg-emerald-500/20 flex items-center justify-center shrink-0">
                            <span className="material-symbols-outlined text-emerald-500 text-[18px]">check_circle</span>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase font-black text-emerald-600 dark:text-emerald-400 mb-1 tracking-wide">Answer</p>
                            <div className="text-emerald-800 dark:text-emerald-200">
                                <ExplanationRenderer content={answer} mode="prose" />
                            </div>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="flex flex-wrap gap-2">
                    {showInput ? (
                        <div className="flex-1 flex gap-2">
                            <input
                                type="text"
                                value={userAnswer}
                                onChange={(e) => setUserAnswer(e.target.value)}
                                placeholder="Type your answer..."
                                className="flex-1 px-4 py-2 text-sm border border-primary/30 rounded-xl bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-primary/50"
                            />
                            <button
                                onClick={() => setIsRevealed(true)}
                                className="px-4 py-2 bg-primary text-white rounded-xl text-xs font-bold hover:bg-primary/90 transition-all"
                            >
                                Check
                            </button>
                        </div>
                    ) : (
                        <>
                            <button
                                onClick={() => setShowInput(true)}
                                className="px-4 py-2 bg-white dark:bg-slate-800 border border-primary/30 rounded-xl text-xs font-bold text-primary hover:bg-primary hover:text-white hover:border-primary transition-all flex items-center gap-2 shadow-md hover:shadow-lg group"
                            >
                                <span className="material-symbols-outlined text-[16px] group-hover:scale-110 transition-transform">edit</span>
                                Try It
                            </button>
                            <button
                                onClick={() => setIsRevealed(true)}
                                className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:border-primary hover:text-primary transition-all flex items-center gap-2 shadow-md hover:shadow-lg group"
                            >
                                <span className="material-symbols-outlined text-[16px] group-hover:scale-110 transition-transform">visibility</span>
                                Reveal
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

export default function StepsTab({ steps, visuals, decisionReason }: StepsTabProps) {
    const [expandedSteps, setExpandedSteps] = React.useState<Set<number>>(new Set([0])); // First step expanded by default

    const toggleStep = (index: number) => {
        setExpandedSteps(prev => {
            const next = new Set(prev);
            if (next.has(index)) {
                next.delete(index);
            } else {
                next.add(index);
            }
            return next;
        });
    };

    const expandAll = () => {
        setExpandedSteps(new Set(steps.map((_, i) => i)));
    };

    const collapseAll = () => {
        setExpandedSteps(new Set());
    };

    return (
        <div className="flex flex-col gap-6">
            {/* Header Controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[24px]">school</span>
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">Step-by-Step Solution</h2>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={expandAll}
                        className="text-xs px-3 py-1.5 text-slate-500 hover:text-primary hover:bg-primary/5 rounded-lg transition-all"
                    >
                        Expand All
                    </button>
                    <button
                        onClick={collapseAll}
                        className="text-xs px-3 py-1.5 text-slate-500 hover:text-primary hover:bg-primary/5 rounded-lg transition-all"
                    >
                        Collapse All
                    </button>
                </div>
            </div>

            {/* Tips Banner */}
            <div className="bg-gradient-to-r from-amber-50 to-yellow-50 dark:from-amber-950/30 dark:to-yellow-950/30 rounded-2xl border border-amber-200 dark:border-amber-800/50 p-4 flex items-center gap-4 shadow-lg shadow-amber-500/5">
                <div className="size-10 rounded-xl bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center shrink-0">
                    <span className="material-symbols-outlined text-amber-600 dark:text-amber-400 text-[22px]">lightbulb</span>
                </div>
                <div className="flex-1">
                    <p className="text-xs font-bold text-amber-800 dark:text-amber-300 uppercase tracking-wide mb-0.5">Pro Tip</p>
                    <p className="text-xs text-amber-700 dark:text-amber-400/80">
                        Work through each step carefully. Use the checkpoints to test your understanding before moving on.
                    </p>
                </div>
            </div>

            {/* Steps Timeline */}
            <div className="space-y-4">
                {steps.map((step, index) => {
                    const mathContent = getMathContent(step);
                    const explanationText = cleanExplanation(step.explanation);
                    const checkpointAnswer = getCheckpointAnswer(step.checkpoint);
                    const isExpanded = expandedSteps.has(index);
                    const stepNumber = step.index || index + 1;

                    // Check if title is just "Step X" (redundant)
                    const isRedundantTitle =
                        step.title.toLowerCase() === `step ${stepNumber}` ||
                        step.title.toLowerCase() === `step ${stepNumber}:`;

                    return (
                        <div
                            key={index}
                            id={`step-${stepNumber}`}
                            className="relative scroll-mt-24"
                        >
                            {/* Step Card */}
                            <div className={`bg-white dark:bg-slate-800/80 rounded-2xl border transition-all duration-300 overflow-hidden shadow-lg hover:shadow-xl ${isExpanded
                                ? 'border-primary/30 shadow-primary/10'
                                : 'border-slate-200 dark:border-slate-700'
                                }`}>

                                {/* Step Header (Always Visible) */}
                                <button
                                    onClick={() => toggleStep(index)}
                                    className="w-full flex items-center gap-4 p-5 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                >
                                    {/* Step Number Badge */}
                                    <div className={`size-12 rounded-xl flex items-center justify-center font-black text-lg shrink-0 transition-all ${isExpanded
                                        ? 'bg-gradient-to-br from-primary to-emerald-500 text-white shadow-lg shadow-primary/30'
                                        : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                                        }`}>
                                        {stepNumber}
                                    </div>

                                    {/* Step Title */}
                                    <div className="flex-1 min-w-0">
                                        <h4 className="text-base font-bold text-slate-900 dark:text-white leading-snug">
                                            {isRedundantTitle ? (
                                                <span className="text-slate-400">Step {stepNumber}</span>
                                            ) : (
                                                <ExplanationRenderer content={step.title} mode="prose" />
                                            )}
                                        </h4>
                                        {!isExpanded && (
                                            <p className="text-xs text-slate-500 mt-1 line-clamp-1">
                                                Click to expand details
                                            </p>
                                        )}
                                    </div>

                                    {/* Expand/Collapse Icon */}
                                    <span className={`material-symbols-outlined text-[24px] text-slate-400 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''
                                        }`}>
                                        expand_more
                                    </span>
                                </button>

                                {/* Step Content (Expandable) */}
                                {isExpanded && (
                                    <div className="px-5 pb-5 pt-0 border-t border-slate-100 dark:border-slate-700 animate-in slide-in-from-top-2 duration-300">
                                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-5">

                                            {/* Left: Explanation (Equal) */}
                                            <div className="lg:col-span-1 space-y-4">
                                                {/* Explanation Text */}
                                                <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                                                    <ExplanationRenderer content={explanationText} mode="prose" />
                                                </div>

                                                {/* Rules/Properties Used */}
                                                {step.rules_used && step.rules_used.length > 0 && (
                                                    <div className="flex flex-wrap gap-2">
                                                        {step.rules_used.map((rule, rIdx) => (
                                                            <span
                                                                key={rIdx}
                                                                className="px-3 py-1.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-medium rounded-lg border border-emerald-200 dark:border-emerald-500/30"
                                                            >
                                                                📐 {formatRuleName(rule)}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}

                                                {/* Checkpoint */}
                                                {step.checkpoint && checkpointAnswer && (
                                                    <div className="mt-4">
                                                        <CheckpointInteraction
                                                            question={step.checkpoint.question}
                                                            answer={checkpointAnswer}
                                                        />
                                                    </div>
                                                )}
                                            </div>

                                            {/* Right: Math Work (Equal) */}
                                            <div className="lg:col-span-1">
                                                {mathContent && (
                                                    <div className="bg-gradient-to-br from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 p-5 rounded-xl border border-slate-200 dark:border-slate-700 shadow-inner">
                                                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Mathematical Work</p>
                                                        <div className="text-slate-900 dark:text-white font-medium">
                                                            <style>{`
                                                                .math-work-content .katex-display {
                                                                    text-align: center !important;
                                                                    margin: 1em 0 !important;
                                                                }
                                                                .math-work-content .katex {
                                                                    font-size: 1.6em;
                                                                }
                                                                .math-work-content mjx-container {
                                                                    font-size: 160% !important;
                                                                    margin: 1em auto !important;
                                                                }
                                                            `}</style>
                                                            <div className="math-work-content overflow-x-auto max-w-full">
                                                                <MathRenderer
                                                                    content={mathContent}
                                                                    mode="block"
                                                                    dynamic={true}
                                                                />
                                                            </div>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Visualizations Section */}
            {((visuals && visuals.length > 0) || decisionReason) && (
                <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
                    <div className="flex items-center gap-2 mb-6">
                        <span className="material-symbols-outlined text-primary text-[24px]">monitoring</span>
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">Visualizations</h3>
                    </div>

                    {decisionReason && (
                        <div className="mb-6 text-sm font-medium text-slate-700 dark:text-slate-300 bg-primary/5 dark:bg-primary/10 p-5 rounded-2xl border border-primary/10 dark:border-primary/20 leading-relaxed shadow-sm">
                            <div className="flex items-center gap-2 mb-2 text-primary text-[10px] font-black uppercase tracking-wider">
                                <span className="material-symbols-outlined text-[16px]">psychology</span>
                                Visualization Reasoning
                            </div>
                            “{decisionReason}”
                        </div>
                    )}

                    <div className="space-y-4">
                        {visuals.map(visual => (
                            <VisualRenderer key={visual.id} visual={visual} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
