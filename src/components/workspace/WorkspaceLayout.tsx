"use client";

import React, { useState, useEffect } from 'react';
import TutorChatSidebar from './TutorChatSidebar';
import QuickToolsSidebar from './QuickToolsSidebar';

interface WorkspaceLayoutProps {
    children: React.ReactNode;
    userName?: string;
    sessionTitle?: string;
    activeTab: string;
    setActiveTab: (tab: string) => void;
    messages: any[];
    tutorMode: string;
    setTutorMode: (mode: string) => void;
}

export default function WorkspaceLayout({
    children,
    userName = "Alex Chen",
    activeTab,
    setActiveTab,
    messages,
    tutorMode,
    setTutorMode
}: WorkspaceLayoutProps) {

    const [isDark, setIsDark] = useState(false);

    useEffect(() => {
        if (document.documentElement.classList.contains('dark')) {
            setIsDark(true);
        }
    }, []);

    const toggleTheme = () => {
        if (isDark) {
            document.documentElement.classList.remove('dark');
            setIsDark(false);
        } else {
            document.documentElement.classList.add('dark');
            setIsDark(true);
        }
    };

    const tabs = [
        { id: 'steps', icon: 'format_list_numbered', label: 'Steps' },
        { id: 'verification', icon: 'verified', label: 'Verification' },
        { id: 'concepts', icon: 'auto_stories', label: 'Concepts' },
        { id: 'practice', icon: 'quiz', label: 'Practice' },
    ];

    return (
        <div className="flex flex-col h-screen bg-white dark:bg-background-dark text-slate-900 dark:text-slate-100 overflow-hidden font-display transition-colors duration-300">
            {/* Workspace Header */}
            <header className="flex items-center justify-between border-b border-slate-200 dark:border-border-dark px-6 py-3 bg-white/80 dark:bg-background-dark/80 backdrop-blur-md sticky top-0 z-50">
                <div className="flex items-center gap-8">
                    <div className="flex items-center gap-3">
                        <div className="size-8 bg-primary dark:bg-accent rounded-lg flex items-center justify-center text-white shadow-[0_4px_12px_rgba(19,91,236,0.3)] dark:shadow-[0_4px_12px_rgba(14,165,233,0.3)]">
                            <span className="material-symbols-outlined font-bold">functions</span>
                        </div>
                        <h2 className="text-lg font-black leading-tight tracking-tight text-slate-900 dark:text-white uppercase text-shadow-glow">uask.ai</h2>
                    </div>
                    <nav className="hidden md:flex items-center gap-6">
                        <a className="text-sm font-bold text-slate-400 hover:text-primary dark:hover:text-white transition-colors" href="/dashboard">Dashboard</a>
                        <a className="text-sm font-bold text-primary dark:text-accent border-b-2 border-primary dark:border-accent pb-1" href="#">Workspace</a>
                        <a className="text-sm font-bold text-slate-400 hover:text-primary dark:hover:text-white transition-colors" href="#">Library</a>
                    </nav>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <button
                            onClick={toggleTheme}
                            className="p-2 lg:p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-surface-dark transition-all text-slate-400 hover:text-primary dark:hover:text-white border border-transparent hover:border-slate-200 dark:hover:border-border-dark"
                        >
                            <span className="material-symbols-outlined text-xl">{isDark ? 'light_mode' : 'dark_mode'}</span>
                        </button>
                        <button className="p-2 lg:p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-surface-dark transition-all text-slate-400 hover:text-primary dark:hover:text-white">
                            <span className="material-symbols-outlined text-xl">notifications</span>
                        </button>
                    </div>
                    <div className="h-8 w-[1px] bg-slate-200 dark:bg-border-dark mx-1"></div>
                    <div className="flex items-center gap-3">
                        <div className="bg-slate-200 dark:bg-slate-800 rounded-full size-8 border border-primary/20 flex items-center justify-center overflow-hidden">
                            <span className="material-symbols-outlined text-slate-400">person</span>
                        </div>
                        <span className="text-sm font-bold hidden sm:inline text-slate-700 dark:text-slate-200">{userName}</span>
                    </div>
                </div>
            </header>

            <main className="flex flex-1 overflow-hidden h-[calc(100vh-65px)]">
                {/* Left Sidebar: Tutor Chat */}
                <TutorChatSidebar messages={messages} tutorMode={tutorMode} setTutorMode={setTutorMode} />

                {/* Main Workspace Area */}
                <div className="flex-1 flex flex-col bg-slate-50 dark:bg-[#0d1117] overflow-hidden">
                    {/* Progress / Status Bar */}
                    <div className="px-6 py-3 border-b border-slate-200 dark:border-border-dark bg-white dark:bg-background-dark">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary dark:bg-accent opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary dark:bg-accent"></span>
                                </span>
                                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">Solution Ready</h3>
                            </div>
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Optimized for Accuracy</span>
                        </div>
                        <div className="w-full h-1 bg-slate-100 dark:bg-surface-dark rounded-full overflow-hidden">
                            <div className="bg-primary dark:bg-accent h-full rounded-full transition-all duration-500 shadow-[0_0_8px_rgba(19,91,236,0.5)] dark:shadow-[0_0_8px_rgba(14,165,233,0.5)]" style={{ width: '100%' }}></div>
                        </div>
                    </div>

                    {/* Content Tabs */}
                    <div className="bg-white dark:bg-background-dark px-6 border-b border-slate-200 dark:border-border-dark">
                        <div className="flex gap-8">
                            {tabs.map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-2 py-4 border-b-2 text-sm font-black transition-all ${activeTab === tab.id
                                        ? 'border-primary dark:border-accent text-primary dark:text-accent'
                                        : 'border-transparent text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
                                        }`}
                                >
                                    <span className="material-symbols-outlined text-lg">{tab.icon}</span>
                                    {tab.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Active Content */}
                    <div className="flex-1 overflow-hidden relative">
                        {children}
                    </div>
                </div>

                {/* Right Sidebar: Tools */}
                <QuickToolsSidebar />
            </main>
        </div>
    );
}
