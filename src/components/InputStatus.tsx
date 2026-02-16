/**
 * Input Status Display Component
 * 
 * Shows live character/token counts with warnings and errors.
 * Used below the question input textbox.
 */

'use client';

import React from 'react';
import { TokenEstimate, getTokenStatus } from '@/lib/tokenEstimator';

type MultiQuestionStatus = {
    isMultiple: boolean;
    confidence: 'low' | 'medium' | 'high';
};

interface InputStatusProps {
    /** Current text in the input */
    text: string;
    /** Token estimate result */
    tokenEstimate: TokenEstimate;
    maxInputTokens: number;
    maxInputChars: number;
    /** Multi-question detection result */
    multiQuestionResult?: MultiQuestionStatus;
    /** Callback when user clicks "Split" action */
    onSplitClick?: () => void;
    /** Whether the component is in a dark container */
    darkContainer?: boolean;
    /** Whether multi-question detected has been confirmed as single */
    isConfirmed?: boolean;
}

export default function InputStatus({
    text,
    tokenEstimate,
    maxInputTokens,
    maxInputChars,
    multiQuestionResult,
    onSplitClick,
    darkContainer = false,
    isConfirmed = false,
}: InputStatusProps) {
    const charCount = text.length;
    const tokenStatus = getTokenStatus(tokenEstimate, maxInputTokens);

    // Determine colors based on status
    const getCharColor = () => {
        if (maxInputChars <= 0) return 'text-red-500';
        const pct = (charCount / maxInputChars) * 100;
        if (pct > 100) return 'text-red-500';
        if (pct > 80) return 'text-amber-500';
        return darkContainer ? 'text-slate-400' : 'text-slate-500';
    };

    const getTokenColor = () => {
        if (tokenStatus.status === 'error') return 'text-red-500';
        if (tokenStatus.status === 'warning') return 'text-amber-500';
        return darkContainer ? 'text-slate-400' : 'text-slate-500';
    };

    const showMultiQuestionWarning = !isConfirmed && multiQuestionResult?.isMultiple && multiQuestionResult.confidence !== 'low';

    return (
        <div className="flex flex-wrap items-center justify-between gap-2 mt-2 text-xs">
            {/* Left: Counters */}
            <div className="flex items-center gap-4">
                {/* Character count */}
                <span className={getCharColor()}>
                    Characters: <span className="font-mono">{charCount}</span>
                    <span className="opacity-60">/{maxInputChars}</span>
                </span>

                {/* Token estimate */}
                <span className={getTokenColor()}>
                    Tokens: <span className="font-mono">{tokenEstimate.tokens}</span>
                    <span className="opacity-60">/{maxInputTokens}</span>
                    {tokenEstimate.mode === 'mathHeavy' && (
                        <span className="ml-1 px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded text-[10px] font-medium">
                            math-heavy
                        </span>
                    )}
                </span>
            </div>

            {/* Right: Status messages */}
            <div className="flex items-center gap-2">
                {/* Token limit error */}
                {tokenStatus.status === 'error' && (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-md">
                        <span className="material-symbols-outlined text-[14px]">error</span>
                        <span>Too long</span>
                        {onSplitClick && (
                            <button
                                onClick={onSplitClick}
                                className="underline hover:no-underline font-medium ml-1"
                            >
                                Split
                            </button>
                        )}
                    </div>
                )}

                {/* Multi-question warning */}
                {showMultiQuestionWarning && tokenStatus.status !== 'error' && (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 rounded-md">
                        <span className="material-symbols-outlined text-[14px]">warning</span>
                        <span>Multiple questions detected</span>
                        {onSplitClick && (
                            <button
                                onClick={onSplitClick}
                                className="underline hover:no-underline font-medium ml-1"
                            >
                                Split
                            </button>
                        )}
                    </div>
                )}

                {/* Confirmed Single Question Badge */}
                {isConfirmed && (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-md animate-in fade-in duration-300">
                        <span className="material-symbols-outlined text-[14px]">check_circle</span>
                        <span>Confirmed one question</span>
                    </div>
                )}
            </div>
        </div>
    );
}
