"use client";

import React from "react";
import SnapSolveUploader from "./SnapSolveUploader";
import PdfPageViewer from "./PdfPageViewer";
import CropWorkspace from "./CropWorkspace";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import {
    CropArea,
    buildRequestHash,
    clamp,
    getCroppedImageBlob,
    hashBytes,
    loadCache,
    saveCache,
    blobToBase64,
    getRotatedSize,
} from "./snapSolveUtils";

type SnapSolveV2Props = {
    onUseText: (text: string) => void;
    onSolveText: (text: string) => void;
    requestedMode?: "minimal" | "detailed";
};

type ExtractQuestion = {
    id: string;
    text: string;
    confidence: number;
    is_valid_math: boolean;
    reason_if_invalid?: string | null;
    type?: string | null;
    bbox?: { x: number; y: number; w: number; h: number } | null;
    requires_figure?: boolean | null;
    figure_type?: string | null;
    figure_bbox?: { x: number; y: number; w: number; h: number } | null;
    figure_role?: string | null;
};

type ExtractResponse = {
    is_math_page: boolean;
    notes: string[];
    questions: ExtractQuestion[];
    cache_hit: boolean;
};

type SolveResult = {
    question_id: string;
    ok: boolean;
    solve_response_json?: Record<string, unknown>;
    error?: string;
    telemetry?: Record<string, unknown>;
    credits_reserved?: number;
    credits_final?: number;
    credits_refunded?: number;
};

import { useAudioRecorder } from "@/hooks/useAudioRecorder";

const MAX_MB = parseInt(process.env.NEXT_PUBLIC_SNAP_MAX_MB || "10", 10);
const MAX_BYTES = MAX_MB * 1024 * 1024;
const MAX_EDGE = 2000;
const JPEG_QUALITY = 0.83;
const TOKENS_PER_CREDIT = 2000;

export default function SnapSolveV2({ onUseText, onSolveText, requestedMode = "minimal" }: SnapSolveV2Props) {
    const [file, setFile] = React.useState<File | null>(null);
    const [fileType, setFileType] = React.useState<"image" | "pdf" | null>(null);
    const [imageSrc, setImageSrc] = React.useState<string | null>(null);
    const [pageNumber, setPageNumber] = React.useState(1);
    const [pageCount, setPageCount] = React.useState(1);
    const [crop, setCrop] = React.useState({ x: 0, y: 0 });
    const [zoom, setZoom] = React.useState(1);
    const [rotation, setRotation] = React.useState(0);
    const [cropPixels, setCropPixels] = React.useState<CropArea | null>(null);
    const [fullPage, setFullPage] = React.useState(false);
    const [status, setStatus] = React.useState<
        "idle" | "uploading" | "rendering" | "cropping" | "extracting" | "ready" | "solving" | "done" | "error" |
        "transcribing" | "resolving_intent" | "executing"
    >("idle");
    const [error, setError] = React.useState<string | null>(null);
    const [extractResult, setExtractResult] = React.useState<ExtractResponse | null>(null);
    const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
    const [solveResults, setSolveResults] = React.useState<SolveResult[]>([]);
    const [isBusy, setIsBusy] = React.useState(false);
    const [imageSize, setImageSize] = React.useState<{ width: number; height: number } | null>(null);
    const [figureCrops, setFigureCrops] = React.useState<Record<string, string>>({});
    const [cropResetToken, setCropResetToken] = React.useState(0);
    const [viewportSize, setViewportSize] = React.useState<{ width: number; height: number } | null>(null);
    const [ocrMetadata, setOcrMetadata] = React.useState({
        ocr_confidence: 0,
        ocr_warnings: [] as string[],
        ocr_source: "image",
        ocr_engine: "snap_v2",
    });

    // Voice & Selection State
    const [voiceMode, setVoiceMode] = React.useState(false);
    const [selectionBBox, setSelectionBBox] = React.useState<{ x: number, y: number, w: number, h: number } | null>(null);
    const [voiceTranscript, setVoiceTranscript] = React.useState<string | null>(null);
    const [voiceIntent, setVoiceIntent] = React.useState<string | null>(null);
    const [errorDiagnosis, setErrorDiagnosis] = React.useState<{
        what_is_wrong: string;
        minimal_fix: string;
        confidence?: number;
    } | null>(null);
    const [localSteps, setLocalSteps] = React.useState<string[] | null>(null);

    // Import hook (assuming it's available as per plan)
    const {
        state: recorderState,
        startRecording,
        stopRecording,
        durationMs,
        error: recorderError
    } = useAudioRecorder();

    const abortRef = React.useRef<AbortController | null>(null);

    const handleVoiceCommand = async (audioBlob: Blob) => {
        setVoiceTranscript(null);
        setVoiceIntent(null);
        if (!audioBlob) {
            console.error("No audio recorded");
            return;
        }
        setStatus("transcribing" as any);
        setIsBusy(true);

        try {
            console.log("Audio blob type:", audioBlob.type); // Debugging

            // Determine extension from blob type (e.g. "audio/mp4" -> "mp4", "audio/webm;codecs=opus" -> "webm")
            // Default to "webm" if parsing fails, but browser usually gives valid mime.
            // Common types: audio/webm, audio/mp4, audio/ogg, audio/wav
            let ext = "webm";
            if (audioBlob.type.includes("mp4")) ext = "mp4";
            else if (audioBlob.type.includes("wav")) ext = "wav";
            else if (audioBlob.type.includes("ogg")) ext = "ogg";
            else if (audioBlob.type.includes("id3")) ext = "mp3"; // rare recording format
            else if (audioBlob.type.includes("mpeg")) ext = "mp3";

            // 1. Transcribe with timeout
            const formData = new FormData();
            formData.append("file", audioBlob, `audio.${ext}`);

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 20000); // 20s timeout for transcription

            const transcribeRes = await fetch("/api/v1/audio/transcribe", {
                method: "POST",
                body: formData,
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!transcribeRes.ok) throw new Error(`Transcription failed: ${transcribeRes.status}`);
            const transcribeData = await transcribeRes.json();
            if (!transcribeData.ok) throw new Error(transcribeData.error || "Unknown transcription error");

            const transcript = transcribeData.transcript;
            setVoiceTranscript(transcript);
            setStatus("resolving_intent" as any); // Custom status for UI

            // 2. Resolve Intent
            const commandPayload = {
                transcript,
                selection_bbox: selectionBBox,
                page_context: {
                    source: fileType === "pdf" ? "pdf_page" : "image",
                    page_number: pageNumber,
                    // Note: We might want real crop bbox if available, but selectionBBox is key
                }
            };

            const commandRes = await fetch("/api/v1/voice/command", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(commandPayload)
            });
            const commandData = await commandRes.json();

            if (!commandData.ok) throw new Error(commandData.error?.message || "Intent resolution failed");

            const intent = commandData.command;
            setVoiceIntent(intent.intent);
            setStatus("executing" as any); // Custom status

            // 3. Execute Intent
            switch (intent.intent) {
                case "EXTRACT_QUESTIONS":
                    await handleExtract();
                    break;
                case "FINAL_ANSWER_ONLY":
                case "NEXT_STEP_ONLY":
                case "DETAILED_SOLUTION":
                    // If we have text ready (extracted), solve it.
                    // If not, we might need to extract first (or solve the crop directly if supported)
                    // For Phase 1, let's assume we solve the crop directly if supported, or error if no questions extracted.
                    // TODO: Logic to solve crop directly if backend supports it vs extracting first.
                    // Falling back to extract -> solve flow or alerting user.
                    if (extractResult && selectedIds.size > 0) {
                        // Solve selected with override
                        // NOTE: We need to modify handleSolveSelected to accept overrides, or just implement a custom call here.
                        // For now, let's just trigger extract if no questions, or user must select.
                        alert(`Intent: ${intent.intent} - Please select questions to apply this.`);
                    } else {
                        await handleExtract(); // Default action to get started
                    }
                    break;
                case "FIND_FIRST_ERROR":
                    if (!selectionBBox || !imageSrc || !imageSize || !cropPixels) {
                        alert("Please select the region with the error first.");
                        break;
                    }
                    setStatus("executing" as any);

                    // Map selection coordinates from viewport to actual image coordinates
                    // selectionBBox is normalized (0-1) relative to viewport
                    // cropPixels is the current visible area in actual image pixels
                    // We need to map the selection through the crop area

                    const selectionInCrop = {
                        x: selectionBBox.x * cropPixels.width,
                        y: selectionBBox.y * cropPixels.height,
                        width: selectionBBox.w * cropPixels.width,
                        height: selectionBBox.h * cropPixels.height
                    };

                    const activeCrop = {
                        x: cropPixels.x + selectionInCrop.x,
                        y: cropPixels.y + selectionInCrop.y,
                        width: selectionInCrop.width,
                        height: selectionInCrop.height
                    };

                    const blob = await getCroppedImageBlob({
                        imageSrc,
                        crop: activeCrop,
                        rotation: rotation,
                        maxEdge: 1500,  // Higher resolution for better OCR
                        quality: 0.95,  // Higher quality to preserve text clarity
                        fullPage: false,
                    });

                    // 2. Upload to GPT-4o Vision endpoint
                    const errForm = new FormData();
                    errForm.append("file", blob, "selection.jpg");
                    errForm.append("transcript", transcript);

                    const errRes = await fetch("/api/v1/find_error", { method: "POST", body: errForm });
                    const errData = await errRes.json();

                    if (errData.ok && errData.what_is_wrong) {
                        setVoiceIntent(`Error Found: ${errData.what_is_wrong}`);
                        setErrorDiagnosis({
                            what_is_wrong: errData.what_is_wrong,
                            minimal_fix: errData.minimal_fix,
                            confidence: errData.confidence
                        });
                    } else if (errData.ok) {
                        setVoiceIntent("No error found.");
                        setErrorDiagnosis({
                            what_is_wrong: "No errors detected",
                            minimal_fix: "Your work appears correct!"
                        });
                    } else {
                        throw new Error(errData.error || "Failed to analyze error");
                    }
                    break;
                default:
                    console.log("Unhandled intent:", intent);
            }
            setStatus("ready");

        } catch (err: any) {
            setError(err.message);
            setStatus("error");
        } finally {
            setIsBusy(false);
        }
    };

    const handleMicDown = async () => {
        await startRecording();
    };

    const handleMicUp = async () => {
        const blob = await stopRecording();
        if (blob) {
            handleVoiceCommand(blob);
        }
    };

    const handleResetCropControls = React.useCallback(() => {
        setCropResetToken((prev) => prev + 1);
        setCrop({ x: 0, y: 0 });
        setZoom(1);
        setRotation(0);
        setCropPixels(null);
        // Reset Voice
        setVoiceMode(false);
        setSelectionBBox(null);
        setVoiceTranscript(null);
        setVoiceIntent(null);
    }, [setCrop, setZoom, setRotation, setCropPixels]);

    const resetAll = React.useCallback(() => {
        if (imageSrc && imageSrc.startsWith("blob:")) {
            URL.revokeObjectURL(imageSrc);
        }
        setFile(null);
        setFileType(null);
        setImageSrc(null);
        setPageNumber(1);
        setPageCount(1);
        setCrop({ x: 0, y: 0 });
        setZoom(1);
        setRotation(0);
        setCropPixels(null);
        setFullPage(false);
        setStatus("idle");
        setError(null);
        setExtractResult(null);
        setSelectedIds(new Set());
        setSolveResults([]);
        setIsBusy(false);
        setFigureCrops({});
        if (abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
        }
        handleResetCropControls();
    }, [imageSrc, handleResetCropControls]);

    const handleFile = React.useCallback((selectedFile: File) => {
        if (!selectedFile) return;
        setStatus("uploading");
        setError(null);
        if (selectedFile.size > MAX_BYTES) {
            setError(`File too large. Max ${MAX_MB}MB.`);
            setStatus("error");
            return;
        }
        const isPdf = selectedFile.type === "application/pdf" || selectedFile.name.toLowerCase().endsWith(".pdf");
        const isImage = selectedFile.type.startsWith("image/");
        if (!isPdf && !isImage) {
            setError("Unsupported file type. Use PDF, JPG, PNG, or WEBP.");
            setStatus("error");
            return;
        }
        resetAll();
        setFile(selectedFile);
        setFileType(isPdf ? "pdf" : "image");
        setStatus(isPdf ? "rendering" : "cropping");
        if (isImage) {
            const url = URL.createObjectURL(selectedFile);
            setImageSrc(url);
        }
    }, [resetAll]);

    React.useEffect(() => {
        if (fileType === "pdf") {
            setStatus("rendering");
        }
    }, [fileType, pageNumber]);

    React.useEffect(() => {
        if (imageSrc && status === "rendering") {
            setStatus("cropping");
        }
    }, [imageSrc, status]);



    const handleExtract = async () => {
        if (!file || !imageSrc) return;
        setIsBusy(true);
        setError(null);
        setStatus("extracting");

        if (abortRef.current) abortRef.current.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        try {
            if (!fullPage && !cropPixels) {
                setError("Select a crop region.");
                setStatus("error");
                setIsBusy(false);
                return;
            }
            const fileBytes = await file.arrayBuffer();
            const fileHash = await hashBytes(fileBytes);
            let normalizedCrop: CropArea | null = null;
            if (!fullPage && cropPixels && imageSize) {
                const rotatedSize = getRotatedSize(imageSize.width, imageSize.height, rotation);
                normalizedCrop = {
                    x: clamp(cropPixels.x / rotatedSize.width, 0, 1),
                    y: clamp(cropPixels.y / rotatedSize.height, 0, 1),
                    width: clamp(cropPixels.width / rotatedSize.width, 0, 1),
                    height: clamp(cropPixels.height / rotatedSize.height, 0, 1),
                };
            }

            const meta = {
                pageNumber,
                crop: fullPage ? null : normalizedCrop,
                rotation,
            };
            const requestHash = await buildRequestHash(fileBytes, meta);
            const cache = loadCache();
            if (cache[requestHash]) {
                setExtractResult(cache[requestHash] as ExtractResponse);
                setStatus("ready");
                setIsBusy(false);
                return;
            }

            const blob = await getCroppedImageBlob({
                imageSrc,
                crop: fullPage ? null : cropPixels,
                rotation,
                maxEdge: MAX_EDGE,
                quality: JPEG_QUALITY,
                fullPage,
            });

            const form = new FormData();
            form.append("file", blob, "extract.jpg");
            form.append("page_number", String(pageNumber));
            form.append("file_hash", fileHash);
            form.append("source", fileType === "pdf" ? "pdf_page" : "image");
            form.append("user_selection", fullPage ? "whole_page" : "crop");
            form.append("rotation", String(rotation));
            if (imageSize) {
                form.append("preview_w", String(imageSize.width));
                form.append("preview_h", String(imageSize.height));
            }
            if (viewportSize) {
                form.append("viewport_w", String(viewportSize.width));
                form.append("viewport_h", String(viewportSize.height));
            }
            if (normalizedCrop && !fullPage) {
                form.append("crop_x", String(normalizedCrop.x));
                form.append("crop_y", String(normalizedCrop.y));
                form.append("crop_w", String(normalizedCrop.width));
                form.append("crop_h", String(normalizedCrop.height));
            }

            const userId = localStorage.getItem("user_id") || "1";
            const res = await fetch(`/api/v1/extract_questions?user_id=${userId}`, {
                method: "POST",
                body: form,
                signal: controller.signal,
            });
            if (!res.ok) {
                const detail = await res.text();
                throw new Error(detail || "Extract failed");
            }

            const data = await res.json();
            setExtractResult(data);

            if (data?.questions && data.questions.length > 0) {
                const confidences = data.questions.map((q: any) => q.confidence ?? 0);
                const avgConfidence = confidences.reduce((sum: number, v: number) => sum + v, 0) / confidences.length;
                const warnings = data.questions
                    .filter((q: any) => q.reason_if_invalid && !q.is_valid_math)
                    .map((q: any) => q.reason_if_invalid)
                    .filter(Boolean);
                setOcrMetadata({
                    ocr_confidence: avgConfidence,
                    ocr_warnings: warnings,
                    ocr_source: fileType === "pdf" ? "pdf" : "image",
                    ocr_engine: "snap_v2",
                });
            }
            cache[requestHash] = data;
            saveCache(cache);
            setStatus(data.ok ? "ready" : "error");
            if (!data.ok) setError(data.error || "Extraction returned error state.");
        } catch (err) {
            if (!(err instanceof DOMException && err.name === "AbortError")) {
                const message = err instanceof Error ? err.message : "Extract failed";
                setError(message);
                setStatus("error");
            }
        } finally {
            setIsBusy(false);
        }
    };

    const handleCaptureFigure = async (questionId: string, cropArea: CropArea | null) => {
        if (!imageSrc) return;
        if (!cropArea) {
            setError("Select a crop region for the figure.");
            return;
        }
        const blob = await getCroppedImageBlob({
            imageSrc,
            crop: cropArea,
            rotation,
            maxEdge: MAX_EDGE,
            quality: JPEG_QUALITY,
            fullPage: false,
        });
        const base64 = await blobToBase64(blob);
        setFigureCrops((prev) => ({ ...prev, [questionId]: base64 }));
    };

    const handleUseSuggestedFigure = async (question: ExtractQuestion) => {
        if (!imageSrc || !imageSize || !question.figure_bbox) return;
        const cropArea: CropArea = {
            x: question.figure_bbox.x * imageSize.width,
            y: question.figure_bbox.y * imageSize.height,
            width: question.figure_bbox.w * imageSize.width,
            height: question.figure_bbox.h * imageSize.height,
        };
        await handleCaptureFigure(question.id, cropArea);
    };

    const toggleSelect = (id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    const selectAllValid = () => {
        if (!extractResult) return;
        const next = new Set<string>();
        extractResult.questions.forEach((q) => {
            if (q.is_valid_math) next.add(q.id);
        });
        setSelectedIds(next);
    };

    const handleSolveSelected = async () => {
        if (!extractResult) return;
        const selected = extractResult.questions.filter((q) => selectedIds.has(q.id));
        if (selected.length === 0) {
            setError("Select at least one question.");
            return;
        }
        setStatus("solving");
        setIsBusy(true);
        setError(null);
        if (abortRef.current) abortRef.current.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const userId = localStorage.getItem("user_id") || "1";
            const items = selected.map((q) => ({
                question_id: q.id,
                text: q.text,
                requested_mode: requestedMode,
                requires_figure: q.requires_figure || false,
                figure_image_base64: figureCrops[q.id] || null,
            }));
            const res = await fetch(`/api/v1/solve_questions_batch?user_id=${userId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    items,
                    features_used: {
                        ocr_used: true,
                        ocr_confidence: ocrMetadata.ocr_confidence,
                        ocr_warnings: ocrMetadata.ocr_warnings,
                        ocr_source: ocrMetadata.ocr_source,
                        ocr_engine: ocrMetadata.ocr_engine,
                    },
                }),
                signal: controller.signal,
            });
            if (!res.ok) {
                const detail = await res.text();
                throw new Error(detail || "Solve failed");
            }
            const data = await res.json();
            setSolveResults(data.results || []);
            setStatus("done");
        } catch (err) {
            if (!(err instanceof DOMException && err.name === "AbortError")) {
                const message = err instanceof Error ? err.message : "Solve failed";
                setError(message);
                setStatus("error");
            }
        } finally {
            setIsBusy(false);
        }
    };

    const canExtract = Boolean(imageSrc) && !isBusy;
    const selectedCount = selectedIds.size;
    const estimatedCredits = React.useMemo(() => {
        if (!extractResult || selectedIds.size === 0) return 0;
        const baseCost = requestedMode === "detailed" ? 2 : 1;
        let total = 0;
        extractResult.questions.forEach((q) => {
            if (!selectedIds.has(q.id)) return;
            const tokenEstimate = Math.max(q.text.length / 4, 1);
            total += baseCost + tokenEstimate / TOKENS_PER_CREDIT;
        });
        return total;
    }, [extractResult, selectedIds, requestedMode]);

    const handleFindErrorLocal = async () => {
        if (!selectionBBox || !imageSrc || !imageSize || !cropPixels) {
            setError("Selection data incomplete. Please re-circle.");
            return;
        }

        setStatus("executing" as any);
        setIsBusy(true);
        setError(null);
        try {
            // 1. Calculate selection coordinates in image space
            const selectionInCrop = {
                x: selectionBBox.x * cropPixels.width,
                y: selectionBBox.y * cropPixels.height,
                width: selectionBBox.w * cropPixels.width,
                height: selectionBBox.h * cropPixels.height
            };
            const activeCrop = {
                x: cropPixels.x + selectionInCrop.x,
                y: cropPixels.y + selectionInCrop.y,
                width: selectionInCrop.width,
                height: selectionInCrop.height
            };

            // 2. Get blob
            const blob = await getCroppedImageBlob({
                imageSrc,
                crop: activeCrop,
                rotation: rotation,
                maxEdge: 1500,
                quality: 0.95,
                fullPage: false
            });

            // 3. Convert blob to base64
            const base64data = await blobToBase64(blob);

            // 4. Call API with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

            const payload = {
                selection_bbox: selectionBBox,
                image_data: base64data,
                ocr_hint: "math",
                max_lines: 6
            };

            const res = await fetch("/api/v1/find_error_local", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || `Server error: ${res.status}`);
            }

            const data = await res.json();

            if (data.ok && data.analysis) {
                setVoiceIntent(data.analysis.first_wrong_line_index !== null ? "Error Found (Local)" : "No Error Found");
                setErrorDiagnosis({
                    what_is_wrong: data.analysis.what_is_wrong,
                    minimal_fix: data.analysis.minimal_fix,
                    confidence: data.analysis.confidence
                });
                setLocalSteps(data.local_steps || null);
            } else {
                setError(data.error?.message || "No error detected local");
            }
        } catch (e: any) {
            setError(e.name === 'AbortError' ? "Request timed out. Please try again." : e.message);
        } finally {
            setStatus("idle" as any);
            setIsBusy(false);
        }
    };

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-bold text-slate-800">Snap & Solve v2</h3>
                    <p className="text-xs text-slate-500">Extract questions, select, and solve.</p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={resetAll}
                        className="px-3 py-2 text-xs font-bold border border-slate-200 rounded-lg hover:border-slate-300"
                    >
                        Reset
                    </button>
                </div>
            </div>

            {!file && <SnapSolveUploader onFile={handleFile} maxMb={MAX_MB} />}

            {file && (
                <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">{file.name}</span>
                        <button type="button" onClick={resetAll} className="text-rose-500 font-bold">
                            Replace file
                        </button>
                        <span>Status: {status}</span>
                    </div>

                    {fileType === "pdf" && (
                        <div className="flex items-center gap-3">
                            <label className="text-xs font-semibold text-slate-500">Page</label>
                            <input
                                type="number"
                                min={1}
                                max={pageCount}
                                value={pageNumber}
                                onChange={(e) => setPageNumber(parseInt(e.target.value, 10) || 1)}
                                className="w-20 text-xs border border-slate-200 rounded px-2 py-1"
                            />
                            <span className="text-xs text-slate-400">/ {pageCount}</span>
                        </div>
                    )}

                    {fileType === "pdf" && file && (
                        <PdfPageViewer
                            file={file}
                            pageNumber={pageNumber}
                            onPageCount={setPageCount}
                            onRendered={(dataUrl) => {
                                setImageSrc(dataUrl);
                                setStatus("cropping");
                            }}
                            onError={(message) => {
                                setError(message);
                                setStatus("error");
                            }}
                        />
                    )}

                    {imageSrc && (
                        <div className="flex flex-col gap-3">
                            {/* Voice Control Toolbar */}
                            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
                                <div className="flex items-center gap-3">
                                    <label className="flex items-center gap-2 text-sm font-bold text-slate-700 cursor-pointer select-none">
                                        <div className={`w-10 h-6 flex items-center bg-slate-300 rounded-full p-1 duration-300 ${voiceMode ? 'bg-indigo-500' : ''}`}>
                                            <div className={`bg-white w-4 h-4 rounded-full shadow-md transform duration-300 ${voiceMode ? 'translate-x-4' : ''}`}></div>
                                        </div>
                                        <input
                                            type="checkbox"
                                            checked={voiceMode}
                                            onChange={(e) => {
                                                setVoiceMode(e.target.checked);
                                                if (!e.target.checked) setSelectionBBox(null);
                                            }}
                                            className="hidden"
                                        />
                                        <span>Circle & Speak Mode</span>
                                    </label>

                                    {voiceMode && (
                                        <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-4">
                                            <button
                                                className={`px-4 py-1.5 rounded-full font-bold text-xs flex items-center gap-2 transition-all ${recorderState === "recording"
                                                    ? "bg-rose-500 text-white scale-105 shadow-lg shadow-rose-500/30"
                                                    : "bg-white border border-slate-300 text-slate-700 hover:border-indigo-400"
                                                    }`}
                                                onMouseDown={handleMicDown}
                                                onMouseUp={handleMicUp}
                                                onMouseLeave={() => { if (recorderState === "recording") handleMicUp(); }}
                                                onTouchStart={(e) => { e.preventDefault(); handleMicDown(); }}
                                                onTouchEnd={(e) => { e.preventDefault(); handleMicUp(); }}
                                            >
                                                <span className={`w-2 h-2 rounded-full ${recorderState === "recording" ? "bg-white animate-pulse" : "bg-slate-400"}`} />
                                                {recorderState === "recording" ? `Release to Send (${(durationMs / 1000).toFixed(1)}s)` : "Hold Space or Click to Speak"}
                                            </button>
                                        </div>
                                    )}
                                </div>

                                {voiceMode && (
                                    <div className="flex-1 text-right text-xs">
                                        {status === "transcribing" && <span className="text-indigo-600 font-medium animate-pulse">Transcribing...</span>}
                                        {status === "resolving_intent" && <span className="text-indigo-600 font-medium animate-pulse">Analyzing Command...</span>}
                                        {voiceTranscript && status !== "transcribing" && status !== "executing" && (
                                            <span className="text-slate-600 italic">"{voiceTranscript}"</span>
                                        )}
                                        {recorderError && <span className="text-rose-500 font-bold">Error: {recorderError}</span>}
                                    </div>
                                )}
                            </div>

                            {/* Voice Intent Display - Separate Section */}
                            {voiceMode && status === "executing" && voiceIntent && (
                                <div className="mt-3 p-3 bg-emerald-50 border-2 border-emerald-200 rounded-lg">
                                    <div className="text-sm font-bold text-emerald-700 mb-1">
                                        Executing: {voiceIntent}
                                    </div>
                                    {voiceTranscript && (
                                        <div className="text-xs text-slate-600 italic">
                                            "{voiceTranscript}"
                                        </div>
                                    )}
                                </div>
                            )}

                            <div className="flex flex-wrap items-center gap-3">
                                <label className="text-xs font-semibold text-slate-500 flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        checked={fullPage}
                                        onChange={(e) => setFullPage(e.target.checked)}
                                    />
                                    Full page (skip crop)
                                </label>
                                <button
                                    type="button"
                                    onClick={() => setRotation((prev) => prev - 90)}
                                    className="px-3 py-1 text-xs font-semibold border border-slate-200 rounded"
                                >
                                    Rotate Left
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setRotation((prev) => prev + 90)}
                                    className="px-3 py-1 text-xs font-semibold border border-slate-200 rounded"
                                >
                                    Rotate Right
                                </button>
                            </div>
                            <CropWorkspace
                                imageSrc={imageSrc}
                                crop={crop}
                                zoom={zoom}
                                rotation={rotation}
                                onCropChange={setCrop}
                                onZoomChange={setZoom}
                                onRotationChange={setRotation}
                                onCropComplete={setCropPixels}
                                onImageSize={setImageSize}
                                onViewportSize={setViewportSize}
                                fullPage={fullPage}
                                resetToken={cropResetToken}
                                selectionMode={voiceMode}
                                onSelectionChange={setSelectionBBox}
                            />

                            {/* Local Find Error Trigger */}
                            {voiceMode && selectionBBox && (
                                <div className="mt-2 flex justify-center">
                                    <button
                                        type="button"
                                        onClick={handleFindErrorLocal}
                                        disabled={status === "executing" || isBusy}
                                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold rounded-full shadow-lg flex items-center gap-2 transition-all animate-in fade-in slide-in-from-bottom-2 disabled:opacity-50"
                                    >
                                        {status === "executing" ? (
                                            <>
                                                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                Analyzing...
                                            </>
                                        ) : (
                                            <>
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                                </svg>
                                                Find Error (Local)
                                            </>
                                        )}
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="flex flex-wrap items-center gap-3">
                        <button
                            type="button"
                            onClick={handleExtract}
                            disabled={!canExtract}
                            className="px-4 py-2 text-sm font-bold rounded-lg bg-primary text-white disabled:opacity-50"
                        >
                            {isBusy && status === "extracting" ? "Extracting..." : "Send to AI"}
                        </button>
                        <button
                            type="button"
                            onClick={handleResetCropControls}
                            disabled={!imageSrc || fullPage}
                            className="px-4 py-2 text-sm font-semibold rounded-lg border border-slate-200 text-slate-600 disabled:opacity-50"
                        >
                            Reset crop controls
                        </button>
                    </div>
                </div>
            )}

            {error && <div className="text-xs text-rose-500 font-semibold">{error}</div>}

            {extractResult && extractResult.questions && extractResult.questions.length > 0 && (
                <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-slate-700">Detected Questions</h4>
                        <button type="button" onClick={selectAllValid} className="text-xs font-semibold text-primary">
                            Select all valid
                        </button>
                    </div>
                    {extractResult.notes && extractResult.notes.length > 0 && (
                        <div className="text-xs text-slate-500">
                            Notes: {extractResult.notes.join(" - ")}
                        </div>
                    )}
                    <div className="space-y-3">
                        {extractResult.questions.map((q) => {
                            const disabled = !q.is_valid_math;
                            return (
                                <div key={q.id} className="border border-slate-200 rounded-lg p-3">
                                    <div className="flex items-start gap-3">
                                        <input
                                            type="checkbox"
                                            checked={selectedIds.has(q.id)}
                                            disabled={disabled}
                                            onChange={() => toggleSelect(q.id)}
                                            className="mt-1"
                                        />
                                        <div className="flex-1">
                                            <UnifiedMathRenderer mode="prose" content={q.text} />
                                            {!q.is_valid_math && (
                                                <div className="text-xs text-rose-500 mt-1">
                                                    Invalid: {q.reason_if_invalid || "Not a valid math question"}
                                                </div>
                                            )}
                                            {q.requires_figure && (
                                                <div className="text-xs text-amber-600 mt-2">
                                                    Needs figure crop.
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    {q.requires_figure && (
                                        <div className="flex flex-wrap items-center gap-2 mt-2">
                                            <button
                                                type="button"
                                                onClick={() => handleCaptureFigure(q.id, cropPixels)}
                                                className="px-2 py-1 text-xs font-semibold border border-slate-200 rounded"
                                            >
                                                Use current crop as figure
                                            </button>
                                            {q.figure_bbox && (
                                                <button
                                                    type="button"
                                                    onClick={() => handleUseSuggestedFigure(q)}
                                                    className="px-2 py-1 text-xs font-semibold border border-slate-200 rounded"
                                                >
                                                    Use suggested figure region
                                                </button>
                                            )}
                                            {figureCrops[q.id] && (
                                                <span className="text-xs text-emerald-600 font-semibold">
                                                    Figure ready
                                                </span>
                                            )}
                                        </div>
                                    )}
                                    <div className="flex items-center gap-2 mt-3">
                                        <button
                                            type="button"
                                            onClick={() => onUseText(q.text)}
                                            className="px-3 py-1 text-xs font-semibold border border-slate-200 rounded"
                                        >
                                            Use in Text
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => onSolveText(q.text)}
                                            className="px-3 py-1 text-xs font-semibold border border-slate-200 rounded"
                                        >
                                            Solve in Text Tab
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                    <div className="flex items-center justify-between">
                        <div className="text-xs text-slate-500">
                            Selected: {selectedCount} | Est. credits: {estimatedCredits.toFixed(2)}
                        </div>
                        <button
                            type="button"
                            onClick={handleSolveSelected}
                            disabled={selectedCount === 0 || isBusy}
                            className="px-4 py-2 text-sm font-bold rounded-lg bg-primary text-white disabled:opacity-50"
                        >
                            {isBusy && status === "solving" ? "Solving..." : "Solve selected"}
                        </button>
                    </div>
                </div>
            )}

            {localSteps && localSteps.length > 0 && (
                <div className="flex flex-col gap-4 mb-4">
                    <h4 className="text-sm font-bold text-slate-700">Official Solution (Local)</h4>
                    <div className="border-2 border-indigo-200 bg-indigo-50 rounded-lg p-4 space-y-2">
                        {localSteps.map((step, idx) => (
                            <div key={idx} className="text-sm">
                                <UnifiedMathRenderer mode="prose" content={step} />
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {errorDiagnosis && (
                <div className="flex flex-col gap-4 mb-4">
                    <h4 className="text-sm font-bold text-slate-700">Error Diagnosis</h4>

                    {/* Diagnose section - Light Red */}
                    <div className="border-2 border-rose-200 bg-rose-50 rounded-lg p-4">
                        <div className="text-xs font-semibold text-rose-700 mb-1">Diagnose:</div>
                        <UnifiedMathRenderer mode="prose" content={errorDiagnosis.what_is_wrong} />
                    </div>

                    {/* Fix section - Light Green */}
                    <div className="border-2 border-emerald-200 bg-emerald-50 rounded-lg p-4">
                        <div className="text-xs font-semibold text-emerald-700 mb-1">Fix:</div>
                        <UnifiedMathRenderer mode="prose" content={errorDiagnosis.minimal_fix} />
                    </div>

                    {errorDiagnosis.confidence !== undefined && (
                        <div className="text-xs text-slate-500">
                            Confidence: {(errorDiagnosis.confidence * 100).toFixed(0)}%
                        </div>
                    )}
                    <button
                        onClick={() => setErrorDiagnosis(null)}
                        className="text-xs text-slate-500 hover:text-slate-700 underline"
                    >
                        Dismiss
                    </button>
                </div>
            )
            }

            {
                solveResults.length > 0 && (
                    <div className="flex flex-col gap-4">
                        <h4 className="text-sm font-bold text-slate-700">Solve Results</h4>
                        {solveResults.map((res) => {
                            const solveData = res.solve_response_json as any;
                            const finalAnswer = solveData?.final_answer?.answer_text
                                || solveData?.final_answer?.answer_latex
                                || solveData?.final_answer?.answer
                                || solveData?.final_answer;
                            return (
                                <div key={res.question_id} className="border border-slate-200 rounded-lg p-3">
                                    {!res.ok && (
                                        <div className="text-xs text-rose-500 font-semibold">
                                            {res.error || "Solve failed"}
                                        </div>
                                    )}
                                    {res.ok && (
                                        <div className="space-y-2">
                                            <div className="text-xs text-slate-500">Question: {res.question_id}</div>
                                            {typeof finalAnswer === "string" ? (
                                                <UnifiedMathRenderer mode="prose" content={finalAnswer} />
                                            ) : (
                                                <div className="text-xs text-slate-500">Answer available in details.</div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )
            }
        </div >
    );
}
