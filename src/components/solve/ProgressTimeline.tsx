"use client";

import React from "react";

export type StepStatus = "pending" | "active" | "in-progress" | "completed" | "failed";

export interface TimelineStep {
    key: string;
    label: string;
    description: string;
    icon: string;
    status: StepStatus;
}

interface ProgressTimelineProps {
    steps: TimelineStep[];
    error?: {
        code?: string;
        message?: string;
    } | null;
}

export default function ProgressTimeline({ steps, error }: ProgressTimelineProps) {
    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2.5 text-[10px] sm:text-[11px] font-black tracking-[0.22em] uppercase text-slate-400 mb-8">
                <span className="material-symbols-outlined text-lg text-[#8B5CF6] motion-safe:animate-spin">autorenew</span>
                <span>System Pipeline State</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-7 sm:gap-x-10 sm:gap-y-9">
                {steps.map((stage) => {
                    const isCompleted = stage.status === "completed";
                    const isActive = stage.status === "active";
                    const isFailed = stage.status === "failed";
                    const icon = isCompleted ? "task_alt" : isFailed ? "error" : stage.icon;

                    return (
                        <div
                            key={stage.key}
                            className={`flex items-center gap-4 transition-all duration-500 ${stage.status === "pending" ? "opacity-45" : "opacity-100"}`}
                        >
                            <div className="relative flex items-center justify-center">
                                <div className={`absolute inset-0 rounded-full blur-xl transition-all duration-700 ${isCompleted ? "bg-emerald-500/30" :
                                        isActive ? "bg-[#2E5BFF]/35" :
                                            isFailed ? "bg-red-500/30" : "bg-transparent"
                                    }`} />

                                <div
                                    className={[
                                        "relative flex size-11 items-center justify-center rounded-xl border text-lg transition-all duration-500",
                                        isCompleted
                                            ? "bg-emerald-500/10 border-emerald-400/70 text-emerald-400"
                                            : isFailed
                                                ? "bg-red-500/10 border-red-400/70 text-red-400"
                                                : isActive
                                                    ? "bg-[#2E5BFF]/20 border-[#2E5BFF] text-[#4b80ff] motion-safe:animate-[uaskPulseGlow_2s_ease-in-out_infinite]"
                                                    : "bg-slate-900/70 border-white/15 text-slate-500",
                                    ].join(" ")}
                                >
                                    <span className="material-symbols-outlined">{icon}</span>
                                </div>
                            </div>
                            <div>
                                <p
                                    className={[
                                        "text-lg leading-tight transition-colors duration-500",
                                        isCompleted ? "font-semibold text-white" :
                                            isActive ? "font-bold text-[#8ab0ff]" :
                                                isFailed ? "font-bold text-red-400" : "font-medium text-slate-300",
                                    ].join(" ")}
                                >
                                    {stage.label}
                                </p>
                                <p className={`mt-1 text-xs transition-colors duration-500 ${isCompleted ? "text-slate-400" :
                                        isActive ? "text-[#7ba5ff]" :
                                            isFailed ? "text-red-300/70" : "text-slate-500"
                                    }`}>
                                    {stage.description}
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>

            {error && (
                <div className="mt-8 p-4 rounded-xl bg-red-500/10 border border-red-500/30 animate-in slide-in-from-top-2">
                    <div className="flex items-center gap-3 text-red-400 font-bold mb-1">
                        <span className="material-symbols-outlined">warning</span>
                        <span>Solve Failed {error.code ? `(${error.code})` : ''}</span>
                    </div>
                    <p className="text-sm text-red-300/80 ml-9">{error.message || "An unexpected error occurred during processing."}</p>
                </div>
            )}

            <style jsx>{`
                @keyframes uaskPulseGlow {
                    0%, 100% { filter: drop-shadow(0 0 4px rgba(46, 91, 255, 0.45)); transform: scale(1); }
                    50% { filter: drop-shadow(0 0 14px rgba(139, 92, 246, 0.78)); transform: scale(1.04); }
                }
            `}</style>
        </div>
    );
}
