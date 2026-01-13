"use client";

import React from "react";

interface WorkspaceTabsProps {
    activeTab: "steps" | "verification" | "concepts" | "practice";
    onSelectTab: (tab: WorkspaceTabsProps["activeTab"]) => void;
    stepsCount?: number;
}

export default function WorkspaceTabs({ activeTab, onSelectTab, stepsCount = 0 }: WorkspaceTabsProps) {
    const tabs = [
        { id: "steps", label: "Steps" },
        { id: "verification", label: "Verification" },
        { id: "concepts", label: "Concepts" },
        { id: "practice", label: "Practice" }
    ] as const;

    return (
        <div className="flex items-center gap-6 border-b border-gray-200 dark:border-border-dark">
            {tabs.map(tab => {
                const isActive = activeTab === tab.id;
                return (
                    <button
                        key={tab.id}
                        onClick={() => onSelectTab(tab.id)}
                        className={`px-1 pb-3 text-sm font-medium transition-colors ${isActive
                            ? "border-b-2 border-primary text-primary dark:text-accent font-bold"
                            : "text-gray-500 hover:text-gray-800 dark:text-slate-400 dark:hover:text-slate-200"
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            {tab.label}
                            {tab.id === "steps" && stepsCount > 0 && (
                                <span className="px-1.5 py-0.5 rounded-full bg-primary/10 dark:bg-accent/20 text-[10px] font-bold">
                                    1/{stepsCount}
                                </span>
                            )}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}
