'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface Hold {
    id: number;
    user_id: number;
    user_email: string;
    request_id: string;
    reserved_credits: number;
    status: string;
    created_at: string;
    age_seconds: number;
}

interface HoldStats {
    active_holds: number;
    stuck_holds_1hr: number;
    max_age_seconds: number;
    total_reserved_credits: number;
}

export default function HoldsPage() {
    const { token } = useAuth();
    const [holds, setHolds] = useState<Hold[]>([]);
    const [stats, setStats] = useState<HoldStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [releasing, setReleasing] = useState<number | null>(null);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [holdsRes, statsRes] = await Promise.all([
                fetch(`${API_BASE}/admin/billing/holds?status=held&limit=50`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE}/admin/billing/holds/stats`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ]);

            if (holdsRes.ok) {
                const data = await holdsRes.json();
                setHolds(data.items);
            }
            if (statsRes.ok) {
                setStats(await statsRes.json());
            }
        } catch (e) {
            console.error('Failed to load holds');
        } finally {
            setLoading(false);
        }
    };

    const releaseHold = async (holdId: number) => {
        const reason = prompt('Enter reason for releasing this hold:');
        if (!reason) return;

        setReleasing(holdId);
        try {
            const res = await fetch(`${API_BASE}/admin/billing/holds/${holdId}/release`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ reason }),
            });
            if (res.ok) {
                fetchData();
            } else {
                alert('Failed to release hold');
            }
        } catch (e) {
            alert('Error releasing hold');
        } finally {
            setReleasing(null);
        }
    };

    const formatAge = (seconds: number) => {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
    };

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    return (
        <div className="p-8 max-w-6xl">
            <h1 className="text-2xl font-bold mb-6">⏳ Holds & Settlement</h1>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-white border rounded-lg p-4">
                        <div className="text-2xl font-bold">{stats.active_holds}</div>
                        <div className="text-sm text-gray-500">Active Holds</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className="text-2xl font-bold text-orange-600">{stats.stuck_holds_1hr}</div>
                        <div className="text-sm text-gray-500">Stuck (&gt;1hr)</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className="text-2xl font-bold">{formatAge(stats.max_age_seconds)}</div>
                        <div className="text-sm text-gray-500">Max Age</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className="text-2xl font-bold">{stats.total_reserved_credits.toFixed(2)}</div>
                        <div className="text-sm text-gray-500">Reserved Credits</div>
                    </div>
                </div>
            )}

            {/* Holds Table */}
            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">ID</th>
                            <th className="px-4 py-3 text-left">User</th>
                            <th className="px-4 py-3 text-left">Request ID</th>
                            <th className="px-4 py-3 text-left">Credits</th>
                            <th className="px-4 py-3 text-left">Age</th>
                            <th className="px-4 py-3 text-left">Status</th>
                            <th className="px-4 py-3 text-left">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {holds.map((hold) => (
                            <tr key={hold.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 font-mono">{hold.id}</td>
                                <td className="px-4 py-3">
                                    <div>{hold.user_email}</div>
                                    <div className="text-xs text-gray-400">ID: {hold.user_id}</div>
                                </td>
                                <td className="px-4 py-3 font-mono text-xs">{hold.request_id.slice(0, 8)}...</td>
                                <td className="px-4 py-3">{hold.reserved_credits.toFixed(2)}</td>
                                <td className={`px-4 py-3 ${hold.age_seconds > 3600 ? 'text-red-600 font-bold' : ''}`}>
                                    {formatAge(hold.age_seconds)}
                                </td>
                                <td className="px-4 py-3">
                                    <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs">
                                        {hold.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <button
                                        onClick={() => releaseHold(hold.id)}
                                        disabled={releasing === hold.id}
                                        className="text-red-600 hover:text-red-800 text-xs"
                                    >
                                        {releasing === hold.id ? 'Releasing...' : 'Force Release'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {holds.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                                    No active holds ✓
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
