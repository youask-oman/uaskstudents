"use client";

interface UsageMeterProps {
    label: string;
    used: number;
    limit: number;
    icon?: string;
    variant?: "default" | "warning" | "danger";
    showBar?: boolean;
    compact?: boolean;
}

/**
 * Compact usage meter showing used/limit with optional progress bar.
 * Used in header to show credits, OCR, and voice remaining.
 */
export default function UsageMeter({
    label,
    used,
    limit,
    icon,
    variant = "default",
    showBar = false,
    compact = true
}: UsageMeterProps) {
    const percentage = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
    const remaining = Math.max(limit - used, 0);

    // Auto-determine variant based on usage
    const effectiveVariant = percentage >= 90 ? "danger" : percentage >= 70 ? "warning" : variant;

    const variantColors = {
        default: "text-slate-600 dark:text-slate-400",
        warning: "text-amber-600 dark:text-amber-400",
        danger: "text-rose-600 dark:text-rose-400"
    };

    const barColors = {
        default: "bg-primary",
        warning: "bg-amber-500",
        danger: "bg-rose-500"
    };

    if (compact) {
        return (
            <div className="flex items-center gap-1.5 text-xs font-medium">
                {icon && (
                    <span className={`material-symbols-outlined text-[14px] ${variantColors[effectiveVariant]}`}>
                        {icon}
                    </span>
                )}
                <span className="text-slate-500 dark:text-slate-400">{label}</span>
                <span className={`font-bold ${variantColors[effectiveVariant]}`}>
                    {remaining}/{limit}
                </span>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                    {icon && (
                        <span className={`material-symbols-outlined text-[14px] ${variantColors[effectiveVariant]}`}>
                            {icon}
                        </span>
                    )}
                    <span className="text-slate-500 dark:text-slate-400 font-medium">{label}</span>
                </div>
                <span className={`font-bold ${variantColors[effectiveVariant]}`}>
                    {remaining} left
                </span>
            </div>
            {showBar && (
                <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full ${barColors[effectiveVariant]} transition-all duration-300`}
                        style={{ width: `${percentage}%` }}
                    />
                </div>
            )}
        </div>
    );
}
