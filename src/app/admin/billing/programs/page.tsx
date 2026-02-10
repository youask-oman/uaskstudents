'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import { API_BASE_URL, parseApiError } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';

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
    const { pushToast } = useToast();
    const [programs, setPrograms] = useState<Program[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingProgram, setEditingProgram] = useState<Program | null>(null);
    const [formData, setFormData] = useState({
        name: '',
        slug: '',
        description: '',
        monthly_gift_credits: 0,
        gift_expiry_window_days: 30,
        reason: ''
    });

    useEffect(() => {
        fetchPrograms();
    }, []);

    const fetchPrograms = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/billing/programs?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setPrograms(data.items);
                setTotal(data.total);
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Failed to load programs",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (e) {
            console.error('Failed to load programs');
            pushToast({
                type: "error",
                title: "Failed to load programs",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setLoading(false);
        }
    };

    const handleOpenCreate = () => {
        setEditingProgram(null);
        setFormData({
            name: '',
            slug: '',
            description: '',
            monthly_gift_credits: 0,
            gift_expiry_window_days: 30,
            reason: ''
        });
        setIsModalOpen(true);
    };

    const handleOpenEdit = (program: Program) => {
        setEditingProgram(program);
        setFormData({
            name: program.name,
            slug: program.slug,
            description: program.description || '',
            monthly_gift_credits: program.monthly_gift_credits || 0,
            gift_expiry_window_days: program.gift_expiry_window_days,
            reason: ''
        });
        setIsModalOpen(true);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const url = editingProgram
                ? `${API_BASE_URL}/api/admin/billing/programs/${editingProgram.id}`
                : `${API_BASE_URL}/api/admin/billing/programs`;

            const method = editingProgram ? 'PUT' : 'POST';
            const idempotencyKey = `${editingProgram ? "program_update" : "program_create"}_${Date.now()}`;

            const payload: any = {
                name: formData.name,
                description: formData.description,
                monthly_gift_credits: formData.monthly_gift_credits,
                gift_expiry_window_days: formData.gift_expiry_window_days,
                reason: formData.reason,
                idempotency_key: idempotencyKey
            };

            if (!editingProgram) {
                payload.slug = formData.slug;
                payload.status = 'active';
            }

            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                setIsModalOpen(false);
                fetchPrograms();
                pushToast({
                    type: "success",
                    title: editingProgram ? "Program updated" : "Program created",
                    message: `${formData.name} saved successfully.`,
                });
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Failed to save program",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (error) {
            console.error(error);
            pushToast({
                type: "error",
                title: "Failed to save program",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        }
    };

    const handleDeactivate = async (id: number) => {
        const reason = prompt("Enter reason for deactivation:");
        if (!reason) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/billing/programs/${id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({ reason, idempotency_key: `program_deactivate_${id}_${Date.now()}` })
            });

            if (res.ok) {
                fetchPrograms();
                pushToast({
                    type: "success",
                    title: "Program archived",
                    message: "The program has been archived successfully.",
                });
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Failed to archive program",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (error) {
            console.error(error);
            pushToast({
                type: "error",
                title: "Failed to archive program",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        }
    };

    if (loading && programs.length === 0) {
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
                        onClick={handleOpenCreate}
                        data-testid="program-new"
                        className="flex items-center gap-2 px-6 py-3 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-2xl shadow-xl shadow-admin-primary/25 transition-all"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        New Program
                    </button>
                </div>
            </header>

            {/* Stats */}
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
            </div>

            {/* Table */}
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
                            <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {programs.map((program, index) => (
                            <tr key={`${program.id}-${index}`} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
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
                                <td className="px-8 py-6 text-right">
                                    <div className="flex justify-end gap-2">
                                        <button
                                            onClick={() => handleOpenEdit(program)}
                                            data-testid={`program-edit-${program.id}`}
                                            className="p-2 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg text-slate-500 transition-colors"
                                        >
                                            <span className="material-symbols-outlined text-[18px]">edit</span>
                                        </button>
                                        {program.status !== 'archived' && (
                                            <button
                                                onClick={() => handleDeactivate(program.id)}
                                                data-testid={`program-archive-${program.id}`}
                                                className="p-2 hover:bg-red-100 dark:hover:bg-red-900/20 rounded-lg text-red-500 transition-colors"
                                            >
                                                <span className="material-symbols-outlined text-[18px]">archive</span>
                                            </button>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ))}
                        {programs.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-8 py-20 text-center">
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
            </footer>

            {/* Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                    <div className="bg-white dark:bg-[#111827] w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden border border-slate-200 dark:border-slate-800">
                        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
                            <h3 className="text-xl font-bold">{editingProgram ? 'Edit Program' : 'Create Program'}</h3>
                            <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            {!editingProgram && (
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Slug (Unique ID)</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.slug}
                                    onChange={e => setFormData({ ...formData, slug: e.target.value })}
                                    data-testid="program-slug"
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none font-mono text-sm"
                                    placeholder="e.g. pro-plan-2026"
                                />
                                </div>
                            )}
                            <div>
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Program Name</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.name}
                                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                                    data-testid="program-name"
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                    placeholder="Pro Membership"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Description</label>
                                <textarea
                                    value={formData.description}
                                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                                    className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                    rows={2}
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Monthly Credits</label>
                                    <input
                                        type="number"
                                        required
                                        value={formData.monthly_gift_credits}
                                        onChange={e => setFormData({ ...formData, monthly_gift_credits: parseFloat(e.target.value) })}
                                        className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Expiry Days</label>
                                    <input
                                        type="number"
                                        required
                                        value={formData.gift_expiry_window_days}
                                        onChange={e => setFormData({ ...formData, gift_expiry_window_days: parseInt(e.target.value) })}
                                        className="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-admin-primary outline-none"
                                    />
                                </div>
                            </div>

                            {/* Audit Reason */}
                            <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
                                <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Change Reason (Audit Log)</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.reason}
                                    onChange={e => setFormData({ ...formData, reason: e.target.value })}
                                    data-testid="program-reason"
                                    className="w-full p-3 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-900/30 rounded-lg focus:ring-2 focus:ring-yellow-500 outline-none text-sm"
                                    placeholder="Why are you making this change?"
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
                                    data-testid="program-submit"
                                    className="px-6 py-2 bg-admin-primary text-white font-bold rounded-lg shadow-lg hover:bg-blue-600 transition-all"
                                >
                                    {editingProgram ? 'Save Changes' : 'Create Program'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
