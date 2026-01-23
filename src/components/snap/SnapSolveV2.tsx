"use client";

import React from "react";
import SnapSolveUploader from "./SnapSolveUploader";
import PdfPageViewer from "./PdfPageViewer";
import CropWorkspace from "./CropWorkspace";
import OcrResultPanel, { OcrResult } from "./OcrResultPanel";
import {
    CropArea,
    buildRequestHash,
    getCroppedImageBlob,
    hashBytes,
    loadCache,
    saveCache,
} from "./snapSolveUtils";

type SnapSolveV2Props = {
    onUseText: (text: string) => void;
    onSolveText: (text: string) => void;
};

const MAX_MB = parseInt(process.env.NEXT_PUBLIC_SNAP_MAX_MB || "10", 10);
const MAX_BYTES = MAX_MB * 1024 * 1024;
const MAX_EDGE = 2000;
const JPEG_QUALITY = 0.83;

export default function SnapSolveV2({ onUseText, onSolveText }: SnapSolveV2Props) {
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
    const [status, setStatus] = React.useState<"idle" | "uploading" | "rendering" | "cropping" | "reading" | "done" | "error">("idle");
    const [error, setError] = React.useState<string | null>(null);
    const [result, setResult] = React.useState<OcrResult | null>(null);
    const [isReading, setIsReading] = React.useState(false);

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
        setResult(null);
        setIsReading(false);
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
        if (isReading && abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
            setIsReading(false);
        }
    }, [file, pageNumber, cropPixels, rotation, fullPage]);

    const handleOcr = async () => {
        if (!file || !imageSrc) return;
        setIsReading(true);
        setError(null);
        setStatus("reading");

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
                setResult(cache[requestHash]);
                setStatus("done");
                setIsReading(false);
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
            form.append("file", blob, "crop.jpg");
            form.append("page_number", String(pageNumber));
            form.append("file_hash", fileHash);
            if (cropPixels && !fullPage) {
                form.append("crop_x", String(cropPixels.x));
                form.append("crop_y", String(cropPixels.y));
                form.append("crop_w", String(cropPixels.width));
                form.append("crop_h", String(cropPixels.height));
            }

            const res = await fetch("/api/v1/ocr_v5", {
                method: "POST",
                body: form,
                signal: controller.signal,
            });
            if (!res.ok) {
                const detail = await res.text();
                throw new Error(detail || "OCR failed");
            }

            const data = await res.json();
            setResult(data);
            cache[requestHash] = data;
            saveCache(cache);
            setStatus("done");
        } catch (err) {
            if (!(err instanceof DOMException && err.name === "AbortError")) {
                const message = err instanceof Error ? err.message : "OCR failed";
                setError(message);
                setStatus("error");
            }
        } finally {
            setIsReading(false);
        }
    };

    const canRead = Boolean(imageSrc) && !isReading;

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-bold text-slate-800">Snap & Solve v2</h3>
                    <p className="text-xs text-slate-500">Upload one image or one PDF page, crop, and read.</p>
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
                            />
                        </div>
                    )}

                    <div className="flex items-center gap-3">
                        <button
                            type="button"
                            onClick={handleOcr}
                            disabled={!canRead}
                            className="px-4 py-2 text-sm font-bold rounded-lg bg-primary text-white disabled:opacity-50"
                        >
                            {isReading ? "Reading..." : "Send to AI"}
                        </button>
                    </div>
                </div>
            )}

            {error && <div className="text-xs text-rose-500 font-semibold">{error}</div>}

            <OcrResultPanel
                result={result}
                onUseText={onUseText}
                onSolveText={onSolveText}
            />
        </div>
    );
}
