"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Plan {
    id: number;
    name: string;
    slug: string;
    credits_per_month: number;
    price_monthly_cents: number;
    features: Record<string, unknown>;
}

export default function PricingSection() {
    const [plans, setPlans] = useState<Plan[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPlans = async () => {
            try {
                const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
                const plansUrl = apiBaseUrl
                    ? `${apiBaseUrl.replace(/\/$/, "")}/api/v1/public/plans`
                    : "/api/v1/public/plans";
                const res = await fetch(plansUrl);
                if (res.ok) {
                    const data = await res.json();
                    // Sort by price to ensure logical order
                    setPlans(data.sort((a: Plan, b: Plan) => a.price_monthly_cents - b.price_monthly_cents));
                } else {
                    console.error("Failed to fetch plans", res.status, res.statusText);
                }
            } catch (error) {
                console.error("Failed to fetch plans", error);
            } finally {
                setLoading(false);
            }
        };

        fetchPlans();
    }, []);

    // Fallback static data if fetch fails or loading (for Skeleton/SEO)
    // Actually, better to show a skeleton state
    if (loading) {
        return (
            <section className="bg-background-light dark:bg-background-dark py-24 transition-colors duration-200" id="pricing">
                <div className="max-w-[1000px] mx-auto px-4 text-center">
                    <h2 className="text-3xl md:text-4xl font-bold font-display mb-4 text-[#111318] dark:text-white">Simple Pricing</h2>
                    <p className="text-[#616f89] dark:text-gray-400 mb-16">Loading plans...</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 animate-pulse">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="h-96 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
                        ))}
                    </div>
                </div>
            </section>
        )
    }

    return (
        <section className="bg-background-light dark:bg-background-dark py-24 transition-colors duration-200" id="pricing">
            <div className="max-w-[1200px] mx-auto px-4">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold font-display mb-4 text-[#111318] dark:text-white">Simple Pricing</h2>
                    <p className="text-[#616f89] dark:text-gray-400">Start for free, upgrade when you&apos;re ready to master it all.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 justify-center">
                    {plans.map((plan) => {
                        const isPro = plan.price_monthly_cents > 0;
                        const priceFormatted = plan.price_monthly_cents === 0 ? "$0" : `$${(plan.price_monthly_cents / 100).toFixed(2)}`;

                        return (
                            <div
                                key={plan.id}
                                className={`
                            relative flex flex-col p-10 rounded-2xl transition-all duration-300
                            ${isPro
                                        ? "bg-white dark:bg-slate-900 border-2 border-primary shadow-2xl shadow-primary/10 scale-105 z-10"
                                        : "bg-white dark:bg-slate-900 border border-[#dbdfe6] dark:border-slate-800 hover:border-primary/30"
                                    }
                        `}
                            >
                                {isPro && (
                                    <div className="absolute top-0 right-0 bg-primary text-white px-4 py-1 rounded-bl-xl font-bold text-xs uppercase tracking-widest">
                                        Recommended
                                    </div>
                                )}

                                <div className="mb-8">
                                    <h3 className="text-2xl font-bold mb-2 text-[#111318] dark:text-white">{plan.name}</h3>
                                    <div className="text-4xl font-black font-display text-[#111318] dark:text-white">
                                        {priceFormatted}<span className="text-lg font-normal text-gray-400">/mo</span>
                                    </div>
                                    <p className="text-sm text-primary font-bold mt-2">
                                        {plan.credits_per_month.toLocaleString()} Credits / Mo
                                    </p>
                                </div>

                                <ul className="space-y-4 mb-10 flex-1">
                                    {/* Feature extraction - this logic can be refined based on actual features JSON structure */}
                                    <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                        <span className="material-symbols-outlined text-green-500 font-bold">check</span>
                                        AI Solution Generation
                                    </li>
                                    <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                        <span className="material-symbols-outlined text-green-500 font-bold">check</span>
                                        OCR & Handwriting Recognition
                                    </li>
                                    {isPro && (
                                        <>
                                            <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                                <span className="material-symbols-outlined text-primary font-bold">check</span>
                                                Priority Processing
                                            </li>
                                            <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                                <span className="material-symbols-outlined text-primary font-bold">check</span>
                                                Advanced Socratic Mode
                                            </li>
                                        </>
                                    )}
                                    <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                        <span className="material-symbols-outlined text-green-500 font-bold">check</span>
                                        Interactive Concept Library
                                    </li>
                                </ul>

                                {isPro ? (
                                    <Link href="/signup?tier=pro" className="w-full">
                                        <button className="w-full py-4 rounded-xl bg-primary text-white font-bold hover:bg-blue-700 transition-colors shadow-lg shadow-primary/20">
                                            Upgrade to {plan.name}
                                        </button>
                                    </Link>
                                ) : (
                                    <Link href="/signup" className="w-full">
                                        <button className="w-full py-4 rounded-xl border-2 border-primary text-primary font-bold hover:bg-primary/5 transition-colors">
                                            Get Started
                                        </button>
                                    </Link>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
