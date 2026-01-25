"use client";

import { useTheme } from "@/hooks/useTheme";

export default function ThemeToggle() {
    const { isDark, toggleTheme } = useTheme();

    return (
        <button
            onClick={toggleTheme}
            className="fixed bottom-5 right-5 z-[60] size-11 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-border-dark shadow-lg flex items-center justify-center text-slate-700 dark:text-slate-200 hover:text-primary dark:hover:text-accent transition-colors"
            aria-label="Toggle theme"
            type="button"
        >
            <span className="material-symbols-outlined text-[20px]">
                {isDark ? "light_mode" : "dark_mode"}
            </span>
        </button>
    );
}
