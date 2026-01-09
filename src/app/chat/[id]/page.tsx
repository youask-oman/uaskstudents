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

    const solutionData = id === 'demo-1'
        ? DEMO_SOLUTION
        : (session.messages.find(m => m.role === 'assistant' && m.structured_data)?.structured_data || null);

    const renderContent = () => {
        if (!solutionData) return <div className="p-8 text-center text-slate-500">No solution details found in this session.</div>;

        switch (activeTab) {
            case 'steps':
                return <StepsTab
                    title={solutionData.problem?.goal || "Solution"}
                    steps={solutionData.solution?.steps || []}
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
                />;
        }
    };

    return (
        <WorkspaceLayout
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            messages={session.messages}
            sessionTitle={session.title}
            tutorMode={tutorMode}
            setTutorMode={setTutorMode}
        >
            {renderContent()}
        </WorkspaceLayout>
    );
}
