"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import SketchCanvas, { SketchCanvasHandle } from "./SketchCanvas";

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

const ACCEPTED_UPLOAD = "image/png,image/jpeg,image/webp,application/pdf";

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
    const fileInputRef = React.useRef<HTMLInputElement | null>(null);
    const cameraInputRef = React.useRef<HTMLInputElement | null>(null);
    const sketchRef = React.useRef<SketchCanvasHandle | null>(null);

    const isSubmitEnabled = React.useMemo(() => {
        return Boolean(uploadedFile || sketchHasContent || questionText.trim().length > 0);
    }, [uploadedFile, sketchHasContent, questionText]);

    const setUploadFile = React.useCallback((file: File | null) => {
        setUploadedFile(file);
        setError(null);
        if (previewUrl && previewUrl.startsWith("blob:")) {
            URL.revokeObjectURL(previewUrl);
        }
        if (!file) {
            setPreviewUrl(null);
            return;
        }
        if (file.type.startsWith("image/")) {
            setPreviewUrl(URL.createObjectURL(file));
        } else {
            setPreviewUrl(null);
        }
    }, [previewUrl]);

    React.useEffect(() => {
        return () => {
            if (previewUrl && previewUrl.startsWith("blob:")) {
                URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    React.useEffect(() => {
        const handlePaste = (event: ClipboardEvent) => {
            if (activeSubTab !== "upload") return;
            if (!event.clipboardData) return;
            const item = Array.from(event.clipboardData.items).find((it) => it.type.startsWith("image/"));
            if (!item) return;
            const blob = item.getAsFile();
            if (!blob) return;
            const pastedFile = new File([blob], `clipboard-${Date.now()}.png`, {
                type: blob.type || "image/png",
            });
            setUploadFile(pastedFile);
            setError(null);
        };

        window.addEventListener("paste", handlePaste);
        return () => window.removeEventListener("paste", handlePaste);
    }, [activeSubTab, setUploadFile]);

    const onFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0] || null;
        if (file) setUploadFile(file);
        event.currentTarget.value = "";
    };

    const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        setIsDragging(false);
        const file = event.dataTransfer.files?.[0] || null;
        if (file) setUploadFile(file);
    };

    const handleClear = () => {
        setUploadFile(null);
        setQuestionText("");
        setError(null);
        setResult(null);
        setSketchHasContent(false);
        sketchRef.current?.clear();
    };

    const handleSubmit = async () => {
        if (!isSubmitEnabled || isSubmitting) return;
        setIsSubmitting(true);
        setError(null);
        setResult(null);
        try {
            const formData = new FormData();
            formData.append("mode", activeSubTab);
            formData.append("question_text", questionText);

            let fileToSend: File | null = null;
            if (activeSubTab === "upload") {
                fileToSend = uploadedFile;
            } else if (activeSubTab === "sketch" && sketchRef.current?.hasContent()) {
                fileToSend = await sketchRef.current.exportAsFile();
            }

            if (fileToSend) {
                formData.append("image", fileToSend);
                formData.append("original_filename", fileToSend.name);
            }

            const response = await fetch("/api/v1/math/solve_from_image_or_sketch", {
                method: "POST",
                body: formData,
            });

            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload?.detail || payload?.error || "Unable to solve this request.");
            }
            setResult(payload as SolveResponse);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Unexpected error";
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="flex flex-col gap-4">
            <div className="inline-flex w-fit rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-800">
                <button
                    type="button"
                    onClick={() => setActiveSubTab("upload")}
                    data-testid="snap-subtab-upload"
                    className={`rounded-lg px-4 py-2 text-sm font-bold ${activeSubTab === "upload" ? "bg-white text-slate-900 shadow dark:bg-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}`}
                >
                    Upload
                </button>
                <button
                    type="button"
                    onClick={() => setActiveSubTab("sketch")}
                    data-testid="snap-subtab-sketch"
                    className={`rounded-lg px-4 py-2 text-sm font-bold ${activeSubTab === "sketch" ? "bg-white text-slate-900 shadow dark:bg-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}`}
                >
                    Sketch
                </button>
            </div>

            {activeSubTab === "upload" ? (
                <div
                    onDrop={handleDrop}
                    onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    className={`rounded-2xl border-2 border-dashed p-6 transition-colors ${
                        isDragging
                            ? "border-primary bg-primary/10"
                            : "border-slate-700 bg-slate-900 text-slate-100"
                    }`}
                >
                    <div className="mb-4 flex items-center gap-2 text-xs">
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="rounded-lg border border-slate-600 px-3 py-1.5 font-semibold"
                        >
                            Upload file
                        </button>
                        <button
                            type="button"
                            onClick={() => cameraInputRef.current?.click()}
                            className="rounded-lg border border-slate-600 px-3 py-1.5 font-semibold"
                        >
                            Camera
                        </button>
                        <span className="rounded-lg border border-slate-600 px-3 py-1.5 font-semibold">
                            Paste from Clipboard
                        </span>
                    </div>
                    <input
                        ref={fileInputRef}
                        type="file"
                        className="hidden"
                        accept={ACCEPTED_UPLOAD}
                        onChange={onFileInputChange}
                        data-testid="snap-upload-input"
                    />
                    <input
                        ref={cameraInputRef}
                        type="file"
                        className="hidden"
                        accept="image/png,image/jpeg,image/webp"
                        capture="environment"
                        onChange={onFileInputChange}
                    />
                    <div className="text-sm text-slate-300">
                        Drag & drop, click upload, or paste a screenshot. Supports JPG, PNG, WEBP, PDF.
                    </div>
                    {uploadedFile && (
                        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-3">
                            <div className="text-xs font-semibold text-slate-300">Selected: {uploadedFile.name}</div>
                            {uploadedFile.type === "application/pdf" && (
                                <div className="mt-2 text-xs text-slate-400">PDF selected</div>
                            )}
                            {previewUrl && (
                                <img
                                    src={previewUrl}
                                    alt="Upload preview"
                                    className="mt-3 max-h-56 rounded-lg border border-slate-700 object-contain"
                                />
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-3">
                        <button
                            type="button"
                            onClick={() => setTool("draw")}
                            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tool === "draw" ? "bg-primary text-white" : "border border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}
                        >
                            Pen
                        </button>
                        <button
                            type="button"
                            onClick={() => setTool("erase")}
                            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tool === "erase" ? "bg-primary text-white" : "border border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}
                        >
                            Eraser
                        </button>
                        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
                            Brush
                            <input
                                type="range"
                                min={2}
                                max={24}
                                value={brushSize}
                                onChange={(e) => setBrushSize(Number(e.target.value))}
                            />
                        </label>
                        <button
                            type="button"
                            onClick={() => {
                                sketchRef.current?.clear();
                                setSketchHasContent(false);
                            }}
                            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300"
                        >
                            Clear canvas
                        </button>
                    </div>
                    <SketchCanvas
                        ref={sketchRef}
                        tool={tool}
                        brushSize={brushSize}
                        onContentChange={setSketchHasContent}
                    />
                </div>
            )}

            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    input your question
                </label>
                <textarea
                    data-testid="snap-question-input"
                    value={questionText}
                    onChange={(e) => setQuestionText(e.target.value)}
                    rows={4}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-primary dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    placeholder="Type any extra context or direct question..."
                />
            </div>

            {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {error}
                </div>
            )}

            <div className="flex items-center justify-end gap-3">
                <button
                    type="button"
                    onClick={handleClear}
                    data-testid="snap-clear-btn"
                    className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
                >
                    Clear
                </button>
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!isSubmitEnabled || isSubmitting}
                    data-testid="snap-submit-btn"
                    className="rounded-lg bg-primary px-5 py-2 text-sm font-bold text-white disabled:opacity-50"
                >
                    {isSubmitting ? "Submitting..." : "Submit"}
                </button>
            </div>

            {result && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-2 text-xs text-slate-500">
                        Mode: {result.meta.mode} · MIME: {result.meta.mime} · Latency: {result.meta.latency_ms}ms
                    </div>
                    <article className="prose prose-slate max-w-none dark:prose-invert">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {result.answer_markdown || "_No answer returned._"}
                        </ReactMarkdown>
                    </article>
                    {result.answer_latex && (
                        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800">
                            <code>{result.answer_latex}</code>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
