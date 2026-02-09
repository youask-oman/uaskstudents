'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

interface Program {
    id: number;
    name: string;
    slug: string;
    description: string | null;
    status: string;
    monthly_gift_credits: number | null;
    gift_expiry_window_days: number;
    enrollment_count: number;
    created_at: string;
}

export default function CreditProgramsPage() {
    const { token } = useAuth();
    const [programs, setPrograms] = useState<Program[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchPrograms();
    }, []);

    const fetchPrograms = async () => {
        try {
            const res = await fetch(`${API_BASE}/admin/billing/programs?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPrograms(data.items);
                setTotal(data.total);
            }
        } catch (e) {
            console.error('Failed to load programs');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-admin-primary/20 rounded-full border-4 border-t-admin-primary animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Programs...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-admin-primary/10 flex items-center justify-center text-admin-primary border border-admin-primary/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">card_giftcard</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Credit Programs</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Define monthly credit allowances, feature entitlements, and auto-grant rules for different user tiers and groups.
                    </p>
                </div>
                <div className="flex gap-4">
                    <Link
                        href="/admin/billing/enrollments"
                        className="flex items-center gap-2 px-6 py-3 bg-white hover:bg-slate-50 text-slate-900 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-white text-sm font-bold rounded-2xl transition-all border border-slate-200 dark:border-slate-800 shadow-lg"
                    >
                        <span className="material-symbols-outlined text-[20px]">group</span>
                        Global Enrollments
                    </Link>
                    <button
                        className="flex items-center gap-2 px-6 py-3 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        New Program
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-[2rem] shadow-2xl flex flex-col gap-4">
                    <div className="flex justify-between items-start">
                        <div className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg font-bold text-[10px] uppercase tracking-widest leading-none">Status</div>
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest italic">Total Definitions</span>
                    </div>
                    <div className="flex items-end justify-between">
                        <h3 className="text-5xl font-black text-slate-900 dark:text-white tracking-tighter">{total}</h3>
                        <p className="text-slate-400 text-xs font-bold mb-2 uppercase tracking-widest">Programs</p>
                    </div>
                </div>
                {/* Could add more KPIs here */}
            </div>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Program</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Slug</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Monthly Grant</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Expiry</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Users</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {programs.map((program) => (
                            <tr key={program.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <div className="flex flex-col gap-1">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white">{program.name}</span>
                                        <span className="text-xs text-slate-400 line-clamp-1">{program.description || 'No description provided'}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6 font-mono text-[11px] text-slate-500">{program.slug}</td>
                                <td className="px-8 py-6">
                                    <span
                                        className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border transition-colors ${program.status === 'active'
                                            ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                            : 'bg-slate-500/10 text-slate-500 border-slate-500/20'
                                            }`}
                                    >
                                        {program.status}
                                    </span>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-sm font-extrabold text-admin-primary">{program.monthly_gift_credits?.toFixed(0) || '0'}</span>
                                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">CR</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <span className="text-xs font-bold text-slate-400 italic">{program.gift_expiry_window_days} Days</span>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-2">
                                        <div className="size-6 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-500 border border-indigo-500/20">
                                            <span className="material-symbols-outlined text-[14px]">person</span>
                                        </div>
                                        <span className="text-sm font-black text-slate-900 dark:text-slate-200">{program.enrollment_count}</span>
                                    </div>
                                </td>
                            </tr>
                        ))}
                        {programs.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-8 py-20 text-center">
                                    <div className="flex flex-col items-center gap-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-600">inventory_2</span>
                                        <p className="text-slate-400 font-bold uppercase tracking-widest text-[10px]">No programs found in system</p>
                                    </div>
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <footer className="flex justify-between items-center px-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest italic">
                    Showing {programs.length} of {total} program definitions
                </p>
                <div className="flex gap-2">
                    {/* Pagination could go here */}
                </div>
            </footer>
        </div>
    );
}
