"use client";

import React from 'react';
import katex from 'katex';

import VisualRenderer, { Visual } from './VisualRenderer';

interface Step {
    index: number;
    title: string;
    explanation: string;
    math: {
        latex_lines: string[];
    };
    visual_refs?: string[];
}

interface StepsTabProps {
    title: string;
    steps: Step[];
    onViewConcepts?: () => void;
    visuals?: Visual[];
}

const Latex = ({ children, block = false }: { children: string; block?: boolean }) => {
    try {
        const html = katex.renderToString(children, {
            throwOnError: false,
            displayMode: block
        });
        return <span dangerouslySetInnerHTML={{ __html: html }} />;
    } catch (e) {
        return <span>{children}</span>;
    }
};

export default function StepsTab({ title, steps, onViewConcepts, visuals }: StepsTabProps) {
    const handleExportPDF = () => {
        window.print();
    };

    const handleShare = async () => {
        const shareData = {
            title: `uask.ai Solution: ${title}`,
            text: `Check out this step-by-step solution for: ${title}`,
            url: window.location.href,
        };

        if (navigator.share) {
            try {
                await navigator.share(shareData);
            } catch (err) {
                console.error("Error sharing:", err);
            }
        } else {
            // Fallback for WhatsApp
            const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(shareData.text + " " + shareData.url)}`;
            window.open(whatsappUrl, '_blank');
        }
    };

    return (
        <div className="flex-1 overflow-y-auto p-4 md:p-8 max-w-4xl mx-auto w-full space-y-8 h-full custom-scrollbar print:p-0">
            <div className="flex items-center justify-between print:hidden">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">{title}</h1>
                <div className="flex gap-2">
                    <button
                        onClick={handleExportPDF}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold border border-slate-200 dark:border-border-dark rounded-lg hover:bg-slate-50 dark:hover:bg-surface-dark transition-colors text-slate-600 dark:text-slate-300"
                    >
                        <span className="material-symbols-outlined text-sm">download</span>
                        Export PDF
                    </button>
                    <button
                        onClick={handleShare}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold bg-primary dark:bg-accent text-white rounded-lg hover:opacity-90 transition-colors shadow-lg shadow-primary/20 dark:shadow-accent/20"
                    >
                        <span className="material-symbols-outlined text-sm">share</span>
                        Share
                    </button>
                </div>
            </div>

            {/* Print Header (Only visible when printing) */}
            <div className="hidden print:block mb-8 border-b-2 border-slate-900 pb-4">
                <h1 className="text-2xl font-bold mb-2">uask.ai Solution</h1>
                <h2 className="text-lg text-slate-600">{title}</h2>
            </div>

            <div className="space-y-6">
                {steps.map((step, idx) => (
                    <div key={idx} className="bg-white dark:bg-card-dark rounded-xl shadow-sm border border-slate-200 dark:border-border-dark overflow-hidden transition-all hover:border-primary/30 dark:hover:border-accent/30">
                        <div className="bg-slate-50/50 dark:bg-white/5 px-6 py-3 border-b border-slate-200 dark:border-border-dark flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <span className="flex items-center justify-center size-6 bg-primary dark:bg-accent text-white text-xs font-bold rounded shadow-sm shadow-primary/30 dark:shadow-accent/30">
                                    {step.index}
                                </span>
                                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">{step.title}</h4>
                            </div>
                            <button className="text-primary dark:text-accent hover:opacity-80 transition-colors">
                                <span className="material-symbols-outlined text-lg">info</span>
                            </button>
                        </div>
                        <div className="p-6">
                            <p className="text-sm text-slate-600 dark:text-slate-300 mb-4 leading-relaxed">
                                {step.explanation || (step as any).content || "No detailed explanation provided."}
                            </p>
                            {step.math?.latex_lines && step.math.latex_lines.length > 0 && (
                                <div className="bg-slate-50 dark:bg-surface-dark/40 p-6 rounded-lg flex flex-col items-center gap-4 border border-slate-100 dark:border-border-dark">
                                    <div className="text-lg md:text-xl text-primary dark:text-latex-cyan overflow-x-auto w-full text-center py-2">
                                        {step.math.latex_lines.map((line, lIdx) => (
                                            <div key={lIdx} className="mb-2 last:mb-0">
                                                <Latex block>{line}</Latex>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {step.visual_refs && step.visual_refs.length > 0 && visuals && (
                                <div className="mt-4">
                                    {step.visual_refs.map(refId => {
                                        const vis = visuals.find(v => v.id === refId);
                                        if (vis) return <VisualRenderer key={refId} visual={vis} />;
                                        return null;
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* AI Thought Bridge */}
            <div
                onClick={onViewConcepts}
                className="flex items-center gap-4 p-5 border border-dashed border-slate-300 dark:border-border-dark rounded-xl bg-slate-50 dark:bg-surface-dark/20 hover:border-primary/50 dark:hover:border-accent/50 transition-colors cursor-pointer group"
            >
                <div className="size-12 rounded-lg bg-white dark:bg-card-dark flex items-center justify-center border border-slate-200 dark:border-border-dark shadow-sm group-hover:border-primary dark:group-hover:border-accent transition-colors">
                    <span className="material-symbols-outlined text-primary dark:text-accent text-2xl">lightbulb</span>
                </div>
                <div className="flex-1">
                    <h5 className="text-[10px] font-bold uppercase text-slate-500 mb-1 tracking-[0.1em]">Related Concept Retrieval</h5>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">Kinematic Equations for Constant Acceleration</p>
                </div>
                <button
                    onClick={(e) => { e.stopPropagation(); onViewConcepts?.(); }}
                    className="px-3 py-1.5 bg-white dark:bg-surface-dark text-slate-700 dark:text-white rounded-lg text-xs font-bold border border-slate-200 dark:border-border-dark hover:border-primary dark:hover:border-accent transition-colors"
                >
                    View Card
                </button>
            </div>
        </div>
    );
}
