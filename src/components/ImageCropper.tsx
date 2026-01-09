"use client";

import { useEffect, useRef, useState } from "react";

interface ImageCropperProps {
    imageSrc: string;
    onCancel: () => void;
    onConfirm: (blob: Blob) => void;
}

export default function ImageCropper({ imageSrc, onCancel, onConfirm }: ImageCropperProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null); // For rendering the crop

    // Selection state (percentages 0-100 to be responsive)
    const [selection, setSelection] = useState({ x: 15, y: 30, w: 70, h: 40 });

    // Use Ref for drag state to avoid closure staleness and re-renders during drag
    const dragRef = useRef({
        isDragging: false,
        startX: 0,
        startY: 0,
        handle: null as string | null,
        initialSelection: { x: 0, y: 0, w: 0, h: 0 }
    });

    // Initial load
    useEffect(() => {
        // Reset selection on new image
        setSelection({ x: 15, y: 30, w: 70, h: 40 });
    }, [imageSrc]);

    const handlePointerDown = (e: React.PointerEvent, handle: string | null = null) => {
        e.preventDefault();
        e.stopPropagation();

        if (containerRef.current) {
            containerRef.current.setPointerCapture(e.pointerId);

            dragRef.current = {
                isDragging: true,
                startX: e.clientX,
                startY: e.clientY,
                handle,
                initialSelection: { ...selection }
            };
        }
    };

    const handlePointerMove = (e: React.PointerEvent) => {
        const state = dragRef.current;
        if (!state.isDragging || !containerRef.current) return;

        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const deltaXPercent = ((e.clientX - state.startX) / rect.width) * 100;
        const deltaYPercent = ((e.clientY - state.startY) / rect.height) * 100;

        let newSel = { ...state.initialSelection };

        if (!state.handle) {
            // Moving the box
            newSel.x = Math.max(0, Math.min(100 - newSel.w, state.initialSelection.x + deltaXPercent));
            newSel.y = Math.max(0, Math.min(100 - newSel.h, state.initialSelection.y + deltaYPercent));
        } else {
            // Resizing logic
            if (state.handle.includes('e')) { // East
                newSel.w = Math.max(5, Math.min(100 - newSel.x, state.initialSelection.w + deltaXPercent));
            }
            if (state.handle.includes('w')) { // West
                const projectedX = state.initialSelection.x + deltaXPercent;
                const safeX = Math.max(0, Math.min(state.initialSelection.x + state.initialSelection.w - 5, projectedX));
                const diff = safeX - state.initialSelection.x;
                newSel.x = safeX;
                newSel.w = state.initialSelection.w - diff;
            }
            if (state.handle.includes('s')) { // South
                newSel.h = Math.max(5, Math.min(100 - newSel.y, state.initialSelection.h + deltaYPercent));
            }
            if (state.handle.includes('n')) { // North
                const projectedY = state.initialSelection.y + deltaYPercent;
                const safeY = Math.max(0, Math.min(state.initialSelection.y + state.initialSelection.h - 5, projectedY));
                const diff = safeY - state.initialSelection.y;
                newSel.y = safeY;
                newSel.h = state.initialSelection.h - diff;
            }
        }
        setSelection(newSel);
    };

    const handlePointerUp = (e: React.PointerEvent) => {
        dragRef.current.isDragging = false;
        if (containerRef.current) {
            containerRef.current.releasePointerCapture(e.pointerId);
        }
    };

    // Initialize Canvas
    useEffect(() => {
        const image = new Image();
        image.src = imageSrc;
        image.onload = () => {
            if (canvasRef.current && containerRef.current) {
                const canvas = canvasRef.current;
                const ctx = canvas.getContext('2d');
                if (!ctx) return;

                // Calculate aspect ratio
                // We want the image to fit the WIDTH of the container (minus padding)
                // allowing HEIGHT to scroll if needed.
                const containerWidth = Math.min(containerRef.current.clientWidth - 48, 800); // 48px padding, max 800px width
                const scale = containerWidth / image.width;

                const displayWidth = containerWidth;
                const displayHeight = image.height * scale;

                canvas.width = displayWidth;
                canvas.height = displayHeight;

                // Draw image
                ctx.drawImage(image, 0, 0, displayWidth, displayHeight);

                // Default selection: Center 80%
                const initialW = displayWidth * 0.8;
                const initialH = Math.min(displayHeight * 0.5, 300); // Don't make it too tall initially
                // NOTE: The original selection state uses percentages.
                // To maintain consistency with the rest of the component,
                // we convert these pixel values back to percentages relative to the displayWidth/Height.
                setSelection({
                    x: ((displayWidth - initialW) / 2 / displayWidth) * 100,
                    y: ((displayHeight - initialH) / 2 / displayHeight) * 100,
                    w: (initialW / displayWidth) * 100,
                    h: (initialH / displayHeight) * 100
                });
            }
        };
    }, [imageSrc]);

    const confirmCrop = () => {
        if (!containerRef.current) return;

        // Find the image element to get natural dimensions
        const img = containerRef.current.querySelector('img');
        if (!img) return;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Use natural dimensions for high-res crop
        const naturalWidth = img.naturalWidth;
        const naturalHeight = img.naturalHeight;

        // Calculate pixel coordinates
        const cropX = (selection.x / 100) * naturalWidth;
        const cropY = (selection.y / 100) * naturalHeight;
        const cropW = (selection.w / 100) * naturalWidth;
        const cropH = (selection.h / 100) * naturalHeight;

        canvas.width = cropW;
        canvas.height = cropH;

        ctx.drawImage(
            img,
            cropX, cropY, cropW, cropH,
            0, 0, cropW, cropH
        );

        canvas.toBlob((blob) => {
            if (blob) onConfirm(blob);
        }, 'image/jpeg', 0.95);
    };

    return (
        <div className="flex flex-col h-full bg-slate-900 border border-slate-700 rounded-xl overflow-hidden relative">
            <div className="bg-slate-800 px-4 py-3 flex items-center justify-between border-b border-slate-700 z-10 shrink-0">
                <div className="flex items-center gap-2 text-white">
                    <span className="material-symbols-outlined text-primary">crop</span>
                    <span className="font-bold text-sm">Select Area to Solve</span>
                </div>
                <div className="text-xs text-slate-400">Drag to move • Pull corners to resize</div>
            </div>

            {/* Scrollable Outer Container */}
            <div className="flex-1 relative bg-black/50 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 p-4">
                <div className="flex justify-center min-h-full py-4">
                    {/* Image Wrapper - The Coordinate Context */}
                    <div
                        ref={containerRef}
                        className="relative inline-block w-full max-w-4xl shadow-2xl touch-none"
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerUp}
                        onPointerLeave={handlePointerUp}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={imageSrc}
                            alt="Crop Source"
                            draggable={false}
                            className="w-full h-auto block select-none"
                        />

                        {/* Overlay Grid */}
                        <div className="absolute inset-0 pointer-events-none">
                            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: `${selection.y}%`, background: 'rgba(0,0,0,0.6)' }}></div>
                            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: `${100 - (selection.y + selection.h)}%`, background: 'rgba(0,0,0,0.6)' }}></div>
                            <div style={{ position: 'absolute', top: `${selection.y}%`, left: 0, width: `${selection.x}%`, height: `${selection.h}%`, background: 'rgba(0,0,0,0.6)' }}></div>
                            <div style={{ position: 'absolute', top: `${selection.y}%`, right: 0, width: `${100 - (selection.x + selection.w)}%`, height: `${selection.h}%`, background: 'rgba(0,0,0,0.6)' }}></div>
                        </div>

                        {/* Selection Box */}
                        <div
                            className="absolute cursor-move border-2 border-primary box-content shadow-[0_0_0_9999px_rgba(0,0,0,0.5)] touch-none"
                            style={{
                                left: `${selection.x}%`,
                                top: `${selection.y}%`,
                                width: `${selection.w}%`,
                                height: `${selection.h}%`,
                                boxShadow: 'none'
                            }}
                            onPointerDown={(e) => handlePointerDown(e)}
                        >
                            {/* Inner Grid Lines */}
                            <div className="absolute inset-0 flex flex-col pointer-events-none opacity-30">
                                <div className="flex-1 border-b border-primary/50"></div>
                                <div className="flex-1 border-b border-primary/50"></div>
                                <div className="flex-1"></div>
                            </div>
                            <div className="absolute inset-0 flex pointer-events-none opacity-30">
                                <div className="flex-1 border-r border-primary/50"></div>
                                <div className="flex-1 border-r border-primary/50"></div>
                                <div className="flex-1"></div>
                            </div>

                            {/* Handles */}
                            {['nw', 'ne', 'sw', 'se'].map((h) => (
                                <div
                                    key={h}
                                    className={`absolute w-6 h-6 border-2 border-white bg-primary rounded-full z-20 flex items-center justify-center
                                        ${h === 'nw' ? '-top-3 -left-3 cursor-nw-resize' : ''}
                                        ${h === 'ne' ? '-top-3 -right-3 cursor-ne-resize' : ''}
                                        ${h === 'sw' ? '-bottom-3 -left-3 cursor-sw-resize' : ''}
                                        ${h === 'se' ? '-bottom-3 -right-3 cursor-se-resize' : ''}
                                    `}
                                    onPointerDown={(e) => handlePointerDown(e, h)}
                                >
                                    <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <div className="p-4 bg-slate-900 border-t border-slate-800 flex justify-between gap-4 z-20 shrink-0">
                <button
                    onClick={onCancel}
                    className="px-6 py-2.5 rounded-lg font-bold text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                >
                    Cancel
                </button>
                <div className="flex gap-3">
                    <button
                        onClick={() => setSelection({ x: 0, y: 0, w: 100, h: 100 })}
                        className="px-4 py-2.5 rounded-lg font-bold text-primary bg-primary/10 hover:bg-primary/20 transition-colors text-sm"
                    >
                        Full Image
                    </button>
                    <button
                        onClick={confirmCrop}
                        className="px-8 py-2.5 rounded-lg font-bold text-white bg-primary hover:bg-blue-600 shadow-lg shadow-primary/25 transition-all active:scale-95 flex items-center gap-2"
                    >
                        <span className="material-symbols-outlined text-lg">check</span>
                        Confirm Selection
                    </button>
                </div>
            </div>
        </div>
    );
}
