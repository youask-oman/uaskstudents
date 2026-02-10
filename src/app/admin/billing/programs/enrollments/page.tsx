'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';

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

export default function EnrollmentsPage() {
    const { token } = useAuth();
    const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [total, setTotal] = useState(0);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    const fetchEnrollments = useCallback(async () => {
        try {
            // Fetch from all programs (first get programs, then enrollments)
            const progRes = await fetch(`${API_BASE}/api/admin/billing/programs?limit=100`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (progRes.ok) {
                const progData = await progRes.json();
                const allEnrollments: Enrollment[] = [];

                for (const program of progData.items.slice(0, 10)) {
                    const enrollRes = await fetch(
                        `${API_BASE}/api/admin/billing/programs/${program.id}/enrollments?limit=50`,
                        { headers: { Authorization: `Bearer ${token}` } }
                    );
                    if (enrollRes.ok) {
                        const data = await enrollRes.json();
                        allEnrollments.push(...data.items);
                    }
                }
                setEnrollments(allEnrollments);
                setTotal(allEnrollments.length);
            }
        } catch (err) {
            console.error('Failed to load enrollments', err);
        } finally {
            setLoading(false);
        }
    }, [API_BASE, token]);

    useEffect(() => {
        fetchEnrollments();
    }, [fetchEnrollments]);

    const filtered = search
        ? enrollments.filter(
            (e) =>
                e.user_email?.toLowerCase().includes(search.toLowerCase()) ||
                e.program_name?.toLowerCase().includes(search.toLowerCase())
        )
        : enrollments;

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    return (
        <div className="p-8 max-w-6xl">
            <h1 className="text-2xl font-bold mb-6">👥 Program Enrollments</h1>

            <div className="mb-4">
                <input
                    type="text"
                    placeholder="Search by email or program..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full md:w-80 border rounded px-3 py-2"
                />
            </div>

            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">User ID</th>
                            <th className="px-4 py-3 text-left">Email</th>
                            <th className="px-4 py-3 text-left">Program</th>
                            <th className="px-4 py-3 text-left">Status</th>
                            <th className="px-4 py-3 text-left">Started</th>
                            <th className="px-4 py-3 text-left">Last Grant</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((e) => (
                            <tr key={e.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 font-mono">{e.user_id}</td>
                                <td className="px-4 py-3">{e.user_email}</td>
                                <td className="px-4 py-3">{e.program_name}</td>
                                <td className="px-4 py-3">
                                    <span
                                        className={`px-2 py-1 rounded text-xs ${e.status === 'active'
                                                ? 'bg-green-100 text-green-700'
                                                : 'bg-gray-100 text-gray-700'
                                            }`}
                                    >
                                        {e.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    {new Date(e.started_at).toLocaleDateString()}
                                </td>
                                <td className="px-4 py-3 font-mono text-xs">{e.last_grant_month || '-'}</td>
                            </tr>
                        ))}
                        {filtered.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                                    No enrollments found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="mt-4 text-sm text-gray-500">
                Showing {filtered.length} of {total} enrollments
            </div>
        </div>
    );
}
