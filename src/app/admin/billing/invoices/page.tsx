'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

interface Invoice {
    id: number;
    user_id: number;
    user_email?: string;
    invoice_number: string;
    status: string;
    subtotal: number;
    tax: number;
    total: number;
    currency: string;
    issued_at?: string | null;
    created_at: string;
}

export default function InvoicesPage() {
    const { token } = useAuth();
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:9000';

    const fetchInvoices = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/invoices?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setInvoices(data.items || []);
                setTotal(data.total || 0);
            }
        } catch (err) {
            console.error('Failed to load invoices', err);
        } finally {
            setLoading(false);
        }
    }, [API_BASE, token]);

    useEffect(() => {
        fetchInvoices();
    }, [fetchInvoices]);

    if (loading && invoices.length === 0) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-admin-primary/20 rounded-full border-4 border-t-admin-primary animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Invoices...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-slate-500/10 flex items-center justify-center text-slate-500 border border-slate-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">receipt</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Invoice Center</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Immutable billing invoices generated for top-ups and legacy subscriptions.
                    </p>
                </div>
                <button
                    onClick={fetchInvoices}
                    className="flex items-center gap-2 px-6 py-3 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-bold rounded-2xl transition-all border border-slate-200 dark:border-slate-800 shadow-lg"
                >
                    <span className="material-symbols-outlined text-[20px]">refresh</span>
                    Refresh
                </button>
            </header>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Invoice</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">User</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Total</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Issued</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {invoices.map((invoice) => (
                            <tr key={invoice.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white">{invoice.invoice_number}</span>
                                        <span className="text-[10px] font-mono text-slate-400">#I-{invoice.id}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <Link href={`/admin/users/${invoice.user_id}`} className="text-sm font-semibold text-slate-500 hover:text-admin-primary transition-colors">
                                        {invoice.user_email || `User #${invoice.user_id}`}
                                    </Link>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 text-[10px] font-black uppercase tracking-widest border border-slate-200 dark:border-slate-700">
                                        {invoice.status}
                                    </span>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-black text-slate-900 dark:text-white italic">
                                        {invoice.total.toFixed(2)} {invoice.currency}
                                    </span>
                                </td>
                                <td className="px-8 py-6 text-xs font-medium text-slate-500 tabular-nums">
                                    {invoice.issued_at ? new Date(invoice.issued_at).toLocaleDateString() : new Date(invoice.created_at).toLocaleDateString()}
                                </td>
                            </tr>
                        ))}
                        {invoices.length === 0 && (
                            <tr>
                                <td colSpan={5} className="px-8 py-20 text-center">
                                    <div className="flex flex-col items-center gap-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-600">receipt_long</span>
                                        <p className="text-slate-400 font-bold uppercase tracking-widest text-[10px]">No invoices found</p>
                                    </div>
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <footer className="flex justify-between items-center px-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest italic">
                    Showing {invoices.length} of {total} invoices
                </p>
            </footer>
        </div>
    );
}
