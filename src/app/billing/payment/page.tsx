"use client";

import { useEffect, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

const PAGE_TITLE = "Top Up Credits";

type TopUpProduct = {
    code: string;
    name: string;
    credits: number;
    price_usd: number;
};

export default function BillingPaymentPage() {
    const { pushToast } = useToast();
    const [products, setProducts] = useState<TopUpProduct[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeCode, setActiveCode] = useState<string | null>(null);

    useEffect(() => {
        const loadProducts = async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/topups/products`);
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
                const data = (await res.json()) as TopUpProduct[];
                setProducts(Array.isArray(data) ? data : []);
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
            const successUrl = `${window.location.origin}/billing/success?product=${encodeURIComponent(product.code)}`;
            const cancelUrl = `${window.location.origin}/billing/payment?status=cancelled`;
            const res = await fetch(`${API_BASE_URL}/api/v1/topups/stripe/checkout`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    product_code: product.code,
                    success_url: successUrl,
                    cancel_url: cancelUrl,
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
            <DashboardNavBar />

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
                                </div>
                                <div className="flex items-baseline gap-2">
                                    <span className="text-3xl font-black text-primary">${product.price_usd.toFixed(2)}</span>
                                    <span className="text-xs text-slate-500">USD</span>
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
