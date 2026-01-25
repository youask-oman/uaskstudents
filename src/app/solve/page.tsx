"use client";

import DashboardNavBar from "@/components/DashboardNavBar";
import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import MathRenderer from "@/components/math/MathRendererSwitch";
import MathInput, { MathInputRef } from "@/components/MathInput";
import { MODES, ModeId, Suggestion } from "@/lib/modes";
import SnapSolveV2 from "@/components/snap/SnapSolveV2";

// Token validation imports
import { estimateTokens } from "@/lib/tokenEstimator";
import { detectMultiQuestion, autoSplitQuestions } from "@/lib/multiQuestionDetector";
import { TokenBudgetPolicy, willRequestFit } from "@/lib/tokenBudget";
import InputStatus from "@/components/InputStatus";
import SplitModal from "@/components/SplitModal";

// Input mode imports
import InputModeSelector from "@/components/InputModeSelector";
import LiveMathPreview from "@/components/LiveMathPreview";
import { InputModeId, INPUT_MODES, GraphingOptions, DEFAULT_GRAPHING_OPTIONS } from "@/lib/inputModes";
import { validateMathQuery, isBlockingInputError, isInputTooShort } from "@/lib/mathValidation";

// Tier-aware solve imports
import SegmentedControl from "@/components/ui/SegmentedControl";
import UsageMeter from "@/components/ui/UsageMeter";
import CostPreview from "@/components/solve/CostPreview";
import { SubscriptionResponse, fetchSubscription, calculateSolveCost } from "@/lib/subscription";
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
    model?: string;
    total_tokens?: number;
    latency_ms_openai?: number;
    truncated?: boolean;
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
};

export default function DashboardPage() {
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
    const voiceSubject = "Mathematics";
    const [formattingEnabled, setFormattingEnabled] = useState(true);
    const [solveProgress, setSolveProgress] = useState(0);

    // Token validation state
    const [showSplitModal, setShowSplitModal] = useState(false);
    const [suggestedSplits, setSuggestedSplits] = useState<string[]>([]);

    // Input mode state
    const [selectedInputMode, setSelectedInputMode] = useState<InputModeId>('expression');
    const [graphingOptions, setGraphingOptions] = useState<GraphingOptions>(DEFAULT_GRAPHING_OPTIONS);

    // Streaming Solve States (Part F1)
    const [streamingContent, setStreamingContent] = useState("");
    const [currentStage, setCurrentStage] = useState("");
    const [streamingTelemetry, setStreamingTelemetry] = useState<StreamingTelemetry | null>(null);
    const [solveStartTime, setSolveStartTime] = useState<number | null>(null);

    // Tier-Aware Solve State
    const selectedGoal = 'solve';
    const [selectedAnswerStyle, setSelectedAnswerStyle] = useState<'quick' | 'tutor'>('quick');
    const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
    const [subscriptionLoaded, setSubscriptionLoaded] = useState(false);
    const [subscriptionError, setSubscriptionError] = useState<string | null>(null);
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
    const hasMultipleQuestions = multiQuestionResult.isMultiple && multiQuestionResult.confidence !== 'low';
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
    const allowDetailed = readySubscription?.allow_detailed ?? false;
    const trustedProfile = readySubscription?.profile ?? null;

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

        fetchHistory();
        fetchOnline();
        loadSubscription();
        loadTokenPolicy();
        const interval = setInterval(fetchOnline, 30000);
        return () => clearInterval(interval);
    }, [router]);

    const handleSuggestionClick = (suggestion: Suggestion) => {
        setMathModeEnabled(true);

        if (suggestion.insertMode === 'replace') {
            // If Math Mode was off, this state update will initialize MathInput with this value
            setQuery(suggestion.latex);

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
            }
        }

        // Close the dropdown panel
        setActiveMode(null);
    };

    const handleClear = () => {
        setQuery("");
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
            setVoiceSessionId(vsid);

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

    const handleSolve = async (overrideText?: string, featureOverrides?: FeaturesUsed) => {
        if (isSolving) return;
        if (!tokenPolicyReady) {
            setInputError("Token policy unavailable. Please refresh.");
            return;
        }

        const userId = localStorage.getItem("user_id") || "1";
        const mathFieldValue = mathModeEnabled && mathInputRef.current?.getValue
            ? mathInputRef.current.getValue()
            : "";
        const textToSolve = overrideText ?? (mathFieldValue.trim() ? mathFieldValue : query);

        const validationError = validateMathQuery(textToSolve);
        if (validationError) {
            setInputError(validationError);
            return;
        }

        setIsSolving(true);
        setStreamingContent("");
        setCurrentStage("Initializing...");
        setStreamingTelemetry(null);
        setSolveStartTime(Date.now());

        try {
            // Bypass Next.js proxy for streaming if on localhost/127.0.0.1 dev server to avoid buffering (Part F2)
            const baseUrl = (typeof window !== 'undefined' && (window.location.port === '3000' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
                ? `${window.location.protocol}//${window.location.hostname}:8000`
                : '';

            console.log(`[SOLVER_STREAM] Host: ${window.location.hostname}, Port: ${window.location.port} -> Fetching from ${baseUrl}/api/v1/solve_v3_stream`);
            const featuresUsed: FeaturesUsed = {
                ocr_used: activeTab === 'snap',
                voice_used: activeTab === 'voice',
                ...(activeTab === 'snap' ? ocrMetadata : {}),
                ...(activeTab === 'voice' ? voiceFeatures : {}),
                ...featureOverrides,
            };
            const response = await fetch(`${baseUrl}/api/v1/solve_v3_stream?user_id=${encodeURIComponent(userId)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                mode: 'cors',
                body: JSON.stringify({
                    // Primary problem input - only one text field
                    confirmed_text: textToSolve,
                    // Tier-aware mode - single field, no duplication
                    requested_mode: selectedAnswerStyle === 'tutor' ? 'detailed' : 'minimal',
                    // Normalized trusted_context (compact enums)
                    trusted_context: {
                        learning_mode: selectedGoal,
                        // Values already normalized from API (CA, CA-ON, 11)
                        grade_level: trustedProfile?.grade_level || undefined,
                        region_country: trustedProfile?.region_country || undefined,
                        region_state_province: trustedProfile?.region_state_province || undefined
                    },
                    // Feature flags for accounting (not sent to OpenAI)
                    features_used: featuresUsed
                })
            });

            console.log(`[SOLVER_STREAM] Response status: ${response.status}, ok: ${response.ok}`);

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

                // Keep the last partial line in the buffer
                accumulatedBuffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (!trimmedLine) continue;

                    if (trimmedLine.startsWith('event: ')) {
                        currentEvent = trimmedLine.slice(7).trim();
                        console.log(`[SSE] Event: ${currentEvent}`);
                    } else if (trimmedLine.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(trimmedLine.slice(6));
                            console.log(`[SSE] Data for ${currentEvent}:`, data);

                            if (currentEvent === 'delta') {
                                setStreamingContent(prev => prev + data.text);
                            } else if (currentEvent === 'stage') {
                                setCurrentStage(data.name);
                            } else if (currentEvent === 'telemetry') {
                                setStreamingTelemetry(data);
                            } else if (currentEvent === 'done') {
                                console.log("[SSE] Done event received", data);
                                if (data.ok) {
                                    setSolveProgress(100);
                                    setTimeout(() => router.push(`/chat/${data.session_id}`), 500);
                                } else {
                                    throw new Error(data.error?.message || "Solve failed");
                                }
                            } else if (currentEvent === 'meta') {
                                if (data.truncated) console.warn("Response truncated");
                            }
                        } catch (e) {
                            console.error("Error parsing SSE data", e);
                        }
                    }
                }
            }
        } catch (err) {
            console.error("[SOLVER_STREAM] Error in stream processing:", err);
            alert((err as Error).message || "Failed to generate solution.");
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

    return (
        <div className="solve-ui bg-background-light dark:bg-background-dark min-h-screen text-slate-900 dark:text-slate-100 font-display transition-colors duration-200">
            <DashboardNavBar />

            <main className="max-w-5xl mx-auto px-4 py-8 md:py-12">
                {/* Page Heading */}
                <div className="mb-8">
                    <h1 className="text-4xl font-black tracking-tight mb-2">New Solve</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-lg">Select your preferred input method and define the context for the best tutor results.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    {/* Main Interaction Area */}
                    <div className="lg:col-span-8 space-y-6">

                        {/* Tier-Aware Controls Section */}
                        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 p-4">
                            <div className="flex flex-wrap items-center justify-between gap-4">
                                {/* Goal Toggle */}
                                <SegmentedControl
                                    label="Goal"
                                    options={[{ value: "solve", label: "Solve", icon: "bolt" }]}
                                    value="solve"
                                    onChange={() => {}}
                                    size="sm"
                                    className="solve-segmented"
                                />

                                {/* Answer Style Toggle */}
                                <SegmentedControl
                                    label="Answer Style"
                                    options={[
                                        { value: "quick", label: "Quick", icon: "speed" },
                                        {
                                            value: "tutor",
                                            label: "Tutor",
                                            icon: "menu_book",
                                            disabled: !allowDetailed,
                                            tooltip: allowDetailed
                                                ? "Step-by-step with checkpoints"
                                                : "Upgrade to unlock detailed explanations"
                                        }
                                    ]}
                                    value={selectedAnswerStyle}
                                    onChange={(v) => {
                                        if (allowDetailed || v === "quick") {
                                            setSelectedAnswerStyle(v as 'quick' | 'tutor');
                                        }
                                    }}
                                    size="sm"
                                    className="solve-segmented"
                                />

                                {/* Usage Meters */}
                                {readySubscription && (
                                    <div className="flex items-center gap-4">
                                        <UsageMeter
                                            label="Credits"
                                            used={readySubscription.usage.credits_used}
                                            limit={readySubscription.plan.credits_monthly}
                                            icon="payments"
                                        />
                                        <UsageMeter
                                            label="OCR"
                                            used={readySubscription.usage.ocr_used}
                                            limit={readySubscription.usage.ocr_limit}
                                            icon="document_scanner"
                                        />
                                    </div>
                                )}
                                {subscriptionLoaded && subscriptionError && (
                                    <div className="text-xs font-semibold text-rose-500">
                                        {subscriptionError}
                                    </div>
                                )}
                            </div>

                            {/* Cost Preview */}
                            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                                {readySubscription ? (
                                    <CostPreview
                                        baseCost={calculateSolveCost(readySubscription, selectedAnswerStyle, false, false)}
                                        ocrCost={activeTab === 'snap' ? readySubscription.plan.multipliers.ocr_add : 0}
                                        voiceCost={activeTab === 'voice' ? readySubscription.plan.multipliers.voice_add : 0}
                                        creditsRemaining={readySubscription.usage.credits_remaining}
                                        isDetailed={selectedAnswerStyle === 'tutor'}
                                    />
                                ) : (
                                    <div className="text-xs text-slate-500">
                                        Subscription data required for cost preview.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Input Mode Tabs */}
                        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl shadow-black/5 border border-slate-200 dark:border-slate-800 transition-colors">
                            <div className="flex border-b border-slate-200 dark:border-slate-800">
                                <button
                                    onClick={() => setActiveTab('text')}
                                    className={`solve-tab ${activeTab === 'text' ? 'solve-tab--active' : ''}`}
                                >
                                    <span className="material-symbols-outlined mb-1 solve-tab-icon">edit_note</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Text</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('snap')}
                                    className={`solve-tab ${activeTab === 'snap' ? 'solve-tab--active' : ''}`}
                                >
                                    <span className="material-symbols-outlined mb-1 solve-tab-icon">add_a_photo</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Snap & Solve</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('voice')}
                                    className={`solve-tab ${activeTab === 'voice' ? 'solve-tab--active' : ''}`}
                                >
                                    <span className="material-symbols-outlined mb-1 solve-tab-icon">mic</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Voice</span>
                                </button>
                            </div>

                            {/* Tab Content */}
                            <div className="p-6">
                                {activeTab === 'snap' && (
                                    <SnapSolveV2
                                        onUseText={(text) => {
                                            setQuery(text);
                                            setActiveTab("text");
                                        }}
                                        onSolveText={(text) => {
                                            setQuery(text);
                                            if (mathInputRef.current) {
                                                mathInputRef.current.setValue(text);
                                            }
                                            handleSolve(text);
                                        }}
                                        requestedMode={selectedAnswerStyle === "tutor" ? "detailed" : "minimal"}
                                    />
                                )}

                                {activeTab === 'text' && (
                                    <div className="flex flex-col gap-6 relative">
                                        {/* Input Mode Selector (Expression / Word Problem / Graphing) */}
                                        <InputModeSelector
                                            selectedMode={selectedInputMode}
                                            onModeChange={setSelectedInputMode}
                                            graphingOptions={graphingOptions}
                                            onGraphingOptionsChange={setGraphingOptions}
                                            onTemplateClick={(template) => {
                                                setQuery(template);
                                                setMathModeEnabled(false); // Switch to regular textarea to show template
                                                if (inputError) setInputError(null);
                                            }}
                                        />

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
                                                                        <MathRenderer content={suggestion.title} mode="inline" className="pointer-events-none" />
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
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        maxLength={textInputMaxChars || undefined}
                                                        onPaste={(pastedText) => {
                                                            if (textInputMaxChars > 0 && pastedText.length > textInputMaxChars) {
                                                                setInputError(`Pasted text was truncated to ${textInputMaxChars} characters.`);
                                                            }
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
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            if (checkResult.isMultiple && checkResult.confidence !== 'low') {
                                                                setSuggestedSplits(autoSplitQuestions(pastedText));
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        maxLength={textInputMaxChars || undefined}
                                                        className="flex-1 p-4 bg-transparent outline-none text-slate-700 dark:text-slate-200 text-lg leading-relaxed resize-none min-h-[180px]"
                                                        style={{
                                                            whiteSpace: 'pre-wrap',
                                                            overflowWrap: 'break-word',
                                                            wordBreak: 'normal',
                                                            hyphens: 'auto',
                                                        }}
                                                        placeholder={INPUT_MODES.find(m => m.id === selectedInputMode)?.placeholder || "Type your question..."}
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
                                                        <span className="text-xs text-red-500 font-medium">{inputError}</span>
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

                                        {/* Live Math Preview */}
                                        <div className="mt-6">
                                            <LiveMathPreview content={query} />
                                        </div>
                                    </div>
                                )}
                                {activeTab === 'voice' && (
                                    <div className="flex flex-col gap-6 items-center justify-center min-h-[400px]">
                                        {voiceStage === 'idle' && (
                                            <div className="text-center space-y-6">
                                                <div
                                                    onClick={startRecording}
                                                    className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center text-primary cursor-pointer hover:scale-110 transition-all hover:bg-primary/20 group"
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

                        {/* Tips Sidebar */}
                        <div className="bg-primary/5 border border-primary/20 rounded-xl p-6">
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

                        {/* Recent Solutions */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-colors">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-slate-900 dark:text-white">Recent History</h3>
                                <a className="text-primary text-xs font-semibold hover:underline" href="#">View All</a>
                            </div>
                            <div className="space-y-3">
                                {history.length === 0 ? (
                                    <p className="text-sm text-slate-500 italic">No history found.</p>
                                ) : (
                                    history.slice(0, 5).map((session) => (
                                        <div
                                            key={session.id}
                                            onClick={() => router.push(`/chat/${session.id}`)}
                                            className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 hover:border-primary/30 transition-colors cursor-pointer group"
                                        >
                                            <p className="text-xs font-bold text-primary mb-1 uppercase tracking-tighter">Session #{session.id}</p>
                                            <p className="text-sm font-medium line-clamp-1 mb-2 text-slate-900 dark:text-slate-200">{session.title}</p>
                                            <div className="flex justify-between items-center text-[10px] text-slate-400 font-medium">
                                                <span>{new Date(session.created_at).toLocaleDateString()}</span>
                                                <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
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

            {/* Streaming Solve Popup (Part F1) */}
            {isSolving && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300">
                    <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl overflow-hidden border border-slate-200 dark:border-slate-800 flex flex-col max-h-[80vh] animate-in zoom-in-95 duration-300">
                        {/* Header */}
                        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
                            <div className="flex items-center gap-3">
                                <div className="size-8 bg-primary rounded-lg flex items-center justify-center text-white">
                                    <span className="material-symbols-outlined text-sm animate-spin-slow">auto_awesome</span>
                                </div>
                                <div>
                                    <h3 className="text-sm font-bold dark:text-white">Solving Problem...</h3>
                                    <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-widest">{currentStage || "Preparing..."}</p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Elapsed Time</p>
                                <p className="text-xs font-mono font-bold text-primary">
                                    {solveStartTime ? ((Date.now() - solveStartTime) / 1000).toFixed(1) : "0.0"}s
                                </p>
                            </div>
                        </div>

                        {/* Progress Bar */}
                        <div className="h-1 bg-slate-100 dark:bg-slate-800">
                            <div
                                className="h-full bg-primary transition-all duration-300"
                                style={{ width: `${solveProgress}%` }}
                            ></div>
                        </div>

                        {/* Content Area - Stage-based progress UI (Part F1) */}
                        <div className="flex-1 overflow-y-auto p-8 space-y-6">
                            {/* Stage Progress Display */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                                    <span className="material-symbols-outlined text-xs animate-spin">sync</span>
                                    AI Processing Status
                                </div>

                                {/* Stage List */}
                                <div className="space-y-3">
                                    {['Preparing request...', 'Calling AI model...', 'Waiting for model...', 'Validating response...', 'Rendering plot...', 'Finalizing...'].map((stage, idx) => {
                                        const isActive = currentStage === stage;
                                        const isPast = ['Preparing request...', 'Calling AI model...', 'Waiting for model...', 'Validating response...', 'Rendering plot...', 'Finalizing...']
                                            .indexOf(currentStage || '') > idx;
                                        return (
                                            <div key={stage} className={`flex items-center gap-3 p-3 rounded-xl transition-all duration-300 ${isActive ? 'bg-primary/10 border border-primary/30' : isPast ? 'opacity-50' : 'opacity-30'}`}>
                                                <span className={`material-symbols-outlined text-lg ${isActive ? 'text-primary animate-pulse' : isPast ? 'text-green-500' : 'text-slate-400'}`}>
                                                    {isPast ? 'check_circle' : isActive ? 'pending' : 'radio_button_unchecked'}
                                                </span>
                                                <span className={`font-semibold ${isActive ? 'text-primary' : 'text-slate-600 dark:text-slate-400'}`}>
                                                    {stage}
                                                </span>
                                                {isActive && <span className="ml-auto text-xs text-primary font-mono">{solveStartTime ? ((Date.now() - solveStartTime) / 1000).toFixed(1) : '0.0'}s</span>}
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* Tokens received indicator */}
                                {streamingContent && streamingContent.length > 0 && (
                                    <div className="mt-4 p-3 bg-slate-100 dark:bg-slate-800 rounded-lg text-xs text-slate-500 font-mono">
                                        📦 Receiving structured data... ({streamingContent.length} characters)
                                    </div>
                                )}
                            </div>

                            {/* Telemetry (Final) */}
                            {streamingTelemetry && (
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6 border-t border-slate-100 dark:border-slate-800 animate-in slide-in-from-bottom-2 duration-500">
                                    <div className="space-y-1">
                                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-tighter">Model</p>
                                        <p className="text-xs font-bold truncate">{streamingTelemetry.model}</p>
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-tighter">Total Tokens</p>
                                        <p className="text-xs font-bold">{streamingTelemetry.total_tokens}</p>
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-tighter">Latency (AI)</p>
                                        <p className="text-xs font-bold">{streamingTelemetry.latency_ms_openai}ms</p>
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-tighter">Status</p>
                                        <p className={`text-xs font-bold ${streamingTelemetry.truncated ? 'text-amber-500' : 'text-emerald-500'}`}>
                                            {streamingTelemetry.truncated ? 'Truncated' : 'Complete'}
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-6 py-4 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                            <p className="text-[10px] text-slate-400 font-medium italic">
                                Do not refresh until the solution is finalized.
                            </p>
                            <div className="flex items-center gap-2">
                                <div className="size-2 bg-emerald-500 rounded-full animate-pulse"></div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Streaming Active</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Split Modal for multiple questions */}
            <SplitModal
                isOpen={showSplitModal}
                onClose={() => setShowSplitModal(false)}
                splits={suggestedSplits}
                onSelectQuestion={(question) => {
                    setQuery(question);
                    setShowSplitModal(false);
                }}
            />

            <ThemeToggle />
        </div>
    );
}
