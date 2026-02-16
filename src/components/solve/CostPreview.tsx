"use client";

interface CostPreviewProps {
    perQuestionCost: number;
    questionCount?: number;
    breakdown?: {
        tier_base: number;
        ocr: number;
        voice: number;
        verify?: number;
        plot?: number;
        asset_type_addon?: number;
        attempt_fee?: number;
    };
    creditsRemaining: number;
    className?: string;
}

/**
 * Displays estimated credit cost before solve.
 * Shows breakdown if OCR/voice add-ons are used.
 */
export default function CostPreview({
    perQuestionCost,
    questionCount = 1,
    breakdown,
    creditsRemaining,
    className = ""
}: CostPreviewProps) {
    const totalCost = perQuestionCost * questionCount;
    const hasEnoughCredits = creditsRemaining >= totalCost;
    const showBreakdown = Boolean(
        breakdown &&
        ((breakdown.ocr || 0) > 0 ||
            (breakdown.voice || 0) > 0 ||
            (breakdown.verify || 0) > 0 ||
            (breakdown.plot || 0) > 0 ||
            (breakdown.asset_type_addon || 0) > 0 ||
            (breakdown.attempt_fee || 0) > 0 ||
            (breakdown.tier_base || 0) > 0)
    );

    return (
        <div className={`flex w-full max-w-full flex-nowrap items-center justify-start gap-2 overflow-hidden text-sm ${className}`}>
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
            {showBreakdown && breakdown && (
                <div className="flex min-w-0 shrink items-center gap-1 overflow-hidden text-xs text-slate-400 whitespace-nowrap">
                    <span>(</span>
                    <span>base {Number(breakdown.tier_base || 0).toFixed(2)}</span>
                    {(breakdown.ocr || 0) > 0 && <span>+ {breakdown.ocr} OCR</span>}
                    {(breakdown.voice || 0) > 0 && <span>+ {breakdown.voice} voice</span>}
                    {(breakdown.verify || 0) > 0 && <span>+ {breakdown.verify} verify</span>}
                    {(breakdown.plot || 0) > 0 && <span>+ {breakdown.plot} plot</span>}
                    {(breakdown.asset_type_addon || 0) > 0 && <span>+ {breakdown.asset_type_addon} asset</span>}
                    {(breakdown.attempt_fee || 0) > 0 && <span>+ {breakdown.attempt_fee} attempt fee</span>}
                    {questionCount > 1 && <span>x {questionCount}</span>}
                    <span>)</span>
                </div>
            )}

            {!hasEnoughCredits && (
                <span className="flex shrink-0 items-center gap-1 whitespace-nowrap text-xs font-medium text-rose-500">
                    <span className="material-symbols-outlined text-[14px]">warning</span>
                    Insufficient credits
                </span>
            )}
        </div>
    );
}
