"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import DashboardNavBar from "@/components/DashboardNavBar";
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import SolutionRenderer from "@/components/SolutionRenderer"; // IMPORT THE RENDERER
import { DEMO_SOLUTION } from "@/lib/mock-response"; // IMPORT DEMO DATA

interface ChatMessage {
    role: string;
    content: string | any; // Allow content to be object for JSON
    media_url?: string;
    created_at: string;
    type?: 'text' | 'solution_json'; // Discriminator
}

interface ChatSession {
    id: number | string;
    title: string;
    subject?: string;
    created_at: string;
    messages: ChatMessage[];
}

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const [session, setSession] = useState<ChatSession | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSession = async () => {
            // MOCK HANDLER FOR DEMO
            if (id === 'demo-1') {
                setTimeout(() => {
                    setSession({
                        id: 'demo-1',
                        title: "Solving Radical Equation",
                        subject: "Algebra",
                        created_at: new Date().toISOString(),
                        messages: [
                            {
                                role: 'user',
                                content: "Solve over reals: sqrt(x+5) = x - 1",
                                created_at: new Date().toISOString(),
                                type: 'text'
                            },
                            {
                                role: 'assistant',
                                content: DEMO_SOLUTION, // Inject the strict JSON object
                                created_at: new Date().toISOString(),
                                type: 'solution_json'
                            }
                        ]
                    });
                    setLoading(false);
                }, 500);
                return;
            }

            try {
                const res = await fetch(`http://localhost:8000/api/v1/sessions/${id}`);
                if (res.ok) {
                    const data = await res.json();
                    setSession(data);
                } else {
                    console.error("Failed to fetch session");
                }
            } catch (error) {
                console.error("Error fetching session:", error);
            } finally {
                setLoading(false);
            }
        };

        if (id) {
            fetchSession();
        }
    }, [id]);

    if (loading) {
        return (
            <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (!session) {
        return (
            <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center text-slate-500">
                Session not found.
            </div>
        );
    }

    return (
        <div className="bg-background-light dark:bg-background-dark min-h-screen text-slate-900 dark:text-slate-100 font-display transition-colors duration-200">
            <DashboardNavBar />

            <main className="max-w-4xl mx-auto px-4 py-8">
                {/* Header */}
                <div className="mb-8 border-b border-slate-200 dark:border-slate-800 pb-4">
                    <div className="flex items-center gap-2 text-sm text-slate-500 mb-2">
                        <button onClick={() => router.push('/dashboard')} className="hover:text-primary transition-colors">Dashboard</button>
                        <span>/</span>
                        <span>Session #{session.id}</span>
                    </div>
                    <h1 className="text-2xl font-bold">{session.title}</h1>
                    {session.subject && (
                        <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded font-bold uppercase mt-2 inline-block">
                            {session.subject}
                        </span>
                    )}
                </div>

                {/* Chat Stream */}
                <div className="space-y-8 mb-12">
                    {session.messages.map((msg, idx) => (
                        <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            {msg.role === 'assistant' && (
                                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 text-primary">
                                    <span className="material-symbols-outlined">smart_toy</span>
                                </div>
                            )}

                            {/* CONDITIONAL RENDERING BASED ON CONTENT TYPE */}
                            {msg.type === 'solution_json' ? (
                                <div className="w-full max-w-4xl">
                                    <SolutionRenderer data={msg.content} />
                                </div>
                            ) : (
                                <div className={`max-w-[80%] rounded-2xl p-6 ${msg.role === 'user'
                                    ? 'bg-primary text-white rounded-br-none'
                                    : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-bl-none shadow-sm'
                                    }`}>
                                    {msg.role === 'user' ? (
                                        <div className="whitespace-pre-wrap">{msg.content}</div>
                                    ) : (
                                        <div className="prose dark:prose-invert max-w-none">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkMath]}
                                                rehypePlugins={[rehypeKatex]}
                                            >
                                                {msg.content}
                                            </ReactMarkdown>
                                        </div>
                                    )}
                                </div>
                            )}

                            {msg.role === 'user' && (
                                <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
                                    <span className="material-symbols-outlined text-slate-500">person</span>
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Input Area (Mock for now) */}
                <div className="sticky bottom-8">
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-2 shadow-xl shadow-black/5 flex gap-2">
                        <input
                            type="text"
                            placeholder="Ask a follow-up question..."
                            className="flex-1 bg-transparent border-none focus:ring-0 px-4 py-3 outline-none"
                        />
                        <button className="bg-primary hover:bg-blue-700 text-white p-3 rounded-lg transition-colors">
                            <span className="material-symbols-outlined">send</span>
                        </button>
                    </div>
                </div>
            </main>
        </div>
    );
}
