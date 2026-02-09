"use client";

import DashboardNavBar from "@/components/DashboardNavBar";
import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import ProgressTimeline, { TimelineStep } from "@/components/solve/ProgressTimeline";
import { useRouter } from "next/navigation";
import MathRenderer from "@/components/math/MathRendererSwitch";
import MathRendererMJX from "@/components/MathRendererMJX";
import MathInput, { MathInputRef } from "@/components/MathInput";
import { MODES, ModeId, Suggestion } from "@/lib/modes";
import SnapSolveV2 from "@/components/snap/SnapSolveV2";
import SnapSolveInputPanel from "@/components/snap_solve/SnapSolveInputPanel";

// Token validation imports
import { estimateTokens } from "@/lib/tokenEstimator";
import { detectMultiQuestion, autoSplitQuestions } from "@/lib/multiQuestionDetector";
import { TokenBudgetPolicy, willRequestFit } from "@/lib/tokenBudget";
import InputStatus from "@/components/InputStatus";
import SplitModal from "@/components/SplitModal";

// Input mode imports
import LiveMathPreview from "@/components/LiveMathPreview";

import {
    validateMathQuery,
    isBlockingInputError,
    isInputTooShort,
    INPUT_ERROR_BLOCKED,
    INPUT_ERROR_NOT_MATH
} from "@/lib/mathValidation";

// Tier-aware solve imports
import SegmentedControl from "@/components/ui/SegmentedControl";
import CostPreview from "@/components/solve/CostPreview";
import { SubscriptionResponse, fetchSubscription, fetchCreditsEstimate, CreditsEstimateResponse, SolveTier } from "@/lib/subscription";
import { TokenPolicy, fetchTokenPolicy } from "@/lib/tokenPolicy";
import ThemeToggle from "@/components/ThemeToggle";

interface ChatSession {
    id: number;
    title: string;
    created_at: string;
}

interface ActiveUser {
    id: number;
    avatar_url?: string;
    full_name: string;
    learning_interests?: string[];
}

interface ClarifierOption {
    label: string;
    value: string;
}

interface ClarifierQuestion {
    question: string;
    options: ClarifierOption[];
}

interface VoiceArtifact {
    id: number;
    transcript_raw?: string;
    normalized_math_text?: string;
    clarifier_question?: ClarifierQuestion;
}

interface StreamingTelemetry {
    provider?: string;
    model?: string;
    total_tokens?: number;
    latency_ms_openai?: number;
    truncated?: boolean;
}

interface StreamingRuntimeMeta {
    request_id?: string;
    provider?: string;
    model?: string;
    tier_requested?: string;
    effective_tier?: string;
    mode_family?: string;
    mode?: string;
    prompt_binding_id?: string;
    global_system_prompt_id?: string;
    developer_prompt_id?: string;
    output_schema_id?: string;
    global_system_prompt_version?: number;
    developer_prompt_version?: number;
    output_schema_version?: number;
    token_config?: {
        max_output_tokens?: number;
        max_input_tokens?: number;
        temperature?: number;
        top_p?: number;
        timeout_ms?: number;
        trim_strategy?: string;
    }
}

interface OcrMetadata {
    ocr_confidence: number;
    ocr_warnings: string[];
    ocr_source: string;
    ocr_engine: string;
}

interface VoiceFeatures {
    voice_confirmed: boolean;
    voice_used?: boolean;
    voice_ambiguity_flags?: string[];
    voice_clarifier_question?: string;
    voice_stt_provider?: string;
    voice_transcript_confidence?: number;
}

type FeaturesUsed = Partial<OcrMetadata & VoiceFeatures> & {
    ocr_used?: boolean;
    ocr_engine?: string;
    ocr_source?: string;
    ocr_warnings?: string[];
    voice_used?: boolean;
    plot_requested?: boolean;
};

export default function DashboardPage() {
    const useSnapSolveUploadPanelV2 = process.env.NEXT_PUBLIC_SNAP_SOLVE_UPLOAD_PANEL_V2 !== "false";
    const [activeTab, setActiveTab] = useState<'text' | 'snap' | 'voice'>('text');
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [query, setQuery] = useState("sqrt(x+5) = x - 1");
    const [isSolving, setIsSolving] = useState(false);
    const [onlineUsers, setOnlineUsers] = useState<ActiveUser[]>([]);
    const [isPublic, setIsPublic] = useState(false);

    const [activeMode, setActiveMode] = useState<ModeId | null>(null);
    const [isSeeAllOpen, setIsSeeAllOpen] = useState(false);
    const [mathModeEnabled, setMathModeEnabled] = useState(true);
    const mathInputRef = useRef<MathInputRef>(null);
    const [inputError, setInputError] = useState<string | null>(null);

    // Voice State
    const [voiceStage, setVoiceStage] = useState<'idle' | 'recording' | 'processing' | 'review' | 'error'>('idle');
    const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
    const [voiceArtifact, setVoiceArtifact] = useState<VoiceArtifact | null>(null);
    const [recordingTime, setRecordingTime] = useState(0);
    // const [voiceSessionId, setVoiceSessionId] = useState<number | null>(null);
    const voiceSubject = "Mathematics";
    const [formattingEnabled, setFormattingEnabled] = useState(true);
    const [solveProgress, setSolveProgress] = useState(0);

    // Token validation state
    const [showSplitModal, setShowSplitModal] = useState(false);
    const [suggestedSplits, setSuggestedSplits] = useState<string[]>([]);
    const [multiQuestionConfirmed, setMultiQuestionConfirmed] = useState(false);
    const [mathValidityConfirmed, setMathValidityConfirmed] = useState(false);

    // Input mode state


    // Plot/Graph inclusion state
    const [graphMode, setGraphMode] = useState<'off' | 'auto' | 'on'>('auto');
    const [attachToStepId] = useState<number | null>(null);

    // Random light background for Plot Mode, Tier Section, and Free Type Mode
    const [plotModeColor, setPlotModeColor] = useState("bg-sky-50");
    const [tierSectionColor, setTierSectionColor] = useState("bg-white");
    const [freeTypeColor, setFreeTypeColor] = useState("bg-white");
    useEffect(() => {
        const colors = [
            "bg-blue-50", "bg-green-50", "bg-purple-50", "bg-orange-50",
            "bg-teal-50", "bg-rose-50", "bg-indigo-50", "bg-cyan-50"
        ];
        setPlotModeColor(colors[Math.floor(Math.random() * colors.length)]);
        setTierSectionColor(colors[Math.floor(Math.random() * colors.length)]);
        setFreeTypeColor(colors[Math.floor(Math.random() * colors.length)]);
    }, []);

    // Streaming Solve States (Part F1)
    const [streamingContent, setStreamingContent] = useState("");
    const [currentStage, setCurrentStage] = useState("");
    const [streamingTelemetry, setStreamingTelemetry] = useState<StreamingTelemetry | null>(null);
    const [streamingMeta, setStreamingMeta] = useState<StreamingRuntimeMeta | null>(null);
    const [runtimeDebugMeta, setRuntimeDebugMeta] = useState<StreamingRuntimeMeta | null>(null);
    const [showRuntimeDebug, setShowRuntimeDebug] = useState(false);
    const [runtimeDebugLoading, setRuntimeDebugLoading] = useState(false);
    const [runtimeDebugError, setRuntimeDebugError] = useState<string | null>(null);
    const [solveStartTime, setSolveStartTime] = useState<number | null>(null);

    // Phase 1: Clarification States
    const [isClarifying, setIsClarifying] = useState(false);
    const [clarificationMessage, setClarificationMessage] = useState("");
    const [clarificationResponse, setClarificationResponse] = useState("");
    const [activeAttemptId, setActiveAttemptId] = useState<string | null>(null);
    const [clarificationHistory, setClarificationHistory] = useState<string[]>([]);

    const [pipelineStages, setPipelineStages] = useState<TimelineStep[]>([
        { key: "attempt_created", label: "Semantic Extraction", description: "Parsing math symbols...", status: "pending", icon: "barcode_reader" },
        { key: "calling_ai_core", label: "Neural Reasoning", description: "Mapping logical steps...", status: "pending", icon: "psychology" },
        { key: "schema_validate", label: "Strict Validation", description: "Checking schema v1.0...", status: "pending", icon: "verified_user" },
        { key: "completed", label: "Packet Delivery", description: "Assembling response...", status: "pending", icon: "network_check" },
    ]);
    const [solveError, setSolveError] = useState<{ code?: string; message: string } | null>(null);

    // SSE / Polling Event Listener
    useEffect(() => {
        if (!activeAttemptId || !isSolving) return;

        let eventSource: EventSource | null = null;
        let pollInterval: NodeJS.Timeout | null = null;
        const channel = `/api/v1/attempt/${activeAttemptId}/events`;

        const updateStep = (key: string, status: "pending" | "active" | "completed" | "failed", description?: string) => {
            setPipelineStages(prev => prev.map(s => {
                if (s.key === key) return { ...s, status, description: description || s.description };
                // If this step is completed, make previous steps completed too if they aren't
                return s;
            }));
        };

        const handleBackendEvent = (data: any) => {
            const { phase, status, metadata } = data;

            if (phase === "attempt_created") {
                updateStep("attempt_created", "completed", "Extraction complete.");
                updateStep("calling_ai_core", "active", "Initializing reasoning...");
            } else if (phase === "calling_ai_core_start") {
                updateStep("calling_ai_core", "active", `Calling ${metadata?.provider || 'AI'}...`);
            } else if (phase === "calling_ai_core_done") {
                updateStep("calling_ai_core", "completed", "Reasoning complete.");
                updateStep("schema_validate", "active", "Validating output...");
            } else if (phase === "schema_validate_start") {
                updateStep("schema_validate", "active", "Validating schema v1.0...");
            } else if (phase === "schema_validate_done") {
                if (status === "success") {
                    updateStep("schema_validate", "completed", "Validation successful.");
                    updateStep("completed", "active", "Streaming results...");
                } else {
                    updateStep("schema_validate", "active", "Schema invalid, attempting repair...");
                }
            } else if (phase === "schema_repair_start") {
                updateStep("schema_validate", "active", "Attempting automated repair...");
            } else if (phase === "schema_repair_done") {
                if (status === "success") {
                    updateStep("schema_validate", "completed", "Repair successful.");
                    updateStep("completed", "active", "Streaming results...");
                } else {
                    updateStep("schema_validate", "failed", "Validation failed.");
                }
            } else if (phase === "completed_success") {
                updateStep("completed", "completed", "Solve complete.");
            } else if (phase === "completed_failure") {
                updateStep("completed", "failed", "Solve failed.");
                setSolveError({ code: metadata?.code, message: metadata?.error || "Solve failed." });
            } else if (phase === "clarification_needed") {
                updateStep("completed", "active", "Clarification requested.");
            }
        };

        const startSSE = () => {
            eventSource = new EventSource(channel, { withCredentials: true });
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleBackendEvent(data);
                } catch (e) {
                    console.error("SSE parse error", e);
                }
            };
            eventSource.onerror = (err) => {
                console.warn("SSE error, falling back to polling", err);
                eventSource?.close();
                startPolling();
            };
        };

        const startPolling = () => {
            pollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/v1/attempt/${activeAttemptId}`);
                    if (res.ok) {
                        const data = await res.json();
                        // Map status to stages (simplified polling fallback)
                        if (data.status === "success") {
                            setPipelineStages(prev => prev.map(s => ({ ...s, status: "completed" })));
                            if (pollInterval) clearInterval(pollInterval);
                        } else if (data.status === "failure") {
                            setPipelineStages(prev => prev.map(s => s.status === "completed" ? s : { ...s, status: "failed" }));
                            setSolveError({ code: data.failure_code, message: data.error_message });
                            if (pollInterval) clearInterval(pollInterval);
                        } else if (data.status === "ambiguous") {
                            if (pollInterval) clearInterval(pollInterval);
                        }
                    }
                } catch (e) {
                    console.error("Polling error", e);
                }
            }, 2000);
        };

        startSSE();

        return () => {
            eventSource?.close();
            if (pollInterval) clearInterval(pollInterval);
        };
    }, [activeAttemptId, isSolving]);

    const buildRuntimeMetaFromPayload = (payload: unknown, fallbackRequestedMode: string): StreamingRuntimeMeta => {
        const toObject = (value: unknown): Record<string, unknown> =>
            (value && typeof value === "object" ? (value as Record<string, unknown>) : {});

        const payloadObj = toObject(payload);
        const nested = toObject(payloadObj.solve_meta ?? payloadObj);
        const versions = toObject(nested.prompt_versions ?? payloadObj.prompt_versions);
        return {
            request_id: (payloadObj.request_id as string | undefined) ?? (nested.request_id as string | undefined),
            provider: (payloadObj.provider as string | undefined) ?? (nested.provider as string | undefined),
            model: (payloadObj.model as string | undefined) ?? (nested.model as string | undefined),
            tier_requested: (payloadObj.tier_requested as string | undefined) ?? (nested.tier_requested as string | undefined),
            effective_tier:
                (payloadObj.effective_tier as string | undefined) ??
                (payloadObj.tier_effective as string | undefined) ??
                (nested.effective_tier as string | undefined) ??
                (nested.tier_effective as string | undefined),
            mode_family:
                (payloadObj.mode_family as string | undefined) ??
                (nested.mode_family as string | undefined) ??
                (nested.mode as string | undefined) ??
                "SOLVE",
            mode: (payloadObj.mode as string | undefined) ?? (nested.mode as string | undefined) ?? fallbackRequestedMode,
            prompt_binding_id:
                (payloadObj.prompt_binding_id as string | undefined) ??
                (nested.prompt_binding_id as string | undefined),
            global_system_prompt_id:
                (payloadObj.global_system_prompt_id as string | undefined) ??
                (nested.global_system_prompt_id as string | undefined),
            developer_prompt_id:
                (payloadObj.developer_prompt_id as string | undefined) ??
                (nested.developer_prompt_id as string | undefined),
            output_schema_id:
                (payloadObj.output_schema_id as string | undefined) ??
                (nested.output_schema_id as string | undefined),
            global_system_prompt_version:
                (payloadObj.global_system_prompt_version as number | undefined) ??
                (versions.system as number | undefined),
            developer_prompt_version:
                (payloadObj.developer_prompt_version as number | undefined) ??
                (versions.developer as number | undefined),
            output_schema_version:
                (payloadObj.output_schema_version as number | undefined) ??
                (versions.schema as number | undefined),
            token_config: (payloadObj.token_config as any) ?? (nested.token_config as any),
        };
    };

    const fetchSolveRuntimeMeta = async (
        userId: string,
        tier: SolveTier,
        requestedMode: string
    ): Promise<StreamingRuntimeMeta> => {
        const queryParams = new URLSearchParams({
            user_id: userId,
            tier: tier.toLowerCase(),
            mode_family: "SOLVE",
            requested_mode: requestedMode,
        });
        const res = await fetch(`/api/v1/solve_v3_runtime_meta?${queryParams.toString()}`, {
            method: "GET",
            credentials: "include",
        });
        if (!res.ok) {
            const raw = await res.text();
            throw new Error(raw || "Failed to fetch runtime metadata");
        }
        const data = await res.json();
        return buildRuntimeMetaFromPayload(data, requestedMode);
    };

    // Tier-Aware Solve State
    const selectedGoal = 'solve';
    const [selectedSolveTier, setSelectedSolveTier] = useState<SolveTier>("FREE");
    const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
    const [subscriptionLoaded, setSubscriptionLoaded] = useState(false);
    const [subscriptionError, setSubscriptionError] = useState<string | null>(null);
    const [estimate, setEstimate] = useState<CreditsEstimateResponse | null>(null);
    const [estimateError, setEstimateError] = useState<string | null>(null);
    const [tokenPolicy, setTokenPolicy] = useState<TokenPolicy | null>(null);
    const [tokenPolicyLoaded, setTokenPolicyLoaded] = useState(false);
    const [tokenPolicyError, setTokenPolicyError] = useState<string | null>(null);
    const ocrMetadata: OcrMetadata = {
        ocr_confidence: 0,
        ocr_warnings: [],
        ocr_source: "image",
        ocr_engine: "snap_v2",
    };
    const [voiceFeatures, setVoiceFeatures] = useState<VoiceFeatures>({
        voice_confirmed: false,
    });

    // Compute token estimate and multi-question detection
    const tokenEstimate = useMemo(() => estimateTokens(query), [query]);
    const multiQuestionResult = useMemo(() => detectMultiQuestion(query), [query]);
    const tokenPolicyReady = tokenPolicyLoaded && !tokenPolicyError && !!tokenPolicy;
    const textInputMaxTokens = tokenPolicy?.text.input_max ?? 1;
    const textInputMaxChars = tokenPolicy?.text.input_max_chars ?? 1;
    const requestBudget: TokenBudgetPolicy | null = useMemo(() => {
        if (!tokenPolicyReady || !tokenPolicy) return null;
        return {
            textInputMax: tokenPolicy.text.input_max,
            textInputMaxChars: tokenPolicy.text.input_max_chars,
            systemAndSchemaBudget: tokenPolicy.request.system_and_schema_budget,
            expectedOutputBudget: tokenPolicy.request.expected_output_budget,
        };
    }, [tokenPolicyReady, tokenPolicy]);
    const requestFit = useMemo(
        () => (requestBudget ? willRequestFit(tokenEstimate.tokens, requestBudget) : { fits: false, estimatedTotal: 0, limit: 0, headroom: 0 }),
        [tokenEstimate.tokens, requestBudget]
    );

    // Determine if solve should be blocked
    const isInputTooLong = tokenPolicyReady
        ? tokenEstimate.tokens > textInputMaxTokens || query.length > textInputMaxChars
        : true;
    const isRequestTooLarge = !requestFit.fits;
    const hasMultipleQuestions = !multiQuestionConfirmed && multiQuestionResult.isMultiple && multiQuestionResult.confidence !== 'low';
    const tokenBlockReason = !tokenPolicyReady
        ? "Token policy unavailable. Please refresh."
        : isInputTooLong
            ? "Input too long. Please split into smaller parts."
            : isRequestTooLarge
                ? "Request too large for AI context. Please shorten."
                : hasMultipleQuestions
                    ? "Multiple questions detected. One at a time please."
                    : null;

    const router = useRouter();
    const subscriptionReady = subscriptionLoaded && !subscriptionError && !!subscription;
    const readySubscription = subscriptionReady ? subscription : null;
    const trustedProfile = readySubscription?.profile ?? null;
    const accountTier: SolveTier = readySubscription
        ? (readySubscription.plan.slug === "research"
            ? "RESEARCH"
            : readySubscription.plan.slug === "short"
                ? "SHORT"
                : readySubscription.plan.slug === "free"
                    ? "FREE"
                    : "STANDARD")
        : "FREE";
    const estimatedQuestionCount = activeTab === "text"
        ? Math.max(1, multiQuestionResult.suggestedSplits.length || 1)
        : 1;

    useEffect(() => {
        const stored = typeof window !== "undefined" ? localStorage.getItem("uask.solveTier") : null;
        if (stored === "FREE" || stored === "STANDARD" || stored === "RESEARCH" || stored === "SHORT") {
            setSelectedSolveTier(stored);
        }
    }, []);

    useEffect(() => {
        if (!subscriptionReady || !readySubscription) return;
        const hasStored = typeof window !== "undefined" ? localStorage.getItem("uask.solveTier") : null;
        if (hasStored) return;
        const defaultTier: SolveTier =
            readySubscription.plan.slug === "research"
                ? "RESEARCH"
                : readySubscription.plan.slug === "short"
                    ? "SHORT"
                    : readySubscription.plan.slug === "free"
                        ? "FREE"
                        : "STANDARD";
        setSelectedSolveTier(defaultTier);
        if (typeof window !== "undefined") {
            localStorage.setItem("uask.solveTier", defaultTier);
        }
    }, [subscriptionReady, readySubscription]);

    useEffect(() => {
        if (!subscriptionReady || !readySubscription) return;
        const runEstimate = async () => {
            try {
                setEstimateError(null);
                const inputType = activeTab === "snap" ? "snap" : activeTab === "voice" ? "voice" : "text";
                const response = await fetchCreditsEstimate({
                    tier: selectedSolveTier,
                    input_type: inputType,
                    asset_type: activeTab === "snap" ? "image" : "none",
                    question_count: estimatedQuestionCount,
                    addons: {
                        ocr: activeTab === "snap",
                        voice: activeTab === "voice",
                        verify: false,
                        plot: false,
                    },
                });
                setEstimate(response);
            } catch (e) {
                setEstimate(null);
                setEstimateError(e instanceof Error ? e.message : "Unable to estimate credits");
            }
        };
        void runEstimate();
    }, [subscriptionReady, readySubscription, selectedSolveTier, activeTab, estimatedQuestionCount]);

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) {
            router.push("/login");
            return;
        }

        const fetchHistory = async () => {
            try {
                const response = await fetch(`/api/v1/history?user_id=${userId}`);
                if (response.ok) {
                    const data = await response.json();
                    setHistory(data);
                }
            } catch (error) {
                console.error("Failed to fetch history:", error);
            }
        };

        const fetchOnline = async () => {
            try {
                const profileRes = await fetch(`/api/v1/user/profile?user_id=${userId}`);
                if (profileRes.ok) {
                    const profile = await profileRes.json();
                    setIsPublic(profile.is_public);

                    if (profile.is_public) {
                        const onlineRes = await fetch(`/api/v1/users/online`);
                        if (onlineRes.ok) {
                            setOnlineUsers(await onlineRes.json());
                        }
                    }
                }
            } catch (e) { console.error(e); }
        };

        // Fetch subscription for tier-aware solve UX
        const loadSubscription = async () => {
            try {
                const subData = await fetchSubscription(userId);
                setSubscription(subData);
                setSubscriptionError(null);
                setSubscriptionLoaded(true);
            } catch (e) {
                const message = e instanceof Error ? e.message : "Subscription unavailable";
                console.warn("Failed to load subscription:", message);
                setSubscriptionError("Unable to load subscription data. Please refresh or contact support.");
                setSubscriptionLoaded(true);
            }
        };
        const loadTokenPolicy = async () => {
            try {
                const policy = await fetchTokenPolicy();
                setTokenPolicy(policy);
                setTokenPolicyError(null);
                setTokenPolicyLoaded(true);
            } catch (e) {
                const message = e instanceof Error ? e.message : "Token policy unavailable";
                console.warn("Failed to load token policy:", message);
                setTokenPolicyError("Unable to load token policy. Please refresh or contact support.");
                setTokenPolicyLoaded(true);
            }
        };

        const restoreAttempt = async () => {
            const savedAttemptId = localStorage.getItem("uask.activeAttemptId");
            const savedQuery = localStorage.getItem("uask.activeQuery");
            if (savedAttemptId) {
                console.log("[RESTORE] Found active attempt:", savedAttemptId);
                setActiveAttemptId(savedAttemptId);
                if (savedQuery) setQuery(savedQuery);

                try {
                    setIsSolving(true);
                    setCurrentStage("Restoring session...");
                    setSolveStartTime(Date.now());

                    const res = await fetch(`/api/v1/attempt/${savedAttemptId}`);
                    if (!res.ok) throw new Error("Failed to fetch attempt");

                    const data = await res.json();
                    if (data.status === "success" && data.session_id) {
                        // Already solved
                        localStorage.removeItem("uask.activeAttemptId");
                        localStorage.removeItem("uask.activeQuery");
                        router.push(`/chat/${data.session_id}`);
                    } else if (data.status === "ambiguous") {
                        setIsClarifying(true);
                        setClarificationMessage(data.error_message || "Clarification needed.");
                    } else if (data.status === "failure") {
                        localStorage.removeItem("uask.activeAttemptId");
                        localStorage.removeItem("uask.activeQuery");
                        alert(`Previous attempt failed: ${data.error_message || "Unknown error"}`);
                        setIsSolving(false);
                        setSolveStartTime(null);
                    } else if (data.status === "pending" || data.status === "processing") {
                        setIsSolving(true);
                        // SSE listener will take over
                    } else {
                        setIsSolving(false);
                        setSolveStartTime(null);
                    }
                } catch (e) {
                    console.error("[RESTORE] Failed:", e);
                    localStorage.removeItem("uask.activeAttemptId");
                    setIsSolving(false);
                    setSolveStartTime(null);
                }
            }
        };

        fetchHistory();
        fetchOnline();
        loadSubscription();
        loadTokenPolicy();
        restoreAttempt();
        const interval = setInterval(fetchOnline, 30000);
        return () => clearInterval(interval);
    }, [router]);

    const handleSuggestionClick = (suggestion: Suggestion) => {
        setMathModeEnabled(true);

        if (suggestion.insertMode === 'replace') {
            // If Math Mode was off, this state update will initialize MathInput with this value
            setQuery(suggestion.latex);
            setMathValidityConfirmed(false);

            // If checking ref immediately (it might be stale if we just switched mode), try to set it
            if (mathInputRef.current) {
                mathInputRef.current.setValue(suggestion.latex);
                mathInputRef.current.focus();
            }
        } else {
            // Append
            if (mathInputRef.current) {
                mathInputRef.current.insert(suggestion.latex);
                mathInputRef.current.focus();
            } else {
                // If switching from text mode, just append to state
                setQuery(prev => prev + suggestion.latex);
                setMathValidityConfirmed(false);
            }
        }

        // Close the dropdown panel
        setActiveMode(null);
    };

    const handleClear = () => {
        setQuery("");
        setMultiQuestionConfirmed(false);
        setMathValidityConfirmed(false);
        setInputError(null);
        if (mathInputRef.current) {
            mathInputRef.current.setValue("");
            mathInputRef.current.focus();
        }
    };

    useEffect(() => {
        let timer: ReturnType<typeof setInterval> | undefined;
        if (voiceStage === 'recording') {
            timer = setInterval(() => setRecordingTime(prev => prev + 1), 1000);
        }
        return () => {
            if (timer) {
                clearInterval(timer);
            }
        };
    }, [voiceStage]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            const chunks: Blob[] = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunks.push(e.data);
            };

            recorder.onstop = async () => {
                const audioBlob = new Blob(chunks, { type: 'audio/webm' });
                await handleAudioUpload(audioBlob);
            };

            setMediaRecorder(recorder);
            recorder.start();
            setVoiceStage('recording');
            setRecordingTime(0);
        } catch (err) {
            console.error("Failed to start recording", err);
            setVoiceStage('error');
        }
    };

    const stopRecording = () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            setVoiceStage('processing');
        }
    };

    const handleAudioUpload = async (blob: Blob) => {
        const userId = localStorage.getItem("user_id") || "1";
        try {
            // 1. Create Session
            const sessionRes = await fetch('/api/v1/voice/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: parseInt(userId) })
            });
            const sessData = await sessionRes.json();
            const vsid = sessData.voice_session_id;
            // setVoiceSessionId(vsid);

            // 2. Upload Audio
            const formData = new FormData();
            formData.append('file', blob, 'voice.webm');
            await fetch(`/api/v1/voice/sessions/${vsid}/audio`, {
                method: 'POST',
                body: formData
            });

            // 3. Create Job
            const jobRes = await fetch(`/api/v1/voice/sessions/${vsid}/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ priority: 'high' })
            });
            const { job_id } = await jobRes.json();

            // 4. Poll
            pollVoiceJob(job_id);

        } catch (err) {
            console.error(err);
            setVoiceStage('error');
        }
    };

    const pollVoiceJob = async (jobId: number) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/v1/voice/jobs/${jobId}`);
                const data = await res.json();
                if (data.status === 'done') {
                    clearInterval(interval);
                    fetchVoiceArtifact(data.artifact_id);
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    setVoiceStage('error');
                }
            } catch (err) {
                console.error(err);
                clearInterval(interval);
                setVoiceStage('error');
            }
        }, 1000);
    };

    const fetchVoiceArtifact = async (artifactId: number) => {
        try {
            const res = await fetch(`/api/v1/voice/artifacts/${artifactId}`);
            const data = await res.json();
            setVoiceArtifact(data);
            setQuery(data.normalized_math_text);
            if (mathInputRef.current) mathInputRef.current.setValue(data.normalized_math_text);
            setVoiceStage('review');
        } catch (err) {
            console.error(err);
            setVoiceStage('error');
        }
    };

    const handleConfirmVoice = async () => {
        if (!voiceArtifact || isSolving) return;
        const transcriptError = validateMathQuery(voiceArtifact.transcript_raw || "");
        const normalizedError = validateMathQuery(query || "");
        if (transcriptError || normalizedError) {
            setInputError(transcriptError || normalizedError);
            return;
        }
        setIsSolving(true);
        setVoiceFeatures((prev) => ({
            ...prev,
            voice_confirmed: true,
            voice_used: true,
        }));
        try {
            await fetch(`/api/v1/voice/artifacts/${voiceArtifact.id}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    confirmed_transcript_text: voiceArtifact.transcript_raw,
                    confirmed_normalized_math_text: query
                })
            });
            await handleSolve(undefined, { voice_confirmed: true, voice_used: true });
        } catch (err) {
            console.error(err);
            setIsSolving(false);
        }
    };

    const handleDebugRuntimeMeta = async () => {
        if (isSolving) return;
        const userId = localStorage.getItem("user_id") || "1";
        const requestedMode = (selectedSolveTier === "FREE" || selectedSolveTier === "SHORT") ? "minimal" : "detailed";

        setRuntimeDebugLoading(true);
        setRuntimeDebugError(null);
        try {
            const runtimeMeta = await fetchSolveRuntimeMeta(userId, selectedSolveTier, requestedMode);
            setRuntimeDebugMeta(runtimeMeta);
            setShowRuntimeDebug(true);
        } catch (err) {
            console.error("[RUNTIME_DEBUG] Failed to load solve runtime metadata:", err);
            setRuntimeDebugError((err as Error).message || "Failed to fetch runtime metadata");
            setShowRuntimeDebug(true);
        } finally {
            setRuntimeDebugLoading(false);
        }
    };

    const handleSolve = async (textOverride?: string, featureOverrides?: Record<string, unknown>) => {
        if (isSolving) return;
        if (!tokenPolicyReady) {
            setInputError("Token policy unavailable. Please refresh.");
            return;
        }

        const userId = localStorage.getItem("user_id") || "1";
        const mathFieldValue = mathModeEnabled && mathInputRef.current?.getValue
            ? mathInputRef.current.getValue()
            : "";
        const textToSolve = textOverride ?? (mathFieldValue.trim() ? mathFieldValue : query);

        const validationError = validateMathQuery(textToSolve);
        const isOverridableError = validationError === INPUT_ERROR_BLOCKED || validationError === INPUT_ERROR_NOT_MATH;

        if (validationError) {
            if (isOverridableError) {
                if (!mathValidityConfirmed) {
                    setInputError(validationError);
                    return;
                }
            } else {
                setInputError(validationError);
                return;
            }
        }

        setIsSolving(true);
        setStreamingContent("");
        setCurrentStage("Initializing...");
        setStreamingTelemetry(null);
        setStreamingMeta(null);
        setSolveStartTime(Date.now());

        // Reset Phase 1 Clarification
        setIsClarifying(false);
        setClarificationMessage("");
        setClarificationResponse("");
        setClarificationHistory([]);
        setActiveAttemptId(null);

        try {
            const streamCandidates = ["/api/v1/solve_v3_stream"];
            const requestedMode = (selectedSolveTier === 'FREE' || selectedSolveTier === 'SHORT') ? 'minimal' : 'detailed';

            void fetchSolveRuntimeMeta(userId, selectedSolveTier, requestedMode)
                .then((runtimeMeta) => {
                    setStreamingMeta((prev) => ({ ...(prev || {}), ...runtimeMeta }));
                })
                .catch((metaErr) => {
                    console.warn("[SOLVER_STREAM] Runtime meta prefetch failed:", metaErr);
                });

            const features = {
                ocr_used: activeTab === 'snap',
                voice_used: activeTab === 'voice',
                plot_requested: graphMode !== 'off',
                ...(activeTab === 'snap' ? ocrMetadata : {}),
                ...(activeTab === 'voice' ? voiceFeatures : {}),
                ...featureOverrides,
            };

            let response: Response | null = null;
            let lastFetchError: unknown = null;
            for (const endpoint of streamCandidates) {
                try {
                    response = await fetch(`${endpoint}?user_id=${encodeURIComponent(userId)}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            confirmed_text: textToSolve,
                            requested_mode: requestedMode,
                            tier: selectedSolveTier.toLowerCase(),
                            trusted_context: {
                                learning_mode: selectedGoal,
                                grade_level: trustedProfile?.grade_level || undefined,
                                region_country: trustedProfile?.region_country || undefined,
                                region_state_province: trustedProfile?.region_state_province || undefined
                            },
                            features_used: features,
                            graph_mode: graphMode,
                            attach_to_step_id: attachToStepId,
                            force_validity: mathValidityConfirmed
                        })
                    });
                    break;
                } catch (fetchErr) {
                    lastFetchError = fetchErr;
                    response = null;
                }
            }

            if (!response) throw (lastFetchError instanceof Error ? lastFetchError : new Error("Network error"));
            if (!response.ok) {
                const message = await response.text();
                throw new Error(message || "Solve request failed");
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No reader available");

            const decoder = new TextDecoder();
            let accumulatedBuffer = "";
            let currentEvent = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                accumulatedBuffer += decoder.decode(value, { stream: true });
                const lines = accumulatedBuffer.split('\n');
                accumulatedBuffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (!trimmedLine) continue;

                    if (trimmedLine.startsWith('event: ')) {
                        currentEvent = trimmedLine.slice(7).trim();
                    } else if (trimmedLine.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(trimmedLine.slice(6));
                            if (currentEvent === 'delta') {
                                setStreamingContent(prev => prev + data.text);
                            } else if (currentEvent === 'stage') {
                                setCurrentStage(data.name);
                            } else if (currentEvent === 'telemetry') {
                                setStreamingTelemetry(data?.telemetry ?? data);
                            } else if (currentEvent === 'done') {
                                if (data.ok) {
                                    setSolveProgress(100);
                                    localStorage.removeItem("uask.activeAttemptId");
                                    localStorage.removeItem("uask.activeQuery");
                                    setTimeout(() => router.push(`/chat/${data.session_id}`), 500);
                                } else if (data.error?.code === "ambiguous_response") {
                                    setIsClarifying(true);
                                    setClarificationMessage(data.error.refusal || data.error.message);
                                    setActiveAttemptId(data.error.request_id);
                                    if (data.error.request_id) {
                                        localStorage.setItem("uask.activeAttemptId", data.error.request_id);
                                        localStorage.setItem("uask.activeQuery", textToSolve);
                                    }
                                } else {
                                    localStorage.removeItem("uask.activeAttemptId");
                                    localStorage.removeItem("uask.activeQuery");
                                    throw new Error(data.error?.message || "Solve failed");
                                }
                            } else if (currentEvent === 'meta') {
                                setStreamingMeta(data);
                                if (data.attempt_id) {
                                    setActiveAttemptId(data.attempt_id);
                                    localStorage.setItem("uask.activeAttemptId", data.attempt_id);
                                }
                                const parsedMeta = buildRuntimeMetaFromPayload(data, requestedMode);
                                setStreamingMeta((prev) => ({ ...(prev || {}), ...parsedMeta }));
                                if (parsedMeta.request_id) {
                                    localStorage.setItem("uask.activeAttemptId", parsedMeta.request_id);
                                    localStorage.setItem("uask.activeQuery", textToSolve);
                                    setActiveAttemptId(parsedMeta.request_id);
                                }
                            }
                        } catch (e) {
                            console.error("Error parsing SSE data", e);
                        }
                    }
                }
            }
        } catch (err) {
            console.error("[SOLVER_STREAM] Error:", err);
            alert((err as Error).message || "Failed to generate solution.");
        } finally {
            setIsSolving(false);
            setSolveStartTime(null);
        }
    };

    const handleClarify = async () => {
        if (!activeAttemptId || !clarificationResponse.trim() || isSolving) return;

        setIsSolving(true);
        setSolveStartTime(Date.now());
        setCurrentStage("Resolving ambiguity...");

        try {
            const userId = localStorage.getItem("user_id") || "1";
            const res = await fetch(`/api/v1/solve/clarify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    attempt_id: activeAttemptId,
                    user_id: userId,
                    user_response: clarificationResponse
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Clarification failed");
            }

            const data = await res.json();
            if (data.status === "success" && data.session_id) {
                setSolveProgress(100);
                localStorage.removeItem("uask.activeAttemptId");
                localStorage.removeItem("uask.activeQuery");
                setTimeout(() => router.push(`/chat/${data.session_id}`), 500);
            } else if (data.status === "ambiguous") {
                setClarificationHistory(prev => [...prev, clarificationResponse]);
                setClarificationMessage(data.clarifier_question || "Still ambiguous. Please provide more detail.");
                setClarificationResponse("");
            } else {
                localStorage.removeItem("uask.activeAttemptId");
                localStorage.removeItem("uask.activeQuery");
                throw new Error(data.error || "Ambiguity resolution failed.");
            }
        } catch (err) {
            console.error("[CLARIFY] Error:", err);
            alert((err as Error).message || "Failed to clarify.");
        } finally {
            setIsSolving(false);
            setSolveStartTime(null);
        }
    };
    useEffect(() => {
        if (!isSolving || !solveStartTime) {
            setSolveProgress(0);
            return;
        }

        const tick = setInterval(() => {
            const elapsed = Date.now() - solveStartTime;

            // Artificial progress bar logic adjusted for streaming
            if (elapsed < 15000) {
                const p = Math.min(95, 5 + Math.floor(elapsed / 200) * 1.5);
                setSolveProgress(p);
            } else {
                setSolveProgress(98);
            }
        }, 250); // 250ms tick as requested (Part F1)

        return () => clearInterval(tick);
    }, [isSolving, solveStartTime]);

    const [elapsedNow, setElapsedNow] = useState<number>(Date.now());
    useEffect(() => {
        if (!isSolving || !solveStartTime) return;
        setElapsedNow(Date.now());
        const timer = window.setInterval(() => setElapsedNow(Date.now()), 100);
        return () => window.clearInterval(timer);
    }, [isSolving, solveStartTime]);

    const elapsedMs = solveStartTime ? Math.max(0, elapsedNow - solveStartTime) : 0;
    const formatElapsed = (ms: number) => {
        const totalTenths = Math.floor(ms / 100);
        const minutes = Math.floor(totalTenths / 600);
        const seconds = Math.floor((totalTenths % 600) / 10);
        const tenths = totalTenths % 10;
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths}`;
    };

    // pipelineStages is now a state variable defined at the top


    return (
        <div className="solve-ui bg-background-light dark:bg-background-dark min-h-screen text-slate-900 dark:text-slate-100 font-display transition-colors duration-200">
            <DashboardNavBar />

            <main className="max-w-6xl mx-auto px-4 py-8 md:py-12">
                {/* Hand-Drawn Title Section */}
                <header className="mb-12 text-center">
                    <h2 className="sketch-title mb-2 flex items-center justify-center gap-3">
                        New Solve
                        <span className="text-xs font-black px-2 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-lg border border-blue-200 dark:border-blue-800 rotate-3 tracking-tighter">
                            uask AI v1.0
                        </span>
                    </h2>
                    <p className="sketch-subtitle mx-auto max-w-2xl px-4">
                        Select your preferred input method and define the context for the best tutor results.
                    </p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    {/* Main Interaction Area */}
                    <div className="lg:col-span-8 space-y-6">

                        {/* Tier-Aware Controls Section */}
                        <div className={`${tierSectionColor} dark:bg-slate-900 rounded-2xl shadow-xl border-2 border-slate-300 dark:border-slate-800 p-6 sketch-container relative transition-colors duration-1000`} style={{ filter: 'url(#handWobble) url(#roughpaper)' }}>
                            <div className="flex flex-col md:flex-row gap-8 items-center justify-between">
                                {/* Goal Section */}
                                <div className="flex flex-col gap-2">
                                    <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500 ml-1">Goal</h3>
                                    <button className="wobbly-button px-6 py-2 flex items-center gap-2 bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-all" style={{ filter: 'url(#handWobble) url(#roughpaper)' }}>
                                        <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-xl hand-drawn-icon">bolt</span>
                                        <span className="font-bold text-lg tracking-tight">Solve</span>
                                    </button>
                                </div>

                                {/* Tier Selector Section */}
                                <div className="flex flex-col gap-2 flex-grow max-w-[450px]">
                                    <div className="flex justify-between items-end mb-1">
                                        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500 ml-1">Tier</h3>
                                        {readySubscription && estimate && (
                                            <div className="scale-90 origin-right">
                                                <CostPreview
                                                    perQuestionCost={estimate.per_question_credits}
                                                    questionCount={estimatedQuestionCount}
                                                    breakdown={estimate.breakdown}
                                                    creditsRemaining={readySubscription.usage.credits_remaining}
                                                />
                                            </div>
                                        )}
                                    </div>
                                    <SegmentedControl
                                        options={[
                                            { value: "FREE", label: "Free", icon: "bolt" },
                                            { value: "SHORT", label: "Short", icon: "bolt" },
                                            { value: "STANDARD", label: "Standard", icon: "school" },
                                            { value: "RESEARCH", label: "Research", icon: "science" },
                                        ]}
                                        value={selectedSolveTier}
                                        onChange={(v) => {
                                            if (v === "FREE" || v === "STANDARD" || v === "RESEARCH" || v === "SHORT") {
                                                setSelectedSolveTier(v as SolveTier);
                                                if (typeof window !== "undefined") {
                                                    localStorage.setItem("uask.solveTier", v);
                                                }
                                            }
                                        }}
                                        size="md"
                                        className="solve-segmented"
                                    />
                                </div>
                            </div>

                            {/* Decorative Flourish */}
                            <div className="absolute -top-4 -right-4 opacity-10 pointer-events-none hidden lg:block">
                                <svg width="100" height="100" viewBox="0 0 100 100" fill="none" className="stroke-slate-400">
                                    <path d="M10 20C30 15 80 10 90 30C100 50 20 80 10 70C0 60 50 40 80 50" strokeWidth="2" strokeLinecap="round" />
                                </svg>
                            </div>
                        </div>





                        {/* Plot Mode Section - Global with Larger Font & Random Light BG */}
                        <div className={`flex flex-col gap-3 px-6 py-4 ${plotModeColor} dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 transition-colors duration-1000`}>
                            <div className="flex items-center gap-4">
                                <span className="material-symbols-outlined text-primary text-2xl">area_chart</span>
                                <span className="text-lg font-bold text-slate-800 dark:text-slate-100 whitespace-nowrap">
                                    Plot Mode
                                </span>

                                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mx-4 flex-1 text-center truncate">
                                    {graphMode === 'off' && "No plots will be generated"}
                                    {graphMode === 'auto' && "AI will generate plots when helpful"}
                                    {graphMode === 'on' && "Force plot generation when possible"}
                                </p>

                                <div className="flex bg-white/50 dark:bg-slate-800 rounded-lg p-1.5 shrink-0 shadow-sm border border-slate-200/50 dark:border-slate-700">
                                    {(['off', 'auto', 'on'] as const).map((mode) => (
                                        <button
                                            key={mode}
                                            type="button"
                                            onClick={() => setGraphMode(mode)}
                                            className={`px-4 py-1.5 text-sm font-bold rounded-md transition-all ${graphMode === mode
                                                ? "bg-white dark:bg-slate-600 text-primary shadow-md scale-105"
                                                : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-700/50"
                                                }`}
                                        >
                                            {mode.charAt(0).toUpperCase() + mode.slice(1)}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Input Mode Tabs */}
                        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl shadow-black/5 border border-slate-200 dark:border-slate-800 transition-colors">
                            <div className="flex p-4 gap-4 justify-center border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/20">
                                <button
                                    onClick={() => setActiveTab('text')}
                                    className={`solve-tab solve-tab--text ${activeTab === 'text' ? 'solve-tab--active' : ''}`}
                                >
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-1 solve-tab-icon">
                                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" style={{ strokeDasharray: '40, 4' }} />
                                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                                    </svg>
                                    <span className="solve-tab-label">Text</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('snap')}
                                    className={`solve-tab solve-tab--snap ${activeTab === 'snap' ? 'solve-tab--active dashed-sketch-border' : ''}`}
                                >
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-1 solve-tab-icon">
                                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" style={{ strokeDasharray: '50, 5' }} />
                                        <circle cx="12" cy="13" r="4" strokeDasharray="2,2" />
                                    </svg>
                                    <span className="solve-tab-label">Snap & Solve</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('voice')}
                                    className={`solve-tab solve-tab--voice ${activeTab === 'voice' ? 'solve-tab--active circle-sketch' : ''}`}
                                >
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-1 solve-tab-icon">
                                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" style={{ strokeDasharray: '30, 3' }} />
                                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                                        <line x1="12" y1="19" x2="12" y2="22" />
                                        <line x1="8" y1="22" x2="16" y2="22" />
                                    </svg>
                                    <span className="solve-tab-label">Voice</span>
                                </button>
                            </div>

                            {/* Tab Content */}
                            <div className="p-6">
                                {isClarifying && (
                                    <div className="mb-6 animate-in fade-in slide-in-from-top-4 duration-500">
                                        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 shadow-sm">
                                            <div className="flex items-start gap-4 mb-4">
                                                <div className="mt-1 bg-amber-100 dark:bg-amber-900/40 p-2 rounded-lg">
                                                    <span className="material-symbols-outlined text-amber-600 dark:text-amber-400">help_center</span>
                                                </div>
                                                <div className="flex-1">
                                                    <h3 className="text-lg font-bold text-amber-900 dark:text-amber-100 mb-1">Clarification Needed</h3>
                                                    <p className="text-amber-800/80 dark:text-amber-200/80 text-sm leading-relaxed">
                                                        {clarificationMessage}
                                                    </p>
                                                </div>
                                            </div>

                                            {clarificationHistory.length > 0 && (
                                                <div className="mb-4 pl-12 space-y-2 opacity-60">
                                                    {clarificationHistory.map((hist, i) => (
                                                        <div key={i} className="text-xs italic border-l-2 border-amber-200 dark:border-amber-800 pl-3 py-1">
                                                            &ldquo;{hist}&rdquo;
                                                        </div>
                                                    ))}
                                                </div>
                                            )}

                                            <div className="pl-12">
                                                <textarea
                                                    value={clarificationResponse}
                                                    onChange={(e) => setClarificationResponse(e.target.value)}
                                                    placeholder="Provide more detail here..."
                                                    className="w-full bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-800 rounded-lg p-3 text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-amber-500/20 transition-all resize-none min-h-[100px]"
                                                />
                                                <div className="mt-4 flex gap-3">
                                                    <button
                                                        onClick={handleClarify}
                                                        disabled={isSolving || !clarificationResponse.trim()}
                                                        className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-amber-600/20 transition-all flex items-center gap-2"
                                                    >
                                                        {isSolving ? "Submitting..." : "Send Clarification"}
                                                        <span className="material-symbols-outlined text-sm">send</span>
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            setIsClarifying(false);
                                                            localStorage.removeItem("uask.activeAttemptId");
                                                            localStorage.removeItem("uask.activeQuery");
                                                            setActiveAttemptId(null);
                                                        }}
                                                        className="text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/40 px-4 py-2 rounded-lg font-medium transition-colors text-sm"
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}


                                {activeTab === 'snap' && (
                                    <div className="space-y-3">
                                        {useSnapSolveUploadPanelV2 ? (
                                            <SnapSolveInputPanel
                                                tier={selectedSolveTier}
                                                requestedMode={selectedSolveTier === "FREE" ? "minimal" : "detailed"}
                                                onResolveText={(text, featureOverrides) => {
                                                    setQuery(text);
                                                    setMathValidityConfirmed(false);
                                                    if (mathInputRef.current) {
                                                        mathInputRef.current.setValue(text);
                                                    }
                                                    return handleSolve(text, {
                                                        ocr_used: true,
                                                        ocr_engine: "openai",
                                                        ...(featureOverrides || {}),
                                                    });
                                                }}
                                            />
                                        ) : (
                                            <SnapSolveV2
                                                onUseText={(text) => {
                                                    setQuery(text);
                                                    setMathValidityConfirmed(false);
                                                    setActiveTab("text");
                                                }}
                                                onSolveText={(text) => {
                                                    setQuery(text);
                                                    setMathValidityConfirmed(false);
                                                    if (mathInputRef.current) {
                                                        mathInputRef.current.setValue(text);
                                                    }
                                                    handleSolve(text);
                                                }}
                                                requestedMode={selectedSolveTier === "RESEARCH" ? "detailed" : "minimal"}
                                            />
                                        )}
                                    </div>
                                )}

                                {activeTab === 'text' && (
                                    <div className="flex flex-col gap-6 relative">
                                        {/* Input Mode Selector (Expression / Word Problem / Graphing) */}


                                        {/* Include Graph Toggle */}


                                        {/* Math Symbol Mode Bar */}
                                        <div className="flex items-center gap-2">
                                            <div className="flex-1 flex gap-2 overflow-x-auto pb-2 scrollbar-hide items-center">
                                                {MODES.slice(0, 5).map(mode => (
                                                    <button
                                                        key={mode.id}
                                                        onClick={() => {
                                                            setActiveMode(mode.id === activeMode ? null : mode.id);
                                                            setIsSeeAllOpen(false);
                                                        }}
                                                        className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all border ${activeMode === mode.id
                                                            ? 'bg-primary text-white border-primary shadow-lg shadow-primary/25'
                                                            : 'bg-white dark:bg-slate-900 text-slate-500 border-slate-200 dark:border-slate-700 hover:border-primary/50'
                                                            }`}
                                                    >
                                                        {mode.label}
                                                    </button>
                                                ))}
                                            </div>

                                            {/* See All Dropdown */}
                                            <div className="relative pb-2">
                                                <button
                                                    onClick={() => setIsSeeAllOpen(!isSeeAllOpen)}
                                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold whitespace-nowrap transition-all border ${isSeeAllOpen || MODES.slice(5).some(m => m.id === activeMode)
                                                        ? 'bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-600 shadow-sm'
                                                        : 'bg-white dark:bg-slate-900 text-slate-500 border-slate-200 dark:border-slate-700 hover:border-primary/50'
                                                        }`}
                                                >
                                                    <span>See All</span>
                                                    <span className={`material-symbols-outlined text-lg transition-transform ${isSeeAllOpen ? 'rotate-180' : ''}`}>expand_more</span>
                                                </button>

                                                {isSeeAllOpen && (
                                                    <div className="absolute top-full right-0 mt-2 w-56 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.2)] z-[100] overflow-hidden animate-in fade-in zoom-in-95 duration-100 origin-top-right">
                                                        <div className="max-h-80 overflow-y-auto custom-scrollbar">
                                                            {MODES.slice(5).map((mode) => (
                                                                <button
                                                                    key={mode.id}
                                                                    onClick={() => {
                                                                        setActiveMode(mode.id);
                                                                        setIsSeeAllOpen(false);
                                                                    }}
                                                                    className={`w-full py-4 text-center transition-colors border-b border-slate-50 dark:border-slate-800/50 last:border-0 font-bold text-slate-700 dark:text-slate-200 hover:bg-primary/5 hover:text-primary dark:hover:bg-primary/10 ${activeMode === mode.id ? 'bg-primary/5 text-primary' : ''}`}
                                                                >
                                                                    {mode.label.toLowerCase()}
                                                                </button>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="relative group z-10">
                                            <div className={`bg-white dark:bg-slate-900 border rounded-xl transition-all shadow-sm flex flex-col min-h-[190px] ${inputError
                                                ? 'border-red-500 ring-1 ring-red-500 bg-red-50/10'
                                                : activeMode
                                                    ? 'border-primary ring-1 ring-primary'
                                                    : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                                                }`}>

                                                {/* Suggestions Dropdown (Combobox) */}
                                                {activeMode && (
                                                    <div className="absolute top-full left-0 right-0 mt-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl overflow-hidden z-50">
                                                        <div className="bg-slate-50 dark:bg-slate-800/50 px-4 py-2 border-b border-slate-100 dark:border-slate-800 text-xs font-bold text-slate-500 uppercase tracking-widest flex justify-between">
                                                            <span>{MODES.find(m => m.id === activeMode)?.label} Templates</span>
                                                            <span className="text-[10px]">Select to insert</span>
                                                        </div>
                                                        <div className="max-h-64 overflow-y-auto p-1">
                                                            {MODES.find(m => m.id === activeMode)?.suggestions.map((suggestion, idx) => (
                                                                <button
                                                                    key={idx}
                                                                    onClick={() => handleSuggestionClick(suggestion)}
                                                                    className="w-full text-left px-4 py-3 rounded-lg hover:bg-primary/5 hover:text-primary dark:hover:bg-primary/10 transition-colors flex items-center gap-3 group/item"
                                                                >
                                                                    <span className="w-8 h-8 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 group-hover/item:text-primary transition-colors text-xs font-mono">
                                                                        TeX
                                                                    </span>
                                                                    <div className="flex-1 font-medium text-slate-700 dark:text-slate-200">
                                                                        <MathRendererMJX content={`\\(${suggestion.title}\\)`} inline className="pointer-events-none" />
                                                                    </div>
                                                                    <span className="material-symbols-outlined text-slate-300 group-hover/item:text-primary text-sm opacity-0 group-hover/item:opacity-100 transition-all">
                                                                        arrow_forward
                                                                    </span>
                                                                </button>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {mathModeEnabled ? (
                                                    <MathInput
                                                        ref={mathInputRef}
                                                        value={query}
                                                        onChange={(value) => {
                                                            // Enforce character limit
                                                            if (textInputMaxChars <= 0 || value.length <= textInputMaxChars) {
                                                                setQuery(value);
                                                                setMultiQuestionConfirmed(false);
                                                                setMathValidityConfirmed(false);
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        maxLength={textInputMaxChars || undefined}
                                                        onPaste={(pastedText) => {
                                                            if (textInputMaxChars > 0 && pastedText.length > textInputMaxChars) {
                                                                setInputError(`Pasted text was truncated to ${textInputMaxChars} characters.`);
                                                            }
                                                            setMultiQuestionConfirmed(false);
                                                            setMathValidityConfirmed(false);
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            if (checkResult.isMultiple && checkResult.confidence !== 'low') {
                                                                setSuggestedSplits(autoSplitQuestions(pastedText));
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        className="flex-1 p-2 min-h-[180px]"
                                                    />
                                                ) : (
                                                    <textarea
                                                        value={query}
                                                        onChange={(event) => {
                                                            const value = event.target.value;
                                                            // Enforce character limit
                                                            if (textInputMaxChars <= 0 || value.length <= textInputMaxChars) {
                                                                setQuery(value);
                                                                setMultiQuestionConfirmed(false);
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        onPaste={(event) => {
                                                            const pastedText = event.clipboardData.getData('text');
                                                            if (textInputMaxChars > 0 && pastedText.length > textInputMaxChars) {
                                                                event.preventDefault();
                                                                const truncated = pastedText.slice(0, textInputMaxChars);
                                                                setQuery(truncated);
                                                                setInputError(`Pasted text was truncated to ${textInputMaxChars} characters.`);
                                                            }
                                                            setMultiQuestionConfirmed(false);
                                                            setMathValidityConfirmed(false);
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            if (checkResult.isMultiple && checkResult.confidence !== 'low') {
                                                                setSuggestedSplits(autoSplitQuestions(pastedText));
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        maxLength={textInputMaxChars || undefined}
                                                        className={`flex-1 p-4 ${freeTypeColor} dark:bg-transparent outline-none text-slate-700 dark:text-slate-200 text-lg leading-relaxed resize-none min-h-[180px] transition-colors duration-500 rounded-t-xl`}
                                                        style={{
                                                            whiteSpace: 'pre-wrap',
                                                            overflowWrap: 'break-word',
                                                            wordBreak: 'normal',
                                                            hyphens: 'auto',
                                                        }}
                                                        placeholder="Type your question..."
                                                    />
                                                )}

                                                {/* Token/Character Status */}
                                                <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-800">
                                                    <InputStatus
                                                        text={query}
                                                        tokenEstimate={tokenEstimate}
                                                        maxInputTokens={textInputMaxTokens}
                                                        maxInputChars={textInputMaxChars}
                                                        multiQuestionResult={multiQuestionResult}
                                                        isConfirmed={multiQuestionConfirmed}
                                                        onSplitClick={() => {
                                                            setSuggestedSplits(autoSplitQuestions(query));
                                                            setShowSplitModal(true);
                                                        }}
                                                    />
                                                </div>

                                                {/* Action Bar inside Input */}
                                                <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 rounded-b-xl">
                                                    <div className="flex items-center gap-3 text-xs text-slate-400">
                                                        <span className="material-symbols-outlined text-sm">keyboard</span>
                                                        <span>{mathModeEnabled ? "Math Mode Active" : "Free Type Mode"}</span>
                                                        <button
                                                            type="button"
                                                            onClick={() => setMathModeEnabled(enabled => !enabled)}
                                                            className={`relative w-10 h-5 rounded-full transition-colors ${mathModeEnabled ? "bg-primary" : "bg-slate-300 dark:bg-slate-700"}`}
                                                        >
                                                            <div className={`absolute top-1 left-1 size-3 bg-white rounded-full transition-transform ${mathModeEnabled ? "translate-x-5" : ""}`}></div>
                                                        </button>
                                                    </div>
                                                    <div className="flex flex-1 flex-col items-center">
                                                        <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                                            Using YouAsk AI
                                                        </span>
                                                        {isSolving && (
                                                            <div className="mt-1 h-1 w-24 rounded-full bg-emerald-100 dark:bg-emerald-900/40 overflow-hidden">
                                                                <div className="h-full w-full bg-emerald-500 animate-pulse"></div>
                                                            </div>
                                                        )}
                                                    </div>
                                                    {inputError && (
                                                        <div className="flex flex-col gap-1 mt-1">
                                                            <span className="text-xs text-red-500 font-medium">{inputError}</span>
                                                            {(inputError === INPUT_ERROR_BLOCKED || inputError === INPUT_ERROR_NOT_MATH) && (
                                                                <button
                                                                    onClick={() => {
                                                                        setMathValidityConfirmed(true);
                                                                        setInputError(null);
                                                                    }}
                                                                    className="text-xs font-bold text-primary hover:underline self-start flex items-center gap-1"
                                                                >
                                                                    <span className="material-symbols-outlined text-[14px]">check_circle</span>
                                                                    This is a valid math question
                                                                </button>
                                                            )}
                                                        </div>
                                                    )}
                                                    {mathValidityConfirmed && !inputError && (
                                                        <div className="flex items-center gap-1.5 mt-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium animate-in fade-in duration-300">
                                                            <span className="material-symbols-outlined text-[14px]">verified_user</span>
                                                            Validity confirmed
                                                        </div>
                                                    )}
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={handleClear}
                                                            className="flex items-center gap-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 px-4 py-2 rounded-lg font-medium transition-colors text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                                                        >
                                                            <span className="material-symbols-outlined text-sm">backspace</span>
                                                            Clear
                                                        </button>
                                                        <button
                                                            onClick={() => handleSolve()}
                                                            disabled={isSolving || isInputTooShort(query) || !!tokenBlockReason || isBlockingInputError(inputError)}
                                                            title={tokenBlockReason || undefined}
                                                            className="relative flex items-center gap-2 bg-primary hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-bold transition-all shadow-lg shadow-primary/25 text-sm overflow-hidden"
                                                        >
                                                            {isSolving && (
                                                                <div className="absolute inset-0">
                                                                    <div className="h-full bg-white/20 transition-all" style={{ width: `${solveProgress}%` }}></div>
                                                                </div>
                                                            )}
                                                            {isSolving ? `Solving... ${solveProgress}%` : 'Solve'}
                                                            <span className="material-symbols-outlined text-sm">auto_awesome</span>
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="mt-8 flex justify-end">
                                            <button
                                                type="button"
                                                onClick={handleDebugRuntimeMeta}
                                                disabled={isSolving || runtimeDebugLoading}
                                                className="flex items-center gap-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 px-3 py-1.5 rounded-lg font-semibold transition-colors text-xs hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <span className="material-symbols-outlined text-sm">bug_report</span>
                                                {runtimeDebugLoading ? "Loading..." : "Debug"}
                                            </button>
                                        </div>

                                        {/* Live Math Preview */}
                                        <div className="mt-6">
                                            <LiveMathPreview content={query} />
                                        </div>
                                    </div>
                                )}
                                {(!isClarifying && activeTab === 'voice') && (
                                    <div className="flex flex-col gap-6 items-center justify-center min-h-[400px]">
                                        {voiceStage === 'idle' && (
                                            <div className="text-center space-y-6">
                                                <div
                                                    onClick={startRecording}
                                                    className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center text-primary cursor-pointer hover:scale-110 transition-all hover:bg-primary/20 group mx-auto"
                                                >
                                                    <span className="material-symbols-outlined text-4xl group-hover:animate-pulse">mic</span>
                                                </div>
                                                <div>
                                                    <h3 className="text-lg font-bold">Tap to Start</h3>
                                                    <p className="text-sm text-slate-500">I&apos;ll transcribe your math speech into LaTeX.</p>
                                                    <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mt-2">
                                                        Using YouAsk voice AI to script
                                                    </p>
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'recording' && (
                                            <div className="h-64 flex flex-col items-center justify-center space-y-8 animate-in fade-in duration-300">
                                                <div className="flex gap-1.5 h-16 items-center">
                                                    {[...Array(20)].map((_, i) => (
                                                        <div
                                                            key={i}
                                                            className="w-1 bg-primary rounded-full animate-voice-bar"
                                                            style={{
                                                                height: `${20 + Math.random() * 80}%`,
                                                                animationDelay: `${i * 0.05}s`
                                                            }}
                                                        />
                                                    ))}
                                                </div>
                                                <div className="text-center space-y-4">
                                                    <div className="text-4xl font-mono font-bold text-slate-800 dark:text-slate-100">
                                                        00:{recordingTime.toString().padStart(2, '0')}
                                                    </div>
                                                    <button
                                                        onClick={stopRecording}
                                                        className="bg-red-500 hover:bg-red-600 text-white px-8 py-3 rounded-full font-bold flex items-center gap-2 transition-all hover:scale-105 active:scale-95 shadow-lg shadow-red-500/20"
                                                    >
                                                        <span className="material-symbols-outlined">stop_circle</span>
                                                        Stop Recording
                                                    </button>
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'processing' && (
                                            <div className="h-64 flex flex-col items-center justify-center space-y-6 animate-in fade-in duration-300">
                                                <div className="relative size-20">
                                                    <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                                                    <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                                    <div className="absolute inset-0 flex items-center justify-center">
                                                        <span className="material-symbols-outlined text-primary text-3xl animate-pulse">auto_awesome</span>
                                                    </div>
                                                </div>
                                                <div className="text-center">
                                                    <h3 className="text-xl font-bold dark:text-white">AI Transcribing...</h3>
                                                    <p className="text-sm text-slate-500">Normalizing your math for the tutor.</p>
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'review' && (
                                            <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
                                                {/* Ambiguity Clarifier Integration */}
                                                {voiceArtifact?.clarifier_question && (
                                                    <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-900/30 rounded-2xl p-6 space-y-4 shadow-sm">
                                                        <div className="flex items-start gap-4 text-amber-800 dark:text-amber-200">
                                                            <div className="size-10 bg-amber-100 dark:bg-amber-900/50 rounded-full flex items-center justify-center shrink-0">
                                                                <span className="material-symbols-outlined">help_center</span>
                                                            </div>
                                                            <div className="space-y-1">
                                                                <p className="text-[10px] font-black uppercase tracking-tight opacity-60">Help us clarify your intent</p>
                                                                <p className="text-lg font-bold leading-tight">{voiceArtifact.clarifier_question.question}</p>
                                                            </div>
                                                        </div>
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 ml-14">
                                                            {voiceArtifact.clarifier_question.options.map((opt: ClarifierOption, idx: number) => {
                                                                const isSelected = query === opt.value;
                                                                return (
                                                                    <button
                                                                        key={idx}
                                                                        onClick={() => {
                                                                            setQuery(opt.value);
                                                                            if (mathInputRef.current) mathInputRef.current.setValue(opt.value);
                                                                        }}
                                                                        className={`px-6 py-4 rounded-xl border-2 font-bold text-sm transition-all flex flex-col items-center justify-center gap-2 ${isSelected
                                                                            ? 'bg-amber-100 dark:bg-amber-900/30 border-amber-400 text-amber-950 dark:text-amber-50 shadow-inner'
                                                                            : 'bg-white dark:bg-slate-900 border-amber-200 dark:border-amber-800/50 text-amber-700 dark:text-amber-300 hover:border-amber-400'
                                                                            }`}
                                                                    >
                                                                        <span className="text-base">
                                                                            <MathRenderer content={opt.label} mode="inline" />
                                                                        </span>
                                                                        <span className="text-[9px] uppercase tracking-widest opacity-60">
                                                                            {isSelected ? 'Selected' : 'Use this interpretation'}
                                                                        </span>
                                                                    </button>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}

                                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-4">
                                                    {/* Editable Transcript Pane */}
                                                    <div className="space-y-4">
                                                        <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                                            Using YouAsk voice AI to script
                                                        </p>
                                                        <div className="flex items-center justify-between px-1">
                                                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                                                <span className="material-symbols-outlined text-sm">notes</span>
                                                                Editable Transcript
                                                            </label>
                                                            <span className="material-symbols-outlined text-slate-300 text-lg">edit</span>
                                                        </div>
                                                        <div className="relative min-h-[320px] bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 flex flex-col">
                                                            <textarea
                                                                value={query}
                                                                onChange={(e) => setQuery(e.target.value)}
                                                                className="flex-1 bg-transparent outline-none text-slate-700 dark:text-slate-200 text-lg leading-relaxed resize-none"
                                                                placeholder="Transcribed text appears here..."
                                                            />
                                                            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 text-[9px] font-black text-slate-400 uppercase tracking-widest flex justify-between items-center">
                                                                <span>Subject: {voiceSubject}</span>
                                                                <span className="text-primary italic">Spoken Text</span>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Live Math Preview Pane */}
                                                    <div className="space-y-4">
                                                        <div className="flex items-center justify-between px-1">
                                                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                                                <span className="material-symbols-outlined text-sm">functions</span>
                                                                Live Math Preview
                                                            </label>
                                                            <div className="flex items-center gap-3">
                                                                <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Formatting</span>
                                                                <button
                                                                    onClick={() => setFormattingEnabled(!formattingEnabled)}
                                                                    className={`relative w-10 h-5 rounded-full transition-colors ${formattingEnabled ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-700'}`}
                                                                >
                                                                    <div className={`absolute top-1 left-1 size-3 bg-white rounded-full transition-transform ${formattingEnabled ? 'translate-x-5' : ''}`}></div>
                                                                </button>
                                                            </div>
                                                        </div>
                                                        <div className="relative min-h-[320px] bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden flex flex-col items-center justify-center p-8 text-white math-grid-bg">
                                                            <div className="relative z-10 w-full text-center space-y-4">
                                                                <div className="text-3xl font-bold p-8 flex items-center justify-center min-h-[160px]">
                                                                    {formattingEnabled ? (
                                                                        <MathRenderer content={query || ""} mode="block" dynamic />
                                                                    ) : (
                                                                        <span className="font-mono text-xl opacity-80 break-all">{query}</span>
                                                                    )}
                                                                </div>
                                                                <p className="text-[11px] font-mono text-slate-500 opacity-60 max-w-xs mx-auto truncate">
                                                                    {query}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Bottom Action Bar */}
                                                <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                                                    <button
                                                        onClick={() => setVoiceStage('idle')}
                                                        className="flex-1 px-8 py-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all active:scale-95"
                                                    >
                                                        <span className="material-symbols-outlined text-xl">refresh</span>
                                                        Try Again
                                                    </button>
                                                    <button
                                                        onClick={handleConfirmVoice}
                                                        disabled={isSolving || isBlockingInputError(inputError)}
                                                        className="relative flex-[2] px-8 py-5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-2xl font-black text-xl shadow-[0_10px_40px_-10px_rgba(37,99,235,0.4)] flex items-center justify-center gap-3 transition-all active:scale-[0.98] disabled:opacity-50 overflow-hidden"
                                                    >
                                                        {isSolving && (
                                                            <div className="absolute inset-0">
                                                                <div className="h-full bg-white/20 transition-all" style={{ width: `${solveProgress}%` }}></div>
                                                            </div>
                                                        )}
                                                        {isSolving ? (
                                                            <>
                                                                <div className="size-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                                                                <span>SOLVING... {solveProgress}%</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <span>CONFIRM & SOLVE</span>
                                                                <span className="material-symbols-outlined animate-pulse">auto_awesome</span>
                                                            </>
                                                        )}
                                                    </button>
                                                    {inputError && (
                                                        <div className="text-xs text-red-500 font-medium">
                                                            {inputError}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'error' && (
                                            <div className="text-center space-y-6">
                                                <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 text-red-500 rounded-full flex items-center justify-center mx-auto">
                                                    <span className="material-symbols-outlined text-3xl">error</span>
                                                </div>
                                                <div>
                                                    <h3 className="text-lg font-bold">Something went wrong</h3>
                                                    <p className="text-sm text-slate-500">I couldn&apos;t process your audio right now.</p>
                                                </div>
                                                <button onClick={() => setVoiceStage('idle')} className="text-primary font-bold hover:underline">Try Again</button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>


                    </div>

                    {/* Sidebar */}
                    <div className="lg:col-span-4 space-y-6">
                        {/* Online Users Widget */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <span className="relative flex h-3 w-3">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                    </span>
                                    Online Students
                                </h3>
                                {isPublic && <span className="text-xs font-bold text-slate-500">{onlineUsers.length} Active</span>}
                            </div>

                            {!isPublic ? (
                                <div className="text-center py-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                                    <p className="text-sm text-slate-500 mb-3 px-4">Turn on Public Profile to see and connect with peers.</p>
                                    <button
                                        onClick={() => router.push('/dashboard')}
                                        className="text-primary text-xs font-bold hover:underline"
                                    >
                                        Go to Settings
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {onlineUsers.length === 0 ? (
                                        <p className="text-sm text-slate-500 italic">No one else is public right now.</p>
                                    ) : (
                                        onlineUsers.slice(0, 5).map((u) => (
                                            <div key={u.id} className="flex items-center gap-3">
                                                <div
                                                    className="w-8 h-8 rounded-full bg-cover bg-center border border-slate-200 dark:border-slate-700"
                                                    style={{ backgroundImage: `url('${u.avatar_url || 'https://lh3.googleusercontent.com/aida-public/AB6AXuD_gpHP7vJM1mkTxszlDYSYslefzDpqT7kS3EUblVETFcyH2Sl2xHETdTN_AcqdawcLn0mOa7LR69Ol1T3hAFSvpJss7LzshfwXBbhjMZqOGSH9S1nVdhEO1aeexaHXJAn_VqN1tFoPVazJP1aq1rARcjsg7F4-pStNL1jl7KEpohReYVX52pfbq3YO6IKCX71lAo42c76k2H4WrKWI5r79xsjqMPNL1zZPzcajFKkIs40bZTGM732P1j_aCdcr67zOQ2bNSaRrATQz'}')` }}
                                                />
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-semibold truncate text-slate-900 dark:text-slate-100">{u.full_name}</p>
                                                    <p className="text-[10px] text-slate-500 truncate">
                                                        {u.learning_interests && u.learning_interests.length > 0
                                                            ? u.learning_interests.slice(0, 2).join(", ")
                                                            : "Studying Math"}
                                                    </p>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Tips Sidebar - Photo */}
                        {activeTab === 'snap' && (
                            <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                                <h3 className="text-primary font-bold flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined">lightbulb</span>
                                    Good Photo Tips
                                </h3>
                                <ul className="space-y-4">
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Ensure good lighting.</strong> Avoid shadows covering the equations or variables.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Focus on one problem.</strong> Crop the image to show only the relevant task.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Include diagrams.</strong> If the problem references a graph, make sure it&apos;s in the shot.</p>
                                    </li>
                                </ul>
                            </div>
                        )}

                        {/* Tips Sidebar - Voice */}
                        {activeTab === 'voice' && (
                            <div className="bg-purple-50 dark:bg-purple-900/10 border border-purple-200 dark:border-purple-800 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                                <h3 className="text-purple-600 dark:text-purple-400 font-bold flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined">mic</span>
                                    Voice Input Tips
                                </h3>
                                <ul className="space-y-4">
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-purple-600 text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Speak clearly.</strong> Ensure you are in a quiet environment for best accuracy.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-purple-600 text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Be specific.</strong> State variables and operations explicitly (e.g., &quot;x squared&quot;).</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-purple-600 text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Review the math.</strong> Check the generated LaTeX before clicking Solve.</p>
                                    </li>
                                </ul>
                            </div>
                        )}

                        {/* Tips Sidebar - Text */}
                        {activeTab === 'text' && (
                            <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                                <h3 className="text-primary font-bold flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined">lightbulb</span>
                                    Good Math Tips
                                </h3>
                                <ul className="space-y-4">
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Use clear notation.</strong> Type standard math symbols or use the helper tools.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>One problem at a time.</strong> Keep questions focused for the best answer.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Check your variables.</strong> define any unusual terms or constants.</p>
                                    </li>
                                </ul>
                            </div>
                        )}

                        {/* Recent Solutions - Always visible */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <span className="material-symbols-outlined text-slate-400">history</span>
                                    Recent History
                                </h3>
                                <button
                                    type="button"
                                    onClick={() => router.push("/dashboard?tab=history")}
                                    className="text-primary text-xs font-semibold hover:underline"
                                >
                                    View All
                                </button>
                            </div>
                            <div className="space-y-3">
                                {history.length === 0 ? (
                                    <div className="text-center py-6 text-slate-400 text-sm italic">
                                        <p>No history found.</p>
                                        <p className="text-xs mt-1">Start solving to see items here.</p>
                                    </div>
                                ) : (
                                    history.slice(0, 3).map((session) => (
                                        <div
                                            key={session.id}
                                            onClick={() => router.push(`/chat/${session.id}`)}
                                            className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 hover:border-primary/30 transition-colors cursor-pointer group"
                                        >
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-[10px] uppercase font-bold text-slate-400 bg-slate-100 dark:bg-slate-700/50 px-1.5 py-0.5 rounded">
                                                    #{session.id}
                                                </span>
                                                <span className="text-[10px] text-slate-400 ml-auto">
                                                    {new Date(session.created_at).toLocaleDateString()}
                                                </span>
                                            </div>
                                            <div className="text-sm font-medium text-slate-900 dark:text-slate-200 line-clamp-2 min-h-[1.25rem]">
                                                <MathRenderer content={session.title || "Untitled Session"} mode="prose" />
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Student Context Card */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-colors">
                            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                                <span className="material-symbols-outlined text-primary">school</span>
                                Your School & Tier
                            </h3>
                            {readySubscription ? (
                                <div className="space-y-2 text-sm">
                                    <p className="text-slate-700 dark:text-slate-300">
                                        <span className="font-semibold">School:</span>{" "}
                                        {readySubscription.profile.school_name || "Not set"}
                                    </p>
                                    <p className="text-slate-700 dark:text-slate-300">
                                        <span className="font-semibold">Location:</span>{" "}
                                        {[readySubscription.profile.region_state_province, readySubscription.profile.region_country].filter(Boolean).join(", ") || "Not set"}
                                    </p>
                                    <p className="text-slate-700 dark:text-slate-300">
                                        <span className="font-semibold">Subscription:</span> {readySubscription.plan.display_name}
                                    </p>
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500">Subscription and school info are loading.</p>
                            )}
                        </div>



                        {/* Pro Callout */}
                        <div className="relative overflow-hidden bg-slate-900 rounded-xl p-6 text-white group">
                            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/20 blur-3xl -mr-16 -mt-16 group-hover:bg-primary/40 transition-colors"></div>
                            <div className="relative z-10">
                                <h4 className="text-lg font-bold mb-2">uask Pro</h4>
                                <p className="text-slate-400 text-sm mb-4">Unlock unlimited step-by-step solutions and 1-on-1 expert tutor sessions.</p>
                                <button className="w-full bg-white text-slate-900 font-bold py-2.5 rounded-lg text-sm hover:bg-slate-100 transition-colors">
                                    Upgrade Now
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </main>

            <footer className="max-w-7xl mx-auto px-4 py-8 border-t border-slate-200 dark:border-slate-800 text-center">
                <p className="text-slate-400 text-xs font-medium">© {new Date().getFullYear()} YouAsk AI LLM Math Solver Labs. All rights reserved.</p>
            </footer>

            {
                showRuntimeDebug && (
                    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm">
                        <div className="w-full max-w-xl rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-xl">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Solve Runtime Debug</h3>
                                <button
                                    type="button"
                                    onClick={() => setShowRuntimeDebug(false)}
                                    className="text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                                >
                                    Close
                                </button>
                            </div>
                            {runtimeDebugError ? (
                                <p className="text-xs text-red-500">{runtimeDebugError}</p>
                            ) : (
                                <div className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
                                    <div>Tier: {runtimeDebugMeta?.effective_tier || selectedSolveTier}</div>
                                    <div>Mode: {runtimeDebugMeta?.mode_family || "SOLVE"}</div>
                                    <div>LLM Provider: {runtimeDebugMeta?.provider || "openai"}</div>
                                    <div>Model: {runtimeDebugMeta?.model || "unknown"}</div>
                                    <div>Prompt Binding ID: {runtimeDebugMeta?.prompt_binding_id || "-"}</div>
                                    <div>Global System Prompt ID: {runtimeDebugMeta?.global_system_prompt_id || "-"}</div>
                                    <div>Developer Prompt ID: {runtimeDebugMeta?.developer_prompt_id || "-"}</div>
                                    <div>Output Schema ID: {runtimeDebugMeta?.output_schema_id || "-"}</div>
                                    <div>Request ID: {runtimeDebugMeta?.request_id || "-"}</div>
                                    {runtimeDebugMeta?.token_config && (
                                        <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                                            <div className="font-semibold mb-1">Token Config:</div>
                                            <div>Max Output: {runtimeDebugMeta.token_config.max_output_tokens ?? "Auto"}</div>
                                            <div>Max Input: {runtimeDebugMeta.token_config.max_input_tokens ?? "Auto"}</div>
                                            <div>Temp: {runtimeDebugMeta.token_config.temperature ?? "Default"}</div>
                                            <div>Top P: {runtimeDebugMeta.token_config.top_p ?? "Default"}</div>
                                            <div>Timeout: {runtimeDebugMeta.token_config.timeout_ms ? `${runtimeDebugMeta.token_config.timeout_ms}ms` : "Default"}</div>
                                            <div>Trim: {runtimeDebugMeta.token_config.trim_strategy ?? "None"}</div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )
            }

            {
                isSolving && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/90 backdrop-blur-sm animate-in fade-in duration-300">
                        <div className="relative w-full max-w-4xl p-8 md:p-12 text-white chalkboard-texture chalk-border shadow-2xl overflow-hidden">
                            {/* Decorative Elements */}
                            <div className="dust-smudge w-40 h-40 -top-10 -left-10 opacity-30"></div>
                            <div className="dust-smudge w-64 h-32 bottom-20 right-10 opacity-20"></div>
                            <div className="absolute top-1/4 right-12 opacity-10 pointer-events-none select-none text-4xl font-sketch">★</div>
                            <div className="absolute bottom-1/4 left-1/4 opacity-10 pointer-events-none select-none text-6xl font-sketch -rotate-12">∫</div>

                            {/* Header */}
                            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12 relative z-10">
                                <div className="flex items-center gap-5">
                                    <div className="w-16 h-16 flex items-center justify-center text-white text-3xl font-architects wobbly-chalk rotate-[-2deg]">
                                        Σ
                                    </div>
                                    <div>
                                        <h1 className="text-3xl md:text-4xl font-architects tracking-wide text-white/90">Solving Math Problem...</h1>
                                        <p className="font-hand text-lg opacity-60 tracking-widest mt-1 uppercase">Advanced Neural Computation</p>
                                    </div>
                                </div>
                                <div className="text-right font-hand">
                                    <p className="text-xs uppercase opacity-50 tracking-widest">Elapsed Time</p>
                                    <div className="text-5xl font-architects cyan-glow flex items-baseline">
                                        {formatElapsed(elapsedMs)}<span className="text-xl ml-1">s</span>
                                    </div>
                                </div>
                            </div>

                            {/* Pipeline Grid */}
                            <div className="mb-12 relative z-10">
                                <div className="flex items-center gap-2 mb-8 opacity-80">
                                    <span className="material-symbols-outlined text-2xl">refresh</span>
                                    <h2 className="font-hand text-xl uppercase tracking-[0.2em]">System Pipeline State</h2>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    {(() => {
                                        const activeIndex = pipelineStages.findIndex(s => s.label === currentStage || s.key === currentStage);
                                        return pipelineStages.map((stage, index) => {
                                            const isCompleted = (activeIndex !== -1 && index < activeIndex) || stage.status === 'completed';
                                            const isActive = (activeIndex !== -1 && index === activeIndex) || (stage.status === 'in-progress');

                                            // Fallback for improved UX: If solving but no stage matched yet (Initializing), highlight first
                                            const effectiveActive = isActive || (activeIndex === -1 && index === 0 && currentStage === 'Initializing...');

                                            return (
                                                <div key={stage.key} className={`flex items-start gap-4 p-5 wobbly-chalk transition-all cursor-default group ${effectiveActive || isCompleted ? 'border-white/60 bg-white/5' : 'border-white/20 opacity-60'}`}>
                                                    <div className={`w-12 h-12 flex items-center justify-center transition-colors ${effectiveActive || isCompleted ? 'text-white' : 'text-white/70'}`}>
                                                        <span className="material-symbols-outlined text-4xl bg-clip-text">
                                                            {stage.icon}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <h3 className={`font-architects text-xl transition-colors ${effectiveActive || isCompleted ? 'text-white' : 'text-white/90'}`}>
                                                            {stage.label}
                                                        </h3>
                                                        <p className="font-hand text-lg opacity-50">{stage.description}</p>
                                                    </div>
                                                    {effectiveActive && <div className="ml-auto w-2 h-2 rounded-full bg-cyan-400 animate-pulse self-center"></div>}
                                                    {isCompleted && <div className="ml-auto material-symbols-outlined text-emerald-400 self-center">check</div>}
                                                </div>
                                            );
                                        })
                                    })()}
                                </div>
                            </div>

                            {/* Footer / Streaming Status */}
                            <div className="pt-8 mt-4 border-t border-dashed border-white/20 flex flex-col md:flex-row justify-between items-end gap-6 relative z-10">
                                <div className="flex items-center gap-6">
                                    {/* Animated Bars */}
                                    <div className="flex items-end gap-1.5 h-12">
                                        {[40, 85, 45, 100, 55, 75, 40].map((h, i) => (
                                            <div
                                                key={i}
                                                className="w-1.5 bg-chalk-cyan rounded-sm cyan-bar-glow animate-voice-bar"
                                                style={{ height: `${h}%`, animationDelay: `${i * 0.1}s` }}
                                            ></div>
                                        ))}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <div className="w-2.5 h-2.5 bg-chalk-cyan rounded-full cyan-bar-glow animate-pulse"></div>
                                            <span className="font-hand text-xl font-bold uppercase tracking-widest text-chalk-cyan cyan-glow">Streaming Active</span>
                                        </div>
                                        <p className="font-hand text-sm opacity-50">Packet delivery in real-time</p>
                                    </div>
                                </div>
                                <div className="text-right space-y-1">
                                    <p className="font-sketch italic opacity-40 text-lg">Solution generation in progress</p>
                                    <div className="flex flex-col items-end gap-1">
                                        <p className="font-hand text-sm uppercase opacity-50 tracking-tighter">v4.0.1 Stable • {streamingContent ? "Encrypted Stream" : "Secure Stream"}</p>
                                        <button
                                            onClick={() => setShowRuntimeDebug(true)}
                                            className="font-hand text-sm font-bold opacity-70 cursor-pointer hover:text-white transition-colors border-b border-dashed border-white/30"
                                        >
                                            ▶ DEBUG / RUNTIME
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Corner Icon */}
                            <div className="absolute top-4 right-4 w-10 h-10 rounded-lg flex items-center justify-center opacity-30 hover:opacity-100 transition-opacity cursor-help">
                                <span className="material-symbols-outlined text-white">auto_fix_high</span>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Split Modal for multiple questions */}
            <SplitModal
                isOpen={showSplitModal}
                onClose={() => setShowSplitModal(false)}
                splits={suggestedSplits}
                onSelectQuestion={(question) => {
                    setQuery(question);
                    setMultiQuestionConfirmed(false);
                    setMathValidityConfirmed(false);
                    setShowSplitModal(false);
                }}
                onConfirmSingleQuestion={() => {
                    setMultiQuestionConfirmed(true);
                    setShowSplitModal(false);
                }}
            />

            <ThemeToggle />
        </div >
    );
}
