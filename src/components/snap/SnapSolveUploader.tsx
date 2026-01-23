"use client";

import React from "react";

type SnapSolveUploaderProps = {
    onFile: (file: File) => void;
    maxMb: number;
};

export default function SnapSolveUploader({ onFile, maxMb }: SnapSolveUploaderProps) {
    const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file) onFile(file);
    };

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) onFile(file);
    };

    return (
        <label
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="group relative flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl px-6 py-12 hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer"
        >
            <input
                type="file"
                className="hidden"
                onChange={handleChange}
                accept="image/*,application/pdf"
            />
            <div className="w-14 h-14 bg-primary/10 rounded-full flex items-center justify-center text-primary mb-4 group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-3xl">upload_file</span>
            </div>
            <h3 className="text-lg font-bold mb-1">Drag & Drop or Click</h3>
            <p className="text-slate-500 text-center max-w-sm">
                Upload one image or one PDF. Max {maxMb}MB.
            </p>
            <div className="flex gap-2 mt-4 text-[10px] font-bold uppercase text-slate-500">
                <span className="px-2 py-1 bg-slate-100 rounded">JPG</span>
                <span className="px-2 py-1 bg-slate-100 rounded">PNG</span>
                <span className="px-2 py-1 bg-slate-100 rounded">WEBP</span>
                <span className="px-2 py-1 bg-slate-100 rounded">PDF</span>
            </div>
        </label>
    );
}
