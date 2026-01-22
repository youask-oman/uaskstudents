"use client";

import { KeyboardEvent } from "react";

interface SegmentedControlOption {
    value: string;
    label: string;
    icon?: string;
    disabled?: boolean;
    tooltip?: string;
}

interface SegmentedControlProps {
    options: SegmentedControlOption[];
    value: string;
    onChange: (value: string) => void;
    label?: string;
    size?: "sm" | "md";
    className?: string;
}

/**
 * Accessible segmented control for binary/multi-option selection.
 * Used for Goal (Solve/Study) and Answer Style (Quick/Tutor) toggles.
 */
export default function SegmentedControl({
    options,
    value,
    onChange,
    label,
    size = "md",
    className = ""
}: SegmentedControlProps) {
    const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, option: SegmentedControlOption) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (!option.disabled) {
                onChange(option.value);
            }
        }
    };

    const sizeClasses = size === "sm"
        ? "px-3 py-1.5 text-xs"
        : "px-4 py-2 text-sm";

    return (
        <div className={`flex flex-col gap-2 ${className}`}>
            {label && (
                <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    {label}
                </label>
            )}
            <div
                className="inline-flex bg-slate-100 dark:bg-slate-800 rounded-lg p-1 gap-1"
                role="radiogroup"
                aria-label={label}
            >
                {options.map((option) => {
                    const isSelected = value === option.value;
                    const isDisabled = option.disabled;

                    return (
                        <button
                            key={option.value}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            aria-disabled={isDisabled}
                            tabIndex={isDisabled ? -1 : 0}
                            title={option.tooltip}
                            onClick={() => !isDisabled && onChange(option.value)}
                            onKeyDown={(e) => handleKeyDown(e, option)}
                            className={`
                                ${sizeClasses}
                                font-semibold rounded-md transition-all duration-200
                                flex items-center justify-center gap-1.5
                                focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900
                                ${isSelected
                                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                                    : isDisabled
                                        ? "text-slate-400 dark:text-slate-600 cursor-not-allowed"
                                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                                }
                            `}
                        >
                            {option.icon && (
                                <span className="material-symbols-outlined text-[16px]">
                                    {option.icon}
                                </span>
                            )}
                            <span>{option.label}</span>
                            {isDisabled && (
                                <span className="material-symbols-outlined text-[14px] ml-0.5">
                                    lock
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
