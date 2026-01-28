"use client";

import { useTheme } from "@/hooks/useTheme";
import { useEffect, useState } from "react";

interface ThemeToggleProps {
    className?: string;
}

export default function ThemeToggle({ className }: ThemeToggleProps) {
    const { isDark, toggleTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setMounted(true);
    }, []);

    // Default floating styles if no className provided, or if user wants to compose
    // We'll trust the user to provide full positioning if they pass a className, 
    // OR we could merge. Safest is to default to fixed if nothing passed.
    const baseClasses = "size-11 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-border-dark shadow-lg flex items-center justify-center text-slate-700 dark:text-slate-200 hover:text-primary dark:hover:text-accent transition-colors";

    // If className is provided, use it + base aesthetics. If not, use fixed positioning.
    const finalClass = className
        ? `${baseClasses} ${className}`
        : `fixed bottom-5 right-5 z-[60] ${baseClasses}`;

    return (
        <button
            onClick={toggleTheme}
            className={finalClass}
            aria-label="Toggle theme"
            type="button"
        >
            <span className="material-symbols-outlined text-[20px]">
                {mounted && isDark ? "light_mode" : "dark_mode"}
            </span>
        </button>
    );
}
