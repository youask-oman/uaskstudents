'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface FeatureFlags {
    billing_v2_enabled: boolean;
    billing_v2_rollout_percent: number;
    credit_programs_enabled: boolean;
    refund_v2_enabled: boolean;
    reconciliation_autofix_enabled: boolean;
    admin_ids: number[];
}

interface AuditEntry {
    id: number;
    admin_user_id: number;
    admin_email: string;
    flag_name: string;
    old_value: string;
    new_value: string;
    reason: string;
    created_at: string;
}

export default function BillingFlagsPage() {
    const { token } = useAuth();
    const [flags, setFlags] = useState<FeatureFlags | null>(null);
    const [audit, setAudit] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [reason, setReason] = useState('');
    const [error, setError] = useState('');

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000';

    const fetchFlags = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/flags`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                setFlags(await res.json());
            }
        } catch (err) {
            console.error("Failed to load flags", err);
            setError('Failed to load flags');
        } finally {
            setLoading(false);
        }
    }, [API_BASE, token]);

    const fetchAudit = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/flags/audit?limit=20`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                setAudit(await res.json());
            }
        } catch (err) {
            console.error('Failed to load audit', err);
        }
    }, [API_BASE, token]);

    useEffect(() => {
        if (token) {
            fetchFlags();
            fetchAudit();
        }
    }, [token, fetchFlags, fetchAudit]);

    const updateFlags = async (updates: Partial<FeatureFlags>) => {
        if (!reason.trim()) {
            setError('Reason is required');
            return;
        }
        setSaving(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/flags`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ ...updates, reason }),
            });
            if (res.ok) {
                setFlags(await res.json());
                setReason('');
                fetchAudit();
            } else {
                const data = await res.json();
                setError(data.detail || 'Failed to update');
            }
        } catch (err) {
            console.error("Failed to update flags", err);
            setError('Failed to update flags');
        } finally {
            setSaving(false);
        }
    };

    const killSwitch = async () => {
        if (!confirm('âš ï¸ KILL SWITCH: This will disable ALL Billing V2 features immediately. Continue?')) {
            return;
        }
        await updateFlags({
            billing_v2_enabled: false,
            billing_v2_rollout_percent: 0,
            credit_programs_enabled: false,
            refund_v2_enabled: false,
        });
    };

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    if (!flags) {
        return <div className="p-8 text-red-500">Failed to load feature flags</div>;
    }

    return (
        <div className="p-8 max-w-4xl">
            <h1 className="text-2xl font-bold mb-6">ðŸš€ Billing Feature Flags</h1>

            {error && (
                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                    {error}
                </div>
            )}

            {/* Kill Switch */}
            <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 mb-6">
                <h2 className="text-lg font-bold text-red-700 mb-2">ðŸ›‘ Emergency Kill Switch</h2>
                <p className="text-sm text-gray-600 mb-3">
                    Immediately disable all Billing V2 features. Use only in emergencies.
                </p>
                <button
                    onClick={killSwitch}
                    disabled={saving}
                    className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
                >
                    {saving ? 'Processing...' : 'ACTIVATE KILL SWITCH'}
                </button>
            </div>

            {/* Reason Input */}
            <div className="mb-6">
                <label className="block text-sm font-medium mb-2">Change Reason (required)</label>
                <input
                    type="text"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="w-full border rounded px-3 py-2"
                    placeholder="e.g., Enabling for 10% rollout after monitoring"
                />
            </div>

            {/* Flags Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                {/* Billing V2 Enabled */}
                <div className="bg-white border rounded-lg p-4">
                    <div className="flex justify-between items-center">
                        <div>
                            <h3 className="font-medium">Billing V2 Enabled</h3>
                            <p className="text-sm text-gray-500">Master switch for all V2 features</p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={flags.billing_v2_enabled}
                                onChange={(e) => updateFlags({ billing_v2_enabled: e.target.checked })}
                                disabled={saving}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 rounded-full peer peer-checked:bg-blue-600"></div>
                        </label>
                    </div>
                </div>

                {/* Rollout Percent */}
                <div className="bg-white border rounded-lg p-4">
                    <h3 className="font-medium">Rollout Percentage</h3>
                    <p className="text-sm text-gray-500 mb-2">% of users on V2</p>
                    <div className="flex items-center gap-2">
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={flags.billing_v2_rollout_percent}
                            onChange={(e) => updateFlags({ billing_v2_rollout_percent: parseInt(e.target.value) })}
                            disabled={saving}
                            className="flex-1"
                        />
                        <span className="font-mono w-12 text-right">{flags.billing_v2_rollout_percent}%</span>
                    </div>
                </div>

                {/* Credit Programs */}
                <div className="bg-white border rounded-lg p-4">
                    <div className="flex justify-between items-center">
                        <div>
                            <h3 className="font-medium">Credit Programs</h3>
                            <p className="text-sm text-gray-500">Enable credit program logic</p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={flags.credit_programs_enabled}
                                onChange={(e) => updateFlags({ credit_programs_enabled: e.target.checked })}
                                disabled={saving}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 rounded-full peer peer-checked:bg-blue-600"></div>
                        </label>
                    </div>
                </div>

                {/* Refund V2 */}
                <div className="bg-white border rounded-lg p-4">
                    <div className="flex justify-between items-center">
                        <div>
                            <h3 className="font-medium">Refund V2</h3>
                            <p className="text-sm text-gray-500">New refund logic with expiry</p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={flags.refund_v2_enabled}
                                onChange={(e) => updateFlags({ refund_v2_enabled: e.target.checked })}
                                disabled={saving}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 rounded-full peer peer-checked:bg-blue-600"></div>
                        </label>
                    </div>
                </div>

                {/* Reconciliation Autofix */}
                <div className="bg-white border rounded-lg p-4">
                    <div className="flex justify-between items-center">
                        <div>
                            <h3 className="font-medium">Reconciliation Autofix</h3>
                            <p className="text-sm text-gray-500">Auto-correct balance mismatches</p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={flags.reconciliation_autofix_enabled}
                                onChange={(e) => updateFlags({ reconciliation_autofix_enabled: e.target.checked })}
                                disabled={saving}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 rounded-full peer peer-checked:bg-blue-600"></div>
                        </label>
                    </div>
                </div>

                {/* Admin IDs */}
                <div className="bg-white border rounded-lg p-4">
                    <h3 className="font-medium">Admin Override IDs</h3>
                    <p className="text-sm text-gray-500 mb-2">Users always on V2</p>
                    <div className="font-mono text-sm bg-gray-100 p-2 rounded">
                        {flags.admin_ids.length > 0 ? flags.admin_ids.join(', ') : 'None'}
                    </div>
                </div>
            </div>

            {/* Audit Log */}
            <h2 className="text-xl font-bold mb-4">ðŸ“‹ Change History</h2>
            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-2 text-left">Time</th>
                            <th className="px-4 py-2 text-left">Admin</th>
                            <th className="px-4 py-2 text-left">Flag</th>
                            <th className="px-4 py-2 text-left">Change</th>
                            <th className="px-4 py-2 text-left">Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {audit.map((entry) => (
                            <tr key={entry.id} className="border-t">
                                <td className="px-4 py-2 text-gray-500">
                                    {new Date(entry.created_at).toLocaleString()}
                                </td>
                                <td className="px-4 py-2">{entry.admin_email}</td>
                                <td className="px-4 py-2 font-mono text-xs">{entry.flag_name}</td>
                                <td className="px-4 py-2">
                                    <span className="text-red-500">{entry.old_value}</span>
                                    {' â†’ '}
                                    <span className="text-green-500">{entry.new_value}</span>
                                </td>
                                <td className="px-4 py-2 text-gray-600">{entry.reason}</td>
                            </tr>
                        ))}
                        {audit.length === 0 && (
                            <tr>
                                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                                    No changes recorded yet
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

