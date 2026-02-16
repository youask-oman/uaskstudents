"use client";

import { Suspense, useEffect, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import { fetchApi, parseApiError } from "@/lib/api";
import { fetchWalletSummary } from "@/lib/wallet";
import { useToast } from "@/components/ui/ToastProvider";

const PAGE_TITLE = "Top Up Credits";

type TopUpProduct = {
    code: string;
    name: string;
    credits: number;
    price_usd: number;
    stripe_price_id?: string | null;
};

export default function BillingPaymentPage() {
    const { pushToast } = useToast();
    const [products, setProducts] = useState<TopUpProduct[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeCode, setActiveCode] = useState<string | null>(null);

    useEffect(() => {
        const loadProducts = async () => {
            try {
                const res = await fetchApi(`/api/v1/topups/products`);
                if (!res.ok) {
                    const err = await parseApiError(res);
                    pushToast({
                        type: "error",
                        title: "Failed to load credit packs",
                        message: err.message,
                        requestId: err.requestId,
                    });
                    return;
                }
                const data = await res.json();
                const rows = Array.isArray(data) ? data : [];
                setProducts(rows);
            } catch (error) {
                pushToast({
                    type: "error",
                    title: "Failed to load credit packs",
                    message: error instanceof Error ? error.message : "Unexpected error",
                });
            } finally {
                setLoading(false);
            }
        };

        void loadProducts();
    }, [pushToast]);

    const handleCheckout = async (product: TopUpProduct) => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login?redirect=/billing/payment";
            return;
        }

        setActiveCode(product.code);
        try {
            try {
                const summary = await fetchWalletSummary();
                localStorage.setItem("topup_last_balance", String(summary.spendable_balance ?? ""));
            } catch {
                localStorage.removeItem("topup_last_balance");
            }
            localStorage.setItem("topup_last_product_code", product.code);
            localStorage.setItem("topup_last_product_credits", String(product.credits));
            localStorage.setItem("topup_last_started_at", new Date().toISOString());

            const res = await fetchApi(`/api/v1/stripe/create_checkout_session`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    pack_code: product.code,
                }),
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Checkout failed",
                    message: err.message,
                    requestId: err.requestId,
                });
                setActiveCode(null);
                return;
            }
            const data = await res.json();
            if (data?.checkout_url) {
                window.location.href = data.checkout_url;
                return;
            }
            pushToast({
                type: "error",
                title: "Checkout unavailable",
                message: "No checkout URL returned. Please contact support.",
            });
        } catch (error) {
            pushToast({
                type: "error",
                title: "Checkout failed",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        } finally {
            setActiveCode(null);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
            <Suspense fallback={<div className="h-16 w-full" />}>
                <DashboardNavBar />
            </Suspense>

            <main className="max-w-4xl mx-auto px-4 py-12 space-y-10">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">{PAGE_TITLE}</h1>
                    <p className="text-slate-500 dark:text-slate-400">
                        Purchase additional credits to continue solving without interruption.
                    </p>
                </div>

                {loading ? (
                    <div className="p-8 text-center text-slate-500">Loading credit packs...</div>
                ) : products.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">No credit packs available yet.</div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {products.map((product) => (
                            <div key={product.code} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 flex flex-col gap-4">
                                <div>
                                <h2 className="text-xl font-bold text-slate-900 dark:text-white">{product.name}</h2>
                                <p className="text-sm text-slate-500">{product.credits.toLocaleString()} credits</p>
                                <p className="text-xs text-slate-400 uppercase tracking-wide">${Number(product.price_usd || 0).toFixed(2)} one-time</p>
                                </div>
                                <button
                                    onClick={() => handleCheckout(product)}
                                    className="mt-auto px-4 py-3 rounded-xl bg-primary text-white font-semibold hover:bg-primary-hover transition-colors disabled:opacity-60"
                                    disabled={activeCode === product.code}
                                >
                                    {activeCode === product.code ? "Redirecting..." : "Continue to Checkout"}
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}
