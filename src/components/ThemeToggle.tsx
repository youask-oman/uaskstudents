"use client";

import React from "react";

export default function ThemeToggle() {
    const [mounted, setMounted] = React.useState(false);
    const [isDark, setIsDark] = React.useState(false);

    // Only run on client after mount to prevent hydration mismatch
    React.useEffect(() => {
        setMounted(true);
        // Check theme after mount
        const stored = localStorage.getItem("theme");
        if (stored) {
            setIsDark(stored === "dark");
        } else {
            setIsDark(
                document.documentElement.classList.contains("dark") ||
                window.matchMedia("(prefers-color-scheme: dark)").matches
            );
        }
    }, []);

    React.useEffect(() => {
        if (!mounted) return;
        const root = document.documentElement;
        if (isDark) {
            root.classList.add("dark");
            localStorage.setItem("theme", "dark");
        } else {
            root.classList.remove("dark");
            localStorage.setItem("theme", "light");
        }
    }, [isDark, mounted]);

    // Don't render anything until mounted to avoid hydration mismatch
    if (!mounted) {
        return (
            <button
                className="fixed bottom-5 right-5 z-[60] size-11 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-border-dark shadow-lg flex items-center justify-center text-slate-700 dark:text-slate-200 hover:text-primary dark:hover:text-accent transition-colors"
                aria-label="Toggle theme"
                type="button"
            >
                <span className="material-symbols-outlined text-[20px]">
                    dark_mode
                </span>
            </button>
        );
    }

    return (
        <button
            onClick={() => setIsDark(prev => !prev)}
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
