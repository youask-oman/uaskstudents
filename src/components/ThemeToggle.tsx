"use client";

import React from "react";

export default function ThemeToggle() {
    const [isDark, setIsDark] = React.useState(() => {
        if (typeof window === "undefined") return false;
        const stored = localStorage.getItem("theme");
        if (stored) return stored === "dark";
        return document.documentElement.classList.contains("dark") ||
            window.matchMedia("(prefers-color-scheme: dark)").matches;
    });

    React.useEffect(() => {
        const root = document.documentElement;
        if (isDark) {
            root.classList.add("dark");
            localStorage.setItem("theme", "dark");
        } else {
            root.classList.remove("dark");
            localStorage.setItem("theme", "light");
        }
    }, [isDark]);

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
