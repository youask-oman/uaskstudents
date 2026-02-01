"use client";

import React from "react";

type ToolMode = "draw" | "erase";

export type SketchCanvasHandle = {
    clear: () => void;
    hasContent: () => boolean;
    exportAsFile: () => Promise<File | null>;
};

type SketchCanvasProps = {
    tool: ToolMode;
    brushSize: number;
    onContentChange?: (hasContent: boolean) => void;
};

export default React.memo(
    React.forwardRef<SketchCanvasHandle, SketchCanvasProps>(function SketchCanvas(
        { tool, brushSize, onContentChange },
        ref
    ) {
        const containerRef = React.useRef<HTMLDivElement | null>(null);
        const fabricCanvasRef = React.useRef<any | null>(null);
        const htmlCanvasRef = React.useRef<HTMLCanvasElement | null>(null);
        const [ready, setReady] = React.useState(false);
        const [zoom, setZoom] = React.useState(1);

        const updateBrush = React.useCallback(() => {
            const canvas = fabricCanvasRef.current;
            if (!canvas) return;
            const brush = canvas.freeDrawingBrush;
            if (!brush) return;
            brush.width = brushSize;
            brush.color = tool === "erase" ? "#ffffff" : "#0f172a";
        }, [tool, brushSize]);

        const updateHasContent = React.useCallback(() => {
            const canvas = fabricCanvasRef.current;
            if (!canvas) return;
            const hasObjects = (canvas.getObjects?.() || []).length > 0;
            onContentChange?.(hasObjects);
        }, [onContentChange]);

        React.useEffect(() => {
            let disposed = false;

            const init = async () => {
                if (!containerRef.current || disposed) return;
                const canvasEl = document.createElement("canvas");
                canvasEl.width = 1200;
                canvasEl.height = 720;
                canvasEl.className = "w-full h-full";
                containerRef.current.innerHTML = "";
                containerRef.current.appendChild(canvasEl);
                htmlCanvasRef.current = canvasEl;

                const fabricLib = await import("fabric");
                if (disposed) return;
                const { Canvas, PencilBrush } = fabricLib;
                const canvas = new Canvas(canvasEl, {
                    isDrawingMode: true,
                    backgroundColor: "#ffffff",
                    selection: false,
                });
                fabricCanvasRef.current = canvas;
                canvas.freeDrawingBrush = new PencilBrush(canvas);
                canvas.on("path:created", updateHasContent);
                updateBrush();
                setReady(true);
                updateHasContent();
            };

            init();

            return () => {
                disposed = true;
                setReady(false);
                if (fabricCanvasRef.current) {
                    fabricCanvasRef.current.dispose();
                    fabricCanvasRef.current = null;
                }
                htmlCanvasRef.current = null;
            };
        }, [updateBrush, updateHasContent]);

        React.useEffect(() => {
            updateBrush();
        }, [updateBrush]);

        React.useImperativeHandle(
            ref,
            () => ({
                clear: () => {
                    const canvas = fabricCanvasRef.current;
                    if (!canvas) return;
                    canvas.clear();
                    canvas.backgroundColor = "#ffffff";
                    canvas.renderAll();
                    updateHasContent();
                },
                hasContent: () => {
                    const canvas = fabricCanvasRef.current;
                    if (!canvas) return false;
                    return (canvas.getObjects?.() || []).length > 0;
                },
                exportAsFile: async () => {
                    const canvas = htmlCanvasRef.current;
                    if (!canvas) return null;
                    return await new Promise<File | null>((resolve) => {
                        canvas.toBlob(
                            (blob) => {
                                if (!blob) {
                                    resolve(null);
                                    return;
                                }
                                resolve(new File([blob], "sketch.png", { type: "image/png" }));
                            },
                            "image/png",
                            1
                        );
                    });
                },
            }),
            [updateHasContent]
        );

        const handleZoom = (delta: number) => {
            const next = Math.max(0.5, Math.min(2, Number((zoom + delta).toFixed(2))));
            setZoom(next);
        };

        return (
            <div className="rounded-xl border border-slate-700 bg-slate-900 p-3">
                <div className="mb-2 flex items-center justify-between">
                    <div className="text-xs font-semibold text-slate-300">
                        {tool === "draw" ? "Draw mode" : "Eraser mode"}
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => handleZoom(-0.1)}
                            className="rounded-md border border-slate-600 px-2 py-1 text-xs font-semibold text-slate-200"
                        >
                            -
                        </button>
                        <span className="text-xs text-slate-300">{Math.round(zoom * 100)}%</span>
                        <button
                            type="button"
                            onClick={() => handleZoom(0.1)}
                            className="rounded-md border border-slate-600 px-2 py-1 text-xs font-semibold text-slate-200"
                        >
                            +
                        </button>
                    </div>
                </div>
                <div className="overflow-hidden rounded-lg border border-slate-700 bg-white">
                    <div
                        style={{ transform: `scale(${zoom})`, transformOrigin: "top left", width: `${100 / zoom}%`, height: `${100 / zoom}%` }}
                        className="h-[360px]"
                    >
                        <div ref={containerRef} className="h-full w-full" />
                    </div>
                </div>
                {!ready && <div className="mt-2 text-xs text-slate-400">Loading sketch tools...</div>}
            </div>
        );
    })
);
