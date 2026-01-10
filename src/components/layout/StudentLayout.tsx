"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

interface StudentLayoutProps {
    children: React.ReactNode;
}

export default function StudentLayout({ children }: StudentLayoutProps) {
    const pathname = usePathname();
    const router = useRouter();
    const [isDark, setIsDark] = useState(false);

    // User State
    const [user, setUser] = useState<any>(null);
    const [energy, setEnergy] = useState(128); // Mock for now

    useEffect(() => {
        const storedUser = localStorage.getItem("user");
        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser));
            } catch (e) {
                console.error("Error parsing user data");
            }
        } else {
            // Failsafe for dev
            setUser({
                full_name: localStorage.getItem("user_name") || "Alex Johnson",
                subscription_tier: "Pro",
                avatar_url: "https://lh3.googleusercontent.com/aida-public/AB6AXuD_gpHP7vJM1mkTxszlDYSYslefzDpqT7kS3EUblVETFcyH2Sl2xHETdTN_AcqdawcLn0mOa7LR69Ol1T3hAFSvpJss7LzshfwXBbhjMZqOGSH9S1nVdhEO1aeexaHXJAn_VqN1tFoPVazJP1aq1rARcjsg7F4-pStNL1jl7KEpohReYVX52pfbq3YO6IKCX71lAo42c76k2H4WrKWI5r79xsjqMPNL1zZPzcajFKkIs40bZTGM732P1j_aCdcr67zOQ2bNSaRrATQz"
            });
        }

        if (document.documentElement.classList.contains("dark")) {
            setIsDark(true);
        }
    }, []);

    const navItems = [
        { label: "Dashboard", icon: "grid_view", href: "/dashboard", id: "dashboard" },
        { label: "New Solve", icon: "add_circle", href: "/solve", id: "new-solve", highlight: true },
        { label: "Plan & Billing", icon: "credit_card", href: "/billing", id: "billing" },
    ];

    const learningItems = [
        { label: "History", icon: "history", href: "#", id: "history" },
        { label: "Saved Items", icon: "bookmark", href: "#", id: "saved" },
        { label: "Concepts", icon: "menu_book", href: "#", id: "concepts" },
    ];

    return (
        <div className="flex h-screen overflow-hidden bg-background-light dark:bg-background-dark font-display text-slate-900 dark:text-slate-100 antialiased">
            {/* Sidebar Navigation */}
            <aside className="w-64 flex flex-col bg-[#111827] h-full border-r border-slate-800/50 flex-shrink-0">
                {/* Top Section: Logo */}
                <div className="p-6 flex items-center gap-3">
                    <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                        <span className="material-symbols-outlined text-white text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>functions</span>
                    </div>
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
                                    ? "text-white bg-white/5 nav-item-active"
                                    : item.highlight
                                        ? "text-white bg-primary shadow-[0_0_15px_rgba(13,89,242,0.35)] hover:bg-primary/90 mt-2"
                                        : "text-slate-400 hover:text-white hover:bg-white/5"
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
                            className="flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-all duration-200 group"
                        >
                            <span className="material-symbols-outlined group-hover:text-primary transition-colors">{item.icon}</span>
                            <span className="text-sm font-medium">{item.label}</span>
                        </Link>
                    ))}
                </nav>

                {/* Bottom Section: Tools & Profile */}
                <div className="px-3 pb-6 border-t border-slate-800">
                    <div className="space-y-1 mb-4 pt-4">
                        <Link href="#" className="flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-all duration-200 group">
                            <span className="material-symbols-outlined text-[20px]">help</span>
                            <span className="text-sm font-medium">Help Center</span>
                        </Link>
                        <Link href="/profile" className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${pathname === '/profile' ? 'text-white bg-white/5' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}>
                            <span className="material-symbols-outlined text-[20px] group-hover:text-primary transition-colors">settings</span>
                            <span className="text-sm font-medium">Settings</span>
                        </Link>
                    </div>

                    {/* User Profile Snippet */}
                    <div className="bg-slate-900/50 rounded-xl p-3 flex items-center gap-3 border border-slate-800/50">
                        <div className="relative">
                            <div
                                className="w-10 h-10 rounded-full bg-cover bg-center border-2 border-primary/30"
                                style={{ backgroundImage: `url('${user?.avatar_url || 'https://lh3.googleusercontent.com/aida-public/AB6AXuD_gpHP7vJM1mkTxszlDYSYslefzDpqT7kS3EUblVETFcyH2Sl2xHETdTN_AcqdawcLn0mOa7LR69Ol1T3hAFSvpJss7LzshfwXBbhjMZqOGSH9S1nVdhEO1aeexaHXJAn_VqN1tFoPVazJP1aq1rARcjsg7F4-pStNL1jl7KEpohReYVX52pfbq3YO6IKCX71lAo42c76k2H4WrKWI5r79xsjqMPNL1zZPzcajFKkIs40bZTGM732P1j_aCdcr67zOQ2bNSaRrATQz'}')` }}
                            />
                            <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-[#111827] rounded-full"></div>
                        </div>
                        <div className="flex flex-col min-w-0">
                            <span className="text-sm font-semibold text-white truncate">{user?.full_name || "Alex Johnson"}</span>
                            <div className="flex items-center gap-1.5">
                                <span className="bg-primary/20 text-primary text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Pro</span>
                                <span className="text-slate-500 text-[11px] truncate">Active</span>
                            </div>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 bg-background-light dark:bg-background-dark overflow-y-auto flex flex-col">
                <header className="h-16 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-8 bg-white/50 dark:bg-background-dark/50 backdrop-blur-md sticky top-0 z-10">
                    <h2 className="text-xl font-bold">
                        {pathname === '/dashboard' ? 'Student Dashboard' : pathname === '/solve' ? 'New Solve' : pathname === '/profile' ? 'Settings' : 'Dashboard'}
                    </h2>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-full border border-slate-200 dark:border-slate-700">
                            <span className="material-symbols-outlined text-sm text-amber-500" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span>
                            <span className="text-xs font-bold">{energy} Energy</span>
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
