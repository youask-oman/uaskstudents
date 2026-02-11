"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { fetchWalletSummary, WalletSummary } from "@/lib/wallet";
import { useTheme } from "@/hooks/useTheme";

type StoredUser = {
    email?: string;
    role?: string;
    avatar_url?: string;
    full_name?: string;
};

const getStoredUser = (): StoredUser | null => {
    if (typeof window === "undefined") return null;
    const userStr = localStorage.getItem("user");
    if (!userStr) return null;
    try {
        return JSON.parse(userStr);
    } catch (error) {
        console.error("Error parsing user data", error);
        return null;
    }
};

export default function DashboardNavBar() {
    const { isDark, toggleTheme } = useTheme();
    const [mounted, setMounted] = useState(false);
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const [userName, setUserName] = useState("Guest");
    const [userEmail, setUserEmail] = useState("");
    const [userRole, setUserRole] = useState("student");
    const [userAvatar, setUserAvatar] = useState("");
    const [userTier, setUserTier] = useState("free");
    const [walletSummary, setWalletSummary] = useState<WalletSummary | null>(null);

    const router = useRouter();
    const pathname = usePathname();
    const [currentTab, setCurrentTab] = useState<string | null>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setMounted(true);
        const syncTabFromUrl = () => {
            if (typeof window === "undefined") return;
            const params = new URLSearchParams(window.location.search);
            setCurrentTab(params.get("tab"));
        };
        const refreshUserInfo = () => {
            if (typeof window === "undefined") return;
            const storedUser = getStoredUser();
            setUserName(storedUser?.full_name || localStorage.getItem("user_name") || "Guest");
            setUserEmail(storedUser?.email || "");
            setUserRole(storedUser?.role || "student");
            setUserTier("free");
            setUserAvatar(storedUser?.avatar_url || localStorage.getItem("user_avatar") || "");
        };

        const refreshWallet = async () => {
            if (typeof window === "undefined") return;
            try {
                const summary = await fetchWalletSummary();
                setWalletSummary(summary);
                setUserTier(summary.effective_tier || "FREE");
            } catch (error) {
                console.warn("Failed to load wallet for navbar:", error);
            }
        };

        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsProfileOpen(false);
            }
        };

        const handleStorage = (event: StorageEvent) => {
            if (!event.key) return;
            if (event.key === "theme") return;
            if (event.key.startsWith("user") || event.key === "token" || event.key === "user_id") {
                refreshUserInfo();
                void refreshWallet();
            }
        };

        refreshUserInfo();
        syncTabFromUrl();
        void refreshWallet();
        document.addEventListener("mousedown", handleClickOutside);
        window.addEventListener("storage", handleStorage);
        window.addEventListener("focus", refreshWallet);
        window.addEventListener("popstate", syncTabFromUrl);
        const refreshInterval = window.setInterval(() => {
            void refreshWallet();
        }, 20000);

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            window.removeEventListener("storage", handleStorage);
            window.removeEventListener("focus", refreshWallet);
            window.removeEventListener("popstate", syncTabFromUrl);
            window.clearInterval(refreshInterval);
        };
    }, []);

    useEffect(() => {
        if (typeof window === "undefined") return;
        const params = new URLSearchParams(window.location.search);
        setCurrentTab(params.get("tab"));
    }, [pathname]);

    const handleSignOut = () => {
        localStorage.clear();
        router.push("/login");
    };

    return (
        <header className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-background-dark/50 backdrop-blur-md sticky top-0 z-50 transition-colors duration-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-16">
                    <Link href="/dashboard" className="flex items-center gap-3">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={mounted && isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" className="h-8 w-auto" />
                        <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">uask.ai</span>
                    </Link>
                    <nav className="hidden md:flex space-x-8">
                        <Link
                            className={`${pathname === "/dashboard" && !currentTab ? "text-primary dark:text-white border-b-2 border-primary pb-1" : "text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-white"} transition-colors text-sm font-medium`}
                            href="/dashboard"
                        >
                            Dashboard
                        </Link>
                        <Link
                            className={`${pathname === "/solve"  ? "text-primary dark:text-white border-b-2 border-primary pb-1" : "text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-white"} transition-colors text-sm font-medium`}
                            href="/solve"
                            onClick={(e) => {
                                if (pathname === "/solve") {
                                    e.preventDefault();
                                    window.location.href = "/solve";
                                }
                            }}
                        >
                            New Solve
                        </Link>
                        <Link
                            className={`${pathname === "/dashboard" && currentTab === "history" ? "text-primary dark:text-white border-b-2 border-primary pb-1" : "text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-white"} transition-colors text-sm font-medium`}
                            href="/dashboard?tab=history"
                        >
                            History
                        </Link>
                    </nav>
                    {walletSummary && (
                        <div className="hidden lg:flex items-center gap-3">
                            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold">
                                <span className="material-symbols-outlined text-[16px]">payments</span>
                                {walletSummary.computed_balance.toFixed(2)} credits
                            </div>
                            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold">
                                <span className="material-symbols-outlined text-[16px]">hourglass_empty</span>
                                {walletSummary.pending_hold_credits.toFixed(2)} on hold
                            </div>
                        </div>
                    )}
                    <div className="flex items-center gap-4">
                        <button
                            onClick={toggleTheme}
                            className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors flex items-center"
                            aria-label="Toggle Dark Mode"
                        >
                            <span className="material-symbols-outlined">{mounted && isDark ? 'light_mode' : 'dark_mode'}</span>
                        </button>
                        <button className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors flex items-center">
                            <span className="material-symbols-outlined">notifications</span>
                        </button>
                        <div
                            className="relative flex items-center gap-3 cursor-pointer group"
                            ref={dropdownRef}
                            onClick={() => setIsProfileOpen(!isProfileOpen)}
                        >
                            <button className="flex items-center gap-3 focus:outline-none">
                                <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center overflow-hidden">
                                    {userAvatar ? (
                                        <>
                                            {/* eslint-disable-next-line @next/next/no-img-element */}
                                            <img
                                                className="w-full h-full object-cover"
                                                src={userAvatar}
                                                alt="User Avatar"
                                            />
                                        </>
                                    ) : (
                                        <span className="text-sm font-bold text-primary">{userName.charAt(0)}</span>
                                    )}
                                </div>
                                <span className="text-sm font-semibold hidden sm:block text-slate-900 dark:text-white">
                                    {userName}
                                </span>
                            </button>

                            {isProfileOpen && (
                                <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 py-2 ring-1 ring-black ring-opacity-5 focus:outline-none transform opacity-100 scale-100 transition-all z-50">
                                    <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
                                        <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{userName}</p>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{userEmail}</p>
                                        <div className="mt-2 text-xs inline-flex items-center px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium capitalize">
                                            {userRole} - {userTier}
                                        </div>
                                    </div>

                                    <div className="py-1">
                                        <Link href="/profile" className="block px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                                            <div className="flex items-center gap-2">
                                                <span className="material-symbols-outlined text-[18px]">person</span>
                                                Your Profile
                                            </div>
                                        </Link>
                                        <Link href="/settings" className="block px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                                            <div className="flex items-center gap-2">
                                                <span className="material-symbols-outlined text-[18px]">settings</span>
                                                Settings
                                            </div>
                                        </Link>
                                        <Link href="/billing" className="block px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                                            <div className="flex items-center gap-2">
                                                <span className="material-symbols-outlined text-[18px]">credit_card</span>
                                                Wallet & Programs
                                            </div>
                                        </Link>
                                    </div>

                                    <div className="border-t border-slate-100 dark:border-slate-800 py-1">
                                        <button
                                            onClick={handleSignOut}
                                            className="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors flex items-center gap-2"
                                        >
                                            <span className="material-symbols-outlined text-[18px]">logout</span>
                                            Sign out
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
}
