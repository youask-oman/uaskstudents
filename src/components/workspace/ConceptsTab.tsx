"use client";

import React from 'react';

interface Concept {
    title: string;
    category: string;
    description: string;
    imageUrl?: string;
    tags: string[];
}

interface ConceptsTabProps {
    concepts: Concept[];
}

export default function ConceptsTab({ concepts }: ConceptsTabProps) {
    const [isHintRevealed, setIsHintRevealed] = React.useState(false);
    const [isSocratic, setIsSocratic] = React.useState(true);

    const toggleSocratic = () => setIsSocratic(!isSocratic);
    const handleReveal = () => setIsHintRevealed(true);

    return (
        <div className="flex-1 overflow-y-auto p-4 md:p-8 max-w-5xl mx-auto w-full space-y-10 h-full custom-scrollbar">
            <div className="flex items-end justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">Retrieved Concepts</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm">Fundamental principles being applied in this problem.</p>
                </div>
                <div
                    onClick={toggleSocratic}
                    className="flex items-center gap-3 bg-slate-100 dark:bg-surface-dark/50 border border-slate-200 dark:border-border-dark p-1.5 rounded-lg cursor-pointer transition-colors hover:bg-slate-200 dark:hover:bg-surface-dark"
                >
                    <span className="text-[10px] font-bold uppercase px-2 text-slate-400 dark:text-slate-500">Socratic Mode</span>
                    <div className={`w-10 h-5 border rounded-full relative transition-colors duration-300 ${isSocratic ? 'bg-primary/20 dark:bg-accent/20 border-primary/40 dark:border-accent/40' : 'bg-slate-200 dark:bg-slate-800 border-slate-300 dark:border-slate-700'}`}>
                        <div className={`absolute top-0.5 size-3.5 rounded-full shadow-sm transition-all duration-300 ${isSocratic ? 'right-0.5 bg-primary dark:bg-accent shadow-primary/50' : 'left-0.5 bg-slate-400 dark:bg-slate-600'}`}></div>
                    </div>
                </div>
            </div>

            {/* ... concepts grid ... */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {concepts.map((concept, idx) => (
                    <div key={idx} className="bg-white dark:bg-card-dark border border-slate-200 dark:border-border-dark rounded-xl overflow-hidden flex flex-col group hover:border-primary/50 dark:hover:border-accent/50 transition-all duration-300">
                        <div className="h-40 bg-slate-100 dark:bg-slate-900 relative overflow-hidden">
                            {concept.imageUrl ? (
                                <img src={concept.imageUrl} alt={concept.title} className="w-full h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity" />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center text-slate-300 dark:text-slate-800">
                                    <span className="material-symbols-outlined text-6xl">menu_book</span>
                                </div>
                            )}
                            <div className="absolute inset-0 bg-gradient-to-t from-white dark:from-card-dark to-transparent"></div>
                            <div className="absolute bottom-4 left-4">
                                <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded border backdrop-blur-sm ${idx % 2 === 0
                                    ? 'bg-primary/20 text-primary dark:text-accent border-primary/30 dark:border-accent/30'
                                    : 'bg-purple-500/20 text-purple-600 dark:text-purple-400 border-purple-500/30'
                                    }`}>
                                    {concept.category}
                                </span>
                                <h3 className="text-lg font-bold text-slate-900 dark:text-white mt-1">{concept.title}</h3>
                            </div>
                        </div>
                        <div className="p-5 flex-1 flex flex-col">
                            <div className="mb-4">
                                <h4 className="text-[10px] font-bold uppercase text-slate-400 dark:text-slate-500 tracking-wider mb-2 uppercase tracking-widest">Core Insight</h4>
                                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                                    {concept.description}
                                </p>
                            </div>
                            <div className="mt-auto flex items-center justify-between pt-4 border-t border-slate-100 dark:border-border-dark">
                                <div className="flex -space-x-2">
                                    {concept.tags.map((tag, tIdx) => (
                                        <div key={tIdx} className="size-6 rounded-full border border-white dark:border-card-dark bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-[10px] text-slate-600 dark:text-slate-300 leading-none">
                                            {tag}
                                        </div>
                                    ))}
                                </div>
                                <button className="text-xs font-bold text-primary dark:text-accent hover:underline flex items-center gap-1">
                                    Open Full Card <span className="material-symbols-outlined text-sm font-bold">arrow_forward</span>
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Hint Ladder Section */}
            <div className={`space-y-4 pt-4 transition-all duration-500 ${isSocratic ? 'opacity-100 translate-y-0' : 'opacity-40 pointer-events-none filter grayscale'}`}>
                <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary dark:text-accent font-bold">stairs</span>
                    <h2 className="text-lg font-bold text-slate-800 dark:text-white">Hint Ladder</h2>
                    <span className="text-[10px] bg-slate-100 dark:bg-surface-dark px-2 py-0.5 rounded border border-slate-200 dark:border-border-dark text-slate-500 dark:text-slate-400 uppercase font-bold tracking-tighter">Socratic Path</span>
                </div>
                <div className="space-y-3">
                    <div className="bg-slate-50/50 dark:bg-surface-dark/30 border border-slate-200 dark:border-border-dark p-4 rounded-xl flex gap-4">
                        <div className="flex flex-col items-center">
                            <div className="size-8 rounded-full bg-primary/20 dark:bg-primary text-primary dark:text-white flex items-center justify-center font-bold text-xs">1</div>
                            <div className="w-[2px] flex-1 bg-slate-200 dark:bg-border-dark mt-2"></div>
                        </div>
                        <div className="pb-2">
                            <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1">Independence of Components</h4>
                            <p className="text-sm text-slate-500 dark:text-slate-400">Remember that horizontal and vertical motions are independent. How does gravity affect horizontal movement?</p>
                        </div>
                    </div>

                    <div className="bg-white dark:bg-card-dark border border-primary/50 dark:border-accent/50 p-4 rounded-xl flex gap-4 shadow-[0_0_15px_rgba(59,130,246,0.05)]">
                        <div className="flex flex-col items-center">
                            <div className="size-8 rounded-full border-2 border-primary dark:border-accent text-primary dark:text-accent flex items-center justify-center font-bold text-xs">2</div>
                            <div className="w-[2px] flex-1 bg-slate-200 dark:bg-border-dark mt-2"></div>
                        </div>
                        <div className="flex-1 pb-2">
                            <div className="flex justify-between items-start mb-2">
                                <h4 className="text-sm font-bold text-slate-900 dark:text-white">Vertical Peak Condition</h4>
                                <span className="text-[10px] font-bold text-primary dark:text-accent animate-pulse uppercase">Revealed</span>
                            </div>
                            <p className="text-sm text-slate-600 dark:text-slate-300">At the high point of a trajectory, the vertical velocity component $v_y$ must stop increasing and briefly become exactly zero before reversing.</p>
                        </div>
                    </div>

                    <div className={`p-4 rounded-xl flex gap-4 border transition-all duration-500 ${isHintRevealed ? 'bg-white dark:bg-card-dark border-primary/50 dark:border-accent/50 shadow-lg' : 'border-dashed border-slate-300 dark:border-border-dark bg-slate-50 dark:bg-transparent'}`}>
                        <div className="flex flex-col items-center">
                            <div className={`size-8 rounded-full flex items-center justify-center font-bold text-xs transition-colors duration-500 ${isHintRevealed ? 'border-2 border-primary dark:border-accent text-primary dark:text-accent' : 'bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-500'}`}>
                                <span className="material-symbols-outlined text-sm font-bold">{isHintRevealed ? 'lightbulb' : 'lock'}</span>
                            </div>
                        </div>
                        <div className="flex-1 flex items-center justify-between">
                            <div>
                                <h4 className={`text-sm font-bold transition-colors ${isHintRevealed ? 'text-slate-900 dark:text-white' : 'text-slate-400 dark:text-slate-500'}`}>Solve for Time</h4>
                                <p className={`text-[11px] transition-colors ${isHintRevealed ? 'text-slate-600 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'}`}>
                                    {isHintRevealed ? 'Use the kinematic equation $v_y = v_0\\sin(\\theta) - gt$ at the peak.' : 'Locked until previous step is understood.'}
                                </p>
                            </div>
                            {!isHintRevealed && (
                                <button
                                    onClick={handleReveal}
                                    className="px-3 py-1.5 bg-white dark:bg-surface-dark text-xs font-bold text-slate-400 border border-slate-200 dark:border-border-dark rounded-lg hover:text-primary dark:hover:text-accent hover:border-primary/50 dark:hover:border-accent/50 transition-colors"
                                >
                                    Reveal Hint
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            <div className="pt-8 pb-4 flex justify-center gap-4">
                <button className="flex items-center gap-2 px-5 py-2.5 bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-lg text-sm font-bold text-slate-600 dark:text-slate-300 hover:text-primary dark:hover:text-white transition-all">
                    <span className="material-symbols-outlined text-lg text-primary dark:text-accent">psychology_alt</span>
                    Explain the logic
                </button>
                <button className="flex items-center gap-2 px-5 py-2.5 bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-lg text-sm font-bold text-slate-600 dark:text-slate-300 hover:text-primary dark:hover:text-white transition-all">
                    <span className="material-symbols-outlined text-lg text-primary dark:text-accent">local_library</span>
                    Full Library
                </button>
                <button className="flex items-center gap-2 px-5 py-2.5 bg-primary dark:bg-accent text-white rounded-lg text-sm font-bold hover:opacity-90 transition-all shadow-lg shadow-primary/20 dark:shadow-accent/20">
                    <span className="material-symbols-outlined text-lg">edit_note</span>
                    Take Notes
                </button>
            </div>
        </div>
    );
}
