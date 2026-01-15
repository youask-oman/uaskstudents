"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import StudentLayout from '@/components/layout/StudentLayout';

interface Payment {
    id: number;
    amount: number;
    status: string;
    created_at: string;
    transaction_id: string;
}

interface UserProfile {
    usage: {
        questions_count: number;
        questions_total: number;
        scans_count: number;
        scans_total: number;
    };
    subscription_tier: string;
    subscription_expiry: string;
}

export default function BillingPage() {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [history, setHistory] = useState<Payment[]>([]);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        const fetchData = async () => {
            try {
                const storedUser = localStorage.getItem('user');
                if (!storedUser) {
                    router.push('/login');
                    return;
                }
                const userData = JSON.parse(storedUser);
                const userId = userData.id || 1;
                const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

                const profileRes = await fetch(`${apiBaseUrl}/api/v1/user/profile?user_id=${userId}`);

                if (profileRes.ok) {
                    const profileData = await profileRes.json();
                    setUser(profileData);
                } else {
                    console.error("Failed to fetch profile:", profileRes.status);
                }

                // Fetch Billing History
                const historyRes = await fetch(`${apiBaseUrl}/api/v1/billing/history?user_id=${userId}`);
                if (historyRes.ok) {
                    const historyData = await historyRes.json();
                    setHistory(historyData);
                } else {
                    console.error("Failed to fetch history:", historyRes.status);
                }

            } catch (error) {
                console.error("Failed to fetch billing data", error);
            } finally {
                setLoading(false);
            }
        };

        if (typeof window !== 'undefined') {
            fetchData();
        }
    }, [router]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#101622]">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    const usagePercent = user ? Math.min(100, Math.round((user.usage.questions_count / user.usage.questions_total) * 100)) : 0;
    const scansPercent = user ? Math.min(100, Math.round((user.usage.scans_count / user.usage.scans_total) * 100)) : 0;

    // Calculate stroke-dasharray for circular progress (C = 2 * pi * r)
    // r=15.9155 => C=100
    const usageDashArray = `${usagePercent}, 100`;
    const scansDashArray = `${scansPercent}, 100`;

    return (
        <StudentLayout>
            <div className="flex flex-1 justify-center py-8 px-4 lg:px-10 bg-[#f6f6f8] dark:bg-[#101622]">
                <div className="layout-content-container flex flex-col max-w-[1200px] flex-1 gap-8">
                    {/* Page Heading */}
                    <div className="flex flex-wrap justify-between items-end gap-4 px-2">
                        <div className="flex min-w-72 flex-col gap-2">
                            <p className="text-slate-900 dark:text-white text-4xl font-black leading-tight tracking-[-0.033em]">Plan & Billing</p>
                            <p className="text-slate-500 dark:text-[#9da6b9] text-base font-normal leading-normal">Manage your subscription, view usage quotas, and download invoices.</p>
                        </div>
                        <div className="flex gap-3">
                            {user?.subscription_tier === 'free' ? (
                                <Link href="/billing/payment" className="flex min-w-[84px] cursor-pointer items-center justify-center rounded-lg h-10 px-6 bg-[#135bec] text-white text-sm font-bold leading-normal shadow-lg shadow-[#135bec]/20 transition-all hover:scale-[1.02]">
                                    <span className="truncate">Upgrade to Pro</span>
                                </Link>
                            ) : (
                                <button
                                    onClick={() => alert("Redirecting to Stripe Customer Portal...")}
                                    className="flex min-w-[84px] cursor-pointer items-center justify-center rounded-lg h-10 px-6 bg-[#135bec] text-white text-sm font-bold leading-normal shadow-lg shadow-[#135bec]/20 transition-all hover:scale-[1.02]">
                                    <span className="truncate">Manage in Stripe</span>
                                </button>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Left Column: Usage & History */}
                        <div className="lg:col-span-2 flex flex-col gap-8">
                            {/* Usage Metrics Section */}
                            <section className="bg-white dark:bg-[#161b26] rounded-xl border border-slate-200 dark:border-[#282e39] p-6">
                                <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[#135bec]">analytics</span>
                                    Usage This Period
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    {/* Metric Ring 1 */}
                                    <div className="flex flex-col items-center gap-3 p-4 rounded-lg bg-slate-50 dark:bg-[#212735] border border-slate-100 dark:border-[#2d3545]">
                                        <div className="relative size-24">
                                            <svg className="size-full" viewBox="0 0 36 36">
                                                <path className="text-slate-200 dark:text-[#2d3545]" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3"></path>
                                                <path className="text-[#135bec] transition-[stroke-dasharray] duration-500 ease-in-out" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray={usageDashArray} strokeLinecap="round" strokeWidth="3"></path>
                                            </svg>
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <span className="text-sm font-bold">{usagePercent}%</span>
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm font-medium opacity-80">Daily AI Solves</p>
                                            <p className="text-lg font-bold">{user?.usage.questions_count}/{user?.usage.questions_total}</p>
                                        </div>
                                    </div>
                                    {/* Metric Ring 2 */}
                                    <div className="flex flex-col items-center gap-3 p-4 rounded-lg bg-slate-50 dark:bg-[#212735] border border-slate-100 dark:border-[#2d3545]">
                                        <div className="relative size-24">
                                            <svg className="size-full" viewBox="0 0 36 36">
                                                <path className="text-slate-200 dark:text-[#2d3545]" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3"></path>
                                                <path className="text-[#135bec] transition-[stroke-dasharray] duration-500 ease-in-out" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray={scansDashArray} strokeLinecap="round" strokeWidth="3"></path>
                                            </svg>
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <span className="text-sm font-bold">{scansPercent}%</span>
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm font-medium opacity-80">OCR Scans</p>
                                            <p className="text-lg font-bold">{user?.usage.scans_count}/{user?.usage.scans_total}</p>
                                        </div>
                                    </div>
                                    {/* Metric Ring 3 (Unlimited) */}
                                    <div className="flex flex-col items-center gap-3 p-4 rounded-lg bg-slate-50 dark:bg-[#212735] border border-slate-100 dark:border-[#2d3545]">
                                        <div className="relative size-24">
                                            <svg className="size-full" viewBox="0 0 36 36">
                                                <path className="text-[#135bec]/20" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3"></path>
                                                <path className="text-[#135bec]" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray="100, 100" strokeLinecap="round" strokeWidth="3"></path>
                                            </svg>
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <span className="material-symbols-outlined text-[#135bec] text-3xl">all_inclusive</span>
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm font-medium opacity-80">Concept Library</p>
                                            <p className="text-lg font-bold">Unlimited</p>
                                        </div>
                                    </div>
                                </div>
                            </section>

                            {/* Billing History Table */}
                            <section className="bg-white dark:bg-[#161b26] rounded-xl border border-slate-200 dark:border-[#282e39] overflow-hidden">
                                <div className="p-6 border-b border-slate-200 dark:border-[#282e39] flex justify-between items-center">
                                    <h3 className="text-lg font-bold flex items-center gap-2">
                                        <span className="material-symbols-outlined text-[#135bec]">receipt_long</span>
                                        Billing History
                                    </h3>
                                    <button className="text-[#135bec] text-sm font-bold hover:underline">View All</button>
                                </div>
                                <div className="overflow-x-auto">
                                    {history.length === 0 ? (
                                        <div className="p-8 text-center text-slate-500 italic">No billing history found.</div>
                                    ) : (
                                        <table className="w-full text-left text-sm">
                                            <thead className="bg-slate-50 dark:bg-[#212735] text-slate-500 dark:text-[#9da6b9] uppercase text-[11px] tracking-wider">
                                                <tr>
                                                    <th className="px-6 py-4 font-bold">Date</th>
                                                    <th className="px-6 py-4 font-bold">Amount</th>
                                                    <th className="px-6 py-4 font-bold">Status</th>
                                                    <th className="px-6 py-4 font-bold text-right">Invoice</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100 dark:divide-[#282e39]">
                                                {history.map((payment) => (
                                                    <tr key={payment.id}>
                                                        <td className="px-6 py-4 font-medium">{new Date(payment.created_at).toLocaleDateString()}</td>
                                                        <td className="px-6 py-4">${payment.amount.toFixed(2)}</td>
                                                        <td className="px-6 py-4">
                                                            <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase ${payment.status === 'completed'
                                                                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                                                                : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                                                                }`}>{payment.status}</span>
                                                        </td>
                                                        <td className="px-6 py-4 text-right">
                                                            <button className="inline-flex items-center gap-1 text-[#135bec] hover:text-[#135bec]/80 font-bold">
                                                                <span className="material-symbols-outlined text-base">download</span> PDF
                                                            </button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    )}
                                </div>
                            </section>
                        </div>

                        {/* Right Column: Plan Sidebar & Payment */}
                        <div className="flex flex-col gap-6">
                            {/* Current Plan Card */}
                            <div className="bg-[#135bec] rounded-xl p-6 text-white shadow-xl shadow-[#135bec]/20 relative overflow-hidden group">
                                <div className="absolute -right-8 -top-8 size-32 bg-white/10 rounded-full blur-2xl group-hover:bg-white/20 transition-all"></div>
                                <div className="relative z-10">
                                    <div className="flex justify-between items-start mb-4">
                                        <span className="px-3 py-1 bg-white/20 rounded-full text-xs font-bold uppercase tracking-widest">{user?.subscription_tier === 'free' ? 'Basic' : 'Active'}</span>
                                        <span className="material-symbols-outlined">rocket_launch</span>
                                    </div>
                                    <h4 className="text-2xl font-black mb-1 capitalize">{user?.subscription_tier || "Free"} Plan</h4>
                                    <p className="text-white/80 text-sm mb-6">
                                        {user?.subscription_tier === 'free' ? 'Upgrade to unlock more.' : `Renews ${user?.subscription_expiry ? new Date(user.subscription_expiry).toLocaleDateString() : 'Active'}`}
                                    </p>
                                    <div className="flex items-baseline gap-1 mb-6">
                                        <span className="text-3xl font-bold">{user?.subscription_tier === 'free' ? '$0' : '$9.99'}</span>
                                        <span className="text-sm text-white/70">/ month</span>
                                    </div>
                                    <Link href="/billing/payment" className="block w-full text-center bg-white text-[#135bec] font-bold py-3 rounded-lg hover:bg-slate-50 transition-colors">
                                        {user?.subscription_tier === 'free' ? 'Upgrade to Pro' : 'Upgrade to Ultra'}
                                    </Link>
                                </div>
                            </div>

                            {/* Upgrade Promo (if not Ultra) */}
                            <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 flex flex-col gap-4">
                                <div className="flex items-center gap-3">
                                    <div className="size-8 rounded-lg bg-yellow-500/20 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-yellow-500 text-xl">star</span>
                                    </div>
                                    <p className="text-sm font-bold text-white">Unlock Ultra</p>
                                </div>
                                <ul className="space-y-2">
                                    <li className="text-xs text-slate-400 flex items-center gap-2">
                                        <span className="material-symbols-outlined text-[#135bec] text-[14px]">check_circle</span>
                                        Unlimited AI Solves
                                    </li>
                                    <li className="text-xs text-slate-400 flex items-center gap-2">
                                        <span className="material-symbols-outlined text-[#135bec] text-[14px]">check_circle</span>
                                        Priority Server Access
                                    </li>
                                </ul>
                                <p className="text-[10px] text-slate-500 mt-2">Get 2 months free with an annual plan upgrade.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </StudentLayout>
    );
}
