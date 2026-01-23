"use client";

import React, { useLayoutEffect, useRef, useState } from "react";
import Cropper, { Area } from "react-easy-crop";
import { CropArea, clamp } from "./snapSolveUtils";

type CropWorkspaceProps = {
    imageSrc: string;
    crop: { x: number; y: number };
    zoom: number;
    rotation: number;
    onCropChange: (crop: { x: number; y: number }) => void;
    onZoomChange: (zoom: number) => void;
    onRotationChange: (rotation: number) => void;
    onCropComplete: (areaPixels: CropArea) => void;
    onImageSize?: (size: { width: number; height: number }) => void;
    fullPage: boolean;
};

export default function CropWorkspace({
    imageSrc,
    crop,
    zoom,
    rotation,
    onCropChange,
    onZoomChange,
    onRotationChange,
    onCropComplete,
    onImageSize,
    fullPage,
}: CropWorkspaceProps) {
    const DEFAULT_WIDTH_SCALE = 0.65;
    const DEFAULT_HEIGHT_SCALE = 0.6;
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [workspaceSize, setWorkspaceSize] = useState({ width: 0, height: 0 });
    const [cropWidthScale, setCropWidthScale] = useState(DEFAULT_WIDTH_SCALE);
    const [cropHeightScale, setCropHeightScale] = useState(DEFAULT_HEIGHT_SCALE);
    const [lockRatio, setLockRatio] = useState(false);
    const prevFullPage = useRef(fullPage);

    useLayoutEffect(() => {
        const updateSize = () => {
            if (!containerRef.current) return;
            const rect = containerRef.current.getBoundingClientRect();
            setWorkspaceSize({ width: rect.width, height: rect.height });
        };
        updateSize();
        window.addEventListener("resize", updateSize);
        return () => window.removeEventListener("resize", updateSize);
    }, []);

    React.useEffect(() => {
        if (fullPage) {
            setCropWidthScale(1);
            setCropHeightScale(1);
        } else if (prevFullPage.current && !fullPage) {
            setCropWidthScale(DEFAULT_WIDTH_SCALE);
            setCropHeightScale(DEFAULT_HEIGHT_SCALE);
            setLockRatio(false);
        }
        prevFullPage.current = fullPage;
    }, [fullPage]);

    const cropSize = {
        width: Math.max(32, workspaceSize.width * cropWidthScale),
        height: Math.max(32, workspaceSize.height * cropHeightScale),
    };

    const handleCropComplete = React.useCallback(
        (_area: Area, areaPixels: Area) => {
            onCropComplete({
                x: areaPixels.x,
                y: areaPixels.y,
                width: areaPixels.width,
                height: areaPixels.height,
            });
        },
        [onCropComplete]
    );

    return (
        <div ref={containerRef} className="relative w-full h-[520px] bg-slate-900 rounded-xl overflow-hidden">
            <Cropper
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                rotation={rotation}
                onCropChange={onCropChange}
                onZoomChange={onZoomChange}
                onRotationChange={onRotationChange}
                onCropComplete={handleCropComplete}
                onMediaLoaded={(media) => {
                    if (onImageSize) {
                        onImageSize({ width: media.naturalWidth, height: media.naturalHeight });
                    }
                }}
                cropSize={cropSize}
                restrictPosition={false}
                objectFit="contain"
                showGrid={true}
            />
            <div className="absolute bottom-3 left-3 right-3 bg-white/90 rounded-2xl px-5 py-3 shadow-lg flex flex-wrap gap-3 items-center justify-between text-[11px]">
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                    Zoom
                    <input
                        type="range"
                        min={1}
                        max={3}
                        step={0.05}
                        value={zoom}
                        onChange={(e) => onZoomChange(parseFloat(e.target.value))}
                        className="w-28"
                    />
                </label>
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                    Rotate
                    <input
                        type="range"
                        min={-180}
                        max={180}
                        step={1}
                        value={rotation}
                        onChange={(e) => onRotationChange(clamp(parseFloat(e.target.value), -180, 180))}
                        className="w-28"
                    />
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600 w-full max-w-[200px]">
                    Horizontal Crop
                    <input
                        type="range"
                        min={0.3}
                        max={1}
                        step={0.05}
                        value={cropWidthScale}
                        disabled={fullPage}
                        onChange={(e) => {
                            const next = parseFloat(e.target.value);
                            setCropWidthScale(next);
                            if (lockRatio) {
                                setCropHeightScale(next);
                            }
                        }}
                        className="w-full"
                    />
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600 w-full max-w-[200px]">
                    Vertical Crop
                    <input
                        type="range"
                        min={0.3}
                        max={1}
                        step={0.05}
                        value={cropHeightScale}
                        disabled={fullPage}
                        onChange={(e) => {
                            const next = parseFloat(e.target.value);
                            setCropHeightScale(next);
                            if (lockRatio) {
                                setCropWidthScale(next);
                            }
                        }}
                        className="w-full"
                    />
                </label>
                <div className="flex flex-col gap-1 text-xs text-slate-500">
                    <label className="flex items-center gap-2 text-[11px]">
                        <input
                            type="checkbox"
                            checked={lockRatio}
                            onChange={(e) => {
                                const next = e.target.checked;
                                setLockRatio(next);
                                if (next) {
                                    setCropHeightScale(cropWidthScale);
                                }
                            }}
                            disabled={fullPage}
                        />
                        Lock ratio
                    </label>
                    <button
                        type="button"
                        className="text-[11px] font-semibold uppercase tracking-[0.3em] text-admin-primary hover:text-admin-primary/80"
                        onClick={() => {
                            setCropWidthScale(DEFAULT_WIDTH_SCALE);
                            setCropHeightScale(DEFAULT_HEIGHT_SCALE);
                        }}
                        disabled={fullPage}
                    >
                        Reset crop size
                    </button>
                </div>
            </div>
        </div>
    );
}
