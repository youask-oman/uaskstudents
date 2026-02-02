"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import SketchCanvas, { SketchCanvasHandle } from "./SketchCanvas";
import PdfCropViewer, { PdfCropSelection } from "./pdf/PdfCropViewer";

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
    confidence: number;
    is_valid_math: boolean;
    source_page_index?: number;
};

type PdfExtractResponse = {
    extracted_questions: ExtractedQuestion[];
    meta: {
        warnings?: string[];
        [key: string]: unknown;
    };
};

type SolvedQuestion = {
    questionId: string;
    result?: SolveResponse;
    error?: string;
};

const ACCEPTED_UPLOAD = "image/png,image/jpeg,image/webp,application/pdf";
const PDF_ENABLED = process.env.NEXT_PUBLIC_SNAP_SOLVE_PDF_ENABLED !== "false";
const PDF_DOCUMENT_ENABLED = process.env.NEXT_PUBLIC_SNAP_SOLVE_PDF_DOCUMENT_EXTRACT_ENABLED === "true";

export default function SnapSolveInputPanel() {
    const [activeSubTab, setActiveSubTab] = React.useState<SnapSubTab>("upload");
    const [questionText, setQuestionText] = React.useState("");
    const [uploadedFile, setUploadedFile] = React.useState<File | null>(null);
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
    const isSubmitEnabled = React.useMemo(() => {
        if (isPdfMode) return false;
        return Boolean(uploadedFile || sketchHasContent || questionText.trim().length > 0);
    }, [uploadedFile, sketchHasContent, questionText, isPdfMode]);

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
    }, [clearPdfCache]);

    const setUploadFile = React.useCallback(
        (file: File | null) => {
            setUploadedFile(file);
            setError(null);
            setResult(null);
            setExtractedQuestions([]);
            setSelectedQuestionIds(new Set());
            setSolvedQuestions([]);

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
        [previewUrl, clearPdfState]
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
            setUploadFile(file);
            if (file.type === "application/pdf") {
                try {
                    await preparePdf(file);
                } catch (e) {
                    setError(e instanceof Error ? e.message : "Unable to prepare PDF.");
                    setUploadFile(null);
                    clearPdfState();
                }
            }
        },
        [setUploadFile, preparePdf, clearPdfState]
    );

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
        setQuestionText("");
        setError(null);
        setResult(null);
        setSketchHasContent(false);
        sketchRef.current?.clear();
        clearPdfState();
    };

    const handleSubmit = async () => {
        if (!isSubmitEnabled || isSubmitting || isPdfMode) return;
        setIsSubmitting(true);
        setError(null);
        setResult(null);
        try {
            const formData = new FormData();
            formData.append("mode", activeSubTab);
            formData.append("question_text", questionText);
            let fileToSend: File | null = null;
            if (activeSubTab === "upload") fileToSend = uploadedFile;
            else if (activeSubTab === "sketch" && sketchRef.current?.hasContent()) fileToSend = await sketchRef.current.exportAsFile();
            if (fileToSend) {
                formData.append("image", fileToSend);
                formData.append("original_filename", fileToSend.name);
            }
            const response = await fetch("/api/v1/math/solve_from_image_or_sketch", { method: "POST", body: formData });
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
        setError(null);
        setSolvedQuestions([]);
        try {
            const payload = {
                pdf_id: pdfSession.pdfId,
                mode,
                page_index: mode === "document" ? null : pdfPage - 1,
                crop: mode === "crop" ? pdfCrop : null,
                image_render: mode === "crop" || mode === "page" ? pdfRender : null,
                question_text: questionText || null,
                engine_choice: "pix2text",
            };
            const res = await fetch("/api/v1/snap-solve/pdf/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = (await res.json()) as PdfExtractResponse;
            if (!res.ok) throw new Error(extractErrorMessage(data, "Extraction failed."));
            const questions = data.extracted_questions || [];
            setExtractedQuestions(questions);
            setSelectedQuestionIds(new Set(questions.map((q) => q.id)));
            if (!questions.length) {
                const warning = Array.isArray(data.meta?.warnings) ? data.meta.warnings[0] : null;
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
        setSolvingSelected(true);
        setError(null);
        const out: SolvedQuestion[] = [];
        for (const q of selected) {
            try {
                const formData = new FormData();
                formData.append("mode", "upload");
                formData.append("question_text", q.text);
                const response = await fetch("/api/v1/math/solve_from_image_or_sketch", { method: "POST", body: formData });
                const payload = await response.json();
                if (!response.ok) throw new Error(extractErrorMessage(payload, "Solve failed."));
                out.push({ questionId: q.id, result: payload as SolveResponse });
            } catch (e) {
                out.push({ questionId: q.id, error: e instanceof Error ? e.message : "Solve failed." });
            }
        }
        setSolvedQuestions(out);
        setSolvingSelected(false);
    };

    return (
        <div className="flex flex-col gap-4">
            <div className="inline-flex w-fit rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-800">
                <button type="button" onClick={() => setActiveSubTab("upload")} data-testid="snap-subtab-upload" className={`rounded-lg px-4 py-2 text-sm font-bold ${activeSubTab === "upload" ? "bg-white text-slate-900 shadow dark:bg-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}`}>Upload</button>
                <button type="button" onClick={() => setActiveSubTab("sketch")} data-testid="snap-subtab-sketch" className={`rounded-lg px-4 py-2 text-sm font-bold ${activeSubTab === "sketch" ? "bg-white text-slate-900 shadow dark:bg-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}`}>Sketch</button>
            </div>

            {activeSubTab === "upload" ? (
                <div onDrop={handleDrop} onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} className={`rounded-2xl border-2 border-dashed p-6 transition-colors ${isDragging ? "border-primary bg-primary/10" : "border-slate-700 bg-slate-900 text-slate-100"}`}>
                    <div className="mb-4 flex items-center gap-2 text-xs">
                        <button type="button" onClick={() => fileInputRef.current?.click()} className="rounded-lg border border-slate-600 px-3 py-1.5 font-semibold">Upload file</button>
                        <button type="button" onClick={openCamera} className="rounded-lg border border-slate-600 px-3 py-1.5 font-semibold">Camera</button>
                        <button type="button" onClick={() => void handleClipboardButtonPaste()} className="rounded-lg border border-slate-600 px-3 py-1.5 font-semibold">Paste from Clipboard</button>
                    </div>
                    <input ref={fileInputRef} type="file" className="hidden" accept={ACCEPTED_UPLOAD} onChange={onFileInputChange} data-testid="snap-upload-input" />
                    <input ref={cameraInputRef} type="file" className="hidden" accept="image/png,image/jpeg,image/webp" capture="environment" onChange={onFileInputChange} />
                    <div className="text-sm text-slate-300">Drag & drop, click upload, or paste a screenshot. Supports JPG, PNG, WEBP, PDF.</div>

                    {uploadedFile && (
                        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-3">
                            <div className="text-xs font-semibold text-slate-300">Selected: {uploadedFile.name}</div>
                            {uploadedFile.type === "application/pdf" && <div className="mt-2 text-xs text-slate-400">PDF selected</div>}
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            {previewUrl && <img src={previewUrl} alt="Upload preview" className="mt-3 max-h-56 rounded-lg border border-slate-700 object-contain" />}
                        </div>
                    )}

                    {isPdfMode && pdfSession && (
                        <div className="mt-4 flex flex-col gap-3">
                            <div className="flex items-center gap-2 text-xs">
                                <button type="button" className="rounded border border-slate-600 px-2 py-1" onClick={() => setPdfPage((p) => Math.max(1, p - 1))} disabled={pdfPage <= 1}>Prev</button>
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
                                <button type="button" className="rounded border border-slate-600 px-2 py-1" onClick={() => setPdfPage((p) => Math.min(pdfSession.pageCount, p + 1))} disabled={pdfPage >= pdfSession.pageCount}>Next</button>
                                <button type="button" className="rounded border border-slate-600 px-2 py-1" onClick={() => setPdfScale((s) => Math.max(0.5, Number((s - 0.1).toFixed(2))))}>-</button>
                                <span>{Math.round(pdfScale * 100)}%</span>
                                <button type="button" className="rounded border border-slate-600 px-2 py-1" onClick={() => setPdfScale((s) => Math.min(4, Number((s + 0.1).toFixed(2))))}>+</button>
                            </div>
                            {pdfLoading && <div className="text-xs text-slate-400">Rendering page...</div>}
                            {pdfPageImage && (
                                <PdfCropViewer
                                    imageUrl={pdfPageImage.url}
                                    pageLabel={`Page ${pdfPage} / ${pdfSession.pageCount}`}
                                    onCropChange={(crop, render) => {
                                        setPdfCrop(crop);
                                        setPdfRender({ ...render, scale: pdfScale });
                                    }}
                                />
                            )}
                            <div className="flex flex-wrap items-center gap-2">
                                <button type="button" onClick={() => void runPdfExtract("crop")} disabled={extracting || !pdfCrop} className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-semibold disabled:opacity-50">Extract Crop</button>
                                <button type="button" onClick={() => void runPdfExtract("page")} disabled={extracting} className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-semibold disabled:opacity-50">Extract This Page</button>
                                {PDF_DOCUMENT_ENABLED && (
                                    <button type="button" onClick={() => void runPdfExtract("document")} disabled={extracting} className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-semibold disabled:opacity-50">Extract Entire PDF</button>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-3">
                        <button type="button" onClick={() => setTool("draw")} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tool === "draw" ? "bg-primary text-white" : "border border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}>Pen</button>
                        <button type="button" onClick={() => setTool("erase")} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tool === "erase" ? "bg-primary text-white" : "border border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}>Eraser</button>
                        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">Brush <input type="range" min={2} max={24} value={brushSize} onChange={(e) => setBrushSize(Number(e.target.value))} /></label>
                        <button type="button" onClick={() => { sketchRef.current?.clear(); setSketchHasContent(false); }} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300">Clear canvas</button>
                    </div>
                    <SketchCanvas ref={sketchRef} tool={tool} brushSize={brushSize} onContentChange={setSketchHasContent} />
                </div>
            )}

            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">input your question</label>
                <textarea data-testid="snap-question-input" value={questionText} onChange={(e) => setQuestionText(e.target.value)} rows={4} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-primary dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" placeholder="Type any extra context or direct question..." />
            </div>

            {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

            {extractedQuestions.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-3 text-sm font-bold">Extracted Questions</div>
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
                                    <div>{q.text}</div>
                                    <div className="text-xs text-slate-500">confidence: {Math.round((q.confidence || 0) * 100)}%</div>
                                </div>
                            </label>
                        ))}
                    </div>
                    <button type="button" onClick={() => void solveSelectedQuestions()} disabled={solvingSelected || selectedQuestionIds.size === 0} className="mt-3 rounded-lg bg-primary px-4 py-2 text-xs font-bold text-white disabled:opacity-50">
                        {solvingSelected ? "Solving..." : "Solve selected"}
                    </button>
                </div>
            )}

            <div className="flex items-center justify-end gap-3">
                <button type="button" onClick={handleClear} data-testid="snap-clear-btn" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200">Clear</button>
                <button type="button" onClick={handleSubmit} disabled={!isSubmitEnabled || isSubmitting} data-testid="snap-submit-btn" className="rounded-lg bg-primary px-5 py-2 text-sm font-bold text-white disabled:opacity-50">{isSubmitting ? "Submitting..." : "Submit"}</button>
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
                            <button type="button" onClick={closeCamera} className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200">Cancel</button>
                            <button type="button" onClick={captureCameraFrame} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white">Capture</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
