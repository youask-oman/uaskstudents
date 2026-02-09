'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

interface Refund {
    id: number;
    user_id: number;
    user_email: string;
    credits: number;
    reason_code: string;
    expires_at: string;
    created_at: string;
}

export default function RefundCenterPage() {
    const { token } = useAuth();
    const [refunds, setRefunds] = useState<Refund[]>([]);
    const [loading, setLoading] = useState(true);
    const [isSuper, setIsSuper] = useState(false);

    // Form state
    const [showForm, setShowForm] = useState(false);
    const [targetUser, setTargetUser] = useState('');
    const [credits, setCredits] = useState('');
    const [reason, setReason] = useState('');
    const [reasonCode, setReasonCode] = useState('SERVICE_ISSUE');

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchRefunds();
        const storedRole = typeof window !== 'undefined' ? localStorage.getItem('user_role') : '';
        if (storedRole === 'system_admin' || storedRole === 'superadmin') {
            setIsSuper(true);
        }
    }, []);

    const fetchRefunds = async () => {
        try {
            const res = await fetch(`${API_BASE}/admin/billing/refunds?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setRefunds(data.items);
            }
        } catch (e) {
            console.error('Failed to load refunds');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await fetch(`${API_BASE}/admin/billing/refunds`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: parseInt(targetUser),
                    credits: parseFloat(credits),
                    reason_code: reasonCode,
                    reason: reason,
                })
            });
            if (res.ok) {
                setShowForm(false);
                setTargetUser('');
                setCredits('');
                setReason('');
                fetchRefunds();
                alert('Refund issued successfully');
            } else {
                const err = await res.json();
                alert(err.detail || 'Failed to issue refund');
            }
        } catch (e) {
            alert('Error issuing refund');
        }
    };

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-rose-500/20 rounded-full border-4 border-t-rose-500 animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Accessing Refund Logs...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-rose-500/10 flex items-center justify-center text-rose-500 border border-rose-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">undo</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Refund Center</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Issue credit adjustments and investigate service refunds. Note that credits issued here typically have a shorter expiry than purchased packs.
                    </p>
                </div>
                {isSuper && (
                    <button
                        onClick={() => setShowForm(!showForm)}
                        className="flex items-center gap-2 px-6 py-3 bg-rose-500 hover:bg-rose-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-rose-500/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">{showForm ? 'close' : 'add'}</span>
                        {showForm ? 'Cancel' : 'Issue Refund'}
                    </button>
                )}
            </header>

            {showForm && (
                <div className="bg-white dark:bg-[#111827] border border-rose-500/20 p-8 rounded-[2.5rem] shadow-3xl animate-in slide-in-from-top duration-300">
                    <h3 className="text-xl font-black text-slate-900 dark:text-white mb-6 italic">Issue New Credit Refund</h3>
                    <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="space-y-2">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Target User ID</label>
                            <input
                                required
                                type="number"
                                value={targetUser}
                                onChange={(e) => setTargetUser(e.target.value)}
                                className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 text-sm focus:ring-2 focus:ring-rose-500 outline-none"
                                placeholder="e.g. 1234"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Credit Amount</label>
                            <input
                                required
                                type="number"
                                step="any"
                                value={credits}
                                onChange={(e) => setCredits(e.target.value)}
                                className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 text-sm focus:ring-2 focus:ring-rose-500 outline-none"
                                placeholder="e.g. 500"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Reason Code</label>
                            <select
                                value={reasonCode}
                                onChange={(e) => setReasonCode(e.target.value)}
                                className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 text-sm focus:ring-2 focus:ring-rose-500 outline-none"
                            >
                                <option value="SERVICE_ISSUE">Service Issue</option>
                                <option value="PAYMENT_REVERSAL">Payment Reversal</option>
                                <option value="ADMIN_ADJUSTMENT">Admin Adjustment</option>
                            </select>
                        </div>
                        <div className="md:col-span-3 space-y-2">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Reason Description (Visible to User)</label>
                            <textarea
                                required
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 text-sm focus:ring-2 focus:ring-rose-500 outline-none min-h-[100px]"
                                placeholder="Explain why this refund is being issued..."
                            />
                        </div>
                        <div className="md:col-span-3 flex justify-end">
                            <button type="submit" className="px-10 py-4 bg-rose-500 text-white font-black rounded-2xl shadow-xl shadow-rose-500/30 hover:bg-rose-600 transition-all uppercase tracking-widest text-xs">
                                Confirm & Post Refund
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Refund ID</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Recipient</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Amount</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Reason</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Timestamp</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Expiry</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {refunds.map((refund) => (
                            <tr key={refund.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <span className="text-xs font-mono font-black text-rose-500">REF-{refund.id.toString().padStart(6, '0')}</span>
                                </td>
                                <td className="px-8 py-6">
                                    <Link href={`/admin/users/${refund.user_id}`} className="flex flex-col gap-0.5 group/link">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white group-hover/link:text-rose-500 transition-colors">{refund.user_email}</span>
                                        <span className="text-[10px] font-medium text-slate-400">UID: #{refund.user_id}</span>
                                    </Link>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-sm font-black text-rose-600 italic">+{refund.credits.toFixed(0)} CR</span>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="px-2 py-0.5 rounded-lg bg-rose-500/10 text-rose-500 text-[10px] font-black uppercase tracking-widest border border-rose-500/20">
                                        {refund.reason_code}
                                    </span>
                                </td>
                                <td className="px-8 py-6 text-xs font-medium text-slate-500 tabular-nums lowercase italic">
                                    {new Date(refund.created_at).toLocaleDateString()}
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-xs font-bold text-slate-400 italic">
                                        {refund.expires_at ? new Date(refund.expires_at).toLocaleDateString() : 'NO EXPIRY'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
