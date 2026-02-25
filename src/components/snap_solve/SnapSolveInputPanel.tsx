"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import SketchCanvas, { SketchCanvasHandle } from "./SketchCanvas";
import PdfCropViewer, { PdfCropSelection } from "./pdf/PdfCropViewer";
import { useToastOptional } from "@/components/ui/ToastProvider";
import {
    buildSolveBatchPayload,
    getSolveBatchCap,
    mapSolveBatchErrorMessage,
    resolveSolveBatchMode,
    resolveSolveBatchTier,
} from "@/lib/solve-batch";

type SnapSubTab = "upload" | "sketch";

type SolveResponse = {
    answer_markdown: string;
    answer_latex: string | null;
    meta: {
        mode: "upload" | "sketch";
        mime: string;
        latency_ms: number;
        request_id?: string;
    };
};

type PdfPrepareResponse = {
    pdf_id: string;
    page_count: number;
};

type ExtractedQuestion = {
    id: string;
    text: string;
    confidence?: number;
    is_valid_math?: boolean;
    page?: number;
    latex?: string | null;
    source_page_index?: number;
};

type PdfExtractResponse = {
    extracted_questions: ExtractedQuestion[];
    meta: {
        warnings?: string[];
        [key: string]: unknown;
    };
};

type OcrExtractResponse = {
    ocr_attempt_id: string;
    status: string;
    extracted_text?: string | null;
    structured_json?: Record<string, unknown> | null;
    quality_score?: number | null;
    cache_hit?: boolean;
    billing?: { hold_applied?: boolean; hold_amount?: number };
};

type LatexToSympyResponse = {
    ok?: boolean;
    backend?: string;
    expression?: string | null;
    error?: string | null;
    detail?: string | null;
};

type SolvedQuestion = {
    questionId: string;
    result?: SolveResponse;
    error?: string;
};

type ImageExtractEngine = "auto" | "pix2text" | "openai" | "glm_ocr";
type OcrEngineAvailability = {
    local_engine_enabled: boolean;
    openai_engine_enabled: boolean;
    glm_ocr_engine_enabled: boolean;
    default_engine: "pix2text" | "openai" | "glm_ocr";
};

const ACCEPTED_UPLOAD = "image/png,image/jpeg,image/webp,application/pdf";
const PDF_ENABLED = process.env.NEXT_PUBLIC_SNAP_SOLVE_PDF_ENABLED !== "false";
const PDF_DOCUMENT_ENABLED = process.env.NEXT_PUBLIC_SNAP_SOLVE_PDF_DOCUMENT_EXTRACT_ENABLED === "true";

type SnapSolveInputPanelProps = {
    onResolveText?: (text: string, featureOverrides?: Record<string, unknown>) => Promise<void> | void;
    tier?: "SHORT_STEPS" | "STANDARD" | "RESEARCH" | "FINAL";
    requestedMode?: "minimal" | "detailed";
};

export default function SnapSolveInputPanel({ onResolveText, tier, requestedMode }: SnapSolveInputPanelProps) {
    const toast = useToastOptional();
    const [activeSubTab, setActiveSubTab] = React.useState<SnapSubTab>("upload");
    const [questionText, setQuestionText] = React.useState("");
    const [uploadedFile, setUploadedFile] = React.useState<File | null>(null);
    const [originalImageFile, setOriginalImageFile] = React.useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
    const [isDragging, setIsDragging] = React.useState(false);
    const [tool, setTool] = React.useState<"draw" | "erase">("draw");
    const [brushSize, setBrushSize] = React.useState(4);
    const [sketchHasContent, setSketchHasContent] = React.useState(false);
    const [isSubmitting, setIsSubmitting] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [result, setResult] = React.useState<SolveResponse | null>(null);
    const [cameraOpen, setCameraOpen] = React.useState(false);
    const [pdfSession, setPdfSession] = React.useState<{ pdfId: string; pageCount: number } | null>(null);
    const [pdfPage, setPdfPage] = React.useState(1);
    const [pdfScale, setPdfScale] = React.useState(1.5);
    const [pdfPageImage, setPdfPageImage] = React.useState<{ url: string; width: number; height: number } | null>(null);
    const [pdfLoading, setPdfLoading] = React.useState(false);
    const [pdfCrop, setPdfCrop] = React.useState<PdfCropSelection | null>(null);
    const [pdfRender, setPdfRender] = React.useState<{ width: number; height: number; scale: number } | null>(null);
    const [extractedQuestions, setExtractedQuestions] = React.useState<ExtractedQuestion[]>([]);
    const [selectedQuestionIds, setSelectedQuestionIds] = React.useState<Set<string>>(new Set());
    const [solvedQuestions, setSolvedQuestions] = React.useState<SolvedQuestion[]>([]);
    const [extracting, setExtracting] = React.useState(false);
    const [solvingSelected, setSolvingSelected] = React.useState(false);
    const [imageExtracting, setImageExtracting] = React.useState(false);
    const [imageExtractedQuestions, setImageExtractedQuestions] = React.useState<ExtractedQuestion[]>([]);
    const [imageExtractEngine, setImageExtractEngine] = React.useState<ImageExtractEngine>("auto");
    const [imageExtractNote, setImageExtractNote] = React.useState<string | null>(null);
    const [imageCrop, setImageCrop] = React.useState<PdfCropSelection | null>(null);
    const [imageRender, setImageRender] = React.useState<{ width: number; height: number } | null>(null);
    const [ocrAttemptId, setOcrAttemptId] = React.useState<string | null>(null);
    const [ocrEngineUsed, setOcrEngineUsed] = React.useState<string | null>(null);
    const [ocrReviewed, setOcrReviewed] = React.useState(false);
    const [extractProgressPct, setExtractProgressPct] = React.useState(0);
    const [pdfExtractProgress, setPdfExtractProgress] = React.useState<{ current: number; total: number; mode: "crop" | "page" | "document" } | null>(null);
    const [sympyParsedExpression, setSympyParsedExpression] = React.useState("");
    const [sympyParseError, setSympyParseError] = React.useState<string | null>(null);
    const [isSympyParsing, setIsSympyParsing] = React.useState(false);
    const [ocrEngineAvailability, setOcrEngineAvailability] = React.useState<OcrEngineAvailability>({
        local_engine_enabled: true,
        openai_engine_enabled: true,
        glm_ocr_engine_enabled: true,
        default_engine: "glm_ocr",
    });
    const fileInputRef = React.useRef<HTMLInputElement | null>(null);
    const cameraInputRef = React.useRef<HTMLInputElement | null>(null);
    const sketchRef = React.useRef<SketchCanvasHandle | null>(null);
    const videoRef = React.useRef<HTMLVideoElement | null>(null);
    const streamRef = React.useRef<MediaStream | null>(null);
    const pdfCacheRef = React.useRef<Map<string, { url: string; width: number; height: number }>>(new Map());

    const isPdfMode = Boolean(uploadedFile && uploadedFile.type === "application/pdf" && pdfSession);
    const extractErrorMessage = React.useCallback((payload: unknown, fallback: string): string => {
        if (!payload || typeof payload !== "object") return fallback;
        const detail = (payload as { detail?: unknown }).detail;
        if (typeof detail === "string") return detail;
        if (detail && typeof detail === "object") {
            const message = (detail as { message?: unknown }).message;
            if (typeof message === "string") return message;
        }
        const error = (payload as { error?: unknown }).error;
        if (typeof error === "string") return error;
        return fallback;
    }, []);
    const normalizeExtractText = React.useCallback((value: string): string => {
        if (!value) return "";
        return value
            .replace(/\\n/g, "\n")
            .replace(/\\r/g, "\r")
            .replace(/\\t/g, "\t")
            .replace(/\\\\/g, "\\")
            .replace(/âˆ’|−|—|–/g, "-")
            .replace(/÷/g, "\\div ")
            .replace(/×/g, "\\times ")
            .replace(/ratio\s+AB:\s*\\?\(\{\\bf\s*B\s*C\}\s*,?\\?\)\s*is:/gi, "ratio \\(\\mathbf{AB}:\\mathbf{BC}\\) is:")
            .replace(/ratio\s+AB:\s*BC\s*,?\s*is:/gi, "ratio \\(\\mathbf{AB}:\\mathbf{BC}\\) is:")
            .replace(/^\s*(\d{1,3})\.\s+\1\.\s+/gm, "$1. ")
            .trim();
    }, []);
    const splitNumberedQuestions = React.useCallback((text: string, idPrefix: string): ExtractedQuestion[] => {
        const normalized = normalizeExtractText(text || "")
            .replace(/\r\n?/g, "\n")
            // Some OCR outputs flatten " ... D 5040 2. Next question" onto one line.
            .replace(/([^\n])\s+(\d{1,3}[.)]\s+[A-Z])/g, "$1\n$2");
        if (!normalized) return [];

        const markerRegex = /^\s*(\d{1,3})[.)]\s+/gm;
        const markers = Array.from(normalized.matchAll(markerRegex));
        if (markers.length < 2) return [];

        const chunks: ExtractedQuestion[] = [];
        for (let i = 0; i < markers.length; i += 1) {
            const start = markers[i].index ?? 0;
            const end = i + 1 < markers.length ? (markers[i + 1].index ?? normalized.length) : normalized.length;
            const chunk = normalizeExtractText(normalized.slice(start, end).trim());
            if (!chunk || chunk.length < 10) continue;
            const n = markers[i][1];
            chunks.push({
                id: `${idPrefix}-q${n}`,
                text: chunk,
                latex: chunk,
                page: 0,
            });
        }
        return chunks.length >= 2 ? chunks : [];
    }, [normalizeExtractText]);
    const normalizeLatexForReview = React.useCallback((value: string): string => {
        if (!value) return "";
        return normalizeExtractText(value)
            .replace(/(?<![A-Za-z])(?:root|oot)\s*(\d+)\s*\\of\s*\{/gi, "\\\\sqrt[$1]{")
            .replace(/(?<![A-Za-z])(?:root|oot)\s*(\d+)\s*of\s*\{/gi, "\\\\sqrt[$1]{")
            .replace(/\\of\s*\{/g, "{")
            .replace(/\\\\/g, "\\")
            .replace(/\\boldsymbol\{([^{}]+)\}/g, "$1")
            .replace(/\\mathbf\{([^{}]+)\}/g, "$1")
            .replace(/\\mathbb\{([A-PR-Za-pr-z0-9])\}/g, "$1")
            .replace(/\{\\bf\s+([^}]+)\}/g, "\\mathbf{$1}")
            .replace(/\\bf\s+([A-Za-z0-9]+)/g, "\\mathbf{$1}")
            .replace(/\\\[/g, "$$")
            .replace(/\\\]/g, "$$")
            .replace(/\\\(/g, "$")
            .replace(/\\\)/g, "$");
    }, [normalizeExtractText]);
    const getUserId = React.useCallback((): string => {
        if (typeof window === "undefined") return "1";
        return localStorage.getItem("user_id") || "1";
    }, []);
    React.useEffect(() => {
        if (typeof window === "undefined") return;
        const saved = localStorage.getItem("snapsolve_ocr_engine");
        if (saved === "auto" || saved === "pix2text" || saved === "openai" || saved === "glm_ocr") {
            setImageExtractEngine(saved);
        }
    }, []);
    React.useEffect(() => {
        let alive = true;
        const loadOcrEngines = async () => {
            try {
                const res = await fetch("/api/v1/ocr/engines");
                if (!res.ok) return;
                const data = (await res.json()) as Partial<OcrEngineAvailability>;
                if (!alive) return;
                if (
                    typeof data.local_engine_enabled !== "boolean"
                    || typeof data.openai_engine_enabled !== "boolean"
                    || typeof data.glm_ocr_engine_enabled !== "boolean"
                ) return;
                setOcrEngineAvailability({
                    local_engine_enabled: data.local_engine_enabled,
                    openai_engine_enabled: data.openai_engine_enabled,
                    glm_ocr_engine_enabled: data.glm_ocr_engine_enabled,
                    default_engine: data.default_engine === "openai"
                        ? "openai"
                        : (data.default_engine === "glm_ocr" ? "glm_ocr" : "pix2text"),
                });
            } catch {
                // Keep defaults if endpoint is unavailable.
            }
        };
        void loadOcrEngines();
        return () => {
            alive = false;
        };
    }, []);
    React.useEffect(() => {
        const allows = (engine: ImageExtractEngine) => {
            if (engine === "auto") return ocrEngineAvailability.glm_ocr_engine_enabled || ocrEngineAvailability.local_engine_enabled || ocrEngineAvailability.openai_engine_enabled;
            if (engine === "pix2text") return ocrEngineAvailability.local_engine_enabled;
            if (engine === "openai") return ocrEngineAvailability.openai_engine_enabled;
            if (engine === "glm_ocr") return ocrEngineAvailability.glm_ocr_engine_enabled;
            return false;
        };
        if (allows(imageExtractEngine)) return;
        const fallback: ImageExtractEngine =
            ocrEngineAvailability.glm_ocr_engine_enabled
                ? "auto"
                : (ocrEngineAvailability.local_engine_enabled
                    ? "auto"
                    : (ocrEngineAvailability.openai_engine_enabled ? "openai" : "auto"));
        setImageExtractEngine(fallback);
        if (typeof window !== "undefined") {
            localStorage.setItem("snapsolve_ocr_engine", fallback);
        }
    }, [imageExtractEngine, ocrEngineAvailability]);
    React.useEffect(() => {
        const active = imageExtracting || extracting;
        if (active) {
            const isMultiPagePdf =
                Boolean(pdfExtractProgress)
                && pdfExtractProgress?.mode === "document"
                && (pdfExtractProgress?.total || 0) > 1;
            if (isMultiPagePdf && pdfExtractProgress) {
                const total = Math.max(1, pdfExtractProgress.total);
                const current = Math.max(0, Math.min(pdfExtractProgress.current, total));
                const floor = Math.floor((current / total) * 100);
                const target = Math.min(
                    98,
                    Math.floor(((Math.min(current + 0.85, total)) / total) * 100),
                );
                setExtractProgressPct((prev) => {
                    const seeded = prev < floor ? floor : prev;
                    if (seeded >= target) return seeded;
                    return Math.min(target, seeded + (seeded < 40 ? 6 : 3));
                });
                const interval = window.setInterval(() => {
                    setExtractProgressPct((prev) => {
                        const seeded = prev < floor ? floor : prev;
                        if (seeded >= target) return seeded;
                        return Math.min(target, seeded + (seeded < 40 ? 4 : 2));
                    });
                }, 350);
                return () => window.clearInterval(interval);
            }
            setExtractProgressPct((prev) => (prev > 5 ? prev : 6));
            const interval = window.setInterval(() => {
                setExtractProgressPct((prev) => {
                    if (prev >= 92) return prev;
                    const step = prev < 30 ? 9 : (prev < 70 ? 5 : 2);
                    return Math.min(92, prev + step);
                });
            }, 450);
            return () => window.clearInterval(interval);
        }
        if (extractProgressPct <= 0) return;
        setExtractProgressPct(100);
        const reset = window.setTimeout(() => {
            setExtractProgressPct(0);
            setPdfExtractProgress(null);
        }, 700);
        return () => window.clearTimeout(reset);
    }, [imageExtracting, extracting, extractProgressPct, pdfExtractProgress]);
    const extractedPreviewQuestions = React.useMemo(
        () => (isPdfMode ? extractedQuestions : imageExtractedQuestions),
        [isPdfMode, extractedQuestions, imageExtractedQuestions],
    );
    const extractedPreviewText = React.useMemo(
        () => extractedPreviewQuestions
            .map((q, index) => `${index + 1}. ${normalizeExtractText(q.text || "")}`)
            .filter(Boolean)
            .join("\n\n"),
        [extractedPreviewQuestions, normalizeExtractText],
    );
    const extractedPreviewLatex = React.useMemo(
        () => extractedPreviewQuestions
            .map((q, index) => {
                const source = q.latex || q.text || "";
                const normalized = normalizeLatexForReview(source);
                return normalized ? `Q${index + 1}\n\n${normalized}` : "";
            })
            .filter(Boolean)
            .join("\n\n"),
        [extractedPreviewQuestions, normalizeLatexForReview],
    );
    const sympyLatexInput = React.useMemo(() => {
        for (const q of extractedPreviewQuestions) {
            const source = q.latex || q.text || "";
            const normalized = normalizeLatexForReview(source).trim();
            if (normalized) return normalized;
        }
        return "";
    }, [extractedPreviewQuestions, normalizeLatexForReview]);

    React.useEffect(() => {
        let cancelled = false;
        const run = async () => {
            if (!sympyLatexInput) {
                if (!cancelled) {
                    setSympyParsedExpression("");
                    setSympyParseError(null);
                    setIsSympyParsing(false);
                }
                return;
            }
            setIsSympyParsing(true);
            setSympyParseError(null);
            try {
                const res = await fetch("/api/extract/latex-to-sympy", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ latex: sympyLatexInput, backend: "antlr" }),
                });
                const raw = await res.text();
                let data: LatexToSympyResponse = {};
                if (raw) {
                    try {
                        data = JSON.parse(raw) as LatexToSympyResponse;
                    } catch {
                        throw new Error(raw || "Invalid parser response.");
                    }
                }
                if (!res.ok) {
                    throw new Error(String(data.detail || raw || "Unable to parse LaTeX."));
                }
                if (!cancelled) {
                    if (data.ok && typeof data.expression === "string" && data.expression.trim()) {
                        setSympyParsedExpression(data.expression.trim());
                        setSympyParseError(null);
                    } else {
                        setSympyParsedExpression("");
                        setSympyParseError(String(data.error || "Unable to parse LaTeX with SymPy."));
                    }
                }
            } catch (err) {
                if (!cancelled) {
                    setSympyParsedExpression("");
                    setSympyParseError(err instanceof Error ? err.message : "Unable to parse LaTeX with SymPy.");
                }
            } finally {
                if (!cancelled) setIsSympyParsing(false);
            }
        };
        void run();
        return () => {
            cancelled = true;
        };
    }, [sympyLatexInput]);

    React.useEffect(() => {
        if (!ocrAttemptId) return;
        if (!questionText.trim()) return;
        if (imageExtractedQuestions.length > 0) return;
        setImageExtractedQuestions([
            {
                id: ocrAttemptId,
                text: questionText,
                latex: questionText,
            },
        ]);
    }, [ocrAttemptId, questionText, imageExtractedQuestions.length]);
    React.useEffect(() => {
        if (!ocrAttemptId) return;
        setOcrReviewed(false);
    }, [ocrAttemptId, questionText]);
    React.useEffect(() => {
        if (imageCrop) setOcrReviewed(false);
    }, [imageCrop]);
    const isSubmitEnabled = React.useMemo(() => {
        if (isPdfMode) return false;
        return Boolean(uploadedFile || sketchHasContent || questionText.trim().length > 0);
    }, [uploadedFile, sketchHasContent, questionText, isPdfMode]);
    const requiresOcrReview = React.useMemo(
        () => Boolean(ocrAttemptId || imageExtractedQuestions.length > 0),
        [ocrAttemptId, imageExtractedQuestions.length]
    );
    const resolveEnabled = isSubmitEnabled && (!requiresOcrReview || ocrReviewed);

    const resolveSolveTier = React.useCallback((): "short_steps" | "standard" | "research" | "final" => {
        const propTier = (tier || "").toLowerCase();
        if (propTier === "short_steps" || propTier === "standard" || propTier === "research" || propTier === "final") {
            return propTier as "short_steps" | "standard" | "research" | "final";
        }
        if (typeof window !== "undefined") {
            const storedTier = (window.localStorage.getItem("selected_solve_tier") || "").toLowerCase();
            if (storedTier === "short_steps" || storedTier === "standard" || storedTier === "research" || storedTier === "final") {
                return storedTier as "short_steps" | "standard" | "research" | "final";
            }
        }
        return "short_steps";
    }, [tier]);

    const resolveSolveMode = React.useCallback(
        (effectiveTier: "short_steps" | "standard" | "research" | "final"): "minimal" | "detailed" => {
            if (requestedMode === "minimal" || requestedMode === "detailed") return requestedMode;
            return (effectiveTier === "short_steps" || effectiveTier === "final") ? "minimal" : "detailed";
        },
        [requestedMode],
    );

    const clearPdfCache = React.useCallback(() => {
        pdfCacheRef.current.forEach((entry) => {
            if (entry.url.startsWith("blob:")) URL.revokeObjectURL(entry.url);
        });
        pdfCacheRef.current.clear();
    }, []);

    const clearPdfState = React.useCallback(() => {
        clearPdfCache();
        setPdfSession(null);
        setPdfPage(1);
        setPdfScale(1.5);
        setPdfPageImage(null);
        setPdfCrop(null);
        setPdfRender(null);
        setExtractedQuestions([]);
        setSelectedQuestionIds(new Set());
        setSolvedQuestions([]);
        setImageExtracting(false);
        setImageExtractedQuestions([]);
        setImageExtractNote(null);
        setImageCrop(null);
        setImageRender(null);
        setSympyParsedExpression("");
        setSympyParseError(null);
        setIsSympyParsing(false);
        setOcrAttemptId(null);
        setOcrEngineUsed(null);
    }, [clearPdfCache]);

    const clearExtractedState = React.useCallback(() => {
        setQuestionText("");
        setError(null);
        setResult(null);
        setExtractedQuestions([]);
        setSelectedQuestionIds(new Set());
        setSolvedQuestions([]);
        setImageExtracting(false);
        setImageExtractedQuestions([]);
        setImageExtractNote(null);
        setSympyParsedExpression("");
        setSympyParseError(null);
        setIsSympyParsing(false);
        setOcrAttemptId(null);
        setOcrEngineUsed(null);
        setOcrReviewed(false);
    }, []);

    const setUploadFile = React.useCallback(
        (file: File | null) => {
            setUploadedFile(file);
            clearExtractedState();
            setImageCrop(null);
            setImageRender(null);

            if (previewUrl && previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
            if (!file) {
                setPreviewUrl(null);
                clearPdfState();
                return;
            }
            if (file.type === "application/pdf") {
                setPreviewUrl(null);
                return;
            }
            clearPdfState();
            if (file.type.startsWith("image/")) setPreviewUrl(URL.createObjectURL(file));
            else setPreviewUrl(null);
        },
        [previewUrl, clearPdfState, clearExtractedState]
    );

    const extractImageQuestions = React.useCallback(
        async (file: File) => {
            if (!file.type.startsWith("image/")) return;
            setOcrReviewed(false);
            setImageExtracting(true);
            setImageExtractedQuestions([]);
            setImageExtractNote(null);
            setOcrAttemptId(null);
            setOcrEngineUsed(null);
            try {
                const form = new FormData();
                form.append("file", file);
                const isCropMode = Boolean(imageCrop && imageRender);
                const engineChoice =
                    imageExtractEngine === "auto"
                        ? (
                            ocrEngineAvailability.default_engine === "glm_ocr"
                                ? "glm_ocr"
                                : (ocrEngineAvailability.default_engine === "openai" ? "openai" : "pix2text")
                        )
                        : imageExtractEngine;
                form.append("engine", engineChoice);
                if (isCropMode && imageCrop && imageRender) {
                    form.append("crop_x", String(imageCrop.x / imageRender.width));
                    form.append("crop_y", String(imageCrop.y / imageRender.height));
                    form.append("crop_w", String(imageCrop.width / imageRender.width));
                    form.append("crop_h", String(imageCrop.height / imageRender.height));
                }
                const userId = getUserId();
                const res = await fetch(`/api/v1/ocr/extract?user_id=${encodeURIComponent(userId)}`, {
                    method: "POST",
                    body: form,
                });
                const payload = (await res.json().catch(() => ({}))) as OcrExtractResponse;
                if (!res.ok) throw new Error(extractErrorMessage(payload, "Unable to extract questions from image."));
                const extractedText = normalizeExtractText(payload.extracted_text || "");
                const structured = payload.structured_json || {};
                const structuredQuestions = Array.isArray((structured as { questions?: unknown[] }).questions)
                    ? ((structured as { questions: unknown[] }).questions)
                    : [];
                const parsedQuestions = structuredQuestions
                    .map((entry, index): ExtractedQuestion | null => {
                        if (!entry || typeof entry !== "object") return null;
                        const q = entry as Record<string, unknown>;
                        const text = normalizeExtractText(String(q.text || q.question_text || "").trim());
                        if (!text) return null;
                        const latexRaw = q.latex || q.question_latex;
                        return {
                            id: String(q.id || q.question_id || `${payload.ocr_attempt_id || "ocr"}-${index + 1}`),
                            text,
                            latex: typeof latexRaw === "string" ? normalizeExtractText(latexRaw) : undefined,
                            confidence: typeof q.confidence === "number" ? q.confidence : undefined,
                            page: typeof q.page === "number" ? q.page : (typeof q.page_index === "number" ? q.page_index : undefined),
                        };
                    })
                    .filter((q): q is ExtractedQuestion => q !== null);
                const attemptId = payload.ocr_attempt_id || "ocr";
                const splitFromStructured = parsedQuestions.length === 1
                    ? splitNumberedQuestions(parsedQuestions[0].text || "", attemptId)
                    : [];
                const splitFromRaw = (!splitFromStructured.length && extractedText)
                    ? splitNumberedQuestions(extractedText, attemptId)
                    : [];

                const nextQuestions = splitFromStructured.length
                    ? splitFromStructured
                    : (splitFromRaw.length
                        ? splitFromRaw
                        : (parsedQuestions.length
                            ? parsedQuestions
                            : (extractedText
                                ? [{
                                    id: attemptId,
                                    text: extractedText,
                                    latex: extractedText,
                                } as ExtractedQuestion]
                                : [])));
                setImageExtractedQuestions(nextQuestions);
                setExtractedQuestions(nextQuestions);
                setSelectedQuestionIds(new Set(nextQuestions.map((q) => q.id)));
                setSolvedQuestions([]);
                // Keep the optional free-text field empty after OCR extraction.
                setQuestionText("");
                setOcrAttemptId(payload.ocr_attempt_id || null);
                setOcrEngineUsed(engineChoice);
                // billing hold info is surfaced via note for now
                if (imageExtractEngine === "auto") {
                    const autoEngine = ocrEngineAvailability.default_engine === "glm_ocr"
                        ? "GLM OCR"
                        : (ocrEngineAvailability.default_engine === "openai" ? "OpenAI" : "Pix2Text");
                    setImageExtractNote(`Auto uses ${autoEngine}.`);
                } else if (payload.billing?.hold_applied) {
                    setImageExtractNote(`OCR hold applied: ${payload.billing.hold_amount ?? 0} credits`);
                }
            } catch (e) {
                setError(e instanceof Error ? e.message : "Unable to extract questions from image.");
            } finally {
                setImageExtracting(false);
            }
        },
        [extractErrorMessage, getUserId, imageCrop, imageExtractEngine, imageRender, normalizeExtractText, ocrEngineAvailability, splitNumberedQuestions]
    );

    React.useEffect(() => {
        return () => {
            if (previewUrl && previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
            clearPdfCache();
            if (streamRef.current) {
                streamRef.current.getTracks().forEach((t) => t.stop());
                streamRef.current = null;
            }
        };
    }, [previewUrl, clearPdfCache]);

    React.useEffect(() => {
        const handlePaste = (event: ClipboardEvent) => {
            if (activeSubTab !== "upload") return;
            if (!event.clipboardData) return;
            const fileFromFiles = Array.from(event.clipboardData.files || []).find((file) => file.type.startsWith("image/"));
            const fileFromItems = Array.from(event.clipboardData.items || [])
                .find((item) => item.type.startsWith("image/"))
                ?.getAsFile();
            const blob = fileFromFiles || fileFromItems;
            if (!blob) return;
            event.preventDefault();
            setUploadFile(new File([blob], `clipboard-${Date.now()}.png`, { type: blob.type || "image/png" }));
        };
        window.addEventListener("paste", handlePaste);
        return () => window.removeEventListener("paste", handlePaste);
    }, [activeSubTab, setUploadFile]);

    const loadPdfPageImage = React.useCallback(
        async (pdfId: string, pageIndex: number, scale: number) => {
            const key = `${pdfId}:${pageIndex}:${scale.toFixed(2)}`;
            const cached = pdfCacheRef.current.get(key);
            if (cached) {
                pdfCacheRef.current.delete(key);
                pdfCacheRef.current.set(key, cached);
                setPdfPageImage(cached);
                setPdfRender({ width: cached.width, height: cached.height, scale });
                return;
            }

            setPdfLoading(true);
            try {
                const res = await fetch(
                    `/api/v1/snap-solve/pdf/page-image?pdf_id=${encodeURIComponent(pdfId)}&page_index=${pageIndex}&scale=${scale}`
                );
                if (!res.ok) {
                    const payload = await res.json().catch(() => ({}));
                    throw new Error(extractErrorMessage(payload, "Failed to render PDF page."));
                }
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const width = Number(res.headers.get("X-Page-Width") || 0);
                const height = Number(res.headers.get("X-Page-Height") || 0);
                const entry = { url, width, height };
                pdfCacheRef.current.set(key, entry);
                while (pdfCacheRef.current.size > 5) {
                    const oldest = pdfCacheRef.current.keys().next().value as string | undefined;
                    if (!oldest) break;
                    const oldEntry = pdfCacheRef.current.get(oldest);
                    if (oldEntry?.url?.startsWith("blob:")) URL.revokeObjectURL(oldEntry.url);
                    pdfCacheRef.current.delete(oldest);
                }
                setPdfPageImage(entry);
                setPdfRender({ width, height, scale });
            } finally {
                setPdfLoading(false);
            }
        },
        [extractErrorMessage]
    );

    React.useEffect(() => {
        if (!pdfSession) return;
        loadPdfPageImage(pdfSession.pdfId, pdfPage - 1, pdfScale).catch((e) => {
            setError(e instanceof Error ? e.message : "Failed to render PDF page.");
        });
    }, [pdfSession, pdfPage, pdfScale, loadPdfPageImage]);

    const preparePdf = React.useCallback(
        async (file: File) => {
            if (!PDF_ENABLED) {
                throw new Error("PDF mode is disabled for this environment.");
            }
            const form = new FormData();
            form.append("file", file);
            const res = await fetch("/api/v1/snap-solve/pdf/prepare", { method: "POST", body: form });
            const payload = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(extractErrorMessage(payload, "Failed to prepare PDF."));
            }
            const prepared = payload as PdfPrepareResponse;
            setPdfSession({ pdfId: prepared.pdf_id, pageCount: prepared.page_count });
            setPdfPage(1);
            setPdfScale(1.5);
            setPdfCrop(null);
            setPdfRender(null);
            setExtractedQuestions([]);
            setSelectedQuestionIds(new Set());
            setSolvedQuestions([]);
        },
        [extractErrorMessage]
    );

    const handleIncomingFile = React.useCallback(
        async (file: File | null) => {
            if (!file) return;
            setOcrReviewed(false);
            setUploadFile(file);
            if (file.type.startsWith("image/")) {
                setOriginalImageFile(file);
            } else {
                setOriginalImageFile(null);
            }
            if (file.type === "application/pdf") {
                try {
                    await preparePdf(file);
                } catch (e) {
                    setError(e instanceof Error ? e.message : "Unable to prepare PDF.");
                    setUploadFile(null);
                    clearPdfState();
                }
                return;
            }
        },
        [setUploadFile, preparePdf, clearPdfState]
    );

    const rotateImageFile = React.useCallback(async (direction: "left" | "right") => {
        if (!uploadedFile || !uploadedFile.type.startsWith("image/")) return;
        const objectUrl = URL.createObjectURL(uploadedFile);
        try {
            const img = new Image();
            const loaded = new Promise<void>((resolve, reject) => {
                img.onload = () => resolve();
                img.onerror = () => reject(new Error("Failed to load image for rotation."));
            });
            img.src = objectUrl;
            await loaded;

            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            if (!ctx) throw new Error("Canvas context unavailable.");

            const rotateRight = direction === "right";
            canvas.width = img.height;
            canvas.height = img.width;

            if (rotateRight) {
                ctx.translate(canvas.width, 0);
                ctx.rotate(Math.PI / 2);
            } else {
                ctx.translate(0, canvas.height);
                ctx.rotate(-Math.PI / 2);
            }
            ctx.drawImage(img, 0, 0);

            const mime = uploadedFile.type || "image/jpeg";
            const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, mime, 0.95));
            if (!blob) throw new Error("Failed to create rotated image.");

            const base = uploadedFile.name.replace(/\.[^.]+$/, "");
            const ext = mime.includes("png") ? "png" : mime.includes("webp") ? "webp" : "jpg";
            const rotated = new File([blob], `${base}_rotated.${ext}`, { type: mime });

            clearExtractedState();
            setImageCrop(null);
            setImageRender(null);
            setUploadFile(rotated);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unable to rotate image.");
        } finally {
            URL.revokeObjectURL(objectUrl);
        }
    }, [clearExtractedState, setUploadFile, uploadedFile]);

    const resetImageOrientation = React.useCallback(() => {
        if (!originalImageFile) return;
        clearExtractedState();
        setImageCrop(null);
        setImageRender(null);
        setUploadFile(originalImageFile);
    }, [clearExtractedState, originalImageFile, setUploadFile]);

    const onFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0] || null;
        void handleIncomingFile(file);
        event.currentTarget.value = "";
    };

    const closeCamera = React.useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
        }
        if (videoRef.current) videoRef.current.srcObject = null;
        setCameraOpen(false);
    }, []);

    React.useEffect(() => {
        if (!cameraOpen || !videoRef.current || !streamRef.current) return;
        const video = videoRef.current;
        const stream = streamRef.current;
        video.srcObject = stream;
        const playVideo = async () => {
            try {
                await video.play();
            } catch {
                // Ignore autoplay race; user can still capture once stream becomes active.
            }
        };
        if (video.readyState >= 1) {
            void playVideo();
        } else {
            video.onloadedmetadata = () => {
                void playVideo();
            };
        }
        return () => {
            video.onloadedmetadata = null;
        };
    }, [cameraOpen]);

    const openCamera = React.useCallback(async () => {
        try {
            let media: MediaStream;
            try {
                media = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: { ideal: "environment" } },
                    audio: false,
                });
            } catch {
                // Some browsers/devices reject facingMode constraints; retry with generic video.
                media = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            }
            streamRef.current = media;
            setCameraOpen(true);
        } catch {
            cameraInputRef.current?.click();
        }
    }, []);

    const captureCameraFrame = React.useCallback(() => {
        const video = videoRef.current;
        if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) {
            setError("Camera is not ready yet.");
            return;
        }
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
            if (!blob) return;
            void handleIncomingFile(new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" }));
            closeCamera();
        }, "image/jpeg", 0.92);
    }, [closeCamera, handleIncomingFile]);

    const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        setIsDragging(false);
        void handleIncomingFile(event.dataTransfer.files?.[0] || null);
    };

    const handleClipboardButtonPaste = React.useCallback(async () => {
        if (!navigator.clipboard || !("read" in navigator.clipboard)) {
            setError("Clipboard read is not supported in this browser. Press Ctrl+V in the upload area instead.");
            return;
        }
        try {
            const items = await (navigator.clipboard as Clipboard & { read: () => Promise<ClipboardItem[]> }).read();
            for (const item of items) {
                const imageType = item.types.find((t) => t.startsWith("image/"));
                if (!imageType) continue;
                const blob = await item.getType(imageType);
                await handleIncomingFile(new File([blob], `clipboard-${Date.now()}.png`, { type: imageType }));
                return;
            }
            setError("No image found in clipboard.");
        } catch {
            setError("Clipboard access blocked. Allow clipboard permission or use Ctrl+V.");
        }
    }, [handleIncomingFile]);

    const handleClear = () => {
        setUploadFile(null);
        setOriginalImageFile(null);
        clearExtractedState();
        setSketchHasContent(false);
        sketchRef.current?.clear();
        clearPdfState();
        setImageCrop(null);
        setImageRender(null);
    };

    const handleSubmit = async () => {
        if (!isSubmitEnabled || isSubmitting || isPdfMode) return;
        if (onResolveText) {
            const extractedText = imageExtractedQuestions
                .map((q, index) => {
                    const text = normalizeExtractText(q.text || "");
                    return text ? `${index + 1}) ${text}` : "";
                })
                .filter(Boolean)
                .join("\n\n");
            const requestText = questionText.trim();
            const resolveText = requestText || extractedText;
            if (!resolveText) {
                setError("Please extract a question first or add a special request.");
                return;
            }
            setIsSubmitting(true);
            setError(null);
            try {
                await onResolveText(resolveText, {
                    ocr_used: Boolean(ocrAttemptId),
                    ocr_source: uploadedFile?.type === "application/pdf" ? "pdf" : "image",
                    ocr_engine: ocrEngineUsed || imageExtractEngine,
                    source_type: ocrAttemptId ? "ocr" : undefined,
                    source_id: ocrAttemptId || undefined,
                    question_text: resolveText,
                });
            } catch (err) {
                setError(err instanceof Error ? err.message : "Unexpected error");
            } finally {
                setIsSubmitting(false);
            }
            return;
        }
        setIsSubmitting(true);
        setError(null);
        setResult(null);
        try {
            const userId = (typeof window !== "undefined" && window.localStorage.getItem("user_id")) || "1";
            const effectiveTier = resolveSolveTier();
            const effectiveMode = resolveSolveMode(effectiveTier);
            const formData = new FormData();
            formData.append("mode", activeSubTab);
            formData.append("question_text", questionText);
            formData.append("tier", effectiveTier);
            formData.append("requested_mode", effectiveMode);
            let fileToSend: File | null = null;
            if (activeSubTab === "upload") fileToSend = uploadedFile;
            else if (activeSubTab === "sketch" && sketchRef.current?.hasContent()) fileToSend = await sketchRef.current.exportAsFile();
            if (fileToSend) {
                formData.append("image", fileToSend);
                formData.append("original_filename", fileToSend.name);
            }
            const response = await fetch(`/api/v1/math/solve_from_image_or_sketch?user_id=${encodeURIComponent(userId)}`, { method: "POST", body: formData });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload?.detail || payload?.error || "Unable to solve this request.");
            setResult(payload as SolveResponse);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unexpected error");
        } finally {
            setIsSubmitting(false);
        }
    };

    const runPdfExtract = async (mode: "crop" | "page" | "document") => {
        if (!pdfSession) return;
        if (mode === "crop" && (!pdfCrop || !pdfRender)) {
            setError("Create a crop selection first.");
            return;
        }
        setExtracting(true);
        setPdfExtractProgress({
            current: 0,
            total: mode === "document" ? Math.max(1, pdfSession.pageCount) : 1,
            mode,
        });
        setError(null);
        setSolvedQuestions([]);
        try {
            const resolvedPdfEngine =
                imageExtractEngine === "auto"
                    ? (
                        ocrEngineAvailability.default_engine === "glm_ocr"
                            ? "glm_ocr"
                            : (ocrEngineAvailability.default_engine === "openai" ? "openai" : "pix2text")
                    )
                    : imageExtractEngine;
            const postExtract = async (payload: Record<string, unknown>): Promise<PdfExtractResponse> => {
                const res = await fetch("/api/v1/snap-solve/pdf/extract", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const rawText = await res.text();
                let data: Partial<PdfExtractResponse> = {};
                if (rawText) {
                    try {
                        data = JSON.parse(rawText) as PdfExtractResponse;
                    } catch {
                        if (!res.ok) {
                            throw new Error(rawText || "Extraction failed.");
                        }
                    }
                }
                if (!res.ok) throw new Error(extractErrorMessage(data, "Extraction failed."));
                return data as PdfExtractResponse;
            };

            let questions: ExtractedQuestion[] = [];
            if (mode === "document") {
                const merged: ExtractedQuestion[] = [];
                const totalPages = Math.max(1, pdfSession.pageCount);
                for (let pageIndex = 0; pageIndex < totalPages; pageIndex += 1) {
                    setPdfExtractProgress({ current: pageIndex, total: totalPages, mode });
                    const data = await postExtract({
                        pdf_id: pdfSession.pdfId,
                        mode: "page",
                        page_index: pageIndex,
                        crop: null,
                        image_render: null,
                        question_text: questionText || null,
                        engine_choice: resolvedPdfEngine,
                    });
                    const pageQuestions = (data.extracted_questions || []).map((q, idx) => ({
                        ...q,
                        id: q.id || `p${pageIndex}-q${idx + 1}`,
                        page: typeof q.page === "number" ? q.page : pageIndex,
                    }));
                    merged.push(...pageQuestions);
                    setPdfExtractProgress({ current: pageIndex + 1, total: totalPages, mode });
                }
                questions = merged;
            } else {
                const data = await postExtract({
                    pdf_id: pdfSession.pdfId,
                    mode,
                    page_index: pdfPage - 1,
                    crop: mode === "crop" ? pdfCrop : null,
                    image_render: mode === "crop" || mode === "page" ? pdfRender : null,
                    question_text: questionText || null,
                    engine_choice: resolvedPdfEngine,
                });
                questions = data.extracted_questions || [];
                setPdfExtractProgress({ current: 1, total: 1, mode });
            }
            setExtractedQuestions(questions);
            setSelectedQuestionIds(new Set(questions.map((q) => q.id)));
            if (!questions.length) {
                const warning = mode === "crop"
                    ? "No questions detected in this crop. Try a larger crop or use Extract This Page."
                    : "No questions detected in selected PDF pages.";
                setError(warning || "No questions detected in this crop. Try a larger crop or use Extract This Page.");
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : "Extraction failed.");
        } finally {
            setExtracting(false);
        }
    };

    const solveSelectedQuestions = async () => {
        const selected = extractedQuestions.filter((q) => selectedQuestionIds.has(q.id));
        if (!selected.length) {
            setError("Select at least one extracted question.");
            return;
        }
        const effectiveTier = resolveSolveTier();
        const effectiveMode = resolveSolveMode(effectiveTier);
        const batchMode = resolveSolveBatchMode(effectiveTier, effectiveMode);
        const cap = getSolveBatchCap(batchMode);
        if (selected.length > cap) {
            const message = mapSolveBatchErrorMessage("TOO_MANY_QUESTIONS", cap);
            setError(message);
            toast?.pushToast({ type: "error", title: "Selection too large", message });
            return;
        }

        setSolvingSelected(true);
        setError(null);
        try {
            const userId = (typeof window !== "undefined" && window.localStorage.getItem("user_id")) || "1";
            const body = buildSolveBatchPayload({
                selectedQuestions: selected.map((q) => ({ question_id: q.id, text: q.text })),
                mode: batchMode,
                tier: resolveSolveBatchTier(effectiveTier),
            });

            const response = await fetch(`/api/v1/math/solve_text_batch?user_id=${encodeURIComponent(userId)}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                const detail = payload?.detail && typeof payload.detail === "object" ? payload.detail : payload;
                const code = typeof detail?.code === "string" ? detail.code : undefined;
                const maxAllowed = typeof detail?.max_allowed === "number" ? detail.max_allowed : cap;
                const message = mapSolveBatchErrorMessage(code, maxAllowed);
                setError(message);
                toast?.pushToast({ type: "error", title: "Solve failed", message });
                return;
            }

            const solutions = Array.isArray(payload?.solutions) ? payload.solutions : [];
            const byId = new Map<string, Record<string, unknown>>();
            for (const solution of solutions) {
                if (!solution || typeof solution !== "object") continue;
                const questionId = String((solution as { question_id?: string }).question_id || "").trim();
                if (!questionId) continue;
                byId.set(questionId, solution as Record<string, unknown>);
            }

            const out: SolvedQuestion[] = selected.map((q) => {
                const solved = byId.get(q.id);
                if (!solved) {
                    return { questionId: q.id, error: "No solution returned for this question." };
                }
                const finalAnswer = (solved.final_answer && typeof solved.final_answer === "object")
                    ? (solved.final_answer as { answer_text?: string; answer_latex?: string | null })
                    : {};
                return {
                    questionId: q.id,
                    result: {
                        answer_markdown: String(finalAnswer.answer_text || "No answer returned."),
                        answer_latex: finalAnswer.answer_latex || null,
                        meta: {
                            mode: "upload",
                            mime: "text/plain",
                            latency_ms: Number(payload?.telemetry?.latency_ms || 0),
                            request_id: typeof payload?.request_id === "string" ? payload.request_id : undefined,
                        },
                    },
                };
            });

            setSolvedQuestions(out);
        } catch (e) {
            const message = e instanceof Error ? e.message : "Solve failed.";
            setError(message);
            toast?.pushToast({ type: "error", title: "Solve failed", message });
        } finally {
            setSolvingSelected(false);
        }
    };

    const btnBase =
        "inline-flex items-center justify-center rounded-xl px-3.5 py-2 text-xs font-semibold tracking-[0.01em] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 disabled:pointer-events-none disabled:opacity-50";
    const btnGhost =
        `${btnBase} border border-slate-500/45 bg-slate-900/55 text-slate-100 shadow-[0_8px_18px_-12px_rgba(6,182,212,0.45)] hover:-translate-y-[1px] hover:border-cyan-300/60 hover:bg-slate-800/80`;
    const btnLightGhost =
        `${btnBase} border border-slate-300 bg-white text-slate-700 shadow-[0_8px_18px_-12px_rgba(2,132,199,0.22)] hover:-translate-y-[1px] hover:border-sky-400 hover:text-sky-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-sky-400 dark:hover:text-sky-200`;
    const btnPrimary =
        `${btnBase} border border-sky-400/40 bg-gradient-to-r from-sky-500 via-cyan-500 to-teal-500 text-white shadow-[0_12px_24px_-14px_rgba(14,165,233,0.9)] hover:-translate-y-[1px] hover:brightness-110`;
    const btnSuccess =
        `${btnBase} border border-emerald-400/40 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow-[0_12px_24px_-14px_rgba(16,185,129,0.9)] hover:-translate-y-[1px] hover:brightness-110`;

    return (
        <div className="flex flex-col gap-4">
            <div className="grid w-full grid-cols-2 gap-2 rounded-2xl border border-slate-200/90 bg-white/85 p-1.5 shadow-[0_16px_30px_-24px_rgba(2,132,199,0.65)] backdrop-blur dark:border-slate-700 dark:bg-slate-800/85">
                <button
                    type="button"
                    onClick={() => setActiveSubTab("upload")}
                    data-testid="snap-subtab-upload"
                    className={`${btnBase} px-4 py-2.5 text-sm font-bold ${activeSubTab === "upload"
                        ? "border border-sky-400/60 bg-gradient-to-r from-sky-500 to-cyan-500 text-white shadow-[0_14px_24px_-14px_rgba(14,165,233,0.95)]"
                        : "border border-slate-300 bg-slate-50 text-slate-700 hover:bg-sky-50 hover:text-sky-700 dark:border-slate-700 dark:bg-slate-900/55 dark:text-slate-200 dark:hover:bg-sky-950/40 dark:hover:text-sky-200"
                        }`}
                >
                    Upload
                </button>
                <button
                    type="button"
                    onClick={() => setActiveSubTab("sketch")}
                    data-testid="snap-subtab-sketch"
                    className={`${btnBase} px-4 py-2.5 text-sm font-bold ${activeSubTab === "sketch"
                        ? "border border-emerald-400/60 bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-[0_14px_24px_-14px_rgba(16,185,129,0.9)]"
                        : "border border-slate-300 bg-slate-50 text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 dark:border-slate-700 dark:bg-slate-900/55 dark:text-slate-200 dark:hover:bg-emerald-950/40 dark:hover:text-emerald-200"
                        }`}
                >
                    Sketch
                </button>
            </div>

            {activeSubTab === "upload" ? (
                <div onDrop={handleDrop} onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} className={`rounded-2xl border-2 border-dashed p-6 transition-colors ${isDragging ? "border-primary bg-primary/10" : "border-slate-700 bg-slate-900 text-slate-100"}`}>
                    <div className="mb-4 flex items-center gap-2 text-xs">
                        <button
                            type="button"
                            onClick={() => {
                                clearExtractedState();
                                fileInputRef.current?.click();
                            }}
                            className={btnGhost}
                        >
                            Upload file
                        </button>
                        <button type="button" onClick={openCamera} className={btnGhost}>Camera</button>
                        <button type="button" onClick={() => void handleClipboardButtonPaste()} className={btnGhost}>Paste from Clipboard</button>
                    </div>
                    <input ref={fileInputRef} type="file" className="hidden" accept={ACCEPTED_UPLOAD} onChange={onFileInputChange} data-testid="snap-upload-input" />
                    <input ref={cameraInputRef} type="file" className="hidden" accept="image/png,image/jpeg,image/webp" capture="environment" onChange={onFileInputChange} />
                    <div className="text-sm text-slate-300">Drag & drop, click upload, or paste a screenshot. Supports JPG, PNG, WEBP, PDF.</div>

                    {uploadedFile && (
                        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-3">
                            <div className="text-xs font-semibold text-slate-300">Selected: {uploadedFile.name}</div>
                            {uploadedFile.type === "application/pdf" && <div className="mt-2 text-xs text-slate-400">PDF selected</div>}
                            {previewUrl && (
                                <div className="mt-3 flex flex-col gap-2">
                                    <div className="flex items-center gap-2 text-xs">
                                        <button
                                            type="button"
                                            className={btnGhost}
                                            onClick={() => {
                                                clearExtractedState();
                                                setImageCrop(null);
                                                if (imageRender) setImageRender({ ...imageRender });
                                            }}
                                        >
                                            Clear crop
                                        </button>
                                        <button
                                            type="button"
                                            className={`${btnGhost} gap-1`}
                                            onClick={() => void rotateImageFile("left")}
                                            title="Rotate left"
                                        >
                                            <span className="material-symbols-outlined text-[14px]">rotate_left</span>
                                            <span>Left</span>
                                        </button>
                                        <button
                                            type="button"
                                            className={`${btnGhost} gap-1`}
                                            onClick={() => void rotateImageFile("right")}
                                            title="Rotate right"
                                        >
                                            <span className="material-symbols-outlined text-[14px]">rotate_right</span>
                                            <span>Right</span>
                                        </button>
                                        <button
                                            type="button"
                                            className={`${btnGhost} gap-1`}
                                            onClick={resetImageOrientation}
                                            title="Reset image"
                                            disabled={!originalImageFile}
                                        >
                                            <span className="material-symbols-outlined text-[14px]">restart_alt</span>
                                            <span>Reset image</span>
                                        </button>
                                    </div>
                                    <PdfCropViewer
                                        imageUrl={previewUrl}
                                        pageLabel="Image (drag to crop area)"
                                        scale={1}
                                        onCropChange={(crop, render) => {
                                            setImageCrop(crop);
                                            setImageRender(render);
                                        }}
                                    />
                                </div>
                            )}
                            {uploadedFile.type.startsWith("image/") && (
                                <div className="mt-3 flex flex-wrap items-center gap-2">
                                    <label className="text-xs text-slate-300">Engine</label>
                                    <select
                                        value={imageExtractEngine}
                                        onChange={(e) => {
                                            const next = e.target.value as ImageExtractEngine;
                                            setImageExtractEngine(next);
                                            if (typeof window !== "undefined") {
                                                localStorage.setItem("snapsolve_ocr_engine", next);
                                            }
                                        }}
                                        className="rounded-lg border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100"
                                    >
                                        {(ocrEngineAvailability.local_engine_enabled || ocrEngineAvailability.openai_engine_enabled || ocrEngineAvailability.glm_ocr_engine_enabled) && (
                                            <option value="auto">
                                                Auto ({
                                                    ocrEngineAvailability.default_engine === "glm_ocr"
                                                        ? "GLM OCR default"
                                                        : (ocrEngineAvailability.default_engine === "openai" ? "OpenAI default" : "Pix2Text default")
                                                })
                                            </option>
                                        )}
                                        {ocrEngineAvailability.glm_ocr_engine_enabled && <option value="glm_ocr">GLM OCR (Ollama)</option>}
                                        {ocrEngineAvailability.local_engine_enabled && <option value="pix2text">Pix2Text (local)</option>}
                                        {ocrEngineAvailability.openai_engine_enabled && <option value="openai">OpenAI (gpt-5-mini)</option>}
                                    </select>
                                    <button
                                        type="button"
                                        onClick={() => void extractImageQuestions(uploadedFile)}
                                        disabled={imageExtracting}
                                        className={btnPrimary}
                                    >
                                        {imageExtracting ? "Extracting..." : "Extract"}
                                    </button>
                                    {imageExtractNote && <span className="text-xs text-emerald-300">{imageExtractNote}</span>}
                                </div>
                            )}
                            {extractProgressPct > 0 && (
                                <div className="mt-3 rounded-md border border-slate-700 bg-slate-900 p-2">
                                    <div className="mb-1 flex items-center justify-between text-[11px] text-slate-300">
                                        <span>{imageExtracting ? "Extracting..." : "Finalizing..."}</span>
                                        <span>{extractProgressPct}%</span>
                                    </div>
                                    <div className="h-1.5 w-full overflow-hidden rounded bg-slate-700">
                                        <div
                                            className="h-full rounded bg-cyan-400 transition-all duration-300"
                                            style={{ width: `${extractProgressPct}%` }}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {isPdfMode && pdfSession && (
                        <div className="mt-4 flex flex-col gap-3">
                            <div className="flex items-center gap-2 text-xs">
                                <button type="button" className={btnGhost} onClick={() => setPdfPage((p) => Math.max(1, p - 1))} disabled={pdfPage <= 1}>Prev</button>
                                <span>Page</span>
                                <input
                                    value={pdfPage}
                                    onChange={(e) => {
                                        const v = Number(e.target.value || "1");
                                        if (!Number.isFinite(v)) return;
                                        setPdfPage(Math.max(1, Math.min(pdfSession.pageCount, Math.floor(v))));
                                    }}
                                    className="w-14 rounded border border-slate-600 bg-slate-900 px-2 py-1 text-center"
                                />
                                <span>/ {pdfSession.pageCount}</span>
                                <button type="button" className={btnGhost} onClick={() => setPdfPage((p) => Math.min(pdfSession.pageCount, p + 1))} disabled={pdfPage >= pdfSession.pageCount}>Next</button>
                                <button type="button" className={btnGhost} onClick={() => setPdfScale((s) => Math.max(0.5, Number((s - 0.1).toFixed(2))))}>-</button>
                                <span>{Math.round(pdfScale * 100)}%</span>
                                <button type="button" className={btnGhost} onClick={() => setPdfScale((s) => Math.min(4, Number((s + 0.1).toFixed(2))))}>+</button>
                            </div>
                            {pdfLoading && <div className="text-xs text-slate-400">Rendering page...</div>}
                            {pdfPageImage && (
                                <div className="relative">
                                    <PdfCropViewer
                                        imageUrl={pdfPageImage.url}
                                        pageLabel={`Page ${pdfPage} / ${pdfSession.pageCount}`}
                                        onCropChange={(crop, render) => {
                                            setPdfCrop(crop);
                                            setPdfRender({ ...render, scale: pdfScale });
                                        }}
                                    />
                                    {extracting && (
                                        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-lg bg-slate-950/45 backdrop-blur-[2px]">
                                            <div className="text-xs font-semibold text-slate-100">
                                                {pdfExtractProgress?.mode === "document"
                                                    ? `Extracting page ${Math.min(pdfExtractProgress.total, pdfExtractProgress.current + 1)} of ${pdfExtractProgress.total}`
                                                    : "Extracting PDF content..."}
                                            </div>
                                            <div className="w-56 overflow-hidden rounded bg-slate-700">
                                                <div
                                                    className="h-1.5 rounded bg-cyan-400 transition-all duration-300"
                                                    style={{ width: `${extractProgressPct}%` }}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                            <div className="flex flex-wrap items-center gap-2">
                                <button type="button" onClick={() => void runPdfExtract("crop")} disabled={extracting || !pdfCrop} className={btnPrimary}>Extract Crop</button>
                                <button type="button" onClick={() => void runPdfExtract("page")} disabled={extracting} className={btnPrimary}>Extract This Page</button>
                                {PDF_DOCUMENT_ENABLED && (
                                    <button type="button" onClick={() => void runPdfExtract("document")} disabled={extracting} className={btnPrimary}>Extract Entire PDF (page-by-page)</button>
                                )}
                            </div>
                            {extractProgressPct > 0 && (
                                <div className="rounded-md border border-slate-700 bg-slate-900 p-2">
                                    <div className="mb-1 flex items-center justify-between text-[11px] text-slate-300">
                                        <span>
                                            {extracting
                                                ? (pdfExtractProgress?.mode === "document"
                                                    ? `Extracting pages ${Math.min(pdfExtractProgress.total, pdfExtractProgress.current + 1)} / ${pdfExtractProgress.total}`
                                                    : "Extracting...")
                                                : "Finalizing..."}
                                        </span>
                                        <span>{extractProgressPct}%</span>
                                    </div>
                                    <div className="h-1.5 w-full overflow-hidden rounded bg-slate-700">
                                        <div
                                            className="h-full rounded bg-cyan-400 transition-all duration-300"
                                            style={{ width: `${extractProgressPct}%` }}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-3">
                        <button type="button" onClick={() => setTool("draw")} className={tool === "draw" ? btnPrimary : btnLightGhost}>Pen</button>
                        <button type="button" onClick={() => setTool("erase")} className={tool === "erase" ? btnPrimary : btnLightGhost}>Eraser</button>
                        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">Brush <input type="range" min={2} max={24} value={brushSize} onChange={(e) => setBrushSize(Number(e.target.value))} /></label>
                        <button type="button" onClick={() => { sketchRef.current?.clear(); setSketchHasContent(false); }} className={btnLightGhost}>Clear canvas</button>
                    </div>
                    <SketchCanvas ref={sketchRef} tool={tool} brushSize={brushSize} onContentChange={setSketchHasContent} />
                </div>
            )}

            {activeSubTab === "upload" && uploadedFile && (uploadedFile.type.startsWith("image/") || isPdfMode) && ((imageExtracting || extracting) || extractedPreviewQuestions.length > 0) && (
                <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-2 text-sm font-bold">Extracted Text</div>
                    {(imageExtracting || extracting) ? (
                        <div className="text-xs text-slate-500">
                            {isPdfMode ? "Extracting text from PDF..." : "Extracting text from image..."}
                        </div>
                    ) : (
                        <div className="grid gap-3 md:grid-cols-2">
                            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
                                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Plain Text</div>
                                <pre data-testid="snap-image-extract-plain" className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200">
                                    {extractedPreviewText || `No questions detected from this ${isPdfMode ? "PDF" : "image"}.`}
                                </pre>
                            </div>
                            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">
                                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">LaTeX Review</div>
                                <article data-testid="snap-image-extract-latex" className="prose prose-slate max-w-none rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm dark:prose-invert dark:border-rose-900/40 dark:bg-rose-950/20">
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                        {extractedPreviewLatex || "_No extracted math text to render._"}
                                    </ReactMarkdown>
                                </article>
                            </div>
                        </div>
                    )}
                    <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-3 dark:border-violet-900/40 dark:bg-violet-950/20">
                        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
                            SymPy `parse_latex()` Output
                        </div>
                        <textarea
                            readOnly
                            value={
                                isSympyParsing
                                    ? "Parsing extracted LaTeX with sympy.parsing.latex.parse_latex()..."
                                    : (sympyParsedExpression || "")
                            }
                            rows={3}
                            className="w-full rounded-lg border border-violet-200 bg-white px-3 py-2 font-mono text-sm text-violet-900 outline-none dark:border-violet-900/50 dark:bg-slate-900 dark:text-violet-200"
                            placeholder="Parsed SymPy expression will appear here."
                        />
                        {sympyParseError && (
                            <div className="mt-2 text-xs text-rose-700 dark:text-rose-300">
                                Parse error: {sympyParseError}
                            </div>
                        )}
                    </div>
                </div>
            )}

            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">(Optional) input your question if you have special request</label>
                <textarea data-testid="snap-question-input" value={questionText} onChange={(e) => setQuestionText(e.target.value)} rows={4} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-primary dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" placeholder="Type any extra context or direct question..." />
            </div>

            {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

            {extractedQuestions.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-3 flex items-center justify-between gap-2">
                        <div className="text-sm font-bold">Extracted Questions</div>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                data-testid="snap-select-all-btn"
                                onClick={() => setSelectedQuestionIds(new Set(extractedQuestions.map((q) => q.id)))}
                                className={btnLightGhost}
                            >
                                Select all
                            </button>
                            <button
                                type="button"
                                data-testid="snap-clear-selection-btn"
                                onClick={() => setSelectedQuestionIds(new Set())}
                                className={btnLightGhost}
                            >
                                Clear selection
                            </button>
                        </div>
                    </div>
                    <div className="space-y-2">
                        {extractedQuestions.map((q) => (
                            <label key={q.id} className="flex items-start gap-2 rounded border border-slate-200 p-2 text-sm dark:border-slate-700">
                                <input
                                    type="checkbox"
                                    checked={selectedQuestionIds.has(q.id)}
                                    onChange={(e) => {
                                        setSelectedQuestionIds((prev) => {
                                            const next = new Set(prev);
                                            if (e.target.checked) next.add(q.id);
                                            else next.delete(q.id);
                                            return next;
                                        });
                                    }}
                                />
                                <div className="flex-1">
                                    <div className="font-medium">{q.text}</div>
                                    <div className="text-xs text-slate-500">confidence: {Math.round((q.confidence || 0) * 100)}%</div>
                                </div>
                            </label>
                        ))}
                    </div>
                    <button type="button" onClick={() => void solveSelectedQuestions()} disabled={solvingSelected || selectedQuestionIds.size === 0} className={`mt-3 ${btnSuccess}`}>
                        {solvingSelected ? "Solving..." : "Solve selected questions individually"}
                    </button>
                </div>
            )}

            <div className="sticky bottom-3 z-20 mt-3 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/95">
                {requiresOcrReview && (
                    <div className="mb-3 flex justify-end">
                        <label className="inline-flex items-center gap-3 rounded-lg border-2 border-emerald-500 bg-emerald-100 px-5 py-2.5 text-base font-extrabold text-emerald-950 shadow-md ring-1 ring-emerald-300/70">
                            <input
                                type="checkbox"
                                checked={ocrReviewed}
                                onChange={(e) => setOcrReviewed(e.target.checked)}
                                className="h-5 w-5 accent-emerald-700"
                            />
                            I confirm the extract is correct and reviewed
                        </label>
                    </div>
                )}

                <div className="flex items-center justify-end gap-3">
                    <button type="button" onClick={handleClear} data-testid="snap-clear-btn" className={btnLightGhost}>Clear</button>
                    <button type="button" onClick={handleSubmit} disabled={!resolveEnabled || isSubmitting} data-testid="snap-submit-btn" className={btnSuccess}>{isSubmitting ? "Resolving..." : "Resolve"}</button>
                </div>
            </div>

            {result && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-2 text-xs text-slate-500">Mode: {result.meta.mode} - MIME: {result.meta.mime} - Latency: {result.meta.latency_ms}ms</div>
                    <article className="prose prose-slate max-w-none dark:prose-invert">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{result.answer_markdown || "_No answer returned._"}</ReactMarkdown>
                    </article>
                    {result.answer_latex && <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"><code>{result.answer_latex}</code></div>}
                </div>
            )}

            {solvedQuestions.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-3 text-sm font-bold">Solved Results</div>
                    <div className="space-y-3">
                        {solvedQuestions.map((item) => (
                            <div key={item.questionId} className="rounded border border-slate-200 p-3 dark:border-slate-700">
                                <div className="mb-2 text-xs text-slate-500">Question ID: {item.questionId}</div>
                                {item.error && <div className="text-sm text-rose-600">{item.error}</div>}
                                {item.result && (
                                    <article className="prose prose-slate max-w-none dark:prose-invert">
                                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                            {item.result.answer_markdown || "_No answer returned._"}
                                        </ReactMarkdown>
                                    </article>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {cameraOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
                    <div className="w-full max-w-2xl rounded-xl bg-slate-900 p-4">
                        <div className="mb-3 text-sm font-bold text-white">Take a photo</div>
                        <video ref={videoRef} className="h-auto max-h-[70vh] w-full rounded-lg bg-black" playsInline autoPlay muted />
                        <div className="mt-4 flex items-center justify-end gap-2">
                            <button type="button" onClick={closeCamera} className={btnGhost}>Cancel</button>
                            <button type="button" onClick={captureCameraFrame} className={btnPrimary}>Capture</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
