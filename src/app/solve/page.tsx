"use client";

import DashboardNavBar from "@/components/DashboardNavBar";
import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import katex from 'katex';
import 'katex/dist/katex.min.css';
import MathInput, { MathInputRef } from "@/components/MathInput";
import { MODES, ModeId, Suggestion } from "@/lib/modes";
import ImageCropper from "@/components/ImageCropper";
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

// Token validation imports
import { estimateTokens, TokenEstimate } from "@/lib/tokenEstimator";
import { detectMultiQuestion, MultiQuestionResult, autoSplitQuestions } from "@/lib/multiQuestionDetector";
import { MAX_INPUT_CHARS, MAX_INPUT_TOKENS, willRequestFit } from "@/lib/tokenBudget";
import InputStatus from "@/components/InputStatus";
import SplitModal from "@/components/SplitModal";

// Input mode imports
import InputModeSelector from "@/components/InputModeSelector";
import LiveMathPreview from "@/components/LiveMathPreview";
import { InputModeId, INPUT_MODES, GraphingOptions, DEFAULT_GRAPHING_OPTIONS } from "@/lib/inputModes";

// Tier-aware solve imports
import SegmentedControl from "@/components/ui/SegmentedControl";
import UsageMeter from "@/components/ui/UsageMeter";
import CostPreview from "@/components/solve/CostPreview";
import { SubscriptionResponse, DEFAULT_SUBSCRIPTION, fetchSubscription, calculateSolveCost } from "@/lib/subscription";

interface ChatSession {
    id: number;
    title: string;
    created_at: string;
}

export default function DashboardPage() {
    const [activeTab, setActiveTab] = useState<'text' | 'snap' | 'voice'>('text');
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [query, setQuery] = useState("sqrt(x+5) = x - 1");
    const [isSolving, setIsSolving] = useState(false);
    const [onlineUsers, setOnlineUsers] = useState<any[]>([]);
    const [isPublic, setIsPublic] = useState(false);

    const [activeMode, setActiveMode] = useState<ModeId | null>(null);
    const [isSeeAllOpen, setIsSeeAllOpen] = useState(false);
    const [mathModeEnabled, setMathModeEnabled] = useState(true);
    const mathInputRef = useRef<MathInputRef>(null);
    const [inputError, setInputError] = useState<string | null>(null);

    // Voice State
    const [voiceStage, setVoiceStage] = useState<'idle' | 'recording' | 'processing' | 'review' | 'error'>('idle');
    const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
    const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
    const [voiceSessionId, setVoiceSessionId] = useState<number | null>(null);
    const [voiceArtifact, setVoiceArtifact] = useState<any>(null);
    const [recordingTime, setRecordingTime] = useState(0);
    const [voiceSubject, setVoiceSubject] = useState("Mathematics");
    const [voiceDifficulty, setVoiceDifficulty] = useState("High School / AP");
    const [formattingEnabled, setFormattingEnabled] = useState(true);
    const [ocrFastMode, setOcrFastMode] = useState(true);
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
    const [streamingTelemetry, setStreamingTelemetry] = useState<any>(null);
    const [solveStartTime, setSolveStartTime] = useState<number | null>(null);

    // Tier-Aware Solve State
    const [selectedGoal, setSelectedGoal] = useState<'solve' | 'study'>('solve');
    const [selectedAnswerStyle, setSelectedAnswerStyle] = useState<'quick' | 'tutor'>('quick');
    const [subscription, setSubscription] = useState<SubscriptionResponse>(DEFAULT_SUBSCRIPTION);
    const [subscriptionLoaded, setSubscriptionLoaded] = useState(false);

    // Compute token estimate and multi-question detection
    const tokenEstimate = useMemo(() => estimateTokens(query), [query]);
    const multiQuestionResult = useMemo(() => detectMultiQuestion(query), [query]);
    const requestFit = useMemo(() => willRequestFit(tokenEstimate.tokens), [tokenEstimate.tokens]);

    // Determine if solve should be blocked
    const isInputTooLong = tokenEstimate.tokens > MAX_INPUT_TOKENS || query.length > MAX_INPUT_CHARS;
    const isRequestTooLarge = !requestFit.fits;
    const hasMultipleQuestions = multiQuestionResult.isMultiple && multiQuestionResult.confidence !== 'low';
    const tokenBlockReason = isInputTooLong
        ? "Input too long. Please split into smaller parts."
        : isRequestTooLarge
            ? "Request too large for AI context. Please shorten."
            : hasMultipleQuestions
                ? "Multiple questions detected. One at a time please."
                : null;

    const router = useRouter();

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
                setSubscriptionLoaded(true);
            } catch (e) {
                console.warn("Failed to load subscription, using defaults", e);
                setSubscriptionLoaded(true);
            }
        };

        fetchHistory();
        fetchOnline();
        loadSubscription();
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
        let timer: any;
        if (voiceStage === 'recording') {
            timer = setInterval(() => setRecordingTime(prev => prev + 1), 1000);
        }
        return () => clearInterval(timer);
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

            setAudioChunks(chunks);
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
        try {
            await fetch(`/api/v1/voice/artifacts/${voiceArtifact.id}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    confirmed_transcript_text: voiceArtifact.transcript_raw,
                    confirmed_normalized_math_text: query
                })
            });
            await handleSolve();
        } catch (err) {
            console.error(err);
            setIsSolving(false);
        }
    };

    // OCR & Workflow State
    const [workflowStage, setWorkflowStage] = useState<'input' | 'selecting' | 'processing' | 'review'>('input');
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [croppedImage, setCroppedImage] = useState<string | null>(null);
    const [ocrConfidence, setOcrConfidence] = useState<number>(0);
    const [progressStep, setProgressStep] = useState(0);
    const [processingTime, setProcessingTime] = useState(0);
    const [uploadId, setUploadId] = useState<number | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [artifactId, setArtifactId] = useState<number | null>(null);
    const [engineTag, setEngineTag] = useState<string | null>(null);
    const [tokenMetrics, setTokenMetrics] = useState<string | null>(null);
    const [ocrBlocks, setOcrBlocks] = useState<any[]>([]);
    const [ocrInventory, setOcrInventory] = useState<any>(null);
    const [selectedQuestionId, setSelectedQuestionId] = useState<number | null>(null);
    const [choices, setChoices] = useState<Record<string, string>>({});

    const PROGRESS_STEPS = [
        { label: "Uploading Image...", percent: 10 },
        { label: "Saving Crop...", percent: 30 },
        { label: "OCR Job Queued...", percent: 45 },
        { label: "Analyzing Image... (this may take a moment)", percent: 65 },
        { label: "Extracting LaTeX...", percent: 85 },
        { label: "Finalizing...", percent: 100 }
    ];

    const processFile = async (file: File) => {
        if (!file) return;
        const objectUrl = URL.createObjectURL(file);
        setCapturedImage(objectUrl);
        setWorkflowStage('selecting');

        // Start background upload of original
        try {
            const formData = new FormData();
            formData.append('file', file);
            const userId = localStorage.getItem("user_id") || "1";

            console.log("Original upload starting...", { file: file.name, size: file.size });
            const res = await fetch(`/api/v1/uploads?user_id=${userId}`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                const data = await res.json();
                console.log("Original uploaded successfully:", data);
                setUploadId(data.upload_id);
            } else {
                const errText = await res.text();
                console.error("Upload failed with status:", res.status, errText);
            }
        } catch (e) {
            console.error("Critical error during upload fetch:", e);
        }
    };

    const handleCropConfirm = async (blob: Blob, coords: { x: number, y: number, w: number, h: number }) => {
        const croppedUrl = URL.createObjectURL(blob);
        setCroppedImage(croppedUrl);
        setWorkflowStage('processing');
        setProgressStep(1); // Starting Step 2: Saving Crop
        setProcessingTime(0);

        const timer = setInterval(() => setProcessingTime(p => p + 1), 1000);

        try {
            const userId = localStorage.getItem("user_id") || "1";
            console.log("Starting Crop Confirmation...", { coords, userId });

            // 1. Ensure Upload ID exists (wait up to 10s if still uploading)
            let currentUploadId = uploadId;
            if (!currentUploadId) {
                console.log("Upload ID not ready, waiting...");
                for (let i = 0; i < 20; i++) {
                    await new Promise(r => setTimeout(r, 500));
                    if (uploadId) {
                        currentUploadId = uploadId;
                        console.log("Upload ID obtained after wait:", currentUploadId);
                        break;
                    }
                }
            }

            if (!currentUploadId) {
                throw new Error("Initial upload failed or timed out. Please try again.");
            }

            // 2. Create Crop
            console.log("Sending crop request to:", `/api/v1/uploads/${currentUploadId}/crops`);
            const cropRes = await fetch(`/api/v1/uploads/${currentUploadId}/crops`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    crop_rect: coords,
                    rotation: 0
                })
            });

            if (!cropRes.ok) {
                const errText = await cropRes.text();
                console.error("Crop creation failed:", cropRes.status, errText);
                throw new Error("Failed to save crop: " + errText);
            }

            const cropData = await cropRes.json();
            console.log("Crop saved successfully:", cropData);
            const cid = cropData.crop_id;

            // 3. Create Job
            setProgressStep(2); // Job Queued
            console.log("Creating OCR Job...", { crop_id: cid, userId });
            const jobRes = await fetch(`/api/v1/ocr/jobs?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    crop_id: cid,
                    preferred_engine: "auto",
                    user_intent: ocrFastMode ? "normal" : "high_accuracy"
                })
            });
            if (!jobRes.ok) {
                const errText = await jobRes.text();
                console.error("Job creation failed:", jobRes.status, errText);
                throw new Error("Failed to create OCR job: " + errText);
            }
            const jobData = await jobRes.json();
            console.log("Job created successfully:", jobData);
            const jid = jobData.job_id;
            setJobId(jid);

            // 4. Polling
            await pollJobStatus(jid, timer);

        } catch (e) {
            console.error("Tiered OCR error", e);
            alert("Analysis failed. Falling back to legacy...");
            // TODO: Legacy fallback logic if needed
            clearInterval(timer);
            setWorkflowStage('input');
        }
    };

    const pollJobStatus = async (jid: string, timer: any) => {
        let backoff = 1000;
        const maxBackoff = 15000;

        const poll = async () => {
            try {
                const res = await fetch(`/api/v1/ocr/jobs/${jid}`);
                const data = await res.json();

                if (data.status === 'completed') {
                    setProgressStep(4);
                    setArtifactId(data.artifact_id);
                    await finalizeOcr(data.artifact_id, timer);
                } else if (data.status === 'failed') {
                    throw new Error(data.error_message || "OCR Job Failed");
                } else {
                    // Update UI for processing state
                    if (data.status === 'processing') {
                        setProgressStep(3); // Analyzing Image
                    }
                    // Keep polling with exponential backoff
                    setTimeout(poll, backoff);
                    backoff = Math.min(backoff * 1.5, maxBackoff);
                }
            } catch (e) {
                console.error("Polling error", e);
                clearInterval(timer);
                setWorkflowStage('input');
            }
        };
        poll();
    };

    const finalizeOcr = async (aid: number, timer: any) => {
        try {
            const res = await fetch(`/api/v1/ocr/artifacts/${aid}`);
            const data = await res.json();

            clearInterval(timer);

            const cleanLatex = (data.raw_markdown || "").trim();
            setQuery(cleanLatex);
            if (mathInputRef.current) {
                mathInputRef.current.setValue(cleanLatex);
            }
            setOcrConfidence(data.confidence_score || 0.95);
            setEngineTag(data.engine_display_tag || "YouAsk AI multimodel");
            setTokenMetrics(data.token_metrics || null);
            setOcrBlocks(data.blocks || []);

            // Structured Inventory
            setOcrInventory({
                doc_type: data.doc_type,
                questions: data.questions || [],
                figures: data.figures || [],
                coverage_checklist: data.coverage_checklist || {}
            });

            // Default to first question if available
            if (data.questions && data.questions.length > 0) {
                const q1 = data.questions[0];
                setSelectedQuestionId(q1.id);
                setQuery(q1.prompt || "");

                const q1Choices: Record<string, string> = {};
                (q1.choices || []).forEach((c: any) => {
                    q1Choices[c.label] = c.text;
                });
                setChoices(q1Choices);
            }

            setTimeout(() => {
                setWorkflowStage('review');
                setActiveTab('text');
            }, 800);
        } catch (e) {
            console.error("Finalization error", e);
            clearInterval(timer);
            setWorkflowStage('input');
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            processFile(e.target.files[0]);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            processFile(e.dataTransfer.files[0]);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const resetWorkflow = () => {
        setWorkflowStage('input');
        setCapturedImage(null);
        setCroppedImage(null);
        setQuery("");
        setInputError(null);
        setProgressStep(0);
        setArtifactId(null);
        setSelectedQuestionId(null);
        setVoiceArtifact(null);
        setVoiceSessionId(null);
        setJobId(null);
        setChoices({});
        if (mathInputRef.current) mathInputRef.current.setValue("");
    };

    const validateMathQuery = (value: string) => {
        const normalized = value.trim().toLowerCase();
        if (!normalized) return "Please enter a math question.";
        if (normalized.length < 3) return "Please enter at least 3 characters.";

        const badWords = [
            "fuck",
            "fucking",
            "shit",
            "shitty",
            "bitch",
            "asshole",
            "bastard",
            "dick",
            "cock",
            "pussy",
            "cunt",
            "nigger",
            "faggot",
            "slut",
            "whore",
            "motherfucker",
            "sex",
            "sexual",
            "porn",
            "porno",
            "pornography",
            "rape",
            "rapist",
            "cum",
            "ejaculate",
            "orgasm",
            "blowjob",
            "handjob",
            "anal",
            "penis",
            "vagina",
            "boobs",
            "tits",
            "nude",
            "nudes",
            "naked"
        ];
        if (badWords.some(word => new RegExp(`\\b${word}\\b`, "i").test(normalized))) {
            return "Inappropriate language detected. Please rephrase.";
        }

        const forbiddenPatterns = [
            /<script/i,
            /<\/\w/i,
            /\bimport\s+\w+/i,
            /\bfrom\s+[\w\.]+\s+import\b/i,
            /require\(/i,
            /eval\(/i,
            /exec\(/i,
            /subprocess/i,
            /system\(/i,
            /\bcat\s/i,
            /\bls\s/i,
            /\bdir\s/i,
            /\bchmod\s/i,
            /\bchown\s/i,
            /curl\s/i,
            /wget\s/i,
            /powershell/i,
            /cmd\.exe/i,
            /rm\s/i,
            /del\s/i,
            /drop\s+table/i,
            /insert\s+into/i,
            /update\s+\w+/i,
            /delete\s+from/i,
            /\bselect\s+.*\bfrom\b/i,
            /union\s+select/i,
            /https?:\/\//i,
            /\$\{/i,
            /\{\{/i
        ];
        if (forbiddenPatterns.some(pattern => pattern.test(normalized))) {
            return "Input blocked. Please enter a valid math question.";
        }

        const mathHints = [
            /\d/,
            /[=<>+\-*/^]/,
            /\\(frac|sqrt|int|sum|lim|log|sin|cos|tan|theta|pi|alpha|beta|gamma|cdot|times)/i,
            /\b(solve|simplify|factor|expand|evaluate|derivative|integral|integrate|limit|graph|plot|domain|range|root|roots|intercept|slope|equation|function|probability|matrix|vector|geometry|algebra|calculus)\b/i
        ];
        if (!mathHints.some(pattern => pattern.test(normalized))) {
            return "Input must be a math question.";
        }

        return null;
    };

    const handleSolve = async () => {
        if (isSolving) return;

        const userId = localStorage.getItem("user_id") || "1";
        const validationError = validateMathQuery(query);
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
            const response = await fetch(`${baseUrl}/api/v1/solve_v3_stream?user_id=${encodeURIComponent(userId)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                mode: 'cors',
                body: JSON.stringify({
                    // Primary problem input - only one text field
                    confirmed_text: query,
                    // Entity references (for OCR flow)
                    artifact_id: artifactId || undefined,
                    question_id: selectedQuestionId || undefined,
                    // Tier-aware mode - single field, no duplication
                    requested_mode: selectedAnswerStyle === 'tutor' ? 'detailed' : 'minimal',
                    // Normalized trusted_context (compact enums)
                    trusted_context: {
                        learning_mode: selectedGoal,
                        // Values already normalized from API (CA, CA-ON, 11)
                        grade_level: subscription.profile.grade_level || undefined,
                        region_country: subscription.profile.region_country || undefined,
                        region_state_province: subscription.profile.region_state_province || undefined
                    },
                    // Feature flags for accounting (not sent to OpenAI)
                    features_used: {
                        ocr_used: activeTab === 'snap',
                        voice_used: activeTab === 'voice'
                    }
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

    const handleConfirmOcr = async () => {
        if (!artifactId || isSolving) return;
        const validationError = validateMathQuery(query);
        if (validationError) {
            setInputError(validationError);
            return;
        }

        setIsSolving(true);
        try {
            const res = await fetch(`/api/v1/ocr/artifacts/${artifactId}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    confirmed_markdown: query,
                    confirmed_text: query,
                    confirmed_latex_blocks: [
                        ...Object.entries(choices).map(([k, v]) => ({ type: 'choice', key: k, value: v }))
                    ]
                })
            });

            if (!res.ok) {
                const message = await res.text();
                throw new Error(message || "Confirm request failed");
            }
            await handleSolve();
        } catch (err) {
            console.error(err);
            alert((err as Error).message || "Failed to confirm and solve.");
        } finally {
            setIsSolving(false);
        }
    };

    return (
        <div className="bg-background-light dark:bg-background-dark min-h-screen text-slate-900 dark:text-slate-100 font-display transition-colors duration-200">
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
                                    options={[
                                        { value: "solve", label: "Solve", icon: "bolt" },
                                        { value: "study", label: "Study", icon: "school", tooltip: "Breaks steps into smaller chunks with check-ins" }
                                    ]}
                                    value={selectedGoal}
                                    onChange={(v) => setSelectedGoal(v as 'solve' | 'study')}
                                    size="sm"
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
                                            disabled: !subscription.allow_detailed,
                                            tooltip: subscription.allow_detailed
                                                ? "Step-by-step with checkpoints"
                                                : "Upgrade to unlock detailed explanations"
                                        }
                                    ]}
                                    value={selectedAnswerStyle}
                                    onChange={(v) => {
                                        if (subscription.allow_detailed || v === "quick") {
                                            setSelectedAnswerStyle(v as 'quick' | 'tutor');
                                        }
                                    }}
                                    size="sm"
                                />

                                {/* Usage Meters */}
                                {subscriptionLoaded && (
                                    <div className="flex items-center gap-4">
                                        <UsageMeter
                                            label="Credits"
                                            used={subscription.usage.credits_used}
                                            limit={subscription.plan.credits_monthly}
                                            icon="payments"
                                        />
                                        <UsageMeter
                                            label="OCR"
                                            used={subscription.usage.ocr_used}
                                            limit={subscription.usage.ocr_limit}
                                            icon="document_scanner"
                                        />
                                    </div>
                                )}
                            </div>

                            {/* Cost Preview */}
                            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                                <CostPreview
                                    baseCost={calculateSolveCost(subscription, selectedAnswerStyle, false, false)}
                                    ocrCost={activeTab === 'snap' ? subscription.plan.multipliers.ocr_add : 0}
                                    voiceCost={activeTab === 'voice' ? subscription.plan.multipliers.voice_add : 0}
                                    creditsRemaining={subscription.usage.credits_remaining}
                                    isDetailed={selectedAnswerStyle === 'tutor'}
                                />
                            </div>
                        </div>

                        {/* Input Mode Tabs */}
                        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl shadow-black/5 border border-slate-200 dark:border-slate-800 transition-colors">
                            <div className="flex border-b border-slate-200 dark:border-slate-800">
                                <button
                                    onClick={() => setActiveTab('text')}
                                    className={`flex-1 flex flex-col items-center py-4 transition-all border-b-2 ${activeTab === 'text' ? 'text-primary border-primary bg-primary/5' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined mb-1">edit_note</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Text</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('snap')}
                                    className={`flex-1 flex flex-col items-center py-4 transition-all border-b-2 ${activeTab === 'snap' ? 'text-primary border-primary bg-primary/5' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined mb-1">add_a_photo</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Snap & Solve</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('voice')}
                                    className={`flex-1 flex flex-col items-center py-4 transition-all border-b-2 ${activeTab === 'voice' ? 'text-primary border-primary bg-primary/5' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined mb-1">mic</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Voice</span>
                                </button>
                            </div>

                            {/* Tab Content */}
                            <div className="p-6">
                                {activeTab === 'snap' && (
                                    <div className="flex flex-col gap-6 relative min-h-[400px]">
                                        {/* STAGE 1: INPUT */}
                                        {workflowStage === 'input' && (
                                            <>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                    <div className="space-y-2">
                                                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Subject Area</label>
                                                        <div className="relative">
                                                            <select className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg h-12 px-4 appearance-none focus:ring-2 focus:ring-primary outline-none">
                                                                <option>Mathematics</option>
                                                                <option>Physics</option>
                                                                <option>Chemistry</option>
                                                            </select>
                                                            <span className="material-symbols-outlined absolute right-3 top-3 pointer-events-none text-slate-400">expand_more</span>
                                                        </div>
                                                    </div>
                                                    <div className="space-y-2">
                                                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Difficulty</label>
                                                        <div className="relative">
                                                            <select className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg h-12 px-4 appearance-none focus:ring-2 focus:ring-primary outline-none">
                                                                <option>High School</option>
                                                                <option>College</option>
                                                            </select>
                                                            <span className="material-symbols-outlined absolute right-3 top-3 pointer-events-none text-slate-400">expand_more</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-3">
                                                    <div>
                                                        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Fast OCR</p>
                                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                                            Faster results with lighter analysis.
                                                        </p>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => setOcrFastMode(value => !value)}
                                                        className={`relative w-12 h-6 rounded-full transition-colors ${ocrFastMode ? "bg-primary" : "bg-slate-300 dark:bg-slate-700"}`}
                                                    >
                                                        <div className={`absolute top-1 left-1 size-4 bg-white rounded-full transition-transform ${ocrFastMode ? "translate-x-6" : ""}`}></div>
                                                    </button>
                                                </div>

                                                <label
                                                    onDrop={handleDrop}
                                                    onDragOver={handleDragOver}
                                                    className="group relative flex flex-col items-center justify-center border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl px-6 py-16 hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer"
                                                >
                                                    <input
                                                        type="file"
                                                        className="hidden"
                                                        onChange={handleFileSelect}
                                                        accept="image/*,application/pdf"
                                                    />
                                                    <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center text-primary mb-4 group-hover:scale-110 transition-transform">
                                                        <span className="material-symbols-outlined text-3xl">upload_file</span>
                                                    </div>
                                                    <h3 className="text-lg font-bold mb-1">Drag & Drop or Click</h3>
                                                    <p className="text-slate-500 dark:text-slate-400 text-center max-w-sm mb-6">
                                                        Upload an image of your math problem. Max 5MB.
                                                    </p>
                                                    <div className="flex gap-3">
                                                        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-[10px] font-bold text-slate-500 uppercase">JPG</span>
                                                        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-[10px] font-bold text-slate-500 uppercase">PNG</span>
                                                    </div>
                                                </label>

                                                <div className="flex flex-col items-center gap-2">
                                                    <label className="flex items-center gap-2 bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:opacity-90 px-8 py-3 rounded-lg font-bold transition-all shadow-lg cursor-pointer">
                                                        <input
                                                            type="file"
                                                            className="hidden"
                                                            accept="image/*"
                                                            capture="environment"
                                                            onChange={handleFileSelect}
                                                        />
                                                        <span className="material-symbols-outlined">photo_camera</span>
                                                        <span>Snap Photo</span>
                                                    </label>
                                                    <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                                        Using YouAsk vision AI
                                                    </span>
                                                </div>
                                            </>
                                        )}

                                        {/* STAGE 1.5: SELECTING (Cropper) */}
                                        {workflowStage === 'selecting' && capturedImage && (
                                            <div className="absolute inset-0 z-50">
                                                <ImageCropper
                                                    imageSrc={capturedImage}
                                                    onCancel={resetWorkflow}
                                                    onConfirm={handleCropConfirm}
                                                />
                                            </div>
                                        )}

                                        {/* STAGE 2: PROCESSING */}
                                        {workflowStage === 'processing' && (
                                            <div className="absolute inset-0 bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm z-50 flex flex-col items-center justify-center rounded-xl p-8">
                                                <div className="w-full max-w-sm space-y-6 text-center">
                                                    {/* Animated Icon */}
                                                    <div className="relative size-16 mx-auto">
                                                        <div className="absolute inset-0 border-4 border-slate-100 dark:border-slate-800 rounded-full"></div>
                                                        <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                                        <div className="absolute inset-0 flex items-center justify-center">
                                                            <span className="material-symbols-outlined text-2xl text-primary font-bold">document_scanner</span>
                                                        </div>
                                                    </div>

                                                    <div className="space-y-1">
                                                        <h3 className="text-lg font-bold dark:text-white">
                                                            {PROGRESS_STEPS[progressStep]?.label || "Processing..."}
                                                        </h3>
                                                        <p className="text-xs text-slate-500">
                                                            Please wait while we analyze your image.
                                                        </p>
                                                    </div>

                                                    {/* Progress Bar */}
                                                    <div className="space-y-2">
                                                        <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                                            <span>Progress</span>
                                                            <span>{PROGRESS_STEPS[progressStep]?.percent || 0}%</span>
                                                        </div>
                                                        <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full bg-primary transition-all duration-500 ease-out"
                                                                style={{ width: `${PROGRESS_STEPS[progressStep]?.percent || 0}%` }}
                                                            ></div>
                                                        </div>
                                                    </div>

                                                    {/* Long Loading Warning */}
                                                    {(processingTime > 8) && (
                                                        <div className="flex gap-2 items-center justify-center text-amber-600 dark:text-amber-400 text-xs">
                                                            <span className="material-symbols-outlined text-sm">schedule</span>
                                                            <p>Taking longer than usual...</p>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {/* STAGE 3: REVIEW (MANDATORY) */}
                                        {workflowStage === 'review' && (
                                            <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                                <div className="flex items-center justify-between mb-2">
                                                    <h3 className="font-bold flex items-center gap-2 text-lg">
                                                        <span className="material-symbols-outlined text-green-500">check_circle</span>
                                                        Review & OCR Check
                                                    </h3>
                                                    <button onClick={resetWorkflow} className="text-xs text-slate-500 hover:text-red-500 underline">
                                                        Retake Photo
                                                    </button>
                                                </div>

                                                {/* INVENTORY OVERVIEW (Selected/Multi-Question Support) */}
                                                {ocrInventory && ocrInventory.questions.length > 0 && (
                                                    <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 rounded-xl p-4 mb-2">
                                                        <div className="flex items-center justify-between mb-3">
                                                            <div className="flex items-center gap-2">
                                                                <span className="material-symbols-outlined text-sm text-primary">inventory_2</span>
                                                                <span className="text-xs font-black uppercase tracking-widest text-slate-500">Page Inventory</span>
                                                            </div>
                                                            <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">
                                                                {ocrInventory.doc_type}
                                                            </span>
                                                        </div>
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                            {ocrInventory.questions.map((q: any, idx: number) => {
                                                                const isSelected = query === q.prompt;
                                                                return (
                                                                    <button
                                                                        key={idx}
                                                                        onClick={() => {
                                                                            setSelectedQuestionId(q.id);
                                                                            setQuery(q.prompt);
                                                                            const newChoices: Record<string, string> = {};
                                                                            (q.choices || []).forEach((c: any) => { newChoices[c.label] = c.text; });
                                                                            setChoices(newChoices);
                                                                        }}
                                                                        className={`text-left p-3 rounded-lg border transition-all flex gap-3 ${isSelected
                                                                            ? 'bg-primary/5 border-primary shadow-sm'
                                                                            : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 hover:border-primary/50'
                                                                            }`}
                                                                    >
                                                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${isSelected ? 'bg-primary text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                                                                            }`}>
                                                                            {q.external_id || (idx + 1)}
                                                                        </div>
                                                                        <div className="flex-1 min-w-0">
                                                                            <p className="text-xs line-clamp-2 text-slate-600 dark:text-slate-400">
                                                                                {q.prompt}
                                                                            </p>
                                                                            {q.has_figure && (
                                                                                <span className="inline-flex items-center gap-1 mt-1 text-[9px] font-bold text-amber-600 dark:text-amber-400 uppercase">
                                                                                    <span className="material-symbols-outlined text-[10px]">image</span>
                                                                                    Figure Linked
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    </button>
                                                                );
                                                            })}
                                                        </div>
                                                        {ocrInventory.coverage_checklist?.warnings?.length > 0 && (
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {ocrInventory.coverage_checklist.warnings.map((w: string, i: number) => (
                                                                    <div key={i} className="flex items-center gap-1 bg-amber-50 dark:bg-amber-900/10 text-amber-600 px-2 py-0.5 rounded text-[9px] font-bold">
                                                                        <span className="material-symbols-outlined text-[10px]">warning</span>
                                                                        {w}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    {/* Left: Original Image */}
                                                    <div className="bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden relative group h-48 md:h-auto">
                                                        {/* Left: Original Image (Cropped) */}
                                                        <div className="bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden relative group h-48 md:h-auto flex items-center justify-center">
                                                            {croppedImage && (
                                                                <img
                                                                    src={croppedImage}
                                                                    alt="Original Capture"
                                                                    className="max-w-full max-h-full object-contain"
                                                                />
                                                            )}
                                                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] px-2 py-1 text-center">
                                                                Your Selection
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Right: Editable Markdown & Choices */}
                                                    <div className="flex flex-col gap-4">
                                                        <div className="flex flex-wrap gap-2">
                                                            <div className="flex-1 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-900/30 rounded-lg p-2.5 flex justify-between items-center min-w-[140px]">
                                                                <span className="text-[10px] font-bold text-green-700 dark:text-green-300 uppercase tracking-widest">
                                                                    Confidence
                                                                </span>
                                                                <span className="font-mono font-bold text-green-600 dark:text-green-400 text-sm">
                                                                    {(ocrConfidence * 100).toFixed(0)}%
                                                                </span>
                                                            </div>
                                                            {engineTag && (
                                                                <div className="flex-1 bg-primary/5 border border-primary/20 rounded-lg p-2.5 flex justify-between items-center min-w-[140px]">
                                                                    <span className="text-[10px] font-bold text-primary uppercase tracking-widest">
                                                                        Processor
                                                                    </span>
                                                                    <span className="text-[10px] font-black text-primary">
                                                                        {engineTag}
                                                                    </span>
                                                                </div>
                                                            )}
                                                        </div>

                                                        <div className="space-y-3">
                                                            <div>
                                                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 block px-1">Problem Text (Markdown)</label>
                                                                <div className="relative border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-900 shadow-sm focus-within:ring-2 focus-within:ring-primary/20 transition-all">
                                                                    <textarea
                                                                        className="w-full bg-transparent p-4 min-h-[120px] outline-none text-sm leading-relaxed custom-scrollbar"
                                                                        value={query}
                                                                        onChange={(e) => {
                                                                            setQuery(e.target.value);
                                                                            if (inputError) setInputError(null);
                                                                        }}
                                                                        placeholder="Enter problem text here..."
                                                                    />
                                                                </div>
                                                            </div>

                                                            <div>
                                                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 block px-1 flex justify-between">
                                                                    <span>Multiple Choice Options</span>
                                                                    <span className="text-primary tracking-normal font-bold">A-D Widget</span>
                                                                </label>
                                                                <div className="grid grid-cols-2 gap-2">
                                                                    {["A", "B", "C", "D"].map(key => (
                                                                        <div key={key} className="relative group">
                                                                            <span className={`absolute left-3 top-1/2 -translate-y-1/2 font-black text-xs ${choices[key] ? 'text-primary' : 'text-slate-300'}`}>{key}</span>
                                                                            <input
                                                                                className={`w-full bg-slate-50 dark:bg-slate-800/50 border ${choices[key] ? 'border-primary/30' : 'border-slate-200'} dark:border-slate-750 rounded-lg py-2 pl-8 pr-3 text-xs outline-none focus:ring-2 focus:ring-primary/20 transition-all`}
                                                                                value={choices[key] || ""}
                                                                                onChange={(e) => setChoices(prev => ({ ...prev, [key]: e.target.value }))}
                                                                                placeholder="..."
                                                                            />
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>

                                                            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 border border-slate-100 dark:border-slate-800">
                                                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 block">Live Preview (Markdown + Math)</label>
                                                                <div className="text-sm overflow-x-auto min-h-[60px]">
                                                                    <div className="prose prose-sm dark:prose-invert max-w-none">
                                                                        <ReactMarkdown
                                                                            remarkPlugins={[remarkMath]}
                                                                            rehypePlugins={[rehypeKatex]}
                                                                        >
                                                                            {query || "*No content entered yet...*"}
                                                                        </ReactMarkdown>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                {ocrBlocks.some(b => b.type === 'figure' || b.type === 'refined_figure') && (
                                                    <div className="space-y-2">
                                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block px-1">Detected Figures</label>
                                                        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                                                            {ocrBlocks.filter(b => b.type === 'figure' || b.type === 'refined_figure').map((b, i) => (
                                                                <div key={i} className="flex-none w-32 h-32 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden relative group cursor-pointer hover:border-primary/50 transition-all">
                                                                    <img
                                                                        src={b.url ? `${b.url}` : b.content}
                                                                        className="w-full h-full object-cover"
                                                                        alt="OCR Block"
                                                                    />
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/20 p-3 rounded-lg text-xs text-amber-800 dark:text-amber-200 flex gap-2">
                                                    <span className="material-symbols-outlined text-sm">info</span>
                                                    <span>Please verify symbols (exponents, minus signs) match your image before solving.</span>
                                                </div>
                                                {inputError && (
                                                    <div className="text-xs text-red-500 font-medium px-2">
                                                        {inputError}
                                                    </div>
                                                )}

                                                <button
                                                    onClick={handleConfirmOcr}
                                                    disabled={isSolving || inputError === "Inappropriate language detected. Please rephrase."}
                                                    className={`relative w-full bg-primary hover:bg-blue-700 text-white py-4 rounded-xl font-bold text-lg shadow-xl shadow-primary/20 flex items-center justify-center gap-2 transition-all overflow-hidden ${isSolving ? 'opacity-50 cursor-not-allowed' : 'hover:scale-[1.02]'}`}
                                                >
                                                    {isSolving && (
                                                        <div className="absolute inset-0">
                                                            <div className="h-full bg-white/20 transition-all" style={{ width: `${solveProgress}%` }}></div>
                                                        </div>
                                                    )}
                                                    {isSolving ? (
                                                        <>
                                                            <span className="animate-spin material-symbols-outlined">sync</span>
                                                            <span>Solving... {solveProgress}%</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <span>Confirm & Solve</span>
                                                            <span className="material-symbols-outlined">arrow_forward</span>
                                                        </>
                                                    )}
                                                </button>
                                            </div>
                                        )}
                                    </div>
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
                                            <div className={`bg-white dark:bg-slate-900 border rounded-xl transition-all shadow-sm flex flex-col min-h-[150px] ${inputError
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
                                                                    <div className="flex-1">
                                                                        <span
                                                                            className="font-medium text-slate-700 dark:text-slate-200"
                                                                            dangerouslySetInnerHTML={{
                                                                                __html: katex.renderToString(suggestion.title, {
                                                                                    throwOnError: false,
                                                                                    displayMode: false
                                                                                })
                                                                            }}
                                                                        />
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
                                                            if (value.length <= MAX_INPUT_CHARS) {
                                                                setQuery(value);
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        maxLength={MAX_INPUT_CHARS}
                                                        onPaste={(pastedText) => {
                                                            if (pastedText.length > MAX_INPUT_CHARS) {
                                                                setInputError(`Pasted text was truncated to ${MAX_INPUT_CHARS} characters.`);
                                                            }
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            if (checkResult.isMultiple && checkResult.confidence !== 'low') {
                                                                setSuggestedSplits(autoSplitQuestions(pastedText));
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        className="flex-1 p-2"
                                                    />
                                                ) : (
                                                    <textarea
                                                        value={query}
                                                        onChange={(event) => {
                                                            const value = event.target.value;
                                                            // Enforce character limit
                                                            if (value.length <= MAX_INPUT_CHARS) {
                                                                setQuery(value);
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        onPaste={(event) => {
                                                            const pastedText = event.clipboardData.getData('text');
                                                            if (pastedText.length > MAX_INPUT_CHARS) {
                                                                event.preventDefault();
                                                                const truncated = pastedText.slice(0, MAX_INPUT_CHARS);
                                                                setQuery(truncated);
                                                                setInputError(`Pasted text was truncated to ${MAX_INPUT_CHARS} characters.`);
                                                            }
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            if (checkResult.isMultiple && checkResult.confidence !== 'low') {
                                                                setSuggestedSplits(autoSplitQuestions(pastedText));
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        maxLength={MAX_INPUT_CHARS}
                                                        className="flex-1 p-4 bg-transparent outline-none text-slate-700 dark:text-slate-200 text-lg leading-relaxed resize-none"
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
                                                            onClick={handleSolve}
                                                            disabled={isSolving || query.trim().length < 3 || !!tokenBlockReason || inputError === "Inappropriate language detected. Please rephrase."}
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
                                                    <p className="text-sm text-slate-500">I'll transcribe your math speech into LaTeX.</p>
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
                                                            {voiceArtifact.clarifier_question.options.map((opt: any, idx: number) => {
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
                                                                        <span className="text-base" dangerouslySetInnerHTML={{
                                                                            __html: katex.renderToString(opt.label, { throwOnError: false })
                                                                        }} />
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
                                                                        <span dangerouslySetInnerHTML={{
                                                                            __html: katex.renderToString(query || '', { throwOnError: false, displayMode: true })
                                                                        }} />
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
                                                        disabled={isSolving || inputError === "Inappropriate language detected. Please rephrase."}
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
                                                    <p className="text-sm text-slate-500">I couldn't process your audio right now.</p>
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
                                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Include diagrams.</strong> If the problem references a graph, make sure it's in the shot.</p>
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
                originalText={query}
                splits={suggestedSplits}
                onSelectQuestion={(question, _index) => {
                    setQuery(question);
                    setShowSplitModal(false);
                }}
            />
        </div>
    );
}
