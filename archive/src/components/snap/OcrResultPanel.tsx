"use client";

import React from "react";

export type OcrResult = {
    extracted_text: string;
    extracted_markdown?: string | null;
    questions?: string[];
};

type OcrResultPanelProps = {
    result: OcrResult | null;
    onUseText: (text: string) => void;
    onSolveText: (text: string) => void;
};

export default function OcrResultPanel({ result, onUseText, onSolveText }: OcrResultPanelProps) {
    if (!result) {
        return (
            <div className="border border-dashed border-slate-200 rounded-xl p-6 text-sm text-slate-500">
                OCR results will appear here after reading.
            </div>
        );
    }

    const questions = result.questions || [];

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-slate-800">Extracted Text</h4>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={() => onUseText(result.extracted_text)}
                        className="text-xs font-bold text-primary hover:underline"
                    >
                        Use in Text tab
                    </button>
                    <button
                        type="button"
                        onClick={() => onSolveText(result.extracted_text)}
                        className="text-xs font-bold text-emerald-600 hover:underline"
                    >
                        Solve now
                    </button>
                </div>
            </div>
            <textarea
                className="w-full min-h-[140px] p-3 border border-slate-200 rounded-lg text-sm text-slate-700"
                value={result.extracted_text}
                readOnly
            />

            {questions.length > 0 && (
                <div>
                    <h5 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">
                        Detected Questions
                    </h5>
                    <div className="flex flex-col gap-2">
                        {questions.map((q, idx) => (
                            <button
                                key={`${idx}-${q.slice(0, 12)}`}
                                type="button"
                                onClick={() => onSolveText(q)}
                                className="text-left p-3 border border-slate-200 rounded-lg hover:border-primary/60 hover:bg-primary/5 transition"
                            >
                                <span className="text-xs text-slate-600">{q}</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
