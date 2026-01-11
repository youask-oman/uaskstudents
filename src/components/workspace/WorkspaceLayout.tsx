"use client";

import React, { useState, useEffect } from 'react';
import TutorChatSidebar from './TutorChatSidebar';
import QuickToolsSidebar from './QuickToolsSidebar';

interface WorkspaceLayoutProps {
    children: React.ReactNode;
    userName?: string;
    sessionTitle?: string;
    problemLatex?: string; // New prop for formula
    activeTab: string;
    setActiveTab: (tab: string) => void;
    messages: any[];
    tutorMode: string;
    setTutorMode: (mode: string) => void;
    onSendMessage: (query: string) => Promise<void>;
    isSaved?: boolean; // New prop for save state
    onSave?: () => void; // New prop for save action
    modelUsed?: string | null;
    tokensUsed?: number | null;
}

export default function WorkspaceLayout({
    children,
    userName = "Alex Chen",
    sessionTitle,
    problemLatex,
    activeTab,
    setActiveTab,
    messages,
    tutorMode,
    setTutorMode,
    onSendMessage,
    isSaved = false,
    onSave,
    modelUsed,
    tokensUsed
}: WorkspaceLayoutProps) {

    const [isDark, setIsDark] = useState(false);
    const [tokenUsage, setTokenUsage] = useState<{ used: number; limit: number } | null>(null);

    useEffect(() => {
        if (document.documentElement.classList.contains('dark')) {
            setIsDark(true);
        }

        // Fetch User Token Usage
        const fetchTokens = async () => {
            try {
                const userId = localStorage.getItem("user_id") || "1";
                const res = await fetch(`http://127.0.0.1:8000/api/v1/user/token-usage?user_id=${userId}`);
                if (res.ok) {
                    const data = await res.json();
                    setTokenUsage({ used: data.tokens_used, limit: data.tokens_limit });
                }
            } catch (error) {
                console.error("Failed to fetch token usage", error);
            }
        };

        fetchTokens();
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
                        <img src={isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" className="h-8 w-auto" />
                        <h2 className="hidden md:block text-lg font-black leading-tight tracking-tight text-slate-900 dark:text-white uppercase text-shadow-glow">uask.ai</h2>
                    </div>
                    {/* Formula Display in Header */}
                    <div className="hidden lg:flex items-center bg-slate-100 dark:bg-surface-dark px-4 py-1.5 rounded-full border border-slate-200 dark:border-border-dark">
                        <span className="text-xs font-bold text-slate-500 mr-2 uppercase tracking-wider">Solving:</span>
                        <span className="font-mono text-sm font-semibold text-primary dark:text-accent">
                            {problemLatex || sessionTitle || "New Problem"}
                        </span>
                    </div>

                    <nav className="hidden md:flex items-center gap-6">
                        <a className="text-sm font-bold text-slate-400 hover:text-primary dark:hover:text-white transition-colors" href="/dashboard">Dashboard</a>
                        <a className="text-sm font-bold text-primary dark:text-accent border-b-2 border-primary dark:border-accent pb-1" href="#">Workspace</a>
                    </nav>
                </div>
                <div className="flex items-center gap-4">
                    {/* Token Usage Indicator */}
                    {tokenUsage && (
                        <div className="hidden md:flex items-center gap-2 bg-slate-50 dark:bg-surface-dark px-3 py-1.5 rounded-lg border border-slate-100 dark:border-border-dark" title="Monthly Token Usage">
                            <div className="flex flex-col items-end">
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Monthly Limit</span>
                                <span className={`text-xs font-bold ${tokenUsage.used > tokenUsage.limit * 0.9 ? 'text-red-500' : 'text-slate-700 dark:text-slate-300'}`}>
                                    {(tokenUsage.used / 1000).toFixed(1)}k / {(tokenUsage.limit / 1000).toFixed(0)}k
                                </span>
                            </div>
                            <div className="w-8 h-8 relative flex items-center justify-center">
                                <svg className="w-full h-full transform -rotate-90">
                                    <circle
                                        cx="16"
                                        cy="16"
                                        r="12"
                                        stroke="currentColor"
                                        strokeWidth="3"
                                        fill="transparent"
                                        className="text-slate-200 dark:text-slate-700"
                                    />
                                    <circle
                                        cx="16"
                                        cy="16"
                                        r="12"
                                        stroke="currentColor"
                                        strokeWidth="3"
                                        fill="transparent"
                                        strokeDasharray={2 * Math.PI * 12}
                                        strokeDashoffset={2 * Math.PI * 12 * (1 - tokenUsage.used / tokenUsage.limit)}
                                        className={tokenUsage.used > tokenUsage.limit * 0.9 ? 'text-red-500' : 'text-primary dark:text-accent'}
                                    />
                                </svg>
                                <span className="material-symbols-outlined text-[14px] absolute text-slate-400">offline_bolt</span>
                            </div>
                        </div>
                    )}

                    <div className="flex items-center gap-2">
                        {/* Save Button */}
                        {onSave && (
                            <button
                                onClick={onSave}
                                disabled={isSaved}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${isSaved
                                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 cursor-default'
                                    : 'bg-primary/10 text-primary hover:bg-primary hover:text-white dark:bg-accent/10 dark:text-accent dark:hover:bg-accent dark:hover:text-white'
                                    }`}
                            >
                                <span className="material-symbols-outlined text-sm">
                                    {isSaved ? 'check_circle' : 'bookmark'}
                                </span>
                                {isSaved ? 'Saved' : 'Save Solution'}
                            </button>
                        )}

                        <button
                            onClick={toggleTheme}
                            className="p-2 lg:p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-surface-dark transition-all text-slate-400 hover:text-primary dark:hover:text-white border border-transparent hover:border-slate-200 dark:hover:border-border-dark"
                        >
                            <span className="material-symbols-outlined text-xl">{isDark ? 'light_mode' : 'dark_mode'}</span>
                        </button>
                    </div>
                    <div className="h-8 w-[1px] bg-slate-200 dark:bg-border-dark mx-1"></div>

                    {/* Profile Link */}
                    <a href="/dashboard" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
                        <div className="bg-slate-200 dark:bg-slate-800 rounded-full size-8 border border-primary/20 flex items-center justify-center overflow-hidden">
                            <span className="material-symbols-outlined text-slate-400">person</span>
                        </div>
                        <span className="text-sm font-bold hidden sm:inline text-slate-700 dark:text-slate-200">{userName}</span>
                    </a>
                </div>
            </header>

            <main className="flex flex-1 overflow-hidden h-[calc(100vh-65px)]">
                {/* Left Sidebar: Tutor Chat */}
                <TutorChatSidebar
                    messages={messages}
                    tutorMode={tutorMode}
                    setTutorMode={setTutorMode}
                    onSendMessage={onSendMessage}
                />

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
                            <div className="flex items-center gap-3">
                                {modelUsed && (
                                    <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-surface-dark px-2 py-0.5 rounded border border-slate-200 dark:border-border-dark">
                                        <span className="material-symbols-outlined text-[12px] text-primary dark:text-accent">smart_toy</span>
                                        <span className="text-[10px] font-black text-slate-600 dark:text-slate-300 uppercase tracking-tight">{modelUsed}</span>
                                    </div>
                                )}
                                {tokensUsed !== null && tokensUsed !== undefined && (
                                    <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-surface-dark px-2 py-0.5 rounded border border-slate-200 dark:border-border-dark">
                                        <span className="material-symbols-outlined text-[12px] text-amber-500">toll</span>
                                        <span className="text-[10px] font-black text-slate-600 dark:text-slate-300 uppercase tracking-tight">{(tokensUsed ?? 0).toLocaleString()} Tokens</span>
                                    </div>
                                )}
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">by uask AI</span>
                            </div>
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
