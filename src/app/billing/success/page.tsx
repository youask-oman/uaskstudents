"use client";

import React, { Suspense, useState } from 'react';
import Image from "next/image";
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

function SuccessContent() {
    const searchParams = useSearchParams();
    const transactionId = searchParams.get('tx') || 'Unknown';

    return (
        <div className="flex-1 flex flex-col items-center justify-center px-4 py-12 relative overflow-hidden">
            {/* Background Decorative Glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full blur-3xl -z-10 bg-[#135bec]/10"></div>

            <div className="flex flex-col max-w-[640px] w-full text-center">
                {/* Celebratory Icon */}
                <div className="flex justify-center mb-6 animate-bounce">
                    <div className="relative">
                        <div className="absolute inset-0 bg-yellow-500/20 blur-2xl rounded-full scale-150"></div>
                        <span className="material-symbols-outlined text-8xl text-yellow-400 drop-shadow-[0_0_15px_rgba(255,215,0,0.4)]">
                            stars
                        </span>
                        <div className="absolute -top-2 -right-2 w-6 h-6 bg-[#135bec] rounded-full border-4 border-[#101622] flex items-center justify-center">
                            <span className="material-symbols-outlined text-[12px] text-white font-bold">check</span>
                        </div>
                    </div>
                </div>

                {/* Headline */}
                <h1 className="text-white font-sans text-[36px] md:text-[48px] font-bold leading-tight pb-3">
                    Welcome to Pro!
                </h1>

                {/* Body Text */}
                <p className="text-[#9da6b9] text-lg font-normal leading-relaxed max-w-lg mx-auto mb-10">
                    Your subscription is now active. You have unlocked unlimited OCR scans, Socratic tutoring, and advanced physics models.
                </p>

                {/* Subscription Summary Card */}
                <div className="w-full mb-10">
                    <div className="flex flex-col md:flex-row items-stretch justify-start rounded-xl border border-white/5 shadow-2xl bg-[#1c1f27]/80 backdrop-blur-sm overflow-hidden text-left">
                        <div className="w-full md:w-32 bg-gradient-to-br from-[#135bec] to-[#0a2e7a] flex items-center justify-center py-6">
                            <span className="material-symbols-outlined text-white text-4xl">workspace_premium</span>
                        </div>
                        <div className="flex w-full grow flex-col justify-center gap-1 p-6">
                            <div className="flex justify-between items-start mb-2">
                                <div>
                                    <p className="text-[#9da6b9] text-xs font-medium uppercase tracking-widest">Transaction ID</p>
                                    <p className="text-white/80 text-sm font-mono">#{transactionId}</p>
                                </div>
                            </div>
                            <p className="text-white text-lg font-bold leading-tight tracking-[-0.015em] mb-3">Subscription Summary</p>
                            <div className="flex flex-col gap-2">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[#135bec] text-sm">check_circle</span>
                                    <p className="text-[#9da6b9] text-sm font-normal">Plan: <span className="text-white font-medium">Pro (Monthly)</span></p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[#135bec] text-sm">calendar_today</span>
                                    <p className="text-[#9da6b9] text-sm font-normal">Next Billing Date: <span className="text-white font-medium">{new Date(new Date().setDate(new Date().getDate() + 30)).toLocaleDateString()}</span></p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-col sm:flex-row gap-4 justify-center w-full px-4">
                    <Link href="/solve" className="flex-1 max-w-[240px] h-14 cursor-pointer flex items-center justify-center rounded-xl bg-[#135bec] hover:bg-[#135bec]/90 text-white gap-2 text-base font-bold leading-normal tracking-[0.015em] transition-all shadow-lg shadow-[#135bec]/20">
                        <span className="material-symbols-outlined">rocket_launch</span>
                        <span>Start Solving</span>
                    </Link>
                    <Link href="/billing" className="flex-1 max-w-[240px] h-14 cursor-pointer flex items-center justify-center rounded-xl bg-[#282e39] hover:bg-[#343b47] text-white gap-2 text-base font-bold leading-normal tracking-[0.015em] transition-all">
                        <span className="material-symbols-outlined">auto_awesome</span>
                        <span>View Billing</span>
                    </Link>
                </div>

                {/* Footer Notification */}
                <div className="mt-12 flex items-center justify-center gap-2 text-[#9da6b9]/60 text-sm">
                    <span className="material-symbols-outlined text-sm">mail</span>
                    <p>Invoice sent to your email address.</p>
                </div>
            </div>
        </div>
    );
}

export default function SuccessPage() {
    const [isDark] = useState(() => (typeof document !== "undefined" ? document.documentElement.classList.contains("dark") : false));

    return (
        <div className="min-h-screen bg-[#f6f6f8] dark:bg-[#101622] text-white font-sans flex flex-col">
            <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-[#282e39] px-6 md:px-10 py-3 bg-[#f6f6f8] dark:bg-[#101622] z-50">
                <div className="flex items-center gap-4 text-white">
                    <Image src={isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" width={96} height={24} className="h-6 w-auto" priority />
                    <h2 className="text-[#101622] dark:text-white text-xl font-bold leading-tight tracking-[-0.015em] font-sans">uask.ai</h2>
                </div>
            </header>

            <Suspense fallback={<div>Loading...</div>}>
                <SuccessContent />
            </Suspense>

            <footer className="p-6 text-center text-[#282e39] text-xs border-t border-white/5">
                © 2024 uask.ai - The Future of Math & Physics Learning. All rights reserved.
            </footer>
        </div>
    );
}
