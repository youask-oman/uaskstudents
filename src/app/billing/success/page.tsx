"use client";

import { useEffect, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import { fetchWalletSummary, WalletSummary } from "@/lib/wallet";

export default function BillingSuccessPage() {
    const [wallet, setWallet] = useState<WalletSummary | null>(null);

    useEffect(() => {
        const loadWallet = async () => {
            try {
                const summary = await fetchWalletSummary();
                setWallet(summary);
            } catch {
                setWallet(null);
            }
        };
        void loadWallet();
    }, []);

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
            <DashboardNavBar />
            <main className="max-w-3xl mx-auto px-4 py-16">
                <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-10 text-center">
                    <div className="flex justify-center mb-6">
                        <div className="size-14 rounded-full bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
                            <span className="material-symbols-outlined text-3xl">check_circle</span>
                        </div>
                    </div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-3">Top-up initiated</h1>
                    <p className="text-slate-500 dark:text-slate-400 mb-6">
                        Your payment is being processed. Credits will appear once the checkout completes.
                    </p>
                    {wallet && (
                        <div className="inline-flex items-center gap-2 bg-slate-50 dark:bg-slate-800 px-4 py-2 rounded-full text-sm text-slate-600 dark:text-slate-300">
                            Current balance: <span className="font-semibold text-slate-900 dark:text-white">{wallet.computed_balance.toFixed(2)} credits</span>
                        </div>
                    )}
                    <div className="mt-8 flex justify-center gap-4">
                        <a
                            href="/billing"
                            className="px-5 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200"
                        >
                            Back to Wallet
                        </a>
                        <a
                            href="/solve"
                            className="px-5 py-2 rounded-lg bg-primary text-white text-sm font-semibold"
                        >
                            Start Solving
                        </a>
                    </div>
                </div>
            </main>
        </div>
    );
}
