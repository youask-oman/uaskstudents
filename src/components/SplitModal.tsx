/**
 * Split Questions Modal
 * 
 * Modal that shows auto-split suggestions when multiple questions are detected.
 * Allows user to select one question to solve or review the split.
 */

'use client';

import React from 'react';

interface SplitModalProps {
    /** Whether modal is open */
    isOpen: boolean;
    /** Close handler */
    onClose: () => void;
    /** Original input text */
    originalText: string;
    /** Suggested split questions */
    splits: string[];
    /** Handler when user selects a question to solve */
    onSelectQuestion: (question: string, index: number) => void;
}

export default function SplitModal({
    isOpen,
    onClose,
    originalText,
    splits,
    onSelectQuestion,
}: SplitModalProps) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                            <span className="material-symbols-outlined text-amber-600 dark:text-amber-400">call_split</span>
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Multiple Questions Detected</h2>
                            <p className="text-sm text-slate-500 dark:text-slate-400">One question at a time for best results</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
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
                                We detected {splits.length} separate questions. Select one to solve:
                            </p>
                            <div className="space-y-3">
                                {splits.map((question, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => onSelectQuestion(question, idx)}
                                        className="w-full text-left p-4 rounded-xl border border-slate-200 dark:border-slate-600 hover:border-primary dark:hover:border-primary hover:bg-primary/5 transition-all group"
                                    >
                                        <div className="flex items-start gap-3">
                                            <div className="size-7 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-sm font-bold text-slate-600 dark:text-slate-300 shrink-0 group-hover:bg-primary group-hover:text-white">
                                                {idx + 1}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm text-slate-700 dark:text-slate-200 line-clamp-3">
                                                    {question}
                                                </p>
                                            </div>
                                            <span className="material-symbols-outlined text-slate-400 group-hover:text-primary">
                                                arrow_forward
                                            </span>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="text-center py-8">
                            <div className="size-16 rounded-2xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mx-auto mb-4">
                                <span className="material-symbols-outlined text-3xl text-amber-600 dark:text-amber-400">edit_note</span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-300 mb-2">
                                We couldn't automatically split your input.
                            </p>
                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                Please manually separate your questions and solve them one at a time.
                            </p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                        Tip: Solving one question at a time gives more accurate results
                    </p>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors"
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    );
}
