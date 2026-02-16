"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import { fetchApi, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import { fetchWalletSummary, WalletSummary } from "@/lib/wallet";

type TopUpProduct = {
    pack_code: string;
    display_name: string;
    credits: number;
};

export default function BillingSuccessPage() {
    const { pushToast } = useToast();
    const [wallet, setWallet] = useState<WalletSummary | null>(null);
    const [purchasedCredits, setPurchasedCredits] = useState<number | null>(() => {
        if (typeof window === "undefined") return null;
        const storedCredits = localStorage.getItem("topup_last_product_credits");
        return storedCredits ? Number(storedCredits) : null;
    });
    const productCode = useMemo(() => {
        if (typeof window === "undefined") return null;
        const params = new URLSearchParams(window.location.search);
        return params.get("pack") || params.get("product");
    }, []);
    const lastBalance = useMemo(() => {
        if (typeof window === "undefined") return null;
        const storedBalance = localStorage.getItem("topup_last_balance");
        return storedBalance ? Number(storedBalance) : null;
    }, []);

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

    useEffect(() => {
        const confirmStripeSession = async () => {
            if (typeof window === "undefined") return;
            const params = new URLSearchParams(window.location.search);
            const sessionId = params.get("session_id");
            if (!sessionId) return;
            const token = localStorage.getItem("token");
            if (!token) return;

            try {
                const res = await fetchApi(`/api/v1/topups/stripe/confirm-session`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${token}`,
                    },
                    body: JSON.stringify({ session_id: sessionId }),
                });
                if (!res.ok) {
                    const err = await parseApiError(res);
                    pushToast({
                        type: "error",
                        title: "Top-up verification failed",
                        message: err.message,
                        requestId: err.requestId,
                    });
                    return;
                }
                const result = await res.json();
                if (result.status === "pending") {
                    pushToast({
                        type: "info",
                        title: "Payment still processing",
                        message: "Stripe has not confirmed the payment yet. Please refresh in a moment.",
                    });
                } else if (result.status === "fulfilled") {
                    pushToast({
                        type: "success",
                        title: "Top-up completed",
                        message: "Credits have been added to your wallet.",
                    });
                    try {
                        const summary = await fetchWalletSummary();
                        setWallet(summary);
                    } catch {
                        // ignore refresh errors
                    }
                }
            } catch (error) {
                pushToast({
                    type: "error",
                    title: "Top-up verification failed",
                    message: error instanceof Error ? error.message : "Unexpected error",
                });
            }
        };

        void confirmStripeSession();
    }, [pushToast]);

    useEffect(() => {
        const loadProductCredits = async () => {
            if (!productCode || purchasedCredits != null) return;
            try {
                const res = await fetchApi(`/api/v1/credits/packs`);
                if (!res.ok) return;
                const payload = await res.json();
                const products = (payload?.items || []) as TopUpProduct[];
                const match = products.find((item) => item.pack_code === productCode);
                if (match) setPurchasedCredits(match.credits);
            } catch {
                return;
            }
        };
        void loadProductCredits();
    }, [productCode, purchasedCredits]);

    const effectiveOldBalance = useMemo(() => {
        if (lastBalance != null) return lastBalance;
        if (wallet && purchasedCredits != null) return wallet.spendable_balance - purchasedCredits;
        if (wallet) return wallet.spendable_balance;
        return null;
    }, [lastBalance, purchasedCredits, wallet]);

    const expectedNewBalance = useMemo(() => {
        if (effectiveOldBalance == null || purchasedCredits == null) return null;
        return effectiveOldBalance + purchasedCredits;
    }, [effectiveOldBalance, purchasedCredits]);

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
            <Suspense fallback={<div className="h-16 w-full" />}>
                <DashboardNavBar />
            </Suspense>
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
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                            <div className="text-xs uppercase tracking-widest text-slate-400">Old Balance</div>
                            <div className="font-semibold text-slate-900 dark:text-white">
                                {effectiveOldBalance != null ? `${effectiveOldBalance.toFixed(2)} credits` : "--"}
                            </div>
                        </div>
                        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                            <div className="text-xs uppercase tracking-widest text-slate-400">Purchased</div>
                            <div className="font-semibold text-slate-900 dark:text-white">
                                {purchasedCredits != null ? `+${purchasedCredits.toFixed(2)} credits` : "--"}
                            </div>
                            {productCode && (
                                <div className="text-[10px] uppercase tracking-widest text-slate-400 mt-1">
                                    {productCode}
                                </div>
                            )}
                        </div>
                        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                            <div className="text-xs uppercase tracking-widest text-slate-400">Expected New Balance</div>
                            <div className="font-semibold text-slate-900 dark:text-white">
                                {expectedNewBalance != null ? `${expectedNewBalance.toFixed(2)} credits` : "--"}
                            </div>
                        </div>
                    </div>
                    {wallet ? (
                        <div className="inline-flex items-center gap-2 bg-slate-50 dark:bg-slate-800 px-4 py-2 rounded-full text-sm text-slate-600 dark:text-slate-300">
                            Current balance: <span className="font-semibold text-slate-900 dark:text-white">{wallet.spendable_balance.toFixed(2)} credits</span>
                        </div>
                    ) : (
                        expectedNewBalance != null && (
                            <div className="inline-flex items-center gap-2 bg-slate-50 dark:bg-slate-800 px-4 py-2 rounded-full text-sm text-slate-600 dark:text-slate-300">
                                Current balance: <span className="font-semibold text-slate-900 dark:text-white">{expectedNewBalance.toFixed(2)} credits</span>
                            </div>
                        )
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
