"use client";

import React from "react";
import { clamp } from "./snapSolveUtils";

type PdfPageViewerProps = {
    file: File;
    pageNumber: number;
    onPageCount: (count: number) => void;
    onRendered: (dataUrl: string, size: { width: number; height: number }) => void;
    onError: (message: string) => void;
};

export default function PdfPageViewer({
    file,
    pageNumber,
    onPageCount,
    onRendered,
    onError,
}: PdfPageViewerProps) {
    const containerRef = React.useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = React.useState(0);

    React.useEffect(() => {
        if (!containerRef.current) return;
        const observer = new ResizeObserver((entries) => {
            const entry = entries[0];
            if (entry?.contentRect?.width) {
                setContainerWidth(entry.contentRect.width);
            }
        });
        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, []);

    React.useEffect(() => {
        let renderTask: any = null;
        let cancelled = false;

        const renderPage = async () => {
            try {
                const pdfjsLib = await import("pdfjs-dist/build/pdf");
                pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
                    "pdfjs-dist/build/pdf.worker.min.mjs",
                    import.meta.url
                ).toString();

                const arrayBuffer = await file.arrayBuffer();
                const doc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
                if (cancelled) return;
                onPageCount(doc.numPages);

                const safePage = clamp(pageNumber, 1, doc.numPages);
                const page = await doc.getPage(safePage);
                if (cancelled) return;
                const viewport = page.getViewport({ scale: 1 });

                const targetWidth = containerWidth || viewport.width;
                const scale = clamp((targetWidth * window.devicePixelRatio) / viewport.width, 1, 3);
                const scaledViewport = page.getViewport({ scale });

                const canvas = document.createElement("canvas");
                const context = canvas.getContext("2d");
                if (!context) throw new Error("Canvas context unavailable");

                canvas.width = scaledViewport.width;
                canvas.height = scaledViewport.height;
                renderTask = page.render({ canvasContext: context, viewport: scaledViewport });
                await renderTask.promise;
                if (cancelled) return;

                const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
                onRendered(dataUrl, { width: canvas.width, height: canvas.height });
            } catch (err) {
                if (cancelled && err?.name === "RenderingCancelledException") return;
                const message = err instanceof Error ? err.message : "Failed to render PDF";
                onError(message);
            }
        };

        renderPage();
        return () => {
            cancelled = true;
            if (renderTask && typeof renderTask.cancel === "function") {
                renderTask.cancel();
            }
        };
    }, [file, pageNumber, containerWidth, onPageCount, onRendered, onError]);

    return (
        <div ref={containerRef} className="w-full">
            <div className="text-xs text-slate-500">Rendering selected page…</div>
        </div>
    );
}
