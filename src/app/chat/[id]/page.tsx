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
    openai_payload?: {
        full_input?: unknown[];
        full_output?: unknown;
    };
}

// V2-lite Schema Interfaces (from canonical_schema.json)
interface V2LiteOutputBlock {
    id: string;
    type: 'explanation' | 'math' | 'worked_step' | 'hint' | 'table' | 'plot' | 'quiz';
    // worked_step fields
    title?: string;
    explanation?: string;
    before_latex?: string;
    after_latex?: string;
    rule_tags?: string[];
    // explanation/hint fields
    text?: string;
    tier?: number;
    // plot
    x_min?: number;
    x_max?: number;
    y_min?: number | null;
    y_max?: number | null;
    series?: Array<{ kind: 'y_of_x' | 'implicit' | 'points'; expr_latex: string; label: string; points?: Array<{ x: number; y: number }> }>;
    key_points?: Array<{ x: number; y: number; label: string }>;
    // table
    headers?: string[];
    rows?: string[][];
    // quiz
    questions?: unknown[];
}

interface V2LiteAnswer {
    status: 'final' | 'pending_student_step' | 'needs_clarification';
    final_latex: string;
    final_text: string;
    values: Array<{ symbol: string; value: number | string | null; value_latex?: string }>;
    constraints: string[];
}

interface V2LiteMeta {
    mode: 'study' | 'solve';
    grade_band: string;
    locale: string;
    subject: string;
    ui_intent?: { verbosity?: string };
}

interface V2LiteProblem {
    original_text: string;
    normalized_latex: string;
    task_tags: string[];
}

interface V2LiteResponse {
    schema_version: string;
    refusal: { is_refusal: boolean; reason?: string; safe_alternative?: string };
    problem: V2LiteProblem; // Always required since v2.0
    // Old fields (v2.0-lite)
    meta?: V2LiteMeta;
    output?: V2LiteOutputBlock[];
    answer?: V2LiteAnswer;
    // New fields (v2.1-lite)
    assumptions?: string[];
    classification?: {
        grade_band?: string;
        domain?: string;
        topic?: string;
        difficulty?: string;
    };
    steps?: Array<{
        index: number;
        title: string;
        explanation: string;
        math_latex: string | string[];
        rules_used: string[];
    }>;
    final_answer?: {
        answer_text: string;
        answer_latex: string;
        values?: Array<{ symbol: string; value: number | string | null; value_latex?: string }>;
        units?: string | null;
    };
    visuals?: {
        should_visualize: boolean;
        decision_reason: string;
        plots: VisualPlot[];
        alternative_visual?: unknown;
    };
    quality?: {
        confidence: number;
        common_mistakes: string[];
    };
    telemetry?: { model?: string; token_budget?: { max_output_tokens?: number } };
}

// Utility: Detect if response is V2-lite format
function isV2LiteSchema(data: unknown): data is V2LiteResponse {
    if (!data || typeof data !== 'object') return false;
    const d = data as Record<string, unknown>;
    return typeof d.schema_version === 'string' && d.schema_version.startsWith('v2');
}

// Utility: Map V2-lite to V3-compatible format
function mapV2LiteToV3(v2: V2LiteResponse): SolveResponseV3 {
    // 1. Map Steps
    let steps: SolveStep[] = [];
    if (v2.steps && v2.steps.length > 0) {
        // Direct mapping for v2.1-lite
        steps = v2.steps.map(s => ({
            ...s,
            math_latex: Array.isArray(s.math_latex) ? s.math_latex.join(' \\\\ ') : s.math_latex
        }));
    } else if (v2.output) {
        // Map from v2.0-lite block structure
        steps = v2.output
            .filter(b => b.type === 'worked_step')
            .map((block, idx) => ({
                index: idx + 1,
                title: block.title || `Step ${idx + 1}`,
                explanation: block.explanation || '',
                math_latex: [block.before_latex, block.after_latex].filter(Boolean).join(' \\Rightarrow '),
                rules_used: block.rule_tags || []
            }));

        // If no worked steps, use explanation blocks
        if (steps.length === 0) {
            v2.output
                .filter(b => b.type === 'explanation')
                .forEach((b, idx) => {
                    steps.push({
                        index: idx + 1,
                        title: "Explanation",
                        explanation: b.text || '',
                        math_latex: '',
                        rules_used: []
                    });
                });
        }
    }

    // 2. Map Answer
    let final_answer: NonNullable<SolveResponseV3["final_answer"]> = {};
    if (v2.final_answer) {
        final_answer = {
            ...v2.final_answer,
            values: v2.final_answer.values?.map((v) => ({
                label: (v as { label?: string; symbol?: string }).label || (v as { label?: string; symbol?: string }).symbol || '',
                value: v.value ?? '',
                value_latex: v.value_latex || String(v.value ?? '')
            })),
            units: v2.final_answer.units ?? undefined
        };
    } else if (v2.answer) {
        final_answer = {
            answer_text: v2.answer.final_text,
            answer_latex: v2.answer.final_latex,
            values: v2.answer.values?.map((v) => ({
                label: (v as { label?: string; symbol?: string }).label || (v as { label?: string; symbol?: string }).symbol || '',
                value: v.value ?? '',
                value_latex: v.value_latex || String(v.value ?? '')
            }))
        };
    }

    // 3. Map Visuals
    let visuals: NonNullable<SolveResponseV3["visuals"]> = { plots: [] };
    if (v2.visuals) {
        visuals = {
            ...v2.visuals,
            plots: (v2.visuals.plots || []).map(p => ({
                ...p,
                y_min: p.y_min ?? undefined,
                y_max: p.y_max ?? undefined
            })),
            alternative_visual: v2.visuals.alternative_visual as { kind?: string; description?: string; data?: Array<{ label: string; x?: number; y?: number }> } | undefined
        };
    } else if (v2.output) {
        visuals.plots = v2.output
            .filter(b => b.type === 'plot')
            .map(b => ({
                plot_id: b.id,
                title: b.title,
                x_min: b.x_min,
                x_max: b.x_max,
                y_min: b.y_min ?? undefined,
                y_max: b.y_max ?? undefined,
                series: b.series?.map(s => ({
                    name: s.label || s.expr_latex,
                    points: s.points || []
                })),
                key_points: b.key_points
            }));
        visuals.should_visualize = (visuals.plots?.length ?? 0) > 0;
    }

    // 4. Map Classification
    let classification: NonNullable<SolveResponseV3["classification"]> = {};
    if (v2.classification) {
        classification = v2.classification;
    } else if (v2.meta) {
        classification = {
            grade_band: v2.meta.grade_band,
            domain: v2.meta.subject,
            topic: v2.problem?.task_tags?.[0],
            difficulty: v2.meta.ui_intent?.verbosity
        };
    }

    return {
        schema_version: v2.schema_version,
        problem: {
            original_text: v2.problem?.original_text,
            normalized_text: v2.problem?.normalized_latex
        },
        classification,
        steps,
        final_answer,
        visuals,
        quality: v2.quality,
        assumptions: v2.assumptions,
        refusal: v2.refusal,
        telemetry: v2.telemetry as TelemetryPayload
    };
}

type SolveStep = NonNullable<SolveResponseV3["steps"]>[number];
type SolvePlan = NonNullable<SolveResponseV3["plan"]>[number];

interface SolveResponseV3 {
    schema_version?: string;
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
        math_latex?: string | string[];
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

    // Type-safe(ish) detection and mapping
    let solutionData: SolveResponseV3 | null = null;
    if (rawData) {
        if (isV2LiteSchema(rawData)) {
            solutionData = mapV2LiteToV3(rawData);
        } else {
            solutionData = rawData as SolveResponseV3;
        }
    }

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

        if (solutionData.refusal?.is_refusal) {
            return (
                <div className="max-w-2xl mx-auto mt-10 p-8 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl text-center">
                    <div className="size-16 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mx-auto mb-6">
                        <span className="material-symbols-outlined text-3xl text-amber-500">security_update_warning</span>
                    </div>
                    <h3 className="text-xl font-bold mb-3 text-slate-800 dark:text-white">Safety Refusal</h3>
                    <p className="text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
                        {solutionData.refusal.reason || "This content was refused by the safety policy."}
                    </p>
                    {solutionData.refusal.safe_alternative && (
                        <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 text-left">
                            <p className="text-xs font-bold text-primary uppercase mb-2">Safe Alternative</p>
                            <p className="text-sm text-slate-700 dark:text-slate-300">{solutionData.refusal.safe_alternative}</p>
                        </div>
                    )}
                </div>
            );
        }

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
            work: Array.isArray(s.math_latex) ? s.math_latex : (s.math_latex ? [s.math_latex] : []),
            rules_used: s.rules_used || [],
            checkpoint: s.checkpoint ? {
                question: s.checkpoint.question || '',
                expected_answer: typeof s.checkpoint.answer === 'string' ? s.checkpoint.answer : '',
                answer: typeof s.checkpoint.answer === 'string' ? s.checkpoint.answer : ''
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
                        decisionReason={solutionData.visuals?.decision_reason}
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
            finalAnswerValues={solutionData?.final_answer?.values}
            finalAnswerUnits={solutionData?.final_answer?.units}
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

