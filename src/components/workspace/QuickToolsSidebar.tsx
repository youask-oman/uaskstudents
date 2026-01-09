"use client";

import React from 'react';

interface QuickToolsSidebarProps {
    activeTool?: string;
}

export default function QuickToolsSidebar({ activeTool }: QuickToolsSidebarProps) {
    const tools = [
        { id: 'canvas', icon: 'draw', label: 'Canvas' },
        { id: 'calculator', icon: 'calculate', label: 'Calculator' },
        { id: 'reference', icon: 'book', label: 'Reference' },
    ];

    return (
        <aside className="w-14 flex-shrink-0 border-l border-slate-200 dark:border-border-dark flex flex-col items-center py-6 gap-6 bg-white dark:bg-background-dark">
            {tools.map((tool) => (
                <button
                    key={tool.id}
                    className={`group relative p-2 rounded-lg transition-colors ${activeTool === tool.id
                            ? 'bg-primary/10 dark:bg-accent/10 border border-primary/20 dark:border-accent/20 text-primary dark:text-accent'
                            : 'hover:bg-slate-100 dark:hover:bg-surface-dark text-slate-500 hover:text-primary dark:hover:text-accent'
                        }`}
                >
                    <span className="material-symbols-outlined">{tool.icon}</span>
                    <span className="absolute right-full mr-2 top-1 bg-slate-800 text-white text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap">
                        {tool.label}
                    </span>
                </button>
            ))}
            <div className="flex-1"></div>
            <button className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white transition-colors">
                <span className="material-symbols-outlined">help_outline</span>
            </button>
        </aside>
    );
}
