"use client";

import React from "react";
import SnapSolveUploader from "./SnapSolveUploader";
import PdfPageViewer from "./PdfPageViewer";
import CropWorkspace from "./CropWorkspace";
import UnifiedMathRenderer from "@/components/math/UnifiedMathRenderer";
import {
    CropArea,
    buildRequestHash,
    getCroppedImageBlob,
    hashBytes,
    loadCache,
    saveCache,
    blobToBase64,
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
    solve_response_json?: Record<string, any>;
    error?: string;
    telemetry?: Record<string, any>;
    credits_reserved?: number;
    credits_final?: number;
    credits_refunded?: number;
};

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
    const [status, setStatus] = React.useState<"idle" | "uploading" | "rendering" | "cropping" | "extracting" | "ready" | "solving" | "done" | "error">("idle");
    const [error, setError] = React.useState<string | null>(null);
    const [extractResult, setExtractResult] = React.useState<ExtractResponse | null>(null);
    const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
    const [solveResults, setSolveResults] = React.useState<SolveResult[]>([]);
    const [isBusy, setIsBusy] = React.useState(false);
    const [imageSize, setImageSize] = React.useState<{ width: number; height: number } | null>(null);
    const [figureCrops, setFigureCrops] = React.useState<Record<string, string>>({});

    const abortRef = React.useRef<AbortController | null>(null);

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
    }, [imageSrc]);

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

    React.useEffect(() => {
        if (isBusy && abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
            setIsBusy(false);
        }
    }, [file, pageNumber, cropPixels, rotation, fullPage]);

    const handleExtract = async () => {
        if (!file || !imageSrc) return;
        setIsBusy(true);
        setError(null);
        setStatus("extracting");

        if (abortRef.current) abortRef.current.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const fileBytes = await file.arrayBuffer();
            const fileHash = await hashBytes(fileBytes);
            const meta = {
                pageNumber,
                crop: fullPage ? null : cropPixels,
                rotation,
            };
            const requestHash = await buildRequestHash(fileBytes, meta);
            const cache = loadCache();
            if (cache[requestHash]) {
                setExtractResult(cache[requestHash]);
                setStatus("ready");
                setIsBusy(false);
                return;
            }

            const blob = await getCroppedImageBlob({
                imageSrc,
                crop: cropPixels,
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
            if (cropPixels && !fullPage) {
                form.append("crop_x", String(cropPixels.x));
                form.append("crop_y", String(cropPixels.y));
                form.append("crop_w", String(cropPixels.width));
                form.append("crop_h", String(cropPixels.height));
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
            cache[requestHash] = data;
            saveCache(cache);
            setStatus("ready");
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
                body: JSON.stringify({ items, features_used: { ocr_used: true } }),
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
                                fullPage={fullPage}
                            />
                        </div>
                    )}

                    <div className="flex items-center gap-3">
                        <button
                            type="button"
                            onClick={handleExtract}
                            disabled={!canExtract}
                            className="px-4 py-2 text-sm font-bold rounded-lg bg-primary text-white disabled:opacity-50"
                        >
                            {isBusy && status === "extracting" ? "Extracting..." : "Send to AI"}
                        </button>
                    </div>
                </div>
            )}

            {error && <div className="text-xs text-rose-500 font-semibold">{error}</div>}

            {extractResult && (
                <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-slate-700">Detected Questions</h4>
                        <button type="button" onClick={selectAllValid} className="text-xs font-semibold text-primary">
                            Select all valid
                        </button>
                    </div>
                    {extractResult.notes?.length > 0 && (
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

            {solveResults.length > 0 && (
                <div className="flex flex-col gap-4">
                    <h4 className="text-sm font-bold text-slate-700">Solve Results</h4>
                    {solveResults.map((res) => {
                        const finalAnswer = res.solve_response_json?.final_answer?.answer_text
                            || res.solve_response_json?.final_answer?.answer_latex
                            || res.solve_response_json?.final_answer?.answer
                            || res.solve_response_json?.final_answer;
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
            )}
        </div>
    );
}
