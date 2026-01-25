/**
 * Input Mode Selector Component
 * 
 * Allows users to select the type of problem they're entering:
 * - Expression: Direct math equations
 * - Word Problem: Natural language problems
 * - Graphing: Equations to plot
 */

'use client';

import React from 'react';
import { INPUT_MODES, InputModeId, GraphingOptions, DEFAULT_GRAPHING_OPTIONS } from '@/lib/inputModes';

interface InputModeSelectorProps {
    /** Currently selected mode */
    selectedMode: InputModeId;
    /** Mode change handler */
    onModeChange: (mode: InputModeId) => void;
    /** Graphing options (only used when mode is 'graphing') */
    graphingOptions?: GraphingOptions;
    /** Graphing options change handler */
    onGraphingOptionsChange?: (options: GraphingOptions) => void;
    /** Template click handler */
    onTemplateClick?: (template: string) => void;
}

export default function InputModeSelector({
    selectedMode,
    onModeChange,
    graphingOptions = DEFAULT_GRAPHING_OPTIONS,
    onGraphingOptionsChange,
    onTemplateClick,
}: InputModeSelectorProps) {
    void graphingOptions;
    void onGraphingOptionsChange;
    const selectedModeData = INPUT_MODES.find(m => m.id === selectedMode);

    return (
        <div className="space-y-3">
            {/* Mode Tabs */}
            <div className="solve-mode-tabs flex items-center gap-1 p-1 rounded-xl">
                {INPUT_MODES.map(mode => (
                    <button
                        key={mode.id}
                        type="button"
                        onClick={() => onModeChange(mode.id)}
                        className={`solve-mode-tab flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${selectedMode === mode.id
                            ? 'is-active'
                            : ''
                            }`}
                    >
                        <span className="material-symbols-outlined text-[18px]">{mode.icon}</span>
                        <span className="hidden sm:inline">{mode.label}</span>
                    </button>
                ))}
            </div>

            {/* Mode Description */}
            <p className="text-xs text-slate-500 dark:text-slate-400 px-1">
                {selectedModeData?.description}
            </p>

            {/* Quick Templates */}
            {selectedModeData && selectedModeData.templates.length > 0 && onTemplateClick && (
                <div className="flex flex-wrap gap-2">
                    <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wide self-center mr-1">Try:</span>
                    {selectedModeData.templates.slice(0, 3).map((template, idx) => (
                        <button
                            key={idx}
                            type="button"
                            onClick={() => onTemplateClick(template)}
                        className="solve-mode-template px-3 py-1 text-xs rounded-full transition-colors truncate max-w-[200px]"
                    >
                        {template}
                    </button>
                ))}
                </div>
            )}
        </div>
    );
}
