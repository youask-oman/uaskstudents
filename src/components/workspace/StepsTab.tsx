"use client";

import React from 'react';
import MathRenderer from '../math/MathRendererSwitch';
import VisualRenderer, { Visual } from './VisualRenderer';

interface Checkpoint {
    question: string;
    expected_answer: string;
    options?: string[];
}

interface Step {
    title: string;
    explanation: string;
    work?: string[];
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
    activeTab?: "steps" | "verification" | "practice";
    onSelectTab?: (tab: "steps" | "verification" | "practice") => void;
}

const ExplanationRenderer = MathRenderer;

// Helper to flatten work lines
const processWorkLines = (work: string[]): string[] => {
    const splitLines: string[] = [];
    if (!work) return splitLines;

    work.forEach(line => {
        const parts = line.split('\n');
        parts.forEach(part => {
            const cleanPart = part.trim();
            if (cleanPart) {
                splitLines.push(cleanPart);
            }
        });
    });
    return splitLines;
};

// Helper to clean explanation text
const cleanExplanation = (text?: string): string => {
    if (!text) return "Follow the procedure on the right.";
    let cleaned = text.trim();
    if (cleaned.startsWith('$$') && cleaned.endsWith('$$')) {
        cleaned = cleaned.slice(2, -2);
    } else if (cleaned.startsWith('$') && cleaned.endsWith('$')) {
        cleaned = cleaned.slice(1, -1);
    }
    return cleaned;
};

// Checkpoint Interaction Component
function CheckpointInteraction({ question, answer }: { question: string, answer: string }) {
    const [isRevealed, setIsRevealed] = React.useState(false);

    return (
        <div className="bg-primary/5 dark:bg-primary/10 border border-primary/20 rounded-xl p-4 transition-all">
            <div className="flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-primary text-[16px]">quiz</span>
                <span className="text-xs font-bold text-primary uppercase">Checkpoint</span>
            </div>
                <div className="text-xs font-medium mb-3 text-[#111318] dark:text-white">
                    <ExplanationRenderer content={question} mode="prose" />
                </div>

            {isRevealed ? (
                <div className="animate-in fade-in zoom-in duration-300">
                    <div className="px-3 py-2 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-500/30 rounded-lg text-sm font-bold flex items-start gap-2 text-emerald-800 dark:text-emerald-300 shadow-sm">
                        <span className="material-symbols-outlined text-[18px] shrink-0 fill-1">check_circle</span>
                        <div>
                            <p className="text-[10px] uppercase font-black text-emerald-600 dark:text-emerald-400 mb-0.5">Answer</p>
                            <ExplanationRenderer content={answer} mode="prose" />
                        </div>
                    </div>
                </div>
            ) : (
                <button
                    onClick={() => setIsRevealed(true)}
                    className="w-full sm:w-auto px-4 py-2 bg-white dark:bg-[#1e2634] border border-primary/30 rounded-lg text-xs font-bold text-primary hover:bg-primary hover:text-white hover:border-primary transition-all flex items-center justify-center gap-2 shadow-sm active:scale-95 group"
                >
                    <span className="material-symbols-outlined text-[18px] group-hover:scale-110 transition-transform">visibility</span>
                    Reveal Answer
                </button>
            )}
        </div>
    );
}

export default function StepsTab({ steps, visuals }: StepsTabProps) {
    return (
        <div className="flex flex-col gap-8">
            {/* Global Tips */}
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
                    // Match visualization to step roughly by index if we wanted, but logic usually separate.
                    // For now displaying visuals in right column if index matches? 
                    // Wait, original design (Step 2937 Line 114) had grid-cols-10.
                    // Left 7 cols, Middle 3 cols? Math Work was Right?
                    // Original Layout: Left: Steps (70%), Middle: Math Work (30%)? 
                    // Wait, Step 2937 says:
                    // Left Content Steps lg:col-span-7
                    // Middle Content Math Work lg:col-span-3
                    // Where are visuals?
                    // Ah, visual is probably a separate step or rendered nearby.
                    // Let's check Visual rendering. Step 2848 showed visuals map.
                    // It was likely passed as a prop but rendered where?
                    // The original code rendered visuals inside step logic? 
                    // No, Step 2848 showed: `visuals.map(visual => ...)`
                    // Let's assume visuals are rendered in a separate block or aligned. 
                    // Actually, looking at the layout: StepsTab usually renders the *steps*. The visuals might be interleaved.
                    // I'll render Visuals *inside* the step if they match? 
                    // Or maybe at the bottom?
                    // Wait, Step 2848 diff shows:
                    // `{visuals.map(visual => ( ... ))}`
                    // It was inside `return ( ... )` of `StepsTab`?
                    // I'll append visuals section at the end if not specific.
                    // BUT, to be safe and cleaner, I'll stick to the layout found in Step 2937.
                    // Step layout: 
                    // <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
                    //   <div className="lg:col-span-7 ...">Title, Explanation, Checkpoint</div>
                    //   <div className="lg:col-span-3 ...">Math Work Box</div>
                    // </div>

                    return (
                        <div key={index} id={`step-${index + 1}`} className="relative pl-8 border-l-2 border-primary/20 scroll-mt-24">
                            {/* Step Dot */}
                            <div className="absolute -left-[9px] top-0 size-4 rounded-full bg-primary border-4 border-white dark:border-[#101622]"></div>

                            {/* Step Container */}
                            <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
                                {/* Left Content: Steps (60% width) */}
                                <div className="lg:col-span-6 space-y-4">
                                    <div>
                                        <div className="flex items-center gap-3 mb-2">
                                            <h4 className="text-xl font-bold text-[#111318] dark:text-white">
                                                Step {index + 1}:
                                            </h4>
                                        </div>
                                        <div className="text-lg font-bold text-[#111318] dark:text-white mb-2 leading-snug">
                                            {(() => {
                                                const title = step.title.trim();
                                                const stepNum = index + 1;
                                                // If title is just "Step X" or "Step X:", don't render it
                                                const isRedundant =
                                                    title.toLowerCase() === `step ${stepNum}` ||
                                                    title.toLowerCase() === `step ${stepNum}:`;

                                                if (isRedundant) return null;
                                                return <ExplanationRenderer content={step.title} mode="prose" />;
                                            })()}
                                        </div>
                                        <div className="text-sm font-semibold text-[#111318] dark:text-slate-300 mb-4 leading-relaxed">
                                            <ExplanationRenderer content={explanationText} mode="prose" />
                                            {step.rules_used && step.rules_used.length > 0 && (
                                                <span className="block mt-2 px-3 py-1.5 rounded-md bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 text-xs font-medium not-italic">
                                                    Using: {step.rules_used.join(", ")}
                                                </span>
                                            )}
                                        </div>

                                        {/* Checkpoint Quiz */}
                                        {step.checkpoint && step.checkpoint.expected_answer && (
                                            <CheckpointInteraction
                                                question={step.checkpoint.question}
                                                answer={step.checkpoint.expected_answer}
                                            />
                                        )}
                                    </div>
                                </div>

                                {/* Middle/Right Content: Math Work Box (40% width) */}
                                <div className="lg:col-span-4">
                                    {(() => {
                                        // Render the entire math content as a single block
                                        // Don't split - keep LaTeX environments intact
                                        const mathContent = cardLines.join('\n').trim();
                                        if (!mathContent) return null;

                                        return (
                                            <div className="w-full bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] shadow-sm">
                                                <div
                                                    className="w-full text-sm text-[#111318] dark:text-white overflow-hidden"
                                                    style={{
                                                        textAlign: 'left',
                                                        fontWeight: 'bold'
                                                    }}
                                                >
                                                    <style>{`
                                                        .math-card-content .katex-display {
                                                            text-align: left !important;
                                                            margin: 0 !important;
                                                        }
                                                        .math-card-content .katex {
                                                            font-weight: bold !important;
                                                        }
                                                    `}</style>
                                                    <div className="math-card-content">
                                                        <MathRenderer
                                                            content={mathContent}
                                                            mode="block"
                                                            dynamic={true}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>
                            </div>
                        </div>
                    );
                })}

                {/* Visualizations Section */}
                {visuals && visuals.length > 0 && (
                    <div className="mt-8 pt-8 border-t border-[#e5e7eb] dark:border-[#2a303c]">
                        <div className="flex items-center gap-2 mb-6">
                            <span className="material-symbols-outlined text-primary text-[24px]">monitoring</span>
                            <h3 className="text-xl font-bold text-[#111318] dark:text-white">Visualizations</h3>
                        </div>
                        {visuals.map(visual => (
                            <VisualRenderer key={visual.id} visual={visual} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
