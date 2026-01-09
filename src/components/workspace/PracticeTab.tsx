"use client";

import React from 'react';
import katex from 'katex';

interface Problem {
    title: string;
    description: string;
    latex?: string;
    difficulty: 'Similar' | 'Step Up' | 'Challenge';
    xp: number;
}

interface PracticeTabProps {
    problems: Problem[];
    progress: number;
    level: string;
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

export default function PracticeTab({ problems, progress, level }: PracticeTabProps) {
    return (
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8 h-full custom-scrollbar">
            <div className="max-w-4xl mx-auto space-y-8">
                {/* Stats Header */}
                <div className="bg-slate-50 dark:bg-card-dark rounded-2xl p-6 border border-slate-200 dark:border-border-dark overflow-hidden relative">
                    <div className="flex items-center justify-between mb-4 relative z-10">
                        <div>
                            <h1 className="text-xl font-black text-slate-900 dark:text-white mb-1">Mastery Progress</h1>
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Topic: Kinematics 2D</p>
                        </div>
                        <div className="text-right">
                            <span className={`text-3xl font-black ${progress >= 60 ? 'text-green-500' : 'text-primary'
                                }`}>{progress}%</span>
                            <p className="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest">{level}</p>
                        </div>
                    </div>
                    <div className="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden flex relative z-10">
                        <div
                            className="bg-gradient-to-r from-primary to-green-500 h-full rounded-full shadow-[0_0_10px_rgba(34,197,94,0.3)] transition-all duration-1000"
                            style={{ width: `${progress}%` }}
                        ></div>
                    </div>
                    <div className="absolute top-0 right-0 p-2 opacity-5 scale-150">
                        <span className="material-symbols-outlined text-9xl">school</span>
                    </div>
                </div>

                <div className="space-y-6">
                    <h2 className="text-lg font-black text-slate-800 dark:text-slate-200 uppercase tracking-wider">Recommended Problems</h2>

                    <div className="grid gap-4">
                        {problems.map((problem, idx) => (
                            <div key={idx} className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-xl transition-all duration-300 hover:border-primary/50 dark:hover:border-accent/50 group">
                                <div className="p-6">
                                    <div className="flex justify-between items-start mb-4">
                                        <div className="flex items-center gap-3">
                                            <span className={`text-[10px] font-black px-2 py-0.5 rounded uppercase tracking-wider border ${problem.difficulty === 'Similar'
                                                    ? 'bg-green-100 dark:bg-green-500/10 text-green-600 dark:text-green-400 border-green-200 dark:border-green-500/20'
                                                    : problem.difficulty === 'Step Up'
                                                        ? 'bg-blue-100 dark:bg-primary/10 text-blue-600 dark:text-primary border-blue-200 dark:border-primary/20'
                                                        : 'bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-200 dark:border-orange-500/20'
                                                }`}>
                                                {problem.difficulty}
                                            </span>
                                            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-black uppercase tracking-widest">+{problem.xp} XP</span>
                                        </div>
                                        <button className="text-slate-300 dark:text-slate-600 hover:text-slate-900 dark:hover:text-white transition-colors"><span className="material-symbols-outlined">more_vert</span></button>
                                    </div>
                                    <h3 className="text-slate-800 dark:text-slate-200 font-bold mb-3">{problem.title}</h3>
                                    <p className="text-slate-500 dark:text-slate-400 text-sm mb-4 leading-relaxed">
                                        {problem.description}
                                    </p>
                                    {problem.latex && (
                                        <div className="bg-slate-50 dark:bg-black/20 p-4 rounded-lg border border-slate-100 dark:border-white/5 mb-4 flex justify-center text-primary dark:text-latex-cyan text-lg">
                                            <Latex>{problem.latex}</Latex>
                                        </div>
                                    )}
                                    <button className={`w-full py-2.5 rounded-lg text-sm font-black transition-all ${problem.difficulty === 'Challenge'
                                            ? 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/30 hover:bg-orange-600 hover:text-white'
                                            : 'bg-primary/10 border border-primary/30 text-primary rounded-lg hover:bg-primary hover:text-white'
                                        }`}>
                                        Start {problem.difficulty === 'Challenge' ? 'Challenge' : 'Problem'}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="pt-8 pb-12 flex flex-col items-center gap-4">
                        <div className="h-px w-full bg-slate-200 dark:bg-border-dark"></div>
                        <p className="text-xs text-slate-400 dark:text-slate-500 text-center max-w-sm">
                            Generate a custom set tailored to your weak points in this topic.
                        </p>
                        <button className="group flex items-center gap-3 px-8 py-4 bg-primary dark:bg-accent text-white rounded-xl font-black hover:scale-[1.02] transition-all shadow-[0_10px_30px_rgba(19,91,236,0.3)] dark:shadow-[0_10px_30px_rgba(14,165,233,0.3)]">
                            <span className="material-symbols-outlined font-bold">auto_awesome</span>
                            Generate AI Practice Set
                            <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform font-bold">arrow_forward</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
