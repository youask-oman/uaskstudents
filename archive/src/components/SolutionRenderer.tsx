
import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface SolutionRendererProps {
    data: any; // Using any for flexibility with the complex schema, or we could define the full interface
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

export default function SolutionRenderer({ data }: SolutionRendererProps) {
    if (!data || !data.problem) return <div className="p-4 text-red-500">Invalid solution data</div>;

    const { meta, problem, solution, verification, visualization } = data;

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* 1. Header & Problem Statement */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                    <span className="material-symbols-outlined text-9xl">calculate</span>
                </div>

                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-4">
                        <span className="bg-primary/10 text-primary px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
                            {meta.problem_type}
                        </span>
                        <span className="text-slate-400 text-xs font-bold uppercase tracking-wider flex items-center gap-1">
                            <span className="material-symbols-outlined text-sm">bar_chart</span>
                            {meta.difficulty_estimate}
                        </span>
                    </div>

                    <h2 className="text-2xl font-medium text-slate-500 mb-2">Goal: {problem.goal}</h2>
                    <div className="text-3xl font-black text-slate-900 dark:text-slate-100 flex items-center gap-3">
                        <Latex>{problem.latex || problem.normalized_text}</Latex>
                    </div>
                </div>
            </div>

            {/* 2. Plan Summary */}
            <div className="bg-blue-50 dark:bg-blue-900/10 rounded-xl p-5 border border-blue-100 dark:border-blue-900/20">
                <h3 className="text-blue-800 dark:text-blue-300 font-bold mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined">map</span>
                    Solution Plan
                </h3>
                <ol className="space-y-2">
                    {data.plan.map((step: any) => (
                        <li key={step.step} className="flex gap-3 text-sm text-blue-900 dark:text-blue-200">
                            <span className="font-bold text-blue-400">{step.step}.</span>
                            <span>{step.summary} <span className="opacity-50 mx-1">—</span> <span className="italic opacity-70">{step.why}</span></span>
                        </li>
                    ))}
                </ol>
            </div>

            {/* 3. Step-by-Step Solution */}
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h3 className="text-xl font-bold flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary">list_alt</span>
                        Step-by-Step Derivation
                    </h3>
                </div>

                <div className="space-y-4">
                    {solution.steps.map((step: any, idx: number) => (
                        <div key={idx} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                            <div className="px-6 py-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                                <h4 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-3">
                                    <span className="w-8 h-8 rounded-full bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 flex items-center justify-center text-sm font-black text-slate-500">
                                        {step.index}
                                    </span>
                                    {step.title}
                                </h4>
                                <span className="text-xs font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
                                    {step.step_type}
                                </span>
                            </div>

                            <div className="p-6 space-y-4">
                                <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                                    {step.explanation}
                                </p>

                                {step.math.latex_lines.length > 0 && (
                                    <div className="bg-slate-50 dark:bg-black/20 rounded-lg p-4 font-mono text-lg text-slate-800 dark:text-slate-200 border-l-4 border-primary/50 overflow-x-auto">
                                        {step.math.latex_lines.map((line: string, i: number) => (
                                            <div key={i} className="mb-2 last:mb-0">
                                                <Latex block>{line}</Latex>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {step.common_pitfalls && step.common_pitfalls.length > 0 && (
                                    <div className="mt-4 flex gap-3 text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/10 p-3 rounded-lg border border-amber-100 dark:border-amber-900/20">
                                        <span className="material-symbols-outlined text-lg">warning</span>
                                        <div>
                                            <span className="font-bold block text-xs uppercase tracking-wider mb-1">Watch out</span>
                                            {step.common_pitfalls[0]}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* 4. Final Answer Box */}
            <div className="bg-emerald-50 dark:bg-emerald-900/10 border-2 border-emerald-500/20 rounded-2xl p-8 text-center relative overflow-hidden group">
                <div className="absolute inset-0 bg-emerald-500/5 group-hover:bg-emerald-500/10 transition-colors"></div>
                <div className="relative z-10">
                    <h3 className="text-emerald-800 dark:text-emerald-400 font-bold uppercase tracking-widest text-sm mb-4">Final Answer</h3>
                    <div className="text-4xl md:text-5xl font-black text-emerald-900 dark:text-emerald-100">
                        <Latex>{solution.result.final_answer_latex || solution.result.final_answer_exact}</Latex>
                    </div>

                    {solution.result.extraneous_solutions_removed.length > 0 && (
                        <div className="mt-4 text-sm text-emerald-700 dark:text-emerald-300">
                            <span className="font-bold">Note:</span> Extraneous solution {solution.result.extraneous_solutions_removed.join(', ')} was removed.
                        </div>
                    )}
                </div>
            </div>

            {/* 5. Verification & Graph Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Verification */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6">
                    <h3 className="font-bold flex items-center gap-2 mb-4 text-slate-800 dark:text-slate-200">
                        <span className="material-symbols-outlined text-green-500">verified_user</span>
                        Verification
                    </h3>
                    {verification.methods_used.map((method: any, idx: number) => (
                        <div key={idx} className="space-y-3">
                            <p className="text-sm text-slate-500 font-medium">{method.description}</p>
                            <div className="bg-slate-50 dark:bg-black/20 rounded p-3 text-sm text-slate-700 dark:text-slate-300 font-mono">
                                {method.work.latex_lines.map((line: string, i: number) => (
                                    <div key={i}><Latex>{line}</Latex></div>
                                ))}
                            </div>
                            <p className="text-green-600 dark:text-green-400 text-sm font-bold flex items-center gap-1">
                                <span className="material-symbols-outlined text-sm">check_circle</span>
                                {method.conclusion}
                            </p>
                        </div>
                    ))}
                </div>

                {/* Graph Placeholder */}
                {visualization.included && (
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 flex flex-col">
                        <h3 className="font-bold flex items-center gap-2 mb-4 text-slate-800 dark:text-slate-200">
                            <span className="material-symbols-outlined text-purple-500">monitoring</span>
                            Visualization
                        </h3>
                        <div className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-700 relative flex items-center justify-center group overflow-hidden">
                            {/* Simple CSS Grid Line Graph Mockup */}
                            <div className="absolute inset-0 opacity-20 bg-[url('https://patterns.ibrahimcesar.cloud/bg-pattern-grid.svg')]"></div>

                            {/* Mock Curves */}
                            <svg viewBox="0 0 100 100" className="w-full h-full p-8" preserveAspectRatio="none">
                                {/* Axis */}
                                <line x1="50" y1="0" x2="50" y2="100" stroke="currentColor" strokeWidth="0.5" className="text-slate-300" />
                                <line x1="0" y1="50" x2="100" y2="50" stroke="currentColor" strokeWidth="0.5" className="text-slate-300" />

                                {/* Curve 1: Sqrt */}
                                <path d="M 10 50 Q 30 30 90 10" fill="none" stroke="#3b82f6" strokeWidth="2" />

                                {/* Curve 2: Linear */}
                                <path d="M 10 90 L 90 10" fill="none" stroke="#ef4444" strokeWidth="2" strokeDasharray="4 4" />

                                {/* Intersection Point */}
                                <circle cx="65" cy="35" r="3" className="fill-purple-600 animate-pulse" />
                            </svg>

                            <div className="absolute bottom-4 left-4 bg-white/90 dark:bg-slate-900/90 shadow rounded px-2 py-1 text-[10px] backdrop-blur">
                                {visualization.plots[0].title}
                            </div>
                        </div>
                        <p className="text-xs text-slate-500 mt-3 leading-relaxed">
                            {visualization.plots[0].interpretation}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
