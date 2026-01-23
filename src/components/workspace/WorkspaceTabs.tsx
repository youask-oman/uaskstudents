"use client";

import React from "react";

interface WorkspaceTabsProps {
    activeTab: "steps" | "verification" | "practice";
    onSelectTab: (tab: WorkspaceTabsProps["activeTab"]) => void;
    stepsCount?: number;
}


export default function WorkspaceTabs({ activeTab, onSelectTab, stepsCount = 0 }: WorkspaceTabsProps) {
    const tabs = [
        { id: "steps", label: "Steps", icon: "format_list_numbered" },
        { id: "verification", label: "Verification", icon: "verified_user" },
        { id: "practice", label: "Practice", icon: "fitness_center" }
    ] as const;

    return (
        <div className="w-full">
            {/* Premium Segmented Control Container */}
            <div className="flex items-center gap-1.5 p-1.5 bg-emerald-100 dark:bg-[#0f1115] rounded-xl border-2 border-emerald-200 dark:border-white/5 overflow-x-auto no-scrollbar">
                {tabs.map(tab => {
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => onSelectTab(tab.id as any)}
                            className={`
                                relative flex-1 min-w-[100px] flex items-center justify-center gap-2 py-3 px-3 rounded-lg text-sm font-bold transition-all duration-300 ease-out select-none
                                ${isActive
                                    ? "bg-white dark:bg-[#1e2634] text-primary shadow-sm shadow-slate-200/50 dark:shadow-none ring-1 ring-black/5 dark:ring-white/10 scale-[1.02]"
                                    : "bg-white/30 text-emerald-800/60 dark:bg-white/5 dark:text-slate-400 hover:bg-white/60 dark:hover:bg-white/10 hover:text-emerald-900 dark:hover:text-slate-200"
                                }
                            `}
                        >
                            {/* Icon with motion pop */}
                            <span className={`material-symbols-outlined text-[20px] transition-transform duration-300 ${isActive ? 'scale-110' : ''} ${isActive ? 'fill-1' : ''}`}>
                                {tab.icon}
                            </span>

                            <span className="whitespace-nowrap">{tab.label}</span>

                            {/* Steps Badge */}
                            {tab.id === "steps" && stepsCount > 0 && (
                                <span className={`
                                    ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-extrabold transition-colors
                                    ${isActive
                                        ? "bg-primary/10 text-primary"
                                        : "bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
                                    }
                                `}>
                                    {stepsCount}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
