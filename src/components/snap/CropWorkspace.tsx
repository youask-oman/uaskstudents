"use client";

"use client";

import React, { useCallback, useLayoutEffect, useRef, useState } from "react";
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
    onViewportSize?: (size: { width: number; height: number }) => void;
    fullPage: boolean;
    resetToken?: number;
    // New props for Selection Mode
    selectionMode?: boolean;
    onSelectionChange?: (bbox: { x: number; y: number; w: number; h: number } | null) => void;
};

const DEFAULT_WIDTH_SCALE = 0.65;
const DEFAULT_HEIGHT_SCALE = 0.6;
const MIN_SCALE = 0.2;
const MAX_SCALE = 1.1;

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
    onViewportSize,
    fullPage,
    resetToken,
    selectionMode = false,
    onSelectionChange,
}: CropWorkspaceProps) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [workspaceSize, setWorkspaceSize] = useState({ width: 0, height: 0 });
    const [mediaSize, setMediaSize] = useState<{ width: number; height: number } | null>(null);
    const [cropWidthScale, setCropWidthScale] = useState(DEFAULT_WIDTH_SCALE);
    const [cropHeightScale, setCropHeightScale] = useState(DEFAULT_HEIGHT_SCALE);
    const [lockRatio, setLockRatio] = useState(false);

    // Selection State
    const [isSelecting, setIsSelecting] = useState(false);
    const [selectionStart, setSelectionStart] = useState<{ x: number, y: number } | null>(null);
    const [currentSelection, setCurrentSelection] = useState<{ x: number, y: number, w: number, h: number } | null>(null);

    const prevFullPage = useRef(fullPage);
    const prevReset = useRef(resetToken);

    const updateSize = useCallback(() => {
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        setWorkspaceSize({ width: rect.width, height: rect.height });
        onViewportSize?.({ width: rect.width, height: rect.height });
    }, [onViewportSize]);

    useLayoutEffect(() => {
        updateSize();
        const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => updateSize()) : null;
        if (observer && containerRef.current) {
            observer.observe(containerRef.current);
        }
        window.addEventListener("resize", updateSize);
        return () => {
            window.removeEventListener("resize", updateSize);
            observer?.disconnect();
        };
    }, [updateSize]);

    React.useEffect(() => {
        updateSize();
    }, [imageSrc, updateSize]);

    // Cleanup selection when mode changes
    React.useEffect(() => {
        if (!selectionMode) {
            setCurrentSelection(null);
            setIsSelecting(false);
            onSelectionChange?.(null);
        }
    }, [selectionMode, onSelectionChange]);

    const clampScale = (value: number) => {
        return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
    };

    const resetCropScale = React.useCallback(() => {
        setCropWidthScale(DEFAULT_WIDTH_SCALE);
        setCropHeightScale(DEFAULT_HEIGHT_SCALE);
        setLockRatio(false);
    }, []);

    React.useEffect(() => {
        if (fullPage) {
            setCropWidthScale(1);
            setCropHeightScale(1);
            setLockRatio(true);
        } else if (prevFullPage.current && !fullPage) {
            resetCropScale();
        }
        prevFullPage.current = fullPage;
    }, [fullPage, resetCropScale]);

    React.useEffect(() => {
        if (resetToken == null) return;
        if (resetToken !== prevReset.current) {
            resetCropScale();
            prevReset.current = resetToken;
        }
    }, [resetToken, resetCropScale]);

    const cropSize = fullPage
        ? {
            width: Math.max(32, workspaceSize.width),
            height: Math.max(32, workspaceSize.height),
        }
        : {
            width: Math.max(32, clamp(workspaceSize.width * cropWidthScale, 32, workspaceSize.width)),
            height: Math.max(32, clamp(workspaceSize.height * cropHeightScale, 32, workspaceSize.height)),
        };
    const cropperKey = `${fullPage ? "full" : "crop"}-${Math.round(cropWidthScale * 100)}-${Math.round(cropHeightScale * 100)}`;

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

    const handleHorizontalChange = (value: number) => {
        const next = clampScale(value);
        setCropWidthScale(next);
        if (lockRatio) {
            setCropHeightScale(next);
        }
    };

    const handleVerticalChange = (value: number) => {
        const next = clampScale(value);
        setCropHeightScale(next);
        if (lockRatio) {
            setCropWidthScale(next);
        }
    };

    // Selection Handlers
    const handlePointerDown = (e: React.PointerEvent) => {
        if (!selectionMode || !containerRef.current) return;
        e.preventDefault();
        const rect = containerRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setSelectionStart({ x, y });
        setIsSelecting(true);
        setCurrentSelection({ x, y, w: 0, h: 0 });
    };

    const handlePointerMove = (e: React.PointerEvent) => {
        if (!isSelecting || !selectionStart || !containerRef.current) return;
        e.preventDefault();
        const rect = containerRef.current.getBoundingClientRect();
        const currentX = clamp(e.clientX - rect.left, 0, rect.width);
        const currentY = clamp(e.clientY - rect.top, 0, rect.height);

        const x = Math.min(selectionStart.x, currentX);
        const y = Math.min(selectionStart.y, currentY);
        const w = Math.abs(currentX - selectionStart.x);
        const h = Math.abs(currentY - selectionStart.y);

        setCurrentSelection({ x, y, w, h });
    };

    const handlePointerUp = () => {
        if (!isSelecting) return;
        setIsSelecting(false);
        if (currentSelection && workspaceSize.width > 0 && workspaceSize.height > 0) {
            // Normalize
            const normalized = {
                x: currentSelection.x / workspaceSize.width,
                y: currentSelection.y / workspaceSize.height,
                w: currentSelection.w / workspaceSize.width,
                h: currentSelection.h / workspaceSize.height
            };
            // Only fire if significant size
            if (normalized.w > 0.01 && normalized.h > 0.01) {
                onSelectionChange?.(normalized);
            } else {
                setCurrentSelection(null);
                onSelectionChange?.(null);
            }
        }
    };

    return (
        <div
            ref={containerRef}
            className="relative w-full min-h-[520px] bg-slate-900 rounded-xl overflow-hidden select-none touch-none"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerUp}
        >
            <Cropper
                key={cropperKey}
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                rotation={rotation}
                minZoom={0.1}
                maxZoom={5}
                onCropChange={selectionMode ? () => { } : onCropChange} // Disable crop move in selection mode
                onZoomChange={selectionMode ? () => { } : onZoomChange}
                onRotationChange={onRotationChange}
                onCropComplete={handleCropComplete}
                onMediaLoaded={(media) => {
                    const natural = { width: media.naturalWidth, height: media.naturalHeight };
                    setMediaSize(natural);
                    if (onImageSize) {
                        onImageSize(natural);
                    }
                }}
                cropSize={cropSize}
                restrictPosition={false}
                objectFit="contain"
                showGrid={!selectionMode} // Hide grid in selection mode to reduce noise
                classes={{
                    containerClassName: selectionMode ? "opacity-50 pointer-events-none" : ""
                }}
            />

            {/* Selection Overlay */}
            {selectionMode && currentSelection && (
                <div
                    className="absolute border-2 border-red-500 bg-red-500/20 pointer-events-none z-10"
                    style={{
                        left: currentSelection.x,
                        top: currentSelection.y,
                        width: currentSelection.w,
                        height: currentSelection.h,
                    }}
                />
            )}

            {/* Instruction Overlay when in Selection Mode */}
            {selectionMode && !currentSelection && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                    <div className="bg-black/60 text-white px-4 py-2 rounded-full text-sm font-medium backdrop-blur-sm">
                        Draw a box to select error region
                    </div>
                </div>
            )}

            <div className={`absolute bottom-0 left-0 right-0 px-4 py-3 bg-white/95 border-t border-slate-200 flex flex-col gap-3 text-[11px] transition-opacity ${selectionMode ? 'opacity-30 pointer-events-none' : 'opacity-100'}`}>
                <div className="flex flex-wrap gap-3">
                    <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                        Zoom
                        <input
                            type="range"
                            min={0.1}
                            max={5}
                            step={0.01}
                            value={zoom}
                            onChange={(e) => onZoomChange(parseFloat(e.target.value))}
                            className="w-28 accent-admin-primary"
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
                            className="w-28 accent-admin-primary"
                        />
                    </label>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                        <input
                            id="lock-ratio"
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
                            className="accent-admin-primary"
                        />
                        <label htmlFor="lock-ratio" className="font-semibold text-xs">
                            Lock ratio
                        </label>
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1">
                        <span className="text-xs font-semibold text-slate-600">Horizontal crop</span>
                        <input
                            type="range"
                            min={MIN_SCALE}
                            max={MAX_SCALE}
                            step={0.01}
                            value={cropWidthScale}
                            disabled={fullPage}
                            onChange={(e) => handleHorizontalChange(parseFloat(e.target.value))}
                            className="w-full accent-admin-primary"
                        />
                    </label>
                    <label className="flex flex-col gap-1">
                        <span className="text-xs font-semibold text-slate-600">Vertical crop</span>
                        <input
                            type="range"
                            min={MIN_SCALE}
                            max={MAX_SCALE}
                            step={0.01}
                            value={cropHeightScale}
                            disabled={fullPage}
                            onChange={(e) => handleVerticalChange(parseFloat(e.target.value))}
                            className="w-full accent-admin-primary"
                        />
                    </label>
                </div>
            </div>
        </div>
    );
}
