"use client";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

import VisualRenderer, { Visual } from './VisualRenderer';
import WorkspaceTabs from './WorkspaceTabs';

interface V3Checkpoint {
    question: string;
    expected_answer: string;
}

interface Step {
    index: number;
    title: string;
    // V2 (Legacy)
    explanation?: string;
    math?: {
        latex_lines: string[];
    };
    visual_refs?: string[];
    // V3 (New)
    concept?: string;
    work?: string[];
    rules_used?: string[];
    result?: string;
    checkpoint?: V3Checkpoint;
}

interface StepsTabProps {
    title: string;
    steps: Step[];
    visuals?: Visual[];
    problemLatex?: string;
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
    activeTab: "steps" | "verification" | "concepts" | "practice";
    onSelectTab: (tab: StepsTabProps["activeTab"]) => void;
}

const MathFont = ({ children }: { children: React.ReactNode }) => (
    <span className="font-serif italic">{children}</span>
);

const renderInlineMath = (line: string) => {
    const regex = /[A-Za-z0-9=+\-*/^()]+/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;

    for (const match of line.matchAll(regex)) {
        const index = match.index ?? 0;
        if (index > lastIndex) {
            parts.push(line.slice(lastIndex, index));
        }
        const token = match[0];
        const isMath = /[0-9=+\-*/^()]/.test(token);
        parts.push(
            <span key={`${index}-${token}`} className={isMath ? "math-inline" : undefined}>
                {token}
            </span>
        );
        lastIndex = index + token.length;
    }

    if (lastIndex < line.length) {
        parts.push(line.slice(lastIndex));
    }

    return <p className="text-sm leading-relaxed text-gray-700 dark:text-slate-200">{parts}</p>;
};

export default function StepsTab({
    title,
    steps,
    visuals,
    problemLatex,
    problem,
    analysisPlan = [],
    finalAnswer,
    activeTab,
    onSelectTab
}: StepsTabProps) {
    const [visualHeight, setVisualHeight] = React.useState(360);
    const [isFullscreen, setIsFullscreen] = React.useState(false);

    React.useEffect(() => {
        if (!isFullscreen) return;
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = previousOverflow;
        };
    }, [isFullscreen]);

    const referencedVisualIds = new Set(
        steps.flatMap(step => step.visual_refs ?? [])
    );

    const unreferencedVisuals = (visuals ?? []).filter(
        visual => !referencedVisualIds.has(visual.id)
    );

    const clampedHeight = Math.min(Math.max(visualHeight, 240), 900);
    const renderHeight = isFullscreen ? Math.max(clampedHeight, 520) : clampedHeight;

    return (
        <div className="max-w-[800px] mx-auto flex flex-col gap-8">
            <section className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark overflow-hidden">
                <div className="p-6 border-b border-gray-50 dark:border-border-dark">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary dark:text-accent text-[10px] font-bold uppercase tracking-wide">
                            {problem?.topic || "Topic"}
                        </span>
                    </div>
                    <h1 className="text-2xl font-bold mb-1">{problem?.goal || title}</h1>
                    {(problemLatex || problem?.input) && (
                        <p className="text-xl math-font text-primary">
                            <MathFont>
                                {problemLatex || problem?.input}
                            </MathFont>
                        </p>
                    )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 divide-x divide-gray-100 dark:divide-border-dark">
                    <div className="p-4">
                        <p className="text-xs font-bold text-green-600 dark:text-green-400 uppercase mb-1">Given</p>
                        <p className="text-sm font-medium math-font">{(problem?.given_data || []).join(", ") || "N/A"}</p>
                    </div>
                    <div className="p-4">
                        <p className="text-xs font-bold text-green-600 dark:text-green-400 uppercase mb-1">Find</p>
                        <p className="text-sm font-medium">{(problem?.unknowns || []).join(", ") || "N/A"}</p>
                    </div>
                    <div className="p-4">
                        <p className="text-xs font-bold text-green-600 dark:text-green-400 uppercase mb-1">Assumptions</p>
                        <p className="text-sm font-medium italic">{(problem?.assumptions || []).join(", ") || "N/A"}</p>
                    </div>
                </div>
                <div className="px-6 py-4 bg-gray-50 dark:bg-slate-900/40">
                    <div className="flex items-center gap-2 text-sm font-bold">
                        <span className="material-symbols-outlined text-primary dark:text-accent">lightbulb</span>
                        Solution Plan
                    </div>
                    <div className="pt-3 text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                        {(analysisPlan.length > 0 ? analysisPlan : ["Identify key information", "Solve step-by-step", "Verify results"]).map((line, idx) => (
                            <div key={idx}>{idx + 1}. {line}</div>
                        ))}
                    </div>
                </div>
            </section>

            <WorkspaceTabs activeTab={activeTab} onSelectTab={onSelectTab} stepsCount={steps.length} />

            <section className="flex flex-col">
                {steps.map((step) => (
                    <div key={step.index} className="relative pl-12 pb-12">
                        <div className="absolute left-0 top-0 size-10 rounded-full bg-primary text-white flex items-center justify-center font-bold z-10">
                            {step.index}
                        </div>
                        <div className="absolute left-5 top-10 bottom-0 w-px bg-gray-200 dark:bg-slate-700"></div>
                        <div className="bg-white dark:bg-surface-dark p-6 rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark">
                            <div className="flex flex-wrap items-center gap-2 mb-4">
                                <span className="px-2 py-0.5 rounded-lg bg-gray-100 dark:bg-slate-800 text-[10px] font-bold text-gray-600 dark:text-slate-300 uppercase">
                                    {step.concept || "Step"}
                                </span>
                                <h4 className="text-sm font-bold">{step.title}</h4>
                            </div>
                            {step.work && step.work.length > 0 ? (
                                <div className="space-y-3">
                                    {step.work.map((line, idx) => (
                                        <div key={idx} className="prose max-w-none">
                                            {line.includes("$") ? (
                                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                                    {line}
                                                </ReactMarkdown>
                                            ) : (
                                                renderInlineMath(line)
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                                    {step.explanation || "No explanation provided."}
                                </div>
                            )}

                            {step.rules_used && step.rules_used.length > 0 && (
                                <div className="mt-4">
                                    <div className="flex items-center gap-2 text-xs font-bold text-primary dark:text-accent uppercase tracking-wide">
                                        Rules Used
                                    </div>
                                    <ul className="mt-2 text-xs text-gray-500 dark:text-slate-400 list-disc list-inside space-y-1">
                                        {step.rules_used.map((rule, idx) => (
                                            <li key={idx}>{rule}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {step.result && (
                                <div className="inline-flex items-center px-3 py-1.5 rounded-full bg-green-50 text-green-700 border border-green-100 dark:bg-green-900/30 dark:text-green-200 dark:border-green-900/40 text-xs font-bold mt-4">
                                    Result: {step.result}
                                </div>
                            )}

                            {step.checkpoint && (
                                <div className="p-4 bg-primary/5 border border-primary/20 dark:border-primary/30 rounded-xl mt-4">
                                    <div className="flex items-center gap-2 mb-2 text-primary dark:text-accent">
                                        <span className="material-symbols-outlined text-sm">quiz</span>
                                        <span className="text-xs font-bold uppercase">Checkpoint</span>
                                    </div>
                                    <p className="text-sm font-medium mb-3">{step.checkpoint.question}</p>
                                    <div className="grid grid-cols-1 gap-2">
                                        <button className="text-left p-2 text-xs border border-gray-200 dark:border-border-dark bg-white dark:bg-surface-dark rounded-lg hover:border-primary transition-colors">
                                            {step.checkpoint.expected_answer}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </section>

            {unreferencedVisuals.length > 0 && (
                <section className="bg-white dark:bg-surface-dark rounded-2xl shadow-sm border border-gray-100 dark:border-border-dark overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-50 dark:border-border-dark flex items-center justify-between">
                        <h4 className="text-sm font-bold flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary dark:text-accent">monitoring</span>
                            Function Visualization
                        </h4>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setVisualHeight(height => Math.min(height + 80, 900))}
                                className="p-1 rounded bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300"
                            >
                                <span className="material-symbols-outlined text-sm">zoom_in</span>
                            </button>
                            <button
                                type="button"
                                onClick={() => setVisualHeight(height => Math.max(height - 80, 240))}
                                className="p-1 rounded bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300"
                            >
                                <span className="material-symbols-outlined text-sm">zoom_out</span>
                            </button>
                            <button
                                type="button"
                                onClick={() => setIsFullscreen(value => !value)}
                                className="p-1 rounded bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300"
                            >
                                <span className="material-symbols-outlined text-sm">fullscreen</span>
                            </button>
                        </div>
                    </div>
                    <div className="p-4 bg-gray-50 dark:bg-slate-900/40">
                        {unreferencedVisuals.map(visual => (
                            <VisualRenderer key={visual.id} visual={visual} height={renderHeight} />
                        ))}
                    </div>
                </section>
            )}
            {isFullscreen && unreferencedVisuals.length > 0 && (
                <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6">
                    <div className="w-full max-w-5xl bg-white dark:bg-surface-dark rounded-2xl shadow-xl border border-gray-100 dark:border-border-dark overflow-hidden">
                        <div className="px-6 py-4 border-b border-gray-50 dark:border-border-dark flex items-center justify-between">
                            <h4 className="text-sm font-bold flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary dark:text-accent">monitoring</span>
                                Function Visualization
                            </h4>
                            <button
                                type="button"
                                onClick={() => setIsFullscreen(false)}
                                className="p-2 rounded-lg bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300"
                            >
                                <span className="material-symbols-outlined text-sm">close</span>
                            </button>
                        </div>
                        <div className="p-4 bg-gray-50 dark:bg-slate-900/40 max-h-[80vh] overflow-auto">
                            {unreferencedVisuals.map(visual => (
                                <VisualRenderer key={visual.id} visual={visual} height={renderHeight} />
                            ))}
                        </div>
                    </div>
                </div>
            )}

            <section className="bg-primary dark:bg-accent p-5 rounded-2xl text-white shadow-lg">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined bg-white/20 p-1 rounded">verified</span>
                        <span className="text-xs font-bold uppercase tracking-widest opacity-80">Final Answer</span>
                    </div>
                    <div className="flex items-center gap-2 bg-white/10 px-3 py-1 rounded-full border border-white/20">
                        <div className="size-2 rounded-full bg-green-400"></div>
                        <span className="text-[10px] font-bold">99% Confidence</span>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-[1.2fr_1fr] gap-4">
                    <div>
                        <p className="text-xl md:text-2xl font-semibold math-font">{finalAnswer || "Result ready"}</p>
                        <p className="text-xs opacity-80 mt-2">Use the final form to verify.</p>
                    </div>
                    <div className="space-y-2">
                        <div className="bg-white/10 px-3 py-2 rounded-lg text-xs border border-white/20">
                            <span className="font-bold uppercase text-[10px] tracking-wide opacity-80">Standard</span>
                            <div className="mt-1 math-font">{finalAnswer || "N/A"}</div>
                        </div>
                        <div className="bg-white/10 px-3 py-2 rounded-lg text-xs border border-white/20">
                            <span className="font-bold uppercase text-[10px] tracking-wide opacity-80">Set</span>
                            <div className="mt-1 math-font">{finalAnswer || "N/A"}</div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
