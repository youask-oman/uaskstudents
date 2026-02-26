"use client";

import React from "react";

export type PdfCropSelection = {
    x: number;
    y: number;
    width: number;
    height: number;
};

type Props = {
    imageUrl: string;
    pageLabel: string;
    onCropChange: (crop: PdfCropSelection | null, render: { width: number; height: number }) => void;
    scale?: number;
};

type DragMode = "create" | "move" | "resize-nw" | "resize-ne" | "resize-sw" | "resize-se";

type DragState = {
    mode: DragMode;
    start: { x: number; y: number };
    baseRect: PdfCropSelection;
};

export default function PdfCropViewer({ imageUrl, pageLabel, onCropChange, scale = 1 }: Props) {
    const wrapRef = React.useRef<HTMLDivElement | null>(null);
    const imgRef = React.useRef<HTMLImageElement | null>(null);
    const rectRef = React.useRef<PdfCropSelection | null>(null);
    const dragRef = React.useRef<DragState | null>(null);
    const pointerIdRef = React.useRef<number | null>(null);
    const [imgSize, setImgSize] = React.useState({ width: 0, height: 0 });
    const [dragging, setDragging] = React.useState(false);
    const [rect, setRect] = React.useState<PdfCropSelection | null>(null);

    React.useEffect(() => {
        setRect(null);
        rectRef.current = null;
        dragRef.current = null;
        setDragging(false);
    }, [imageUrl]);

    const toImagePx = (clientX: number, clientY: number) => {
        const img = imgRef.current;
        if (!img) return null;
        const box = img.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0) return null;
        const rx = Math.max(0, Math.min(box.width, clientX - box.left));
        const ry = Math.max(0, Math.min(box.height, clientY - box.top));
        const sx = img.naturalWidth / box.width;
        const sy = img.naturalHeight / box.height;
        return { x: rx * sx, y: ry * sy, sx, sy };
    };

    const getBounds = React.useCallback(() => {
        const img = imgRef.current;
        return {
            width: img?.naturalWidth || imgSize.width || 1,
            height: img?.naturalHeight || imgSize.height || 1,
        };
    }, [imgSize.height, imgSize.width]);

    const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

    const normalizeRect = (x1: number, y1: number, x2: number, y2: number): PdfCropSelection => {
        const x = Math.min(x1, x2);
        const y = Math.min(y1, y2);
        const width = Math.max(1, Math.abs(x2 - x1));
        const height = Math.max(1, Math.abs(y2 - y1));
        return { x, y, width, height };
    };

    const commitRect = React.useCallback((next: PdfCropSelection | null) => {
        rectRef.current = next;
        setRect(next);
    }, []);

    const handleDown = (e: React.PointerEvent) => {
        const p = toImagePx(e.clientX, e.clientY);
        if (!p) return;
        const bounds = getBounds();
        const current = rectRef.current;
        const toleranceX = Math.max(8, 10 * p.sx);
        const toleranceY = Math.max(8, 10 * p.sy);

        let mode: DragMode = "create";
        let baseRect: PdfCropSelection = { x: p.x, y: p.y, width: 1, height: 1 };

        if (current) {
            const left = current.x;
            const right = current.x + current.width;
            const top = current.y;
            const bottom = current.y + current.height;
            const nearNW = Math.abs(p.x - left) <= toleranceX && Math.abs(p.y - top) <= toleranceY;
            const nearNE = Math.abs(p.x - right) <= toleranceX && Math.abs(p.y - top) <= toleranceY;
            const nearSW = Math.abs(p.x - left) <= toleranceX && Math.abs(p.y - bottom) <= toleranceY;
            const nearSE = Math.abs(p.x - right) <= toleranceX && Math.abs(p.y - bottom) <= toleranceY;
            const inside = p.x >= left && p.x <= right && p.y >= top && p.y <= bottom;

            if (nearNW) mode = "resize-nw";
            else if (nearNE) mode = "resize-ne";
            else if (nearSW) mode = "resize-sw";
            else if (nearSE) mode = "resize-se";
            else if (inside) mode = "move";
            else mode = "create";

            if (mode !== "create") {
                baseRect = current;
            }
        }

        if (mode === "create") {
            const initial = {
                x: clamp(p.x, 0, bounds.width - 1),
                y: clamp(p.y, 0, bounds.height - 1),
                width: 1,
                height: 1,
            };
            baseRect = initial;
            commitRect(initial);
        }

        dragRef.current = { mode, start: { x: p.x, y: p.y }, baseRect };
        pointerIdRef.current = e.pointerId;
        (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
        setDragging(true);
        e.preventDefault();
    };

    const handleMove = (e: React.PointerEvent) => {
        if (!dragging || !dragRef.current) return;
        const p = toImagePx(e.clientX, e.clientY);
        if (!p) return;
        const bounds = getBounds();
        const drag = dragRef.current;
        const base = drag.baseRect;
        let next: PdfCropSelection | null = null;

        if (drag.mode === "create") {
            const x2 = clamp(p.x, 0, bounds.width);
            const y2 = clamp(p.y, 0, bounds.height);
            next = normalizeRect(drag.start.x, drag.start.y, x2, y2);
        } else if (drag.mode === "move") {
            const dx = p.x - drag.start.x;
            const dy = p.y - drag.start.y;
            const x = clamp(base.x + dx, 0, bounds.width - base.width);
            const y = clamp(base.y + dy, 0, bounds.height - base.height);
            next = { x, y, width: base.width, height: base.height };
        } else if (drag.mode === "resize-nw") {
            const x1 = clamp(p.x, 0, base.x + base.width - 1);
            const y1 = clamp(p.y, 0, base.y + base.height - 1);
            next = normalizeRect(x1, y1, base.x + base.width, base.y + base.height);
        } else if (drag.mode === "resize-ne") {
            const x2 = clamp(p.x, base.x + 1, bounds.width);
            const y1 = clamp(p.y, 0, base.y + base.height - 1);
            next = normalizeRect(base.x, y1, x2, base.y + base.height);
        } else if (drag.mode === "resize-sw") {
            const x1 = clamp(p.x, 0, base.x + base.width - 1);
            const y2 = clamp(p.y, base.y + 1, bounds.height);
            next = normalizeRect(x1, base.y, base.x + base.width, y2);
        } else if (drag.mode === "resize-se") {
            const x2 = clamp(p.x, base.x + 1, bounds.width);
            const y2 = clamp(p.y, base.y + 1, bounds.height);
            next = normalizeRect(base.x, base.y, x2, y2);
        }

        if (next) commitRect(next);
    };

    const handleUp = (e: React.PointerEvent) => {
        const activePointerId = pointerIdRef.current;
        if (activePointerId !== null) {
            (e.currentTarget as HTMLElement).releasePointerCapture?.(activePointerId);
            pointerIdRef.current = null;
        }
        if (dragging) {
            onCropChange(rectRef.current, imgSize);
        }
        dragRef.current = null;
        setDragging(false);
    };

    const nudgeRectSize = React.useCallback((factor: number) => {
        const current = rectRef.current;
        if (!current) return;
        const bounds = getBounds();
        const cx = current.x + current.width / 2;
        const cy = current.y + current.height / 2;
        const width = clamp(current.width * factor, 8, bounds.width);
        const height = clamp(current.height * factor, 8, bounds.height);
        const x = clamp(cx - width / 2, 0, bounds.width - width);
        const y = clamp(cy - height / 2, 0, bounds.height - height);
        const next = { x, y, width, height };
        commitRect(next);
        onCropChange(next, bounds);
    }, [commitRect, getBounds, onCropChange]);

    const clearRect = React.useCallback(() => {
        commitRect(null);
        onCropChange(null, getBounds());
    }, [commitRect, getBounds, onCropChange]);

    return (
        <div className="rounded-xl border border-slate-700 bg-slate-900 p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-semibold text-slate-300">{pageLabel}</div>
                <div className="flex items-center gap-1">
                    <button
                        type="button"
                        className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-700 disabled:opacity-50"
                        onClick={() => nudgeRectSize(0.85)}
                        disabled={!rect}
                    >
                        Smaller
                    </button>
                    <button
                        type="button"
                        className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-700 disabled:opacity-50"
                        onClick={() => nudgeRectSize(1.15)}
                        disabled={!rect}
                    >
                        Bigger
                    </button>
                    <button
                        type="button"
                        className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-700 disabled:opacity-50"
                        onClick={clearRect}
                        disabled={!rect}
                    >
                        Clear
                    </button>
                </div>
            </div>
            <div className="mb-2 text-[11px] text-slate-400">
                Drag to create crop. Drag inside box to move. Drag corners to resize.
            </div>
            <div
                ref={wrapRef}
                className="relative overflow-hidden rounded-lg border border-slate-700 bg-black"
                onPointerDown={handleDown}
                onPointerMove={handleMove}
                onPointerUp={handleUp}
                onPointerLeave={handleUp}
            >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                    ref={imgRef}
                    src={imageUrl}
                    alt="PDF page"
                    className="select-none"
                    style={{ width: `${Math.min(1, Math.max(0.5, scale)) * 100}%`, maxWidth: "100%", height: "auto" }}
                    draggable={false}
                    onLoad={(e) => {
                        const img = e.currentTarget;
                        setImgSize({ width: img.naturalWidth, height: img.naturalHeight });
                        onCropChange(rectRef.current, { width: img.naturalWidth, height: img.naturalHeight });
                    }}
                />
                {rect && imgSize.width > 0 && imgSize.height > 0 && (
                    <div
                        className="pointer-events-none absolute border-2 border-primary bg-primary/20"
                        style={{
                            left: `${(rect.x / imgSize.width) * 100}%`,
                            top: `${(rect.y / imgSize.height) * 100}%`,
                            width: `${(rect.width / imgSize.width) * 100}%`,
                            height: `${(rect.height / imgSize.height) * 100}%`,
                        }}
                    >
                        <div className="absolute -left-1.5 -top-1.5 h-3 w-3 rounded-full border border-white bg-primary" />
                        <div className="absolute -right-1.5 -top-1.5 h-3 w-3 rounded-full border border-white bg-primary" />
                        <div className="absolute -left-1.5 -bottom-1.5 h-3 w-3 rounded-full border border-white bg-primary" />
                        <div className="absolute -right-1.5 -bottom-1.5 h-3 w-3 rounded-full border border-white bg-primary" />
                    </div>
                )}
            </div>
        </div>
    );
}
