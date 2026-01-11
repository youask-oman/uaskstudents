"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export default function TopNavBar() {
    const [isDark, setIsDark] = useState(false);

    useEffect(() => {
        // Check initial preference
        if (document.documentElement.classList.contains("dark") ||
            (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            setIsDark(true);
            document.documentElement.classList.add('dark');
        } else {
            setIsDark(false);
            document.documentElement.classList.remove('dark');
        }
    }, []);

    const toggleTheme = () => {
        if (isDark) {
            document.documentElement.classList.remove("dark");
            localStorage.theme = 'light';
            setIsDark(false);
        } else {
            document.documentElement.classList.add("dark");
            localStorage.theme = 'dark';
            setIsDark(true);
        }
    };

    return (
        <header className="sticky top-0 z-50 w-full border-b border-[#f0f2f4] dark:border-slate-800 bg-white/80 dark:bg-background-dark/80 backdrop-blur-md px-4 md:px-10 py-3 transition-colors duration-200">
            <div className="max-w-[1200px] mx-auto flex items-center justify-between">
                <Link href="/" className="flex items-center gap-3 text-primary">
                    <img src={isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" className="h-8 w-auto" />
                    <h2 className="text-[#111318] dark:text-white text-xl font-bold leading-tight tracking-tight font-display">
                        uask.ai
                    </h2>
                </Link>

                <nav className="hidden md:flex flex-1 justify-center gap-8">
                    <Link className="text-[#111318] dark:text-gray-300 text-sm font-medium hover:text-primary transition-colors" href="/#how-it-works">How it Works</Link>
                    <Link className="text-[#111318] dark:text-gray-300 text-sm font-medium hover:text-primary transition-colors" href="/#features">Features</Link>
                    <Link className="text-[#111318] dark:text-gray-300 text-sm font-medium hover:text-primary transition-colors" href="/#pricing">Pricing</Link>
                </nav>

                <div className="flex items-center gap-3">
                    <button
                        onClick={toggleTheme}
                        className="p-2 text-[#111318] dark:text-white hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors flex items-center justify-center"
                        aria-label="Toggle Dark Mode"
                    >
                        <span className="material-symbols-outlined text-xl">
                            {isDark ? 'light_mode' : 'dark_mode'}
                        </span>
                    </button>

                    <Link href="/login">
                        <button className="hidden sm:flex px-4 py-2 text-[#111318] dark:text-white text-sm font-bold hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                            Login
                        </button>
                    </Link>

                    <Link href="/signup">
                        <button className="flex items-center justify-center rounded-lg h-10 px-5 bg-primary text-white text-sm font-bold hover:bg-blue-700 transition-colors shadow-lg shadow-primary/20">
                            Sign Up
                        </button>
                    </Link>

                    <button className="hidden md:flex items-center justify-center rounded-lg h-10 w-10 bg-[#f0f2f4] dark:bg-slate-800 text-[#111318] dark:text-white hover:bg-gray-200 dark:hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined">open_in_new</span>
                    </button>
                </div>
            </div>
        </header>
    );
}
