"use client";

import React from "react";
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
}: CropWorkspaceProps) {
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
        <div className="relative w-full h-[420px] bg-slate-900 rounded-xl overflow-hidden">
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
                objectFit="contain"
                showGrid={true}
            />
            <div className="absolute bottom-3 left-3 right-3 bg-white/90 rounded-lg px-4 py-2 shadow flex flex-wrap gap-4 items-center">
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                    Zoom
                    <input
                        type="range"
                        min={1}
                        max={3}
                        step={0.05}
                        value={zoom}
                        onChange={(e) => onZoomChange(parseFloat(e.target.value))}
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
                    />
                </label>
            </div>
        </div>
    );
}
