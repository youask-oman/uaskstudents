"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useTheme } from "@/hooks/useTheme";

export default function TopNavBar() {
    const { isDark, toggleTheme } = useTheme();
    const [mounted, setMounted] = useState(false);
    const [user, setUser] = useState<{ name: string, avatar: string } | null>(null);

    useEffect(() => {
        setMounted(true);
        if (typeof window !== "undefined") {
            const token = localStorage.getItem("token");
            if (token) {
                setUser({
                    name: localStorage.getItem("user_name") || "User",
                    avatar: localStorage.getItem("user_avatar") || ""
                });
            }
        }
    }, []);

    const handleLogout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user_id");
        localStorage.removeItem("user_name");
        localStorage.removeItem("user_role");
        localStorage.removeItem("user_avatar");
        localStorage.removeItem("session_token");
        localStorage.removeItem("user");
        setUser(null);
        window.location.href = "/";
    };

    return (
        <header className="sticky top-0 z-50 w-full border-b border-[#f0f2f4] dark:border-slate-800 bg-white/80 dark:bg-background-dark/80 backdrop-blur-md px-4 md:px-10 py-3 transition-colors duration-200">
            <div className="max-w-[1200px] mx-auto flex items-center justify-between">
                <Link href="/" className="flex items-center gap-3 text-primary">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={mounted && isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" className="h-8 w-auto" />
                    <h2 className="text-[#111318] dark:text-white text-xl font-bold leading-tight tracking-tight font-display">
                        uask.ai
                    </h2>
                </Link>

                <nav className="hidden md:flex flex-1 justify-center gap-8">
                    <Link className="text-[#111318] dark:text-gray-300 text-sm font-medium hover:text-primary transition-colors" href="/#how-it-works">How it Works</Link>
                    <Link className="text-[#111318] dark:text-gray-300 text-sm font-medium hover:text-primary transition-colors" href="/#features">Features</Link>
                    <Link className="text-[#111318] dark:text-gray-300 text-sm font-medium hover:text-primary transition-colors" href="/pricing">Pricing</Link>
                </nav>

                <div className="flex items-center gap-3">
                    <button
                        onClick={toggleTheme}
                        className="p-2 text-[#111318] dark:text-white hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors flex items-center justify-center"
                        aria-label="Toggle Dark Mode"
                    >
                        <span className="material-symbols-outlined text-xl">
                            {mounted && isDark ? 'light_mode' : 'dark_mode'}
                        </span>
                    </button>

                    {user ? (
                        <div className="flex items-center gap-3">
                            <Link href="/solve">
                                <button className="hidden sm:flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary text-sm font-bold hover:bg-primary/20 rounded-lg transition-colors">
                                    <span className="material-symbols-outlined text-[18px]">dashboard</span>
                                    Workspace
                                </button>
                            </Link>

                            <div className="relative group">
                                <button className="h-9 w-9 rounded-full bg-gradient-to-tr from-primary to-purple-500 text-white flex items-center justify-center font-bold text-sm border-2 border-white dark:border-slate-800">
                                    {user.avatar ? (
                                        <>
                                            {/* eslint-disable-next-line @next/next/no-img-element */}
                                            <img src={user.avatar} className="rounded-full w-full h-full object-cover" alt="User Avatar" />
                                        </>
                                    ) : (
                                        user.name.charAt(0)
                                    )}
                                </button>
                                {/* Dropdown */}
                                <div className="absolute right-0 top-full mt-2 w-48 bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 transform origin-top-right z-50">
                                    <div className="p-3 border-b border-gray-100 dark:border-slate-800">
                                        <p className="text-sm font-bold text-gray-900 dark:text-white truncate">{user.name}</p>
                                    </div>
                                    <div className="p-1">
                                        <Link href="/profile" className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-slate-800 rounded-lg">
                                            <span className="material-symbols-outlined text-[18px]">person</span>
                                            Profile
                                        </Link>
                                        <Link href="/solve" className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-slate-800 rounded-lg">
                                            <span className="material-symbols-outlined text-[18px]">calculate</span>
                                            Solver
                                        </Link>
                                        <button onClick={handleLogout} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/10 rounded-lg">
                                            <span className="material-symbols-outlined text-[18px]">logout</span>
                                            Sign Out
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <>
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
                        </>
                    )}

                    <button className="md:hidden p-2 text-[#111318] dark:text-white hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                        <span className="material-symbols-outlined">menu</span>
                    </button>
                </div>
            </div>
        </header>
    );
}
