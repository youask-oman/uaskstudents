"use client";

import React from 'react';
import katex from 'katex';

interface VerificationMethod {
    description: string;
    work: {
        latex_lines: string[];
    };
    conclusion: string;
}

interface VerificationTabProps {
    methods: VerificationMethod[];
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

export default function VerificationTab({ methods }: VerificationTabProps) {
    const [isRechecking, setIsRechecking] = React.useState(false);
    const [isConfirming, setIsConfirming] = React.useState(false);
    const [status, setStatus] = React.useState<'idle' | 'success' | 'error'>('idle');

    const handleRecheck = () => {
        setIsRechecking(true);
        setStatus('idle');
        // Simulate re-running checks
        setTimeout(() => {
            setIsRechecking(false);
            setStatus('success');
            setTimeout(() => setStatus('idle'), 3000);
        }, 2000);
    };

    const handleConfirm = () => {
        setIsConfirming(true);
        // Simulate confirmation
        setTimeout(() => {
            setIsConfirming(false);
            alert("Solution confirmed and saved to your library!");
        }, 1500);
    };

    return (
        <div className="flex-1 overflow-y-auto p-4 md:p-8 max-w-4xl mx-auto w-full space-y-6 h-full custom-scrollbar">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Automated Verification</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Cross-referencing solution logic with physical laws and mathematical consistency.</p>
                </div>
                {status === 'success' && (
                    <div className="flex items-center gap-2 bg-green-500/10 text-green-600 dark:text-green-400 px-3 py-1.5 rounded-lg border border-green-500/20 text-xs font-bold animate-in fade-in slide-in-from-top-2 duration-300">
                        <span className="material-symbols-outlined text-sm">check_circle</span>
                        All checks verified!
                    </div>
                )}
            </div>

            <div className="space-y-6">
                {methods.map((method, idx) => (
                    <div key={idx} className={`bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-border-dark overflow-hidden transition-all ${isRechecking ? 'opacity-50 scale-[0.99]' : 'hover:border-green-500/30'}`}>
                        <div className="bg-slate-50/50 dark:bg-white/5 px-6 py-4 border-b border-slate-200 dark:border-border-dark flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`size-6 rounded-full flex items-center justify-center ${isRechecking ? 'bg-slate-200 dark:bg-slate-800' : 'bg-green-500/20'}`}>
                                    <span className={`material-symbols-outlined text-sm font-bold ${isRechecking ? 'text-slate-400 animate-spin' : 'text-green-600 dark:text-green-400'}`}>
                                        {isRechecking ? 'sync' : 'check'}
                                    </span>
                                </div>
                                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">Consistency Check #{idx + 1}</h4>
                            </div>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${isRechecking
                                ? 'text-slate-400 bg-slate-100 dark:bg-slate-800/50 border-slate-200 dark:border-border-dark'
                                : 'text-green-600 dark:text-green-400 bg-green-500/10 border-green-500/20'}`}>
                                {isRechecking ? 'Verifying...' : 'Passed'}
                            </span>
                        </div>
                        <div className="p-6">
                            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 leading-relaxed">
                                {method.description}
                            </p>
                            <div className="bg-slate-50 dark:bg-surface-dark/40 p-4 rounded-lg border border-slate-100 dark:border-border-dark flex flex-col gap-3">
                                {method.work.latex_lines.map((line, lIdx) => (
                                    <div key={lIdx} className="text-primary dark:text-latex-cyan text-lg overflow-x-auto w-full">
                                        <Latex>{line}</Latex>
                                    </div>
                                ))}
                            </div>
                            <p className="text-green-700 dark:text-green-400 text-sm font-bold flex items-center gap-1 mt-4">
                                <span className="material-symbols-outlined text-sm">check_circle</span>
                                {method.conclusion}
                            </p>
                        </div>
                    </div>
                ))}

                {/* Sanity Check Warning (as seen in workspace 2) */}
                <div className={`bg-white dark:bg-card-dark rounded-xl border overflow-hidden transition-all ${isRechecking ? 'opacity-50 scale-[0.99]' : 'border-orange-200 dark:border-orange-500/20'}`}>
                    <div className="bg-orange-50/50 dark:bg-orange-500/5 px-6 py-4 border-b border-orange-100 dark:border-orange-500/10 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="size-6 rounded-full bg-orange-500/20 flex items-center justify-center">
                                <span className="material-symbols-outlined text-orange-600 dark:text-orange-400 text-sm">info</span>
                            </div>
                            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">Sanity Check</h4>
                        </div>
                        <span className="text-[10px] font-bold text-orange-600 dark:text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20">WARNING (TOLERANCE)</span>
                    </div>
                    <div className="p-6">
                        <ul className="space-y-3">
                            <li className="flex gap-3 text-sm">
                                <span className="material-symbols-outlined text-green-500 text-lg font-bold">check_circle</span>
                                <span className="text-slate-600 dark:text-slate-300"><strong>Positivity:</strong> Values calculated are within expected physical bounds (e.g., $t &gt; 0$).</span>
                            </li>
                            <li className="flex gap-3 text-sm">
                                <span className="material-symbols-outlined text-orange-500 text-lg">warning</span>
                                <span className="text-slate-500 dark:text-slate-400 italic"><strong>Note:</strong> Ideal conditions assumed. Real-world friction or resistance neglected.</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            <div className="pt-8 pb-4 flex justify-center gap-4">
                <button
                    onClick={handleRecheck}
                    disabled={isRechecking}
                    className="flex items-center gap-2 px-5 py-2.5 bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-lg text-sm font-bold text-slate-600 dark:text-slate-300 hover:text-primary dark:hover:text-white transition-all disabled:opacity-50"
                >
                    <span className={`material-symbols-outlined text-lg text-primary dark:text-accent ${isRechecking ? 'animate-spin' : ''}`}>
                        {isRechecking ? 'sync' : 'replay'}
                    </span>
                    {isRechecking ? 'Re-running...' : 'Re-run Checks'}
                </button>
                <button
                    onClick={handleConfirm}
                    disabled={isConfirming}
                    className="flex items-center gap-2 px-5 py-2.5 bg-primary dark:bg-accent text-white rounded-lg text-sm font-bold hover:opacity-90 transition-all shadow-lg shadow-primary/20 dark:shadow-accent/20 disabled:opacity-50"
                >
                    <span className={`material-symbols-outlined text-lg ${isConfirming ? 'animate-bounce' : ''}`}>
                        {isConfirming ? 'pending' : 'check_circle'}
                    </span>
                    {isConfirming ? 'Confirming...' : 'Confirm Solution'}
                </button>
            </div>
        </div>
    );
}
