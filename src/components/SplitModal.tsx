/**
 * Task Split Modal
 * 
 * Modal that shows detected tasks for a single question.
 * Allows user to select task subset and review workload-based credits.
 */

'use client';

import React from 'react';

interface SplitModalProps {
    /** Whether modal is open */
    isOpen: boolean;
    /** Close handler */
    onClose: () => void;
    /** Dismiss handler for top-right X button */
    onDismiss?: () => void;
    /** Original input text */
    /** Suggested split tasks */
    splits: string[];
    /** Handler when user selects a question to solve */
    onSelectQuestion: (question: string, index: number) => void;
    /** Handler when user confirms it is a single question */
    onConfirmSingleQuestion?: () => void;
    /** Handler to confirm selected questions and return to input */
    onConfirmSelectedQuestions?: (selectedQuestions: string[]) => void;
    perTaskCredits?: Record<string, number>;
    totalEstimatedCredits?: number | null;
    combinedModeMessage?: string | null;
    reconfirmMessage?: string | null;
}

export default function SplitModal({
    isOpen,
    onClose,
    onDismiss,
    splits,
    onSelectQuestion,
    onConfirmSingleQuestion,
    perTaskCredits,
    totalEstimatedCredits,
    combinedModeMessage,
    reconfirmMessage,
}: SplitModalProps) {
    const allSelectedIndexes = React.useMemo(
        () => new Set(splits.map((_, idx) => idx)),
        [splits]
    );

    const liveSelectedTaskCost = React.useMemo(() => {
        const sum = Array.from(allSelectedIndexes).reduce((acc, idx) => {
            const taskId = `t${idx + 1}`;
            return acc + Number(perTaskCredits?.[taskId] ?? 0);
        }, 0);
        return sum;
    }, [allSelectedIndexes, perTaskCredits]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div data-testid="split-modal" className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                            <span className="material-symbols-outlined text-amber-600 dark:text-amber-400">call_split</span>
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Tasks Detected</h2>
                            <p className="text-sm text-slate-500 dark:text-slate-400">Tasks are auto-included for this single question</p>
                        </div>
                    </div>
                    <button
                        onClick={onDismiss || onClose}
                        className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                    >
                        <span className="material-symbols-outlined text-slate-500">close</span>
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[60vh]">
                    {splits.length > 0 ? (
                        <>
                            <p className="text-sm text-slate-600 dark:text-slate-300 mb-4">
                                We detected {splits.length} tasks.
                            </p>
                            {reconfirmMessage && (
                                <p className="text-base font-bold text-amber-700 dark:text-amber-300 mb-4">
                                    {reconfirmMessage}
                                </p>
                            )}
                            <div className="space-y-3">
                                {splits.map((question, idx) => (
                                    <div
                                        key={idx}
                                        className="w-full text-left p-4 rounded-xl border border-slate-200 dark:border-slate-600 hover:border-primary dark:hover:border-primary hover:bg-primary/5 transition-all group"
                                    >
                                        <div className="flex items-start gap-3">
                                            <div
                                                className="mt-0.5 size-5 rounded border flex items-center justify-center shrink-0 bg-primary border-primary text-white"
                                                aria-hidden="true"
                                            >
                                                <span className="material-symbols-outlined text-sm">check</span>
                                            </div>
                                            <div className="size-7 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-sm font-bold text-slate-600 dark:text-slate-300 shrink-0 group-hover:bg-primary group-hover:text-white">
                                                {idx + 1}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm text-slate-700 dark:text-slate-200 line-clamp-3">
                                                    {question}
                                                </p>
                                            </div>
                                            <div className="px-2 py-1 text-[11px] font-bold rounded border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300">
                                                {Number(perTaskCredits?.[`t${idx + 1}`] ?? 0).toFixed(1)} cr
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => onSelectQuestion(question, idx)}
                                                className="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-primary"
                                            >
                                                Solve one
                                                <span className="material-symbols-outlined text-slate-400 group-hover:text-primary">
                                                arrow_forward
                                                </span>
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="text-center py-8">
                            <div className="size-16 rounded-2xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mx-auto mb-4">
                                <span className="material-symbols-outlined text-3xl text-amber-600 dark:text-amber-400">edit_note</span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-300 mb-2">
                                We couldn&apos;t automatically detect tasks.
                            </p>
                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                You can continue as one combined solution.
                            </p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-6 py-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                        Pricing is workload-based by detected tasks.
                    </p>
                    <div className="flex gap-3">
                        {(typeof totalEstimatedCredits === "number" || liveSelectedTaskCost > 0) && (
                            <span className="px-3 py-2 text-xs font-bold rounded-lg border border-blue-300 bg-blue-50 text-blue-700">
                                Total estimated cost: {(typeof totalEstimatedCredits === "number" ? totalEstimatedCredits : liveSelectedTaskCost).toFixed(1)} credits
                            </span>
                        )}
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={onConfirmSingleQuestion || onClose}
                            className="px-4 py-2 text-sm font-bold text-primary bg-primary/10 hover:bg-primary/20 rounded-lg transition-colors border border-primary/20"
                        >
                            Confirm and return to Solve
                        </button>
                    </div>
                </div>
                {combinedModeMessage && (
                    <div className="px-6 pb-4 text-xs text-slate-500">
                        {combinedModeMessage}
                    </div>
                )}
            </div>
        </div>
    );
}
