"use client";

import React from 'react';
import katex from 'katex';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

import VisualRenderer, { Visual } from './VisualRenderer';

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
    onViewConcepts?: () => void;
    visuals?: Visual[];
    problemLatex?: string;
}

// Math Font Component for specific styling if needed
const MathFont = ({ children }: { children: React.ReactNode }) => (
    <span className="font-serif italic">{children}</span>
);

export default function StepsTab({ title, steps, onViewConcepts, visuals, problemLatex }: StepsTabProps) {
    const handleExportPDF = () => {
        window.print();
    };
    const referencedVisualIds = new Set(
        steps.flatMap(step => step.visual_refs ?? [])
    );

    const unreferencedVisuals = (visuals ?? []).filter(
        visual => !referencedVisualIds.has(visual.id)
    );

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
            const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(shareData.text + " " + shareData.url)}`;
            window.open(whatsappUrl, '_blank');
        }
    };

    return (
        <div className="flex-1 overflow-y-auto p-4 lg:p-12 bg-off-white h-full custom-scrollbar">
            <div className="max-w-6xl mx-auto relative">
                {/* Header Section from Stitch Design */}
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-12 lg:mb-16 gap-4">
                    <div>
                        <h1 className="text-3xl lg:text-4xl font-bold tracking-tight text-navy">{title}</h1>
                        {problemLatex && (
                            <p className="text-navy/50 mt-3 font-serif italic text-xl md:text-2xl">
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                    {`$${problemLatex}$`}
                                </ReactMarkdown>
                            </p>
                        )}
                    </div>
                    <button
                        onClick={handleExportPDF}
                        className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-navy bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-all shadow-sm group"
                    >
                        <span className="material-symbols-outlined text-sm group-hover:text-electric-blue transition-colors">download</span>
                        EXPORT PDF
                    </button>
                </div>

                <div className="relative space-y-16 lg:space-y-24 pb-32">
                    {/* Timeline Line */}
                    <div className="absolute left-6 top-0 bottom-0 w-px bg-slate-200 -z-10 hidden md:block" />

                    {steps.map((step, idx) => {
                        const isV3 = Boolean(step.work || step.concept);
                        const hasSidebar = step.concept || (step.rules_used && step.rules_used.length > 0);

                        return (
                            <div key={idx} className="relative flex flex-col md:flex-row gap-8 lg:gap-12 group">
                                {/* Timeline Bubble */}
                                <div className="flex-shrink-0 relative z-10 hidden md:block">
                                    <div className="size-12 bg-electric-blue text-white rounded-full flex items-center justify-center font-bold text-xl shadow-lg ring-4 ring-off-white">
                                        {step.index}
                                    </div>
                                </div>
                                {/* Mobile Index */}
                                <div className="md:hidden flex items-center gap-3">
                                    <div className="size-8 bg-electric-blue text-white rounded-full flex items-center justify-center font-bold text-sm shadow-sm">
                                        {step.index}
                                    </div>
                                    <span className="text-sm font-bold text-navy uppercase tracking-widest">Step {step.index}</span>
                                </div>

                                <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                                    {/* Main Content Area */}
                                    <div className={`${hasSidebar ? 'lg:col-span-8' : 'lg:col-span-12'} space-y-4`}>
                                        <h4 className="text-sm font-bold text-navy/40 uppercase tracking-[0.2em] flex items-center gap-3">
                                            <span className="w-8 h-[1px] bg-navy/10 hidden md:inline-block"></span> {step.title}
                                        </h4>

                                        {/* Content Box */}
                                        <div className="bg-white rounded-2xl border border-slate-100 py-8 px-6 md:px-8 shadow-sm text-navy/80 leading-relaxed font-display">
                                            {isV3 ? (
                                                <div className="space-y-4">
                                                    {(step.work || []).map((line, i) => (
                                                        <div key={i} className="prose prose-slate max-w-none prose-p:my-2 prose-p:leading-relaxed question-content">
                                                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                                                {line}
                                                            </ReactMarkdown>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <div className="prose prose-slate max-w-none">
                                                    <p>{step.explanation || "No explanation provided."}</p>
                                                    {step.math?.latex_lines?.map((line, lIdx) => (
                                                        <div key={lIdx} className="my-4 text-center text-lg lg:text-xl text-navy font-serif">
                                                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{`$$${line}$$`}</ReactMarkdown>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}

                                            {/* Visuals */}
                                            {step.visual_refs && step.visual_refs.length > 0 && visuals && (
                                                <div className="mt-8 pt-8 border-t border-slate-50">
                                                    {step.visual_refs.map(refId => {
                                                        const vis = visuals.find(v => v.id === refId);
                                                        if (vis) return <VisualRenderer key={refId} visual={vis} />;
                                                        return null;
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Logic Sidebar (Desktop) */}
                                    {hasSidebar && (
                                        <div className="lg:col-span-4 mt-4 lg:mt-10">
                                            <div className="bg-navy rounded-2xl p-6 text-white shadow-xl">
                                                <div className="flex items-center gap-2 text-electric-blue mb-4">
                                                    <span className="material-symbols-outlined text-lg">science</span>
                                                    <span className="text-[10px] font-bold uppercase tracking-widest">Logic Sidebar</span>
                                                </div>
                                                {step.concept && (
                                                    <div className="mb-4">
                                                        <h5 className="font-bold text-sm mb-2 text-white/90">Concept Applied</h5>
                                                        <p className="text-xs text-white/60 leading-relaxed">
                                                            {step.concept}
                                                        </p>
                                                    </div>
                                                )}
                                                {step.rules_used && step.rules_used.length > 0 && (
                                                    <div>
                                                        <h5 className="font-bold text-sm mb-2 text-white/90">Rules Used</h5>
                                                        <div className="flex flex-wrap gap-2">
                                                            {step.rules_used.map((rule, ri) => (
                                                                <span key={ri} className="px-2 py-1 rounded bg-white/10 text-[10px] text-white/80 font-medium">
                                                                    {rule}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {step.checkpoint && (
                                                    <div className="mt-6 pt-4 border-t border-white/10">
                                                        <h5 className="font-bold text-sm mb-2 text-white/90">Concept Check</h5>
                                                        <p className="text-xs text-white/60 leading-relaxed italic mb-1">"{step.checkpoint.question}"</p>
                                                        <div className="flex items-center gap-2 mt-2">
                                                            <span className="material-symbols-outlined text-green-400 text-sm">check_circle</span>
                                                            <span className="text-xs font-bold text-green-400">{step.checkpoint.expected_answer}</span>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
                {unreferencedVisuals.length > 0 && (
                    <div className="mt-12 space-y-6 border-t border-slate-200 pt-12">
                        <div className="flex items-center gap-3">
                            <div className="size-10 rounded-full bg-electric-blue/10 text-electric-blue flex items-center justify-center">
                                <span className="material-symbols-outlined text-lg">insights</span>
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-navy">Visual Summary</h3>
                                <p className="text-sm text-navy/50">Rendered after the steps to match schema requirements.</p>
                            </div>
                        </div>
                        <div className="space-y-6">
                            {unreferencedVisuals.map(visual => (
                                <VisualRenderer key={visual.id} visual={visual} />
                            ))}
                        </div>
                    </div>
                )}
                {/* Footer Feedback */}
                <div className="flex flex-col md:flex-row items-center justify-center gap-8 py-12 border-t border-slate-200 mt-12 pb-24">
                    <span className="text-sm font-semibold text-navy/40 italic">Was this solution helpful?</span>
                    <div className="flex gap-4">
                        <button className="flex items-center gap-2 px-6 py-2.5 border border-slate-200 rounded-xl text-xs font-bold uppercase text-navy hover:bg-white hover:border-green-500/30 transition-all bg-white shadow-sm">
                            <span className="material-symbols-outlined text-green-500 text-lg">thumb_up</span> Helpful
                        </button>
                        <button className="flex items-center gap-2 px-6 py-2.5 border border-slate-200 rounded-xl text-xs font-bold uppercase text-navy hover:bg-white hover:border-red-500/30 transition-all bg-white shadow-sm">
                            <span className="material-symbols-outlined text-red-400 text-lg">thumb_down</span> Not quite
                        </button>
                    </div>
                </div>

                {/* Developer Debug View */}
                <div className="mt-12 pt-8 border-t border-slate-200">
                    <details>
                        <summary className="text-[10px] font-bold uppercase text-slate-400 cursor-pointer hover:text-primary transition-colors">Developer JSON View</summary>
                        <div className="mt-4 p-4 bg-slate-900 text-slate-300 rounded-xl overflow-x-auto text-[10px] font-mono leading-relaxed border border-slate-700">
                            <div className="mb-2 text-primary font-bold">RESPONSE DATA (V3):</div>
                            <pre>{JSON.stringify({ steps, visuals }, null, 2)}</pre>
                        </div>
                    </details>
                </div>
            </div>

            {/* Styles for Tailwind arbitrary overrides if config not loaded yet */}
            <style jsx global>{`
                .text-off-white { color: #FAFAFA; }
                .bg-off-white { background-color: #FAFAFA; }
                .text-navy { color: #1E293B; }
                .bg-navy { background-color: #1E293B; }
                .text-electric-blue { color: #2563EB; }
                .bg-electric-blue { background-color: #2563EB; }
                .ring-off-white { --tw-ring-color: #FAFAFA; }
            `}</style>
        </div>
    );
}
