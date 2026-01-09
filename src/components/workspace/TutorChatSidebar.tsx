"use client";

import React from 'react';

interface Message {
    role: string;
    content: string;
    created_at: string;
}

interface TutorChatSidebarProps {
    messages: Message[];
    tutorMode?: string;
    setTutorMode: (mode: string) => void;
}

export default function TutorChatSidebar({ messages, tutorMode = "Physics", setTutorMode }: TutorChatSidebarProps) {
    const handleModeChange = () => {
        const nextMode = tutorMode === "Physics" ? "Mathematics" : tutorMode === "Mathematics" ? "Chemistry" : "Physics";
        setTutorMode(nextMode);
    };
    return (
        <aside className="w-80 flex-shrink-0 border-r border-slate-200 dark:border-border-dark flex flex-col bg-white dark:bg-background-dark h-full">
            <div className="p-4 border-b border-slate-200 dark:border-border-dark flex justify-between items-center">
                <div className="flex items-center gap-2 text-primary dark:text-accent font-semibold">
                    <span className="material-symbols-outlined text-lg">chat_bubble</span>
                    <span>Tutor Chat</span>
                </div>
                <button className="p-1 hover:bg-slate-100 dark:hover:bg-surface-dark rounded text-xs uppercase font-bold text-slate-500">History</button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.filter(msg => typeof msg.content === 'string').map((msg, idx) => (
                    <div key={idx} className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                        {msg.role === 'assistant' && (
                            <div className="flex items-center gap-2 mb-1">
                                <div className="size-5 bg-primary/20 rounded-full flex items-center justify-center">
                                    <span className="material-symbols-outlined text-[12px] text-primary dark:text-accent">robot_2</span>
                                </div>
                                <span className="text-xs font-bold text-slate-700 dark:text-slate-300">uask AI</span>
                            </div>
                        )}
                        <div className={`p-3 rounded-xl text-sm max-w-[90%] leading-relaxed ${msg.role === 'user'
                            ? 'bg-primary text-white rounded-tr-none'
                            : 'bg-slate-100 dark:bg-surface-dark border border-slate-200 dark:border-border-dark text-slate-800 dark:text-slate-200 rounded-tl-none'
                            }`}>
                            {msg.content}
                        </div>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">
                            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                ))}
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-border-dark bg-white dark:bg-background-dark">
                <div className="relative">
                    <textarea
                        className="w-full bg-slate-50 dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-xl px-4 py-3 text-sm text-slate-900 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-1 focus:ring-primary dark:focus:ring-accent focus:border-primary dark:focus:border-accent resize-none pr-12"
                        placeholder="Ask a question..."
                        rows={3}
                    ></textarea>
                    <div className="absolute right-2 bottom-3 flex gap-1">
                        <button className="p-2 text-slate-400 hover:text-primary dark:hover:text-accent transition-colors">
                            <span className="material-symbols-outlined">photo_camera</span>
                        </button>
                        <button className="p-2 bg-primary dark:bg-accent text-white rounded-lg hover:opacity-90 transition-colors shadow-lg shadow-primary/20 dark:shadow-accent/20">
                            <span className="material-symbols-outlined text-sm">send</span>
                        </button>
                    </div>
                </div>
                <div className="mt-2 flex items-center justify-between px-1">
                    <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Tutor Mode: {tutorMode}</span>
                    <button
                        onClick={handleModeChange}
                        className="text-[10px] text-primary dark:text-accent font-bold hover:underline"
                    >
                        Change
                    </button>
                </div>
            </div>
        </aside>
    );
}
