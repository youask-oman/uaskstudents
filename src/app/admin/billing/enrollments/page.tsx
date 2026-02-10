'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

interface Enrollment {
    id: number;
    user_id: number;
    user_email: string;
    program_id: number;
    program_name: string;
    status: string;
    started_at: string;
    last_grant_month: string | null;
}

interface Program {
    id: number;
    name: string;
}

export default function GlobalEnrollmentsPage() {
    const { token } = useAuth();
    const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
    const [programs, setPrograms] = useState<Program[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [total, setTotal] = useState(0);

    // Modal
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [formData, setFormData] = useState({
        user_id: '',
        program_id: '',
        reason: ''
    });

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchEnrollments();
        fetchPrograms();
    }, []);

    const fetchEnrollments = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/programs/enrollments/all?limit=100`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setEnrollments(data.items);
                setTotal(data.total);
            }
        } catch (e) {
            console.error('Failed to load enrollments');
        } finally {
            setLoading(false);
        }
    };

    const fetchPrograms = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/programs?status=active`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPrograms(data.items);
            }
        } catch (e) {
            console.error('Failed to load programs');
        }
    };

    const handleEnroll = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/programs/enrollments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    user_id: parseInt(formData.user_id),
                    program_id: parseInt(formData.program_id),
                    reason: formData.reason
                })
            });

            if (res.ok) {
                setIsModalOpen(false);
                setFormData({ user_id: '', program_id: '', reason: '' });
                fetchEnrollments();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (error) {
            console.error(error);
            alert('Failed to enroll user');
        }
    };

    const handleUnenroll = async (userId: number, programId: number) => {
        const reason = prompt("Enter reason for unenrollment:");
        if (!reason) return;

        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/programs/enrollments/unenroll`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    user_id: userId,
                    program_id: programId,
                    reason
                })
            });

            if (res.ok) {
                fetchEnrollments();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (error) {
            console.error(error);
            alert('Failed to unenroll user');
        }
    };

    const filtered = search
        ? enrollments.filter(
            (e) =>
                e.user_email?.toLowerCase().includes(search.toLowerCase()) ||
                e.program_name?.toLowerCase().includes(search.toLowerCase())
        )
        : enrollments;

    if (loading && enrollments.length === 0) {
        return (
            <div className="p-8 flex items-center justify-center min-h-screen">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <div className="size-12 bg-admin-primary/20 rounded-full border-4 border-t-admin-primary animate-spin"></div>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Loading Enrollments...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-10">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-500 border border-purple-500/20 shadow-xl">
                            <span className="material-symbols-outlined text-2xl">groups</span>
                        </div>
                        <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight italic">Global Enrollments</h1>
                    </div>
                    <p className="text-sm font-medium text-slate-500 max-w-2xl">
                        Monitor users across all active credit programs, tracking enrollment dates and last grant distribution status.
                    </p>
                </div>
                <div className="flex gap-4">
                    <input
                        type="text"
                        placeholder="Search by email or program..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full md:w-80 bg-white/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-purple-500 transition-all outline-none"
                    />
                    <button
                        onClick={() => setIsModalOpen(true)}
                        className="flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-2xl shadow-xl shadow-purple-500/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">person_add</span>
                        Enroll User
                    </button>
                </div>
            </header>

            <div className="bg-white dark:bg-[#111827]/50 backdrop-blur-3xl border border-slate-200 dark:border-slate-800 rounded-[2.5rem] shadow-3xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">User</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Program</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Enrolled On</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Last Grant</th>
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {filtered.map((e) => (
                            <tr key={e.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <td className="px-8 py-6">
                                    <Link href={`/admin/users/${e.user_id}`} className="flex flex-col gap-1 group/link">
                                        <span className="text-sm font-bold text-slate-900 dark:text-white group-hover/link:text-purple-500 transition-colors">{e.user_email}</span>
                                        <span className="text-[10px] font-mono text-slate-500 uppercase">UID: #{e.user_id}</span>
                                    </Link>
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-2">
                                        <div className="size-2 bg-purple-500 rounded-full shadow-[0_0_8px_rgba(168,85,247,0.5)]"></div>
                                        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{e.program_name}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6">
                                    <span
                                        className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border transition-colors ${e.status === 'active'
                                            ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                            : 'bg-slate-500/10 text-slate-500 border-slate-500/20'
                                            }`}
                                    >
                                        {e.status}
                                    </span>
                                </td>
                                <td className="px-8 py-6 text-sm font-semibold text-slate-500 italic">
                                    {new Date(e.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                </td>
                                <td className="px-8 py-6">
                                    <div className="flex items-center gap-1.5">
                                        <span className="material-symbols-outlined text-[16px] text-slate-400">history</span>
                                        <span className="text-xs font-mono text-slate-500">{e.last_grant_month || 'NEVER'}</span>
                                    </div>
                                </td>
                                <td className="px-8 py-6 text-right">
                                    {e.status === 'active' && (
                                        <button
                                            onClick={() => handleUnenroll(e.user_id, e.program_id)}
                                            className="px-3 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg text-xs font-bold transition-all"
                                        >
                                            Unenroll
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {filtered.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-8 py-20 text-center">
                                    <div className="flex flex-col items-center gap-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-600">person_search</span>
                                        <p className="text-slate-400 font-bold uppercase tracking-widest text-[10px]">No enrollments match your criteria</p>
                                    </div>
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <footer className="flex justify-between items-center px-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest italic">
                    Showing {filtered.length} of {total} total enrollments
                </p>
            </footer>

            {/* Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                    <div className="bg-white dark:bg-[#111827] w-full max-w-md rounded-2xl shadow-2xl overflow-hidden border border-slate-200 dark:border-slate-800">
                        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
                            <h3 className="text-xl font-bold">Enroll User</h3>
                            <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>
                        <form onSubmit={handleEnroll} className="p-6 space-y-4">
                            <div>
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">User ID</label>
                                <input
                                    type="number"
                                    required
                                    value={formData.user_id}
                                    onChange={e => setFormData({ ...formData, user_id: e.target.value })}
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                                    placeholder="1001"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Select Program</label>
                                <select
                                    required
                                    value={formData.program_id}
                                    onChange={e => setFormData({ ...formData, program_id: e.target.value })}
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                                >
                                    <option value="">Select a program...</option>
                                    {programs.map(p => (
                                        <option key={p.id} value={p.id}>{p.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Reason (Audit Log)</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.reason}
                                    onChange={e => setFormData({ ...formData, reason: e.target.value })}
                                    className="w-full p-3 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-900/30 rounded-lg focus:ring-2 focus:ring-yellow-500 outline-none text-sm"
                                    placeholder="Why are you enrolling this user?"
                                />
                            </div>
                            <div className="flex justify-end gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setIsModalOpen(false)}
                                    className="px-4 py-2 text-slate-500 font-bold hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-6 py-2 bg-purple-600 text-white font-bold rounded-lg shadow-lg hover:bg-purple-700 transition-all"
                                >
                                    Enroll User
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
