"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface CreditPack {
    code: string;
    name: string;
    credits: number;
    price_usd: number;
}

export default function PricingSection() {
    const [packs, setPacks] = useState<CreditPack[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPacks = async () => {
            try {
                const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
                const packsUrl = apiBaseUrl
                    ? `${apiBaseUrl.replace(/\/$/, "")}/api/v1/topups/products`
                    : "/api/v1/topups/products";
                const res = await fetch(packsUrl);
                if (res.ok) {
                    const data = await res.json();
                    const sorted = [...(data as CreditPack[])].sort((a, b) => a.price_usd - b.price_usd);
                    setPacks(sorted);
                } else {
                    console.error("Failed to fetch credit packs", res.status, res.statusText);
                }
            } catch (error) {
                console.error("Failed to fetch credit packs", error);
            } finally {
                setLoading(false);
            }
        };

        fetchPacks();
    }, []);

    if (loading) {
        return (
            <section className="bg-background-light dark:bg-background-dark py-24 transition-colors duration-200" id="pricing">
                <div className="max-w-[1000px] mx-auto px-4 text-center">
                    <h2 className="text-3xl md:text-4xl font-bold font-display mb-4 text-[#111318] dark:text-white">Credit Packs</h2>
                    <p className="text-[#616f89] dark:text-gray-400 mb-16">Loading credit packs...</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 animate-pulse">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="h-96 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
                        ))}
                    </div>
                </div>
            </section>
        );
    }

    return (
        <section className="bg-background-light dark:bg-background-dark py-24 transition-colors duration-200" id="pricing">
            <div className="max-w-[1200px] mx-auto px-4">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold font-display mb-4 text-[#111318] dark:text-white">Credit Packs</h2>
                    <p className="text-[#616f89] dark:text-gray-400">Purchase credits when you need them. No subscriptions.</p>
                </div>

                {packs.length === 0 ? (
                    <div className="text-center text-slate-500">No credit packs available right now.</div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 justify-center">
                        {packs.map((pack, index) => {
                            const isFeatured = index === packs.length - 1;
                            const priceFormatted = `$${pack.price_usd.toFixed(2)}`;

                            return (
                                <div
                                    key={pack.code}
                                    className={`
                                relative flex flex-col p-10 rounded-2xl transition-all duration-300
                                ${isFeatured
                                        ? "bg-white dark:bg-slate-900 border-2 border-primary shadow-2xl shadow-primary/10 scale-105 z-10"
                                        : "bg-white dark:bg-slate-900 border border-[#dbdfe6] dark:border-slate-800 hover:border-primary/30"
                                    }
                            `}
                                >
                                    {isFeatured && (
                                        <div className="absolute top-0 right-0 bg-primary text-white px-4 py-1 rounded-bl-xl font-bold text-xs uppercase tracking-widest">
                                            Best Value
                                        </div>
                                    )}

                                    <div className="mb-8">
                                        <h3 className="text-2xl font-bold mb-2 text-[#111318] dark:text-white">{pack.name}</h3>
                                        <div className="text-4xl font-black font-display text-[#111318] dark:text-white">
                                            {priceFormatted}
                                            <span className="text-lg font-normal text-gray-400"> one-time</span>
                                        </div>
                                        <p className="text-sm text-primary font-bold mt-2">
                                            {pack.credits.toLocaleString()} Credits
                                        </p>
                                    </div>

                                    <ul className="space-y-4 mb-10 flex-1">
                                        <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                            <span className="material-symbols-outlined text-green-500 font-bold">check</span>
                                            Use on any solve tier
                                        </li>
                                        <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                            <span className="material-symbols-outlined text-green-500 font-bold">check</span>
                                            Credits never auto-renew
                                        </li>
                                        <li className="flex items-center gap-3 text-sm text-[#111318] dark:text-gray-300">
                                            <span className="material-symbols-outlined text-green-500 font-bold">check</span>
                                            Track usage in Wallet & Programs
                                        </li>
                                    </ul>

                                    <Link href="/billing" className="w-full">
                                        <button className="w-full py-4 rounded-xl bg-primary text-white font-bold hover:bg-blue-700 transition-colors shadow-lg shadow-primary/20">
                                            Buy Credits
                                        </button>
                                    </Link>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </section>
    );
}
