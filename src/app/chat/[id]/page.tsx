"use client";

import { useState, useEffect, use } from "react";
import WorkspaceLayout from "@/components/workspace/WorkspaceLayout";
import StepsTab from "@/components/workspace/StepsTab";


import { DEMO_SOLUTION } from "@/lib/mock-response";

interface ChatMessage {
    role: string;
    content: unknown;
    created_at: string;
    type?: 'text' | 'solution_json';
    structured_data?: Record<string, unknown> | null;
    model_used?: string;
    tokens_used?: number;
    telemetry?: TelemetryPayload;
}


interface ChatSession {
    id: number | string;
    title: string;
    subject?: string;
    created_at: string;
    messages: ChatMessage[];
    is_saved?: boolean;
}

interface VisualSeriesPoint {
    x: number;
    y: number;
    label?: string;
}

interface VisualSeries {
    name?: string;
    kind?: string;
    expression_latex?: string;
    points?: VisualSeriesPoint[];
    style_hint?: string;
}


interface VisualPlot {
    plot_id?: string;
    plot_type?: string;
    name?: string;
    title?: string;
    x_label?: string;
    y_label?: string;
    x_min?: number;
    x_max?: number;
    y_min?: number;
    y_max?: number;
    series?: VisualSeries[];
    key_points?: Array<{
        label?: string;
        x?: number;
        y?: number;
    }>;
    annotations?: Array<{
        text?: string;
        x?: number;
        y?: number;
    }>;
}


interface TelemetryPayload {
    request_id?: string;
    model?: string;
    total_tokens?: number;
    input_tokens?: number;
    output_tokens?: number;
    latency_ms_openai?: number;
    latency_ms_total?: number;
    cached_tokens?: number;
    learning_mode?: string;
    requested_mode?: string;
    solve_tier?: string;
}

type SolveStep = NonNullable<SolveResponseV3["steps"]>[number];
type SolvePlan = NonNullable<SolveResponseV3["plan"]>[number];

interface SolveResponseV3 {
    problem: {
        original_text?: string;
        normalized_text?: string;
        detected_tasks?: string[];
    };
    classification?: {
        grade_band?: string;
        domain?: string;
        topic?: string;
        difficulty?: string;
        detected_tasks?: string[];
    };
    steps?: Array<{
        index: number;
        title?: string;
        explanation?: string;
        math_latex?: string;
        rules_used?: string[];
        checkpoint?: {
            question?: string;
            answer?: string;
        };
    }>;
    final_answer?: {
        answer_text?: string;
        answer_latex?: string;
        values?: Array<{ label: string; value: number | string; value_latex: string }>;
        units?: string;
    };
    verification?: {
        method?: string;
        work_latex?: string;
        conclusion?: string;
    };
    visuals?: {
        should_visualize?: boolean;
        decision_reason?: string;
        plots?: VisualPlot[];
        alternative_visual?: {
            kind?: string;
            description?: string;
            data?: Array<{ label: string; x?: number; y?: number }>;
        };
    };
    quality?: {
        confidence?: number;
        common_mistakes?: string[];
    };
    refusal?: {
        is_refusal?: boolean;
        reason?: string;
        safe_alternative?: string;
    };
    assumptions?: string[];
    plan?: Array<{ summary?: string; title?: string }>;
    telemetry?: TelemetryPayload;
    _telemetry?: TelemetryPayload;
    _truncated?: boolean;
    validation_errors?: string[];
    message?: string;
    error?: string;
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
    const rawData = id === 'demo-1' ? DEMO_SOLUTION : (assistantMsg?.structured_data || null);

    // Type-safe(ish) casting for V3 Schema
    const solutionData = (rawData || null) as SolveResponseV3 | null;

    const sessionTokensUsed = session.messages.reduce((sum, message) => sum + (message.tokens_used ?? 0), 0);
    const totalTokensUsed = (monthlyTokensUsed ?? sessionTokensUsed) + 6000;

    // Helper to map V3 Visuals to Visual Component Props
    const mapVisuals = (plots: VisualPlot[]) => {
        return plots.map((p, index) => ({
            id: p.plot_id || `plot_${index}`,
            type: "function_plot",
            title: p.title,
            axes: { x_label: p.x_label, y_label: p.y_label },
            domain: { x_min_latex: String(p.x_min ?? ""), x_max_latex: String(p.x_max ?? "") },
            series: p.series?.map((s) => ({
                label: s.name || '',
                points: s.points?.map((pt) => ({ x: pt.x, y: pt.y })) ?? []
            })) ?? [],
            markers: p.key_points?.map((kp) => ({
                label: kp.label || '',
                x: kp.x ?? 0,
                y: kp.y ?? 0
            })) ?? []
        }));
    };


    const visualsData = solutionData?.visuals?.plots ?? [];
    console.log("[DEBUG] solutionData:", solutionData);
    console.log("[DEBUG] visualsData:", visualsData);
    const visuals = mapVisuals(visualsData);
    console.log("[DEBUG] Mapped visuals:", visuals);
    const planSummaries = (solutionData?.plan as SolvePlan[] | undefined)?.map((p) => p.summary || p.title).filter(Boolean) ?? [];
    const fallbackPlan = (solutionData?.steps ?? []).map((s) => s.title).filter(Boolean);
    const analysisPlanEntries = planSummaries.length > 0 ? planSummaries : fallbackPlan;

    const renderContent = () => {
        if (!solutionData) return <div className="p-8 text-center text-slate-500">No solution details found in this session.</div>;

        if (solutionData.error && !solutionData._truncated) {
            return (
                <div className="max-w-2xl mx-auto mt-10 p-6 bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/50 rounded-2xl text-center">
                    <span className="material-symbols-outlined text-4xl text-red-500 mb-4">error_outline</span>
                    <h3 className="text-lg font-bold text-red-700 dark:text-red-300 mb-2">Solver Error</h3>
                    <p className="text-sm text-red-600 dark:text-red-200">{solutionData.message || solutionData.error || "An unexpected error occurred."}</p>
                    {solutionData.validation_errors && solutionData.validation_errors.length > 0 && (
                        <div className="mt-4 text-left bg-white/50 dark:bg-black/20 p-4 rounded-xl text-xs font-mono text-red-800 dark:text-red-200 overflow-auto max-h-40">
                            {solutionData.validation_errors.map((e: string, i: number) => <div key={i}>{e}</div>)}
                        </div>
                    )}
                </div>
            );
        }

        // Show truncation warning if applicable but continue to render what we have
        const truncationWarning = solutionData._truncated ? (
            <div className="max-w-2xl mx-auto mb-6 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl flex items-center gap-3">
                <span className="material-symbols-outlined text-xl text-amber-500">warning</span>
                <div>
                    <p className="text-sm font-semibold text-amber-700 dark:text-amber-300">Response Truncated</p>
                    <p className="text-xs text-amber-600 dark:text-amber-400">The AI response was cut off due to output limits. Showing partial solution.</p>
                </div>
            </div>
        ) : null;

        // Extract Common Props
        const steps = (solutionData?.steps as SolveStep[]) || [];
        // Map steps to match StepsTab expectation (work array)
        const mappedSteps = steps.map((s, idx) => ({
            ...s,
            title: s.title || `Step ${idx + 1}`,
            explanation: s.explanation || '',
            work: s.math_latex ? [s.math_latex] : [],
            rules_used: s.rules_used || [],
            checkpoint: s.checkpoint ? {
                question: s.checkpoint.question || '',
                expected_answer: s.checkpoint.answer || '',
                answer: s.checkpoint.answer || ''
            } : undefined
        }));


        const problem = solutionData.problem || {};
        const problemLatex = problem.normalized_text || problem.original_text;

        switch (activeTab) {
            case 'steps':
                return <>
                    {truncationWarning}
                    <StepsTab
                        steps={mappedSteps}
                        visuals={visuals}
                        problemLatex={problemLatex}
                        problem={{
                            goal: problem.original_text,
                            given_data: solutionData.assumptions,
                            assumptions: solutionData.assumptions
                        }}
                        analysisPlan={[]}
                        finalAnswer={solutionData.final_answer?.answer_text}
                        activeTab={activeTab as "steps"}
                        onSelectTab={setActiveTab}
                    />
                </>;


            default:
                return null;
        }
    };



    const telemetry = assistantMsg?.telemetry || solutionData?.telemetry || solutionData?._telemetry;
    const finalAnswerLatex = solutionData?.final_answer?.answer_latex || null;
    const finalAnswerText = solutionData?.final_answer?.answer_text || null;
    const finalAnswerValue = finalAnswerLatex || finalAnswerText || solutionData?.final_answer || (solutionData?._truncated ? "Partial solution in progress..." : null);
    const finalAnswerMode = finalAnswerLatex ? "inline" : "prose";

    return (
        <WorkspaceLayout
            messages={session.messages}
            activeTab={activeTab as "steps"}
            onSelectTab={setActiveTab}
            problem={{
                ...solutionData?.problem,
                topic: solutionData?.classification?.topic,
                goal: solutionData?.classification?.detected_tasks?.[0] || "Solve",
                input: solutionData?.problem?.normalized_text || solutionData?.problem?.original_text,
                given_data: solutionData?.problem?.original_text ? [solutionData.problem.original_text] : [],
                unknowns: solutionData?.classification?.detected_tasks,
                assumptions: solutionData?.assumptions
            }}
            stepsCount={(solutionData?.steps || []).length}
            analysisPlan={analysisPlanEntries.filter((s): s is string => !!s)}
            finalAnswer={typeof finalAnswerValue === 'string' ? finalAnswerValue : finalAnswerText || undefined}
            finalAnswerMode={finalAnswerMode as "inline" | "prose"}
            confidence={solutionData?.quality?.confidence ? Math.round(solutionData.quality.confidence * 100) : 99}
            llmUsed="YouAsk AI"
            totalTokensUsed={totalTokensUsed}
            questionTokensUsed={sessionTokensUsed}
            totalProblemsSolved={totalProblemsSolved ?? 0}
            tokenUsage={totalTokensUsed}
            sessionId={typeof id === 'string' ? id : (Array.isArray(id) ? id[0] : id)}
            initialSaved={session?.is_saved}
            telemetry={telemetry}
            // NEW: Classification data
            classification={solutionData?.classification}
            // NEW: Quality insights - common mistakes
            commonMistakes={solutionData?.quality?.common_mistakes}
            // NEW: Visuals/Plots
            visuals={solutionData?.visuals as never}
            // NEW: Original problem text for chat context
            originalProblemText={solutionData?.problem?.original_text}
            // NEW: Steps for chat context
            steps={(solutionData?.steps || []).map((s, i) => ({
                title: s.title || `Step ${i + 1}`,
                index: s.index || i + 1
            }))}
        >
            {renderContent()}
        </WorkspaceLayout>
    );
}

