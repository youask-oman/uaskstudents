"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";

export default function DashboardNavBar() {
    const [isDark, setIsDark] = useState(false);
    const [isProfileOpen, setIsProfileOpen] = useState(false);

    // User State
    const [userName, setUserName] = useState("Guest");
    const [userEmail, setUserEmail] = useState("");
    const [userRole, setUserRole] = useState("student");
    const [userTier, setUserTier] = useState("free");
    const [userAvatar, setUserAvatar] = useState("");

    const router = useRouter();
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Load user info
        if (typeof window !== 'undefined') {
            setUserName(localStorage.getItem('user_name') || "Guest");
            // In a real app we'd store these better, but for MVP grabbing from 'user' object string in localstorage if exists
            const userStr = localStorage.getItem('user');
            if (userStr) {
                try {
                    const user = JSON.parse(userStr);
                    setUserEmail(user.email || "");
                    setUserRole(user.role || "student");
                    setUserTier(user.subscription_tier || "free");
                    setUserAvatar(user.avatar_url || localStorage.getItem('user_avatar') || "");
                } catch (e) {
                    console.error("Error parsing user data");
                }
            }
        }

        // Check initial theme preference
        if (document.documentElement.classList.contains("dark")) {
            setIsDark(true);
        }

        // Click outside to close dropdown
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsProfileOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, []);

    const handleSignOut = () => {
        localStorage.clear();
        router.push("/login");
    };

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
        <header className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-background-dark/50 backdrop-blur-md sticky top-0 z-50 transition-colors duration-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-16">
                    <Link href="/dashboard" className="flex items-center gap-3">
                        <img src={isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" className="h-8 w-auto" />
                        <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">uask.ai</span>
                    </Link>
                    <nav className="hidden md:flex space-x-8">
                        <Link className="text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-white transition-colors text-sm font-medium" href="/dashboard">Dashboard</Link>
                        <Link className="text-primary dark:text-white border-b-2 border-primary pb-1 text-sm font-medium" href="/dashboard">New Solve</Link>
                        <Link className="text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-white transition-colors text-sm font-medium" href="#">History</Link>
                        <Link className="text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-white transition-colors text-sm font-medium" href="#">Resources</Link>
                    </nav>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={toggleTheme}
                            className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors flex items-center"
                            aria-label="Toggle Dark Mode"
                        >
                            <span className="material-symbols-outlined">{isDark ? 'light_mode' : 'dark_mode'}</span>
                        </button>
                        <button className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors flex items-center">
                            <span className="material-symbols-outlined">notifications</span>
                        </button>
                        <div className="h-8 w-px bg-slate-200 dark:border-slate-800"></div>
                        <div
                            className="relative flex items-center gap-3 cursor-pointer group"
                            ref={dropdownRef}
                            onClick={() => setIsProfileOpen(!isProfileOpen)}
                        >
                            <button className="flex items-center gap-3 focus:outline-none">
                                <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center overflow-hidden">
                                    <img
                                        className="w-full h-full object-cover"
                                        src={userAvatar || "https://lh3.googleusercontent.com/aida-public/AB6AXuAXYVbFfVBihqvOGXdUgQeFj3bBK56JWwJVwY0vHS3d_muo1q74kW5qIOfQePEV1c7AAUsvFWeNgynfnwD8zU0AfkFQW7u66ROKZaze1j4dD4kQFDi-LopffszdUQ5N5-xc7Kf108CGZLvA9vs49eetg9ucr2APBoHzjuDMJkoMTDTiZFsh0L7QHFzqYvIKN5JXNufZOslKMrUig-s00M1n_Q27MaX2Mcn4Z5xHgAo5Dk8a46yKVidS1eYrHxji1z05Is4fUzxBIATw"}
                                        alt="User Avatar"
                                    />
                                </div>
                                <span className="text-sm font-semibold hidden sm:block text-slate-900 dark:text-white">
                                    {userName}
                                </span>
                            </button>

                            {/* Profile Dropdown */}
                            {isProfileOpen && (
                                <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 py-2 ring-1 ring-black ring-opacity-5 focus:outline-none transform opacity-100 scale-100 transition-all z-50">
                                    <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
                                        <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{userName}</p>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{userEmail}</p>
                                        <div className="mt-2 text-xs inline-flex items-center px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium capitalize">
                                            {userRole} • {userTier}
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
                                                Subscription
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
        </header >
    );
}
