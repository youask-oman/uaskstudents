"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import WorkspaceLayout from "@/components/workspace/WorkspaceLayout";
import StepsTab from "@/components/workspace/StepsTab";
import VerificationTab from "@/components/workspace/VerificationTab";
import ConceptsTab from "@/components/workspace/ConceptsTab";
import PracticeTab from "@/components/workspace/PracticeTab";
import { DEMO_SOLUTION } from "@/lib/mock-response";

interface ChatMessage {
    role: string;
    content: string | any;
    created_at: string;
    type?: 'text' | 'solution_json';
    structured_data?: any;
    model_used?: string;
    tokens_used?: number;
}

interface ChatSession {
    id: number | string;
    title: string;
    subject?: string;
    created_at: string;
    messages: ChatMessage[];
    is_saved?: boolean; // Added is_saved
}

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const [session, setSession] = useState<ChatSession | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('steps');
    const [tutorMode, setTutorMode] = useState("Physics");

    useEffect(() => {
        const fetchSession = async () => {
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
                                content: DEMO_SOLUTION,
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
                const res = await fetch(`http://127.0.0.1:8000/api/v1/sessions/${id}`);
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

    const assistantMsg = session.messages.find(m => m.role === 'assistant' && (m.structured_data || m.model_used));
    const solutionData = id === 'demo-1'
        ? DEMO_SOLUTION
        : (assistantMsg?.structured_data || null);

    const modelUsed = assistantMsg?.model_used || (id === 'demo-1' ? "YouAsk AI (Multimodal)" : "OpenAI GPT-4o Mini");
    const tokensUsed = (assistantMsg && typeof assistantMsg.tokens_used === 'number') ? assistantMsg.tokens_used : (id === 'demo-1' ? 750 : 500);

    const handleSendMessage = async (query: string) => {
        const userId = localStorage.getItem("user_id") || "1";
        const sessionIdInt = typeof id === 'string' && id.startsWith('demo') ? 1 : parseInt(id as string);

        // Optimistically add user message
        const userMsg: ChatMessage = {
            role: 'user',
            content: query,
            created_at: new Date().toISOString()
        };

        setSession(prev => prev ? { ...prev, messages: [...prev.messages, userMsg] } : null);

        try {
            console.log("Sending message to API...", { session_id: sessionIdInt, user_id: userId, query });

            const res = await fetch('http://127.0.0.1:8000/api/v1/ask-question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionIdInt,
                    user_id: parseInt(userId),
                    query: query
                })
            });

            console.log("API Response Status:", res.status);

            if (!res.ok) {
                const errorText = await res.text();
                console.error("API Error Body:", errorText);
                throw new Error(`Failed to get answer: ${res.status} ${res.statusText}`);
            }

            const data = await res.json();

            // Add AI response
            const aiMsg: ChatMessage = {
                role: 'assistant',
                content: data.relevant ? data.content : `⚠️ **Problem Focus Guard:** ${data.content}`,
                created_at: data.created_at,
                model_used: data.model_used || "OpenAI GPT-4o Mini",
                tokens_used: data.tokens_used || 100
            };

            setSession(prev => prev ? { ...prev, messages: [...prev.messages, aiMsg] } : null);

            if (!data.relevant) {
                // Could show a toast or alert specifically about relevance
            }

        } catch (err: any) {
            console.error("Chat Error:", err);
            // Revert or show error
            const errorMsg: ChatMessage = {
                role: 'assistant',
                content: `Error: ${err.message || "I'm having trouble connecting to my brain right now."}`,
                created_at: new Date().toISOString()
            };
            setSession(prev => prev ? { ...prev, messages: [...prev.messages, errorMsg] } : null);
        }
    };

    const handleViewConcepts = () => {
        setActiveTab('concepts');
    };

    const handleSave = async () => {
        if (!session || typeof session.id !== 'number') return;

        try {
            const res = await fetch(`http://localhost:8000/api/v1/sessions/${session.id}/save`, {
                method: 'POST'
            });

            if (res.ok) {
                setSession(prev => prev ? { ...prev, is_saved: true } : null);
            } else {
                console.error("Failed to save session");
            }
        } catch (error) {
            console.error("Error saving session:", error);
        }
    };

    const renderContent = () => {
        if (!solutionData) return <div className="p-8 text-center text-slate-500">No solution details found in this session.</div>;

        switch (activeTab) {
            case 'steps':
                return <StepsTab
                    title={solutionData.problem?.goal || "Solution"}
                    steps={solutionData.solution?.steps || []}
                    onViewConcepts={handleViewConcepts}
                />;
            case 'verification':
                return <VerificationTab
                    methods={solutionData.verification?.methods_used || []}
                />;
            case 'concepts':
                return <ConceptsTab
                    concepts={solutionData.concepts || []}
                />;
            case 'practice':
                return <PracticeTab
                    problems={[
                        {
                            title: "Simpler Variant",
                            description: "Solve the equation for x.",
                            latex: "\\sqrt{2x+3} = 5",
                            difficulty: "Similar",
                            xp: 50
                        },
                        {
                            title: "Advanced Variant",
                            description: "Solve for x and identify any extraneous solutions.",
                            latex: "\\sqrt{3x+1} = x - 3",
                            difficulty: "Step Up",
                            xp: 120
                        }
                    ]}
                    progress={45}
                    level="Intermediate"
                />;
            default:
                return <StepsTab
                    title={solutionData.problem?.goal || "Solution"}
                    steps={solutionData.solution?.steps || []}
                    onViewConcepts={handleViewConcepts}
                />;
        }
    };

    return (
        <WorkspaceLayout
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            messages={session.messages}
            sessionTitle={session.title}
            problemLatex={solutionData?.problem?.latex || session.title}
            tutorMode={tutorMode}
            setTutorMode={setTutorMode}
            onSendMessage={handleSendMessage}
            isSaved={Boolean(session.is_saved)}
            onSave={session.id !== 'demo-1' ? handleSave : undefined}
            modelUsed={modelUsed}
            tokensUsed={tokensUsed || 0}
        >
            {renderContent()}
        </WorkspaceLayout>
    );
}
