"use client";

import React from "react";
import MathRenderer from "./math/MathRendererSwitch";

interface LiveMathPreviewProps {
    /** The LaTeX or math content to render */
    content: string;
    /** Whether to hide the preview if content is empty */
    hideIfEmpty?: boolean;
}

export default function LiveMathPreview({ content, hideIfEmpty = true }: LiveMathPreviewProps) {
    if (hideIfEmpty && !content.trim()) return null;

    return (
        <div className="bg-yellow-50 dark:bg-slate-900 rounded-xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)] border border-yellow-100 dark:border-slate-800 overflow-hidden w-full transition-all duration-300 animate-in fade-in slide-in-from-top-4" suppressHydrationWarning>
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-yellow-100/50 dark:border-slate-800/50">
                <div className="flex items-center gap-3">
                    <div className="size-8 rounded-lg bg-yellow-100/50 dark:bg-blue-900/20 flex items-center justify-center text-yellow-600 dark:text-blue-400 font-serif font-bold text-lg">
                        S
                    </div>
                    <span className="font-bold text-slate-800 dark:text-slate-200">Live Math Preview</span>
                </div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                    LaTeX Engine v2.4
                </div>
            </div>

            {/* Content Area */}
            <div className="p-8 flex items-center justify-center min-h-[120px] bg-yellow-50 dark:bg-slate-900">
                <div className="text-xl text-red-600 dark:text-red-400 leading-relaxed">
                    <MathRenderer content={content} mode="block" />
                </div>
            </div>
        </div>
    );
}
