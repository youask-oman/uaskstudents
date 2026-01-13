"use client";

import { useState, useEffect, use } from "react";
import WorkspaceLayout from "@/components/workspace/WorkspaceLayout";
import StepsTab from "@/components/workspace/StepsTab";
import VerificationTab from "@/components/workspace/VerificationTab";
import ConceptsTab from "@/components/workspace/ConceptsTab";
import PracticeTab from "@/components/workspace/PracticeTab";
import { DEMO_SOLUTION } from "@/lib/mock-response";

interface ChatMessage {
    role: string;
    content: unknown;
    created_at: string;
    type?: 'text' | 'solution_json';
    structured_data?: Record<string, unknown> | null;
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
    const [session, setSession] = useState<ChatSession | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('steps');
    const [monthlyTokensUsed, setMonthlyTokensUsed] = useState<number | null>(null);
    const [totalProblemsSolved, setTotalProblemsSolved] = useState<number | null>(null);

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
                const res = await fetch(`/api/v1/sessions/${id}`);
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

    useEffect(() => {
        const fetchTokenUsage = async () => {
            const userId = localStorage.getItem("user_id");
            if (!userId) return;
            try {
                const res = await fetch(`/api/v1/user/token-usage?user_id=${userId}`);
                if (!res.ok) return;
                const data = await res.json();
                if (typeof data.tokens_used === "number") {
                    setMonthlyTokensUsed(data.tokens_used);
                }
            } catch (error) {
                console.error("Failed to fetch token usage:", error);
            }
        };

        fetchTokenUsage();
    }, []);

    useEffect(() => {
        const fetchProfileUsage = async () => {
            const userId = localStorage.getItem("user_id");
            if (!userId) return;
            try {
                const res = await fetch(`/api/v1/user/profile?user_id=${userId}`);
                if (!res.ok) return;
                const data = await res.json();
                if (typeof data?.usage?.questions_count === "number") {
                    setTotalProblemsSolved(data.usage.questions_count);
                }
            } catch (error) {
                console.error("Failed to fetch profile usage:", error);
            }
        };

        fetchProfileUsage();
    }, []);

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
    const sessionTokensUsed = session.messages.reduce((sum, message) => sum + (message.tokens_used ?? 0), 0);
    const totalTokensUsed = (monthlyTokensUsed ?? sessionTokensUsed) + 6000;



    const renderContent = () => {
        if (!solutionData) return <div className="p-8 text-center text-slate-500">No solution details found in this session.</div>;

        switch (activeTab) {
            case 'steps':
                return <StepsTab
                    title={solutionData.problem?.goal || "Solution"}
                    steps={solutionData.solution?.steps || []}
                    visuals={solutionData.visuals || []}
                    problemLatex={solutionData.problem?.input || solutionData.problem?.latex}
                    problem={solutionData.problem}
                    analysisPlan={solutionData.analysis?.plan || []}
                    finalAnswer={solutionData.solution?.final_answer}
                    activeTab={activeTab as "steps" | "verification" | "concepts" | "practice"}
                    onSelectTab={setActiveTab}
                />;
            case 'verification':
                return <VerificationTab
                    methods={solutionData.verification || []}
                    activeTab={activeTab as "steps" | "verification" | "concepts" | "practice"}
                    onSelectTab={setActiveTab}
                    stepsCount={(solutionData.solution?.steps || []).length}
                    problem={solutionData.problem}
                    analysisPlan={solutionData.analysis?.plan || []}
                    finalAnswer={solutionData.solution?.final_answer}
                    confidence={solutionData.meta?.confidence}
                    keyConcepts={solutionData.solution?.key_concepts || []}
                    features={solutionData.solution?.features}
                    commonMistakes={solutionData.solution?.common_mistakes || []}
                    similarExamples={solutionData.similar_examples || []}
                />;
            case 'concepts':
                return <ConceptsTab
                    keyConcepts={solutionData.solution?.key_concepts || []}
                    commonMistakes={solutionData.solution?.common_mistakes || []}
                    features={solutionData.solution?.features}
                    visuals={solutionData.visuals || []}
                    activeTab={activeTab as "steps" | "verification" | "concepts" | "practice"}
                    onSelectTab={setActiveTab}
                    stepsCount={(solutionData.solution?.steps || []).length}
                />;
            case 'practice':
                return <PracticeTab
                    similarExamples={solutionData.similar_examples || []}
                    progress={45}
                    level="Intermediate"
                    topic={solutionData.problem?.topic}
                    activeTab={activeTab as "steps" | "verification" | "concepts" | "practice"}
                    onSelectTab={setActiveTab}
                    stepsCount={(solutionData.solution?.steps || []).length}
                />;
            default:
                return <StepsTab
                    title={solutionData.problem?.goal || "Solution"}
                    steps={solutionData.solution?.steps || []}
                    visuals={solutionData.visuals || []}
                    problemLatex={solutionData.problem?.input || solutionData.problem?.latex}
                    problem={solutionData.problem}
                    analysisPlan={solutionData.analysis?.plan || []}
                    finalAnswer={solutionData.solution?.final_answer}
                    activeTab={activeTab as "steps" | "verification" | "concepts" | "practice"}
                    onSelectTab={setActiveTab}
                />;
        }
    };

    return (
        <WorkspaceLayout
            messages={session.messages}
            problem={solutionData?.problem}
            analysisPlan={solutionData?.analysis?.plan || []}
            keyConcepts={solutionData?.solution?.key_concepts || []}
            stepsCount={(solutionData?.solution?.steps || []).length}
            onSelectConcepts={() => setActiveTab("concepts")}
            llmUsed="YouAsk AI"
            totalTokensUsed={totalTokensUsed}
            questionTokensUsed={sessionTokensUsed}
            totalProblemsSolved={totalProblemsSolved ?? 0}
            tokenUsage={totalTokensUsed}
        >
            {renderContent()}
        </WorkspaceLayout>
    );
}
