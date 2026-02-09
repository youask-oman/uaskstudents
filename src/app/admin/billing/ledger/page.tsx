'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface LedgerEntry {
    id: number;
    user_id: number;
    user_email: string;
    action_type: string;
    request_id: string;
    status: string;
    credits_charged: number | null;
    credits_before: number | null;
    credits_after: number | null;
    provider_cost_usd: number | null;
    tier: string | null;
    created_at: string;
}

export default function LedgerPage() {
    const { token } = useAuth();
    const [entries, setEntries] = useState<LedgerEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);

    // Filters
    const [userId, setUserId] = useState('');
    const [requestId, setRequestId] = useState('');
    const [status, setStatus] = useState('');

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchLedger();
    }, []);

    const fetchLedger = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.append('limit', '50');
            if (userId) params.append('user_id', userId);
            if (requestId) params.append('request_id', requestId);
            if (status) params.append('status', status);

            const res = await fetch(`${API_BASE}/admin/billing/ledger?${params}`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setEntries(data.items);
                setTotal(data.total);
            }
        } catch (e) {
            console.error('Failed to load ledger');
        } finally {
            setLoading(false);
        }
    };

    const applyFilters = () => {
        fetchLedger();
    };

    return (
        <div className="p-8 max-w-7xl">
            <h1 className="text-2xl font-bold mb-6">📒 Ledger Explorer</h1>

            {/* Filters */}
            <div className="bg-gray-50 border rounded-lg p-4 mb-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">User ID</label>
                        <input
                            type="number"
                            value={userId}
                            onChange={(e) => setUserId(e.target.value)}
                            className="w-full border rounded px-3 py-2"
                            placeholder="e.g., 123"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1">Request ID</label>
                        <input
                            type="text"
                            value={requestId}
                            onChange={(e) => setRequestId(e.target.value)}
                            className="w-full border rounded px-3 py-2"
                            placeholder="e.g., abc123..."
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1">Status</label>
                        <select
                            value={status}
                            onChange={(e) => setStatus(e.target.value)}
                            className="w-full border rounded px-3 py-2"
                        >
                            <option value="">All</option>
                            <option value="CHARGED">Charged</option>
                            <option value="VOIDED">Voided</option>
                            <option value="PENDING">Pending</option>
                            <option value="ERROR">Error</option>
                        </select>
                    </div>
                    <div className="flex items-end">
                        <button
                            onClick={applyFilters}
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
                        >
                            Search
                        </button>
                    </div>
                </div>
            </div>

            {/* Ledger Table */}
            <div className="bg-white border rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">ID</th>
                            <th className="px-4 py-3 text-left">User</th>
                            <th className="px-4 py-3 text-left">Action</th>
                            <th className="px-4 py-3 text-left">Status</th>
                            <th className="px-4 py-3 text-left">Credits</th>
                            <th className="px-4 py-3 text-left">Before</th>
                            <th className="px-4 py-3 text-left">After</th>
                            <th className="px-4 py-3 text-left">Cost (USD)</th>
                            <th className="px-4 py-3 text-left">Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {entries.map((e) => (
                            <tr key={e.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 font-mono">{e.id}</td>
                                <td className="px-4 py-3">
                                    <div className="text-xs">{e.user_email}</div>
                                    <div className="text-xs text-gray-400">#{e.user_id}</div>
                                </td>
                                <td className="px-4 py-3">{e.action_type}</td>
                                <td className="px-4 py-3">
                                    <span
                                        className={`px-2 py-1 rounded text-xs ${e.status === 'CHARGED'
                                                ? 'bg-green-100 text-green-700'
                                                : e.status === 'ERROR'
                                                    ? 'bg-red-100 text-red-700'
                                                    : 'bg-gray-100 text-gray-700'
                                            }`}
                                    >
                                        {e.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 font-medium">
                                    {e.credits_charged?.toFixed(2) || '-'}
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    {e.credits_before?.toFixed(2) || '-'}
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    {e.credits_after?.toFixed(2) || '-'}
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    ${e.provider_cost_usd?.toFixed(4) || '-'}
                                </td>
                                <td className="px-4 py-3 text-gray-500 text-xs">
                                    {new Date(e.created_at).toLocaleString()}
                                </td>
                            </tr>
                        ))}
                        {entries.length === 0 && !loading && (
                            <tr>
                                <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                                    No ledger entries found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="mt-4 text-sm text-gray-500">
                Showing {entries.length} of {total} entries
            </div>
        </div>
    );
}
