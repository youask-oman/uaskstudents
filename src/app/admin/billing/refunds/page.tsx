'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface Refund {
    id: number;
    user_id: number;
    user_email: string;
    credits: number;
    reason_code: string;
    source_attempt_id: string | null;
    expires_at: string | null;
    created_at: string;
}

export default function RefundsPage() {
    const { token } = useAuth();
    const [refunds, setRefunds] = useState<Refund[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [creating, setCreating] = useState(false);

    // Create form state
    const [userId, setUserId] = useState('');
    const [credits, setCredits] = useState('');
    const [reasonCode, setReasonCode] = useState('SERVICE_ISSUE');
    const [reason, setReason] = useState('');

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchRefunds();
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

    const createRefund = async () => {
        if (!userId || !credits || !reason) {
            alert('All fields are required');
            return;
        }

        setCreating(true);
        try {
            const res = await fetch(`${API_BASE}/admin/billing/refunds`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    user_id: parseInt(userId),
                    credits: parseFloat(credits),
                    reason_code: reasonCode,
                    reason,
                }),
            });
            if (res.ok) {
                setShowCreate(false);
                setUserId('');
                setCredits('');
                setReason('');
                fetchRefunds();
            } else {
                const data = await res.json();
                alert(data.detail || 'Failed to create refund');
            }
        } catch (e) {
            alert('Error creating refund');
        } finally {
            setCreating(false);
        }
    };

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    return (
        <div className="p-8 max-w-6xl">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">💸 Refund Center</h1>
                <button
                    onClick={() => setShowCreate(!showCreate)}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
                >
                    {showCreate ? 'Cancel' : '+ Create Refund'}
                </button>
            </div>

            {/* Create Form */}
            {showCreate && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                    <h2 className="font-bold mb-4">Create Refund</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium mb-1">User ID</label>
                            <input
                                type="number"
                                value={userId}
                                onChange={(e) => setUserId(e.target.value)}
                                className="w-full border rounded px-3 py-2"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Credits</label>
                            <input
                                type="number"
                                step="0.01"
                                value={credits}
                                onChange={(e) => setCredits(e.target.value)}
                                className="w-full border rounded px-3 py-2"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Reason Code</label>
                            <select
                                value={reasonCode}
                                onChange={(e) => setReasonCode(e.target.value)}
                                className="w-full border rounded px-3 py-2"
                            >
                                <option value="SERVICE_ISSUE">Service Issue</option>
                                <option value="PAYMENT_REVERSAL">Payment Reversal</option>
                                <option value="ADMIN_ADJUSTMENT">Admin Adjustment</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Reason</label>
                            <input
                                type="text"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                className="w-full border rounded px-3 py-2"
                                placeholder="Why is this refund being issued?"
                            />
                        </div>
                    </div>
                    <button
                        onClick={createRefund}
                        disabled={creating}
                        className="mt-4 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
                    >
                        {creating ? 'Creating...' : 'Create Refund'}
                    </button>
                </div>
            )}

            {/* Refunds Table */}
            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">ID</th>
                            <th className="px-4 py-3 text-left">User</th>
                            <th className="px-4 py-3 text-left">Credits</th>
                            <th className="px-4 py-3 text-left">Reason Code</th>
                            <th className="px-4 py-3 text-left">Source</th>
                            <th className="px-4 py-3 text-left">Expires</th>
                            <th className="px-4 py-3 text-left">Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {refunds.map((r) => (
                            <tr key={r.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 font-mono">{r.id}</td>
                                <td className="px-4 py-3">
                                    <div>{r.user_email}</div>
                                    <div className="text-xs text-gray-400">ID: {r.user_id}</div>
                                </td>
                                <td className="px-4 py-3 font-medium text-green-600">
                                    +{r.credits.toFixed(2)}
                                </td>
                                <td className="px-4 py-3">
                                    <span className="px-2 py-1 bg-gray-100 rounded text-xs">
                                        {r.reason_code}
                                    </span>
                                </td>
                                <td className="px-4 py-3 font-mono text-xs">
                                    {r.source_attempt_id?.slice(0, 8) || '-'}
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    {r.expires_at ? new Date(r.expires_at).toLocaleDateString() : '-'}
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    {new Date(r.created_at).toLocaleDateString()}
                                </td>
                            </tr>
                        ))}
                        {refunds.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                                    No refunds found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
