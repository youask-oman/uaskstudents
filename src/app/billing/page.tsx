"use client";

import { useEffect, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import { fetchSubscription, SubscriptionResponse } from "@/lib/subscription";

type Invoice = {
    id: number;
    invoice_number: string;
    kind: string;
    status: string;
    total_amount: number;
    currency: string;
    created_at: string;
};

export default function BillingPage() {
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadData = async () => {
            const userId = localStorage.getItem("user_id");
            const token = localStorage.getItem("access_token");
            if (!userId || !token) return;

            try {
                // Fetch Subscription
                const sub = await fetchSubscription(userId);
                setSubscription(sub);

                // Fetch Invoices
                const invRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/billing/invoices`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (invRes.ok) {
                    const data = await invRes.json();
                    setInvoices(data);
                }
            } catch (error) {
                console.error("Error loading billing data:", error);
            } finally {
                setLoading(false);
            }
        };

        void loadData();
    }, []);

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
            <DashboardNavBar />

            <main className="max-w-4xl mx-auto px-4 py-12">
                <div className="mb-10">
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">Billing & Subscription</h1>
                    <p className="text-slate-500 dark:text-slate-400">Manage your subscription and view your payment history.</p>
                </div>

                {/* Subscription Card */}
                <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-8 mb-8">
                    <div className="flex justify-between items-start mb-6">
                        <div>
                            <span className="text-xs font-bold text-primary uppercase tracking-widest px-2 py-1 bg-primary/10 rounded-full mb-3 inline-block">
                                Current Plan
                            </span>
                            <h2 className="text-2xl font-bold text-slate-900 dark:text-white capitalize">
                                {subscription?.plan.display_name || "Loading..."}
                            </h2>
                        </div>
                        <div className="text-right">
                            <p className="text-sm text-slate-400">Status</p>
                            <p className={`text-sm font-bold capitalize ${subscription?.status === 'active' ? 'text-green-500' : 'text-slate-500'}`}>
                                {subscription?.status || "---"}
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 bg-slate-50 dark:bg-slate-800/50 rounded-xl">
                        <div>
                            <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Credits Balance</p>
                            <p className="text-xl font-bold text-slate-900 dark:text-white">
                                {subscription?.usage.credits_balance?.toLocaleString() || (subscription?.usage.credits_remaining?.toLocaleString()) || "0"} 🧞
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-semibold text-slate-400 uppercase mb-1">Next Billing Date</p>
                            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                {subscription?.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : "---"}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Invoices List */}
                <div className="space-y-4">
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white">Invoices & Receipts</h3>

                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
                        {loading ? (
                            <div className="p-12 text-center text-slate-500">Loading history...</div>
                        ) : invoices.length === 0 ? (
                            <div className="p-12 text-center text-slate-500">No invoices found.</div>
                        ) : (
                            <table className="w-full text-left">
                                <thead className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                                    <tr>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase">Date</th>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase">Invoice #</th>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase">Amount</th>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase text-right">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {invoices.map(inv => (
                                        <tr key={inv.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                            <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                                                {new Date(inv.created_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4 text-sm font-mono text-slate-900 dark:text-white">
                                                {inv.invoice_number}
                                            </td>
                                            <td className="px-6 py-4 text-sm font-bold text-slate-900 dark:text-white">
                                                {inv.currency === 'USD' ? '$' : ''}{inv.total_amount.toFixed(2)}
                                            </td>
                                            <td className="px-6 py-4 text-right flex items-center justify-end gap-3">
                                                <a
                                                    href={`/api/v1/billing/invoices/${inv.id}/html`}
                                                    target="_blank"
                                                    className="text-primary hover:text-primary-hover font-medium text-xs transition-colors"
                                                >
                                                    View
                                                </a>
                                                <span className={`inline-flex px-2 py-1 rounded text-xs font-bold uppercase ${inv.status === 'PAID' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
                                                    }`}>
                                                    {inv.status}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
