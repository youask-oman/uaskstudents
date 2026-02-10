'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface HealthDashboard {
    mismatch_count_today: number;
    mismatch_count_7d: number;
    stuck_holds_count: number;
    stuck_holds_p95_age: number;
    billing_errors_24h: number;
    autofix_enabled: boolean;
}

interface Mismatch {
    user_id: number;
    user_email: string;
    cached_balance: number;
    computed_balance: number;
    delta: number;
    last_fix_time: string | null;
}

export default function HealthPage() {
    const { token } = useAuth();
    const [health, setHealth] = useState<HealthDashboard | null>(null);
    const [mismatches, setMismatches] = useState<Mismatch[]>([]);
    const [loading, setLoading] = useState(true);
    const [running, setRunning] = useState(false);

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [healthRes, mismatchRes] = await Promise.all([
                fetch(`${API_BASE}/api/admin/billing/health`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE}/api/admin/billing/health/mismatches?limit=20`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ]);

            if (healthRes.ok) setHealth(await healthRes.json());
            if (mismatchRes.ok) {
                const data = await mismatchRes.json();
                setMismatches(data.items);
            }
        } catch (e) {
            console.error('Failed to load health data');
        } finally {
            setLoading(false);
        }
    };

    const runReconciliation = async () => {
        if (!confirm('Run reconciliation job now? This may take a while.')) return;

        setRunning(true);
        try {
            const res = await fetch(`${API_BASE}/api/admin/billing/health/run-reconciliation`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                alert(`Reconciliation complete: ${JSON.stringify(data.stats)}`);
                fetchData();
            } else {
                alert('Failed to run reconciliation');
            }
        } catch (e) {
            alert('Error running reconciliation');
        } finally {
            setRunning(false);
        }
    };

    const exportCSV = () => {
        window.open(`${API_BASE}/api/admin/billing/health/export`, '_blank');
    };

    if (loading) {
        return <div className="p-8">Loading...</div>;
    }

    return (
        <div className="p-8 max-w-6xl">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">❤️ Billing Health</h1>
                <div className="flex gap-2">
                    <button
                        onClick={exportCSV}
                        className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded"
                    >
                        Export CSV
                    </button>
                    <button
                        onClick={runReconciliation}
                        disabled={running}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
                    >
                        {running ? 'Running...' : 'Run Reconciliation'}
                    </button>
                </div>
            </div>

            {/* Health Dashboard */}
            {health && (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                    <div className="bg-white border rounded-lg p-4">
                        <div className={`text-2xl font-bold ${health.mismatch_count_today > 0 ? 'text-red-600' : 'text-green-600'}`}>
                            {health.mismatch_count_today}
                        </div>
                        <div className="text-sm text-gray-500">Mismatches Today</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className="text-2xl font-bold">{health.mismatch_count_7d}</div>
                        <div className="text-sm text-gray-500">Mismatches (7d)</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className={`text-2xl font-bold ${health.stuck_holds_count > 0 ? 'text-orange-600' : ''}`}>
                            {health.stuck_holds_count}
                        </div>
                        <div className="text-sm text-gray-500">Stuck Holds</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className="text-2xl font-bold">{health.stuck_holds_p95_age}s</div>
                        <div className="text-sm text-gray-500">P95 Hold Age</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className={`text-2xl font-bold ${health.billing_errors_24h > 0 ? 'text-red-600' : ''}`}>
                            {health.billing_errors_24h}
                        </div>
                        <div className="text-sm text-gray-500">Errors (24h)</div>
                    </div>
                    <div className="bg-white border rounded-lg p-4">
                        <div className={`text-2xl font-bold ${health.autofix_enabled ? 'text-green-600' : 'text-gray-400'}`}>
                            {health.autofix_enabled ? 'ON' : 'OFF'}
                        </div>
                        <div className="text-sm text-gray-500">Autofix</div>
                    </div>
                </div>
            )}

            {/* Mismatches Table */}
            <h2 className="text-xl font-bold mb-4">⚠️ Balance Mismatches</h2>
            <div className="bg-white border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left">User</th>
                            <th className="px-4 py-3 text-left">Cached</th>
                            <th className="px-4 py-3 text-left">Computed</th>
                            <th className="px-4 py-3 text-left">Delta</th>
                            <th className="px-4 py-3 text-left">Last Fix</th>
                        </tr>
                    </thead>
                    <tbody>
                        {mismatches.map((m) => (
                            <tr key={m.user_id} className="border-t hover:bg-gray-50">
                                <td className="px-4 py-3">
                                    <div>{m.user_email}</div>
                                    <div className="text-xs text-gray-400">ID: {m.user_id}</div>
                                </td>
                                <td className="px-4 py-3">{m.cached_balance.toFixed(2)}</td>
                                <td className="px-4 py-3">{m.computed_balance.toFixed(2)}</td>
                                <td className={`px-4 py-3 font-bold ${m.delta > 0 ? 'text-red-600' : 'text-green-600'}`}>
                                    {m.delta > 0 ? '+' : ''}{m.delta.toFixed(2)}
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                    {m.last_fix_time ? new Date(m.last_fix_time).toLocaleString() : 'Never'}
                                </td>
                            </tr>
                        ))}
                        {mismatches.length === 0 && (
                            <tr>
                                <td colSpan={5} className="px-4 py-8 text-center text-green-600">
                                    ✓ No balance mismatches detected
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
