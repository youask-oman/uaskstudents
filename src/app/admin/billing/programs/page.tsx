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
        return <div className="p-8">Loading...</div>;
    }

    return (
        <div className="p-8 max-w-6xl">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">💳 Credit Programs</h1>
                <Link
                    href="/admin/billing/programs/enrollments"
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
                >
                    View Enrollments
                </Link>
            </div>

            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">ID</th>
                            <th className="px-4 py-3 text-left">Name</th>
                            <th className="px-4 py-3 text-left">Slug</th>
                            <th className="px-4 py-3 text-left">Status</th>
                            <th className="px-4 py-3 text-left">Monthly Credits</th>
                            <th className="px-4 py-3 text-left">Expiry Days</th>
                            <th className="px-4 py-3 text-left">Enrollments</th>
                        </tr>
                    </thead>
                    <tbody>
                        {programs.map((program) => (
                            <tr key={program.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 font-mono">{program.id}</td>
                                <td className="px-4 py-3 font-medium">{program.name}</td>
                                <td className="px-4 py-3 font-mono text-xs">{program.slug}</td>
                                <td className="px-4 py-3">
                                    <span
                                        className={`px-2 py-1 rounded text-xs ${program.status === 'active'
                                                ? 'bg-green-100 text-green-700'
                                                : 'bg-gray-100 text-gray-700'
                                            }`}
                                    >
                                        {program.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    {program.monthly_gift_credits?.toFixed(2) || '-'}
                                </td>
                                <td className="px-4 py-3">{program.gift_expiry_window_days}</td>
                                <td className="px-4 py-3 font-medium">{program.enrollment_count}</td>
                            </tr>
                        ))}
                        {programs.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                                    No credit programs found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="mt-4 text-sm text-gray-500">
                Showing {programs.length} of {total} programs
            </div>
        </div>
    );
}
