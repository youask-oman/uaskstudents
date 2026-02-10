'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { API_BASE_URL, parseApiError } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';

interface WalletSummary {
    user_id: number;
    user_email: string;
    cached_balance: number;
    computed_balance: number;
    delta: number;
    total_lots: number;
    active_lots: number;
    pending_holds: number;
    pending_hold_credits: number;
}

interface CreditLot {
    id: number;
    lot_type: string;
    credits_total: number;
    credits_remaining: number;
    status: string;
    reason_code: string | null;
    expires_at: string | null;
    created_at: string;
}

interface LedgerEntry {
    id: number;
    event_type: string;
    status: string | null;
    credits_delta: number;
    credits_before: number;
    credits_after: number;
    reference: string | null;
    request_id: string | null;
    created_at: string;
}

export default function UserWalletPage() {
    const { token } = useAuth();
    const params = useParams();
    const userId = params.userId as string;
    const { pushToast } = useToast();

    const [wallet, setWallet] = useState<WalletSummary | null>(null);
    const [lots, setLots] = useState<CreditLot[]>([]);
    const [ledger, setLedger] = useState<LedgerEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [granting, setGranting] = useState(false);
    const [refunding, setRefunding] = useState(false);

    useEffect(() => {
        if (userId) {
            fetchData();
        }
    }, [userId]);

    const fetchData = async () => {
        try {
            const [walletRes, lotsRes, ledgerRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/admin/billing/users/${userId}/wallet`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE_URL}/api/admin/billing/users/${userId}/lots?limit=50`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE_URL}/api/admin/billing/users/${userId}/ledger?limit=50`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ]);

            if (walletRes.ok) setWallet(await walletRes.json());
            else {
                const err = await parseApiError(walletRes);
                pushToast({
                    type: "error",
                    title: "Failed to load wallet",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
            if (lotsRes.ok) {
                const data = await lotsRes.json();
                setLots(data.items);
            } else {
                const err = await parseApiError(lotsRes);
                pushToast({
                    type: "error",
                    title: "Failed to load lots",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
            if (ledgerRes.ok) {
                const data = await ledgerRes.json();
                setLedger(data.items);
            } else {
                const err = await parseApiError(ledgerRes);
                pushToast({
                    type: "error",
                    title: "Failed to load ledger",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (e) {
            console.error('Failed to load wallet');
            pushToast({
                type: "error",
                title: "Failed to load wallet",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setLoading(false);
        }
    };

    const grantCredits = async () => {
        const credits = prompt('Enter credit amount to grant:');
        if (!credits) return;

        const reason = prompt('Enter reason for grant:');
        if (!reason) return;

        setGranting(true);
        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/billing/users/${userId}/lots`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    credits: parseFloat(credits),
                    reason,
                    expires_days: 30,
                    lot_type: 'ADJUSTMENT',
                    idempotency_key: `grant_${userId}_${Date.now()}`,
                }),
            });
            if (res.ok) {
                fetchData();
                pushToast({
                    type: "success",
                    title: "Credits granted",
                    message: "Adjustment lot created successfully.",
                });
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Grant failed",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (e) {
            pushToast({
                type: "error",
                title: "Grant failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setGranting(false);
        }
    };

    const refundCredits = async () => {
        const credits = prompt('Enter credit amount to refund:');
        if (!credits) return;

        const reason = prompt('Enter reason for refund:');
        if (!reason) return;

        setRefunding(true);
        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/billing/users/${userId}/refund`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    credits: parseFloat(credits),
                    reason,
                    reason_code: 'SERVICE_ISSUE',
                    source_payment_id: `manual_refund_${Date.now()}`,
                    idempotency_key: `refund_${userId}_${Date.now()}`,
                }),
            });
            if (res.ok) {
                fetchData();
                pushToast({
                    type: "success",
                    title: "Refund issued",
                    message: "Refund credit lot created successfully.",
                });
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Refund failed",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (e) {
            pushToast({
                type: "error",
                title: "Refund failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        } finally {
            setRefunding(false);
        }
    };

    const forceReconcile = async () => {
        if (!confirm("Force reconcile this user's balance?")) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/admin/billing/users/${userId}/reconcile`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                body: JSON.stringify({
                    reason: "Manual reconcile from wallet page",
                    idempotency_key: `reconcile_${userId}_${Date.now()}`,
                }),
            });
            if (res.ok) {
                const data = await res.json();
                pushToast({
                    type: "success",
                    title: "Reconciled",
                    message: `Balance ${data.old_balance} -> ${data.new_balance} (delta ${data.delta})`,
                });
                fetchData();
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Reconcile failed",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (e) {
            pushToast({
                type: "error",
                title: "Reconcile failed",
                message: e instanceof Error ? e.message : "Unexpected error",
            });
        }
    };

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    if (!wallet) {
        return <div className="p-8 text-red-500">User not found</div>;
    }

    return (
        <div className="p-8 max-w-6xl">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold">User Wallet</h1>
                    <p className="text-gray-500">{wallet.user_email} (ID: {wallet.user_id})</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={forceReconcile}
                        className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded"
                    >
                        Force Reconcile
                    </button>
                    <button
                        onClick={refundCredits}
                        disabled={refunding}
                        className="bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded"
                    >
                        {refunding ? 'Refunding...' : 'Issue Refund'}
                    </button>
                    <button
                        onClick={grantCredits}
                        disabled={granting}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
                    >
                        {granting ? 'Granting...' : '+ Grant Credits'}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-white border rounded-lg p-4">
                    <div className="text-2xl font-bold">{wallet.cached_balance.toFixed(2)}</div>
                    <div className="text-sm text-gray-500">Cached Balance</div>
                </div>
                <div className="bg-white border rounded-lg p-4">
                    <div className="text-2xl font-bold">{wallet.computed_balance.toFixed(2)}</div>
                    <div className="text-sm text-gray-500">Computed Balance</div>
                </div>
                <div className="bg-white border rounded-lg p-4">
                    <div className={`text-2xl font-bold ${Math.abs(wallet.delta) > 0.01 ? 'text-red-600' : 'text-green-600'}`}>
                        {wallet.delta.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-500">Delta</div>
                </div>
                <div className="bg-white border rounded-lg p-4">
                    <div className="text-2xl font-bold">{wallet.pending_holds}</div>
                    <div className="text-sm text-gray-500">Pending Holds ({wallet.pending_hold_credits.toFixed(2)} credits)</div>
                </div>
            </div>

            <h2 className="text-xl font-bold mb-4">Credit Lots ({wallet.active_lots} active / {wallet.total_lots} total)</h2>
            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">ID</th>
                            <th className="px-4 py-3 text-left">Type</th>
                            <th className="px-4 py-3 text-left">Total</th>
                            <th className="px-4 py-3 text-left">Remaining</th>
                            <th className="px-4 py-3 text-left">Status</th>
                            <th className="px-4 py-3 text-left">Reason</th>
                            <th className="px-4 py-3 text-left">Expires</th>
                        </tr>
                    </thead>
                    <tbody>
                        {lots.map((lot) => (
                            <tr key={lot.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 font-mono">{lot.id}</td>
                                <td className="px-4 py-3">{lot.lot_type || 'TOPUP'}</td>
                                <td className="px-4 py-3">{lot.credits_total.toFixed(2)}</td>
                                <td className="px-4 py-3 font-medium">{lot.credits_remaining.toFixed(2)}</td>
                                <td className="px-4 py-3">
                                    <span
                                        className={`px-2 py-1 rounded text-xs ${lot.status === 'ACTIVE'
                                            ? 'bg-green-100 text-green-700'
                                            : 'bg-gray-100 text-gray-700'
                                            }`}
                                    >
                                        {lot.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-xs">{lot.reason_code || '-'}</td>
                                <td className="px-4 py-3 text-gray-500">
                                    {lot.expires_at ? new Date(lot.expires_at).toLocaleDateString() : 'Never'}
                                </td>
                            </tr>
                        ))}
                        {lots.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                                    No credit lots found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <h2 className="text-xl font-bold mb-4 mt-8">Ledger Entries</h2>
            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">Time</th>
                            <th className="px-4 py-3 text-left">Event</th>
                            <th className="px-4 py-3 text-left">Delta</th>
                            <th className="px-4 py-3 text-left">Balance</th>
                            <th className="px-4 py-3 text-left">Reference</th>
                            <th className="px-4 py-3 text-left">Request</th>
                        </tr>
                    </thead>
                    <tbody>
                        {ledger.map((entry) => (
                            <tr key={entry.id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3 text-xs text-gray-500">
                                    {new Date(entry.created_at).toLocaleString()}
                                </td>
                                <td className="px-4 py-3 text-xs font-semibold">{entry.event_type}</td>
                                <td className={`px-4 py-3 text-xs font-bold ${entry.credits_delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {entry.credits_delta.toFixed(2)}
                                </td>
                                <td className="px-4 py-3 text-xs font-mono text-gray-600">
                                    {entry.credits_before.toFixed(2)} → {entry.credits_after.toFixed(2)}
                                </td>
                                <td className="px-4 py-3 text-xs text-gray-500">{entry.reference || '-'}</td>
                                <td className="px-4 py-3 text-xs font-mono text-gray-500">{entry.request_id || '-'}</td>
                            </tr>
                        ))}
                        {ledger.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                                    No ledger entries found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="mt-6 flex gap-4">
                <Link
                    href={`/admin/billing/ledger?user_id=${userId}`}
                    className="text-blue-600 hover:underline"
                >
                    View Ledger →
                </Link>
                <Link
                    href={`/admin/billing/holds?user_id=${userId}`}
                    className="text-blue-600 hover:underline"
                >
                    View Holds →
                </Link>
            </div>
        </div>
    );
}
