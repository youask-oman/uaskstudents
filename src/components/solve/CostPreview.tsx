"use client";

interface CostPreviewProps {
    baseCost: number;
    ocrCost?: number;
    voiceCost?: number;
    creditsRemaining: number;
    isDetailed?: boolean;
    className?: string;
}

/**
 * Displays estimated credit cost before solve.
 * Shows breakdown if OCR/voice add-ons are used.
 */
export default function CostPreview({
    baseCost,
    ocrCost = 0,
    voiceCost = 0,
    creditsRemaining,
    isDetailed = false,
    className = ""
}: CostPreviewProps) {
    const totalCost = baseCost + ocrCost + voiceCost;
    const hasEnoughCredits = creditsRemaining >= totalCost;

    return (
        <div className={`flex items-center gap-2 text-sm ${className}`}>
            <div className="flex items-center gap-1">
                <span className="material-symbols-outlined text-[16px] text-primary">
                    payments
                </span>
                <span className="text-slate-500 dark:text-slate-400 font-medium">
                    Cost:
                </span>
                <span className={`font-bold ${hasEnoughCredits ? "text-slate-900 dark:text-white" : "text-rose-500"}`}>
                    {totalCost} credit{totalCost !== 1 ? "s" : ""}
                </span>
            </div>

            {/* Show breakdown for detailed mode or add-ons */}
            {(isDetailed || ocrCost > 0 || voiceCost > 0) && (
                <div className="flex items-center gap-1 text-xs text-slate-400">
                    <span>(</span>
                    <span>{baseCost} base</span>
                    {ocrCost > 0 && <span>+ {ocrCost} OCR</span>}
                    {voiceCost > 0 && <span>+ {voiceCost} voice</span>}
                    <span>)</span>
                </div>
            )}

            {!hasEnoughCredits && (
                <span className="text-xs text-rose-500 font-medium flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">warning</span>
                    Insufficient credits
                </span>
            )}
        </div>
    );
}
