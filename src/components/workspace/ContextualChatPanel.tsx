"use client";

import React, { useState, useRef, useEffect } from 'react';
import MathRenderer from '../math/MathRendererSwitch';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface ContextualChatPanelProps {
    sessionId: string | number;
    originalProblem: string;
    finalAnswer?: string;
    steps?: Array<{ title: string; index: number }>;
    classification?: {
        domain?: string;
        topic?: string;
    };
    disabled?: boolean;
}

export default function ContextualChatPanel({
    sessionId,
    originalProblem,
    steps = [],
    classification,
    disabled = false
}: ContextualChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: "👋 Hi! I'm here to help you understand this solution better. Ask me anything about the problem or the steps!",
            timestamp: new Date()
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Generate context-aware suggested prompts
    const suggestedPrompts = React.useMemo(() => {
        const prompts: string[] = [
            "Can you explain this in simpler terms?",
            "What's another way to solve this?",
        ];

        if (steps.length > 0) {
            prompts.push(`Why did we "${steps[0].title}"?`);
        }
        if (steps.length > 1) {
            prompts.push(`Explain step ${steps.length} more`);
        }

        return prompts.slice(0, 4);
    }, [steps]);

    const sendMessage = async () => {
        if (!input.trim() || loading || disabled) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim(),
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const response = await fetch(`/api/v1/sessions/${sessionId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMessage.content,
                    context: {
                        original_problem: originalProblem,
                        classification: classification
                    }
                })
            });

            if (!response.ok) throw new Error('Chat request failed');

            const data = await response.json();

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.response || data.message || "I'm sorry, I couldn't process that request.",
                timestamp: new Date()
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Chat error:', error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: "Sorry, I encountered an error. Please try again.",
                timestamp: new Date()
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="h-full flex flex-col bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-950">
            {/* Header */}
            <div className="p-4 border-b border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm">
                <div className="flex items-center gap-3">
                    <div className="size-10 rounded-xl bg-gradient-to-br from-primary to-emerald-500 flex items-center justify-center shadow-lg shadow-primary/20">
                        <span className="material-symbols-outlined text-white text-[20px]">smart_toy</span>
                    </div>
                    <div>
                        <h3 className="font-bold text-sm text-slate-900 dark:text-white">AI Tutor</h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            Ask about: {classification?.topic || 'this solution'}
                        </p>
                    </div>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div
                            className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.role === 'user'
                                ? 'bg-gradient-to-r from-primary to-emerald-500 text-white rounded-br-md shadow-lg shadow-primary/20'
                                : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-bl-md shadow-sm'
                                }`}
                        >
                            <MathRenderer content={msg.content} mode="prose" />
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm">
                            <div className="flex items-center gap-2">
                                <div className="flex gap-1">
                                    <span className="size-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                    <span className="size-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                    <span className="size-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                                </div>
                                <span className="text-xs text-slate-500">Thinking...</span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Suggested Prompts */}
            {messages.length <= 2 && (
                <div className="px-4 pb-3">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Try asking:</p>
                    <div className="flex flex-wrap gap-2">
                        {suggestedPrompts.map((prompt, i) => (
                            <button
                                key={i}
                                onClick={() => setInput(prompt)}
                                disabled={disabled || loading}
                                className="text-xs px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full hover:border-primary hover:text-primary transition-all duration-200 text-slate-600 dark:text-slate-300 shadow-sm hover:shadow-md disabled:opacity-50"
                            >
                                {prompt}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Input Area */}
            <div className="p-4 border-t border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm">
                <div className="flex gap-2 items-end">
                    <div className="flex-1 relative">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyPress}
                            placeholder="Ask a question about this problem..."
                            rows={1}
                            disabled={disabled || loading}
                            className="w-full px-4 py-3 text-sm border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all resize-none disabled:opacity-50"
                            style={{ minHeight: '44px', maxHeight: '120px' }}
                        />
                    </div>
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || loading || disabled}
                        className="size-11 flex items-center justify-center bg-gradient-to-r from-primary to-emerald-500 text-white rounded-xl shadow-lg shadow-primary/30 hover:shadow-xl hover:shadow-primary/40 hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:scale-100 disabled:shadow-none"
                    >
                        <span className="material-symbols-outlined text-[20px]">
                            {loading ? 'hourglass_empty' : 'send'}
                        </span>
                    </button>
                </div>
                <p className="text-[10px] text-slate-400 mt-2 text-center">
                    Responses are AI-generated. Verify important information.
                </p>
            </div>
        </div>
    );
}
