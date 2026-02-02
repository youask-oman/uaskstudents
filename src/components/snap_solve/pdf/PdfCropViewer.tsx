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

export default function PdfCropViewer({ imageUrl, pageLabel, onCropChange, scale = 1 }: Props) {
    const wrapRef = React.useRef<HTMLDivElement | null>(null);
    const imgRef = React.useRef<HTMLImageElement | null>(null);
    const [imgSize, setImgSize] = React.useState({ width: 0, height: 0 });
    const [dragging, setDragging] = React.useState(false);
    const [start, setStart] = React.useState<{ x: number; y: number } | null>(null);
    const [rect, setRect] = React.useState<PdfCropSelection | null>(null);

    React.useEffect(() => {
        setRect(null);
        setStart(null);
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
        return { x: rx * sx, y: ry * sy };
    };

    const handleDown = (e: React.PointerEvent) => {
        const p = toImagePx(e.clientX, e.clientY);
        if (!p) return;
        setDragging(true);
        setStart(p);
        const initial = { x: p.x, y: p.y, width: 1, height: 1 };
        setRect(initial);
        onCropChange(initial, imgSize);
    };

    const handleMove = (e: React.PointerEvent) => {
        if (!dragging || !start) return;
        const p = toImagePx(e.clientX, e.clientY);
        if (!p) return;
        const x = Math.min(start.x, p.x);
        const y = Math.min(start.y, p.y);
        const width = Math.max(1, Math.abs(p.x - start.x));
        const height = Math.max(1, Math.abs(p.y - start.y));
        const next = { x, y, width, height };
        setRect(next);
        onCropChange(next, imgSize);
    };

    const handleUp = () => {
        setDragging(false);
    };

    return (
        <div className="rounded-xl border border-slate-700 bg-slate-900 p-3">
            <div className="mb-2 text-xs font-semibold text-slate-300">{pageLabel}</div>
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
                        onCropChange(rect, { width: img.naturalWidth, height: img.naturalHeight });
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
                    />
                )}
            </div>
        </div>
    );
}
