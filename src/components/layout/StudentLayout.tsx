"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import logoLight from "@/app/logo/logo-01.png";
import logoDark from "@/app/logo/logo-13.png";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";
import { fetchWalletSummary, WalletSummary } from "@/lib/wallet";

interface StudentLayoutProps {
    children: React.ReactNode;
}

type StudentUser = {
    full_name: string;
    avatar_url?: string | null;
};

const DEFAULT_STUDENT_USER: StudentUser = {
    full_name: "Student",
    avatar_url: ""
};

const getInitialUser = (): StudentUser => {
    if (typeof window === "undefined") {
        return DEFAULT_STUDENT_USER;
    }
    const storedUser = localStorage.getItem("user");
    if (!storedUser) {
        return {
            ...DEFAULT_STUDENT_USER,
            full_name: localStorage.getItem("user_name") || DEFAULT_STUDENT_USER.full_name,
        };
    }
    try {
        const parsed = JSON.parse(storedUser);
        return {
            full_name: parsed.full_name || localStorage.getItem("user_name") || DEFAULT_STUDENT_USER.full_name,
            avatar_url: parsed.avatar_url || localStorage.getItem("user_avatar") || DEFAULT_STUDENT_USER.avatar_url,
        };
    } catch {
        return DEFAULT_STUDENT_USER;
    }
};

export default function StudentLayout({ children }: StudentLayoutProps) {
    const pathname = usePathname();
    const router = useRouter();
    // Initialize with default to match server
    const [user, setUser] = useState<StudentUser>(DEFAULT_STUDENT_USER);
    const [walletSummary, setWalletSummary] = useState<WalletSummary | null>(null);
    useEffect(() => {
        // Hydrate from local storage on mount
        const storedUser = getInitialUser();
        // eslint-disable-next-line
        setUser(storedUser);
    }, []);
    useEffect(() => {
        let active = true;
        const loadWallet = async () => {
            try {
                const summary = await fetchWalletSummary();
                if (active) setWalletSummary(summary);
            } catch {
                if (active) setWalletSummary(null);
            }
        };
        void loadWallet();
        return () => {
            active = false;
        };
    }, []);

    // Logout Refs & Timer
    const logoutTimerRef = useRef<NodeJS.Timeout | null>(null);

    const handleLogout = useCallback(() => {
        localStorage.removeItem("user");
        localStorage.removeItem("user_id");
        localStorage.removeItem("token");
        localStorage.removeItem("session_token");
        router.push("/login");
    }, [router]);

    const resetIdleTimer = useCallback(() => {
        if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
        logoutTimerRef.current = setTimeout(() => {
            handleLogout();
        }, 10 * 60 * 1000); // 10 minutes
    }, [handleLogout]);

    useEffect(() => {
        // Heartbeat (Every 2 mins)
        const heartbeatInterval = setInterval(async () => {
            const userId = localStorage.getItem("user_id");
            const sessionToken = localStorage.getItem("session_token");

            if (userId) {
                try {
                    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
                    let url = `${apiBaseUrl}/api/v1/user/heartbeat?user_id=${userId}`;
                    if (sessionToken) {
                        url += `&session_token=${sessionToken}`;
                    }

                    const res = await fetch(url, { method: 'POST' });
                    if (res.status === 401) {
                        // Session Invalid/Expired -> Force Logout
                        handleLogout();
                    }
                } catch {
                    // console.error("Heartbeat failed", e); // Silently fail
                }
            }
        }, 2 * 60 * 1000);

        // 3. Idle Timer
        const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
        const activityHandler = () => resetIdleTimer();
        events.forEach(event => window.addEventListener(event, activityHandler));
        resetIdleTimer();

        return () => {
            clearInterval(heartbeatInterval);
            if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
            events.forEach(event => window.removeEventListener(event, activityHandler));
        };
    }, [handleLogout, resetIdleTimer]);

    const navItems = [
        { label: "Dashboard", icon: "grid_view", href: "/dashboard", id: "dashboard" },
        { label: "New Solve", icon: "add_circle", href: "/solve", id: "new-solve", highlight: true },
        { label: "Wallet & Programs", icon: "credit_card", href: "/billing", id: "billing" },
    ];

    const learningItems = [
        { label: "History", icon: "history", href: "/dashboard?tab=history", id: "history" },
        { label: "Bookmarked", icon: "bookmark", href: "/dashboard?tab=bookmarked", id: "bookmarked" },
    ];

    return (
        <div className="flex h-screen w-full overflow-hidden bg-background-light dark:bg-background-dark font-display text-slate-900 dark:text-slate-100 antialiased fixed inset-0">
            {/* Sidebar Navigation */}
            <aside className="w-64 flex flex-col bg-white dark:bg-[#111827] h-full border-r border-slate-200 dark:border-slate-800/50 flex-shrink-0 transition-colors duration-200">
                <div className="p-6 flex items-center gap-3">
                    <Image src={logoLight} alt="uask.ai" className="h-8 w-auto dark:hidden" />
                    <Image src={logoDark} alt="uask.ai" className="h-8 w-auto hidden dark:block" />
                    <div className="flex flex-col">
                        <span className="text-white font-bold text-xl tracking-tight leading-none">uask<span className="text-primary">.ai</span></span>
                        <span className="text-slate-500 text-[10px] uppercase tracking-widest font-semibold">Student Portal</span>
                    </div>
                </div>

                {/* Middle Section: Main Navigation */}
                <nav className="flex-1 px-3 space-y-1 mt-4">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.id}
                                href={item.href}
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group relative ${isActive && !item.highlight
                                    ? "text-primary bg-primary/10 dark:text-white dark:bg-white/5 nav-item-active"
                                    : item.highlight
                                        ? "text-white bg-primary shadow-[0_0_15px_rgba(13,89,242,0.35)] hover:bg-primary/90 mt-2"
                                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5"
                                    }`}
                            >
                                {isActive && !item.highlight && (
                                    <div className="absolute left-0 top-1/4 h-1/2 w-1 bg-primary rounded-r-full" />
                                )}
                                <span className={`material-symbols-outlined ${isActive || item.highlight ? "text-primary" : "group-hover:text-primary transition-colors"} ${item.highlight ? "text-white" : ""}`} style={{ fontVariationSettings: isActive || item.highlight ? "'FILL' 1" : "" }}>
                                    {item.icon}
                                </span>
                                <span className={`text-sm ${item.highlight ? "font-semibold" : "font-medium"}`}>{item.label}</span>
                            </Link>
                        );
                    })}

                    <div className="pt-4 pb-2 px-4">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Learning</span>
                    </div>

                    {learningItems.map((item) => (
                        <Link
                            key={item.id}
                            href={item.href}
                            className="flex items-center gap-3 px-4 py-3 text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-primary hover:bg-slate-100 dark:hover:bg-white/5 rounded-lg transition-all duration-200 group"
                        >
                            <span className="material-symbols-outlined group-hover:text-primary transition-colors">{item.icon}</span>
                            <span className="text-sm font-medium">{item.label}</span>
                        </Link>
                    ))}
                </nav>

                {/* Bottom Section: Tools & Profile */}
                <div className="px-3 pb-6 border-t border-slate-800">
                    <div className="space-y-1 mb-4 pt-4">
                        <Link href="/profile" className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${pathname === '/profile' ? 'text-primary dark:text-white bg-primary/10 dark:bg-white/5' : 'text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-primary hover:bg-slate-100 dark:hover:bg-white/5'}`}>
                            <span className="material-symbols-outlined text-[20px] group-hover:text-primary transition-colors">settings</span>
                            <span className="text-sm font-medium">Settings</span>
                        </Link>
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all duration-200 group"
                        >
                            <span className="material-symbols-outlined text-[20px] group-hover:text-red-400 transition-colors">logout</span>
                            <span className="text-sm font-medium">Logout</span>
                        </button>
                    </div>

                    {/* User Profile Snippet */}
                    <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 flex items-center gap-3 border border-slate-200 dark:border-slate-800/50">
                        <div className="relative">
                            <div className="w-10 h-10 rounded-full border-2 border-primary/30 bg-slate-200 dark:bg-slate-800 flex items-center justify-center overflow-hidden">
                                {user?.avatar_url ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={user.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                                ) : (
                                    <span className="text-xs font-bold text-slate-700 dark:text-slate-200">
                                        {(user?.full_name || "S").charAt(0)}
                                    </span>
                                )}
                            </div>
                            <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-[#111827] rounded-full"></div>
                        </div>
                        <div className="flex flex-col min-w-0">
                            <span className="text-sm font-semibold text-white truncate">{user?.full_name || "Student"}</span>
                            <div className="flex items-center gap-1.5">
                                <span className="bg-primary/20 text-primary text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">
                                    {walletSummary?.effective_tier || "FREE"}
                                </span>
                                <span className="text-slate-500 text-[11px] truncate">
                                    {walletSummary ? `${walletSummary.computed_balance.toFixed(2)} credits` : "Wallet loading..."}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 bg-background-light dark:bg-background-dark overflow-y-auto flex flex-col">
                <header className="h-16 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-8 bg-white/50 dark:bg-background-dark/50 backdrop-blur-md sticky top-0 z-10">
                    <h2 className="text-xl font-bold">
                        {pathname === '/dashboard'
                            ? 'Student Dashboard'
                            : pathname === '/solve'
                                ? 'New Solve'
                                : pathname === '/profile'
                                    ? 'Settings'
                                    : pathname === '/billing'
                                        ? 'Wallet & Programs'
                                        : 'Dashboard'}
                    </h2>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center justify-center w-10 h-10">
                            <ThemeToggle className="static shadow-none border-none bg-transparent dark:bg-transparent w-full h-full hover:bg-slate-100 dark:hover:bg-slate-800" />
                        </div>
                        <button className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                            <span className="material-symbols-outlined text-slate-500">notifications</span>
                        </button>
                    </div>
                </header>

                <div className="flex-1">
                    {children}
                </div>
            </main>
        </div>
    );
}
