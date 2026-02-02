"use client";

import { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Tab = "pricing" | "tokens" | "transactions" | "history" | "diagnostics";

interface ConfigVersion {
    id: number;
    version: number;
    config_type: string;
    change_msg: string;
    created_at: string;
    diff_json: Record<string, unknown>;
}

interface Transaction {
    id: number;
    user_id: number;
    action_type: string;
    status: string;
    estimated_credits: number;
    actual_credits: number;
    delta_credits: number;
    created_at: string;
}

export default function BillingControlCenter() {
    const [activeTab, setActiveTab] = useState<Tab>("pricing");
    const [loading, setLoading] = useState(false);
    const [pricingConfig, setPricingConfig] = useState<Record<string, unknown>>({});
    const [tokensConfig, setTokensConfig] = useState<Record<string, unknown>>({});
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [history, setHistory] = useState<ConfigVersion[]>([]);
    const [changeMsg, setChangeMsg] = useState("");

    // Calculator state
    const [calcInput, setCalcInput] = useState({ est_input: 500, est_output: 2000, act_input: 500, act_output: 1500, action_type: "solve_quick" });
    const [calcResult, setCalcResult] = useState<{ estimate: { credits: number }; actual: { credits: number }; delta_credits: number } | null>(null);

    // Diagnostics state
    const [diagUserId, setDiagUserId] = useState("");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [diagResult, setDiagResult] = useState<any>(null);
    const [seedAmount, setSeedAmount] = useState(1000);

    const getToken = () => typeof window !== "undefined" ? localStorage.getItem("token") : null;

    const fetchConfig = useCallback(async (type: string) => {
        setLoading(true);
        try {
            let url = `${API_BASE}/api/admin/config/${type}`;
            // Token limits use a different endpoint
            if (type === "tokens") {
                url = `${API_BASE}/api/v1/config/token-policy`;
            }
            const res = await fetch(url, {
                headers: { Authorization: `Bearer ${getToken()}` }
            });
            if (!res.ok) {
                if (type === "pricing") setPricingConfig({});
                else setTokensConfig({});
                setLoading(false);
                return;
            }
            const data = await res.json();
            if (type === "pricing") setPricingConfig(data || {});
            else setTokensConfig(data.policy || data || {});
        } catch (e) { console.error(e); }
        setLoading(false);
    }, []);

    const fetchTransactions = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/admin/transactions`, {
                headers: { Authorization: `Bearer ${getToken()}` }
            });
            if (!res.ok) { setTransactions([]); setLoading(false); return; }
            const data = await res.json();
            setTransactions(Array.isArray(data.data) ? data.data : []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, []);

    const fetchHistory = useCallback(async (type: string) => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/admin/config/history/${type}`, {
                headers: { Authorization: `Bearer ${getToken()}` }
            });
            if (!res.ok) { setHistory([]); setLoading(false); return; }
            const data = await res.json();
            setHistory(Array.isArray(data) ? data : []);
        } catch (e) { console.error(e); setHistory([]); }
        setLoading(false);
    }, []);

    const saveConfig = async (type: string, value: Record<string, unknown>) => {
        if (!changeMsg.trim()) { alert("Please provide a change message"); return; }
        setLoading(true);
        try {
            await fetch(`${API_BASE}/api/admin/config/${type}`, {
                method: "PUT",
                headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
                body: JSON.stringify({ value, change_msg: changeMsg })
            });
            setChangeMsg("");
            fetchConfig(type);
            alert("Saved successfully!");
        } catch (e) { console.error(e); alert("Save failed"); }
        setLoading(false);
    };

    const runCalculator = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/admin/calculator`, {
                method: "POST",
                headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
                body: JSON.stringify(calcInput)
            });
            const data = await res.json();
            setCalcResult(data);
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    useEffect(() => {
        const loadData = async () => {
            if (activeTab === "pricing") await fetchConfig("pricing");
            else if (activeTab === "tokens") await fetchConfig("tokens");
            else if (activeTab === "transactions") await fetchTransactions();
            else if (activeTab === "history") await fetchHistory("pricing");
        };
        loadData();
    }, [activeTab, fetchConfig, fetchTransactions, fetchHistory]);

    const checkUserCredits = async () => {
        if (!diagUserId) return;
        setLoading(true);
        try {
            // Check if input is email (contains @) or user ID
            const isEmail = diagUserId.includes("@");
            const param = isEmail ? `email=${encodeURIComponent(diagUserId)}` : `user_id=${diagUserId}`;
            const res = await fetch(`${API_BASE}/api/admin/diagnostics/credits?${param}`, {
                headers: { Authorization: `Bearer ${getToken()}` }
            });
            const data = await res.json();
            setDiagResult(data);
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const seedCredits = async () => {
        if (!diagUserId) return;
        setLoading(true);
        try {
            // Check if input is email (contains @) or user ID  
            const isEmail = diagUserId.includes("@");
            const param = isEmail ? `email=${encodeURIComponent(diagUserId)}` : `user_id=${diagUserId}`;
            const res = await fetch(`${API_BASE}/api/admin/credits/seed?${param}&amount=${seedAmount}`, {
                method: "POST",
                headers: { Authorization: `Bearer ${getToken()}` }
            });
            const data = await res.json();
            setDiagResult(data);
            alert("Credits seeded successfully!");
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const tabs: { key: Tab; label: string }[] = [
        { key: "pricing", label: "Pricing & Fees" },
        { key: "tokens", label: "Token Limits" },
        { key: "transactions", label: "Transactions" },
        { key: "history", label: "Config History" },
        { key: "diagnostics", label: "Diagnostics" }
    ];

    return (
        <div className="p-8">
            <h1 className="text-2xl font-bold mb-6">Billing Control Center</h1>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-slate-200 dark:border-slate-700">
                {tabs.map(t => (
                    <button
                        key={t.key}
                        onClick={() => setActiveTab(t.key)}
                        className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === t.key
                            ? "border-b-2 border-admin-primary text-admin-primary"
                            : "text-slate-500 hover:text-slate-700"}`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {loading && <p className="text-slate-500">Loading...</p>}

            {/* Pricing Tab */}
            {activeTab === "pricing" && !loading && (
                <div className="space-y-6">
                    <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow">
                        <h2 className="text-lg font-semibold mb-4">Token Pricing</h2>
                        <pre className="bg-slate-100 dark:bg-slate-900 p-4 rounded text-sm overflow-auto max-h-64">
                            {JSON.stringify(pricingConfig, null, 2)}
                        </pre>
                        <div className="mt-4 flex gap-2">
                            <input
                                placeholder="Change message..."
                                value={changeMsg}
                                onChange={e => setChangeMsg(e.target.value)}
                                className="flex-1 px-3 py-2 border rounded dark:bg-slate-700 dark:border-slate-600"
                            />
                            <button onClick={() => saveConfig("pricing", pricingConfig)} className="px-4 py-2 bg-admin-primary text-white rounded">
                                Save
                            </button>
                        </div>
                    </div>

                    {/* Calculator */}
                    <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow">
                        <h2 className="text-lg font-semibold mb-4">Billing Calculator</h2>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
                            <input type="number" placeholder="Est Input" value={calcInput.est_input} onChange={e => setCalcInput({ ...calcInput, est_input: +e.target.value })} className="px-3 py-2 border rounded dark:bg-slate-700" />
                            <input type="number" placeholder="Est Output" value={calcInput.est_output} onChange={e => setCalcInput({ ...calcInput, est_output: +e.target.value })} className="px-3 py-2 border rounded dark:bg-slate-700" />
                            <input type="number" placeholder="Act Input" value={calcInput.act_input} onChange={e => setCalcInput({ ...calcInput, act_input: +e.target.value })} className="px-3 py-2 border rounded dark:bg-slate-700" />
                            <input type="number" placeholder="Act Output" value={calcInput.act_output} onChange={e => setCalcInput({ ...calcInput, act_output: +e.target.value })} className="px-3 py-2 border rounded dark:bg-slate-700" />
                            <select value={calcInput.action_type} onChange={e => setCalcInput({ ...calcInput, action_type: e.target.value })} className="px-3 py-2 border rounded dark:bg-slate-700">
                                <option value="solve_quick">solve_quick</option>
                                <option value="solve_tutor">solve_tutor</option>
                                <option value="image_import">image_import</option>
                            </select>
                        </div>
                        <button onClick={runCalculator} className="px-4 py-2 bg-green-600 text-white rounded">Calculate</button>
                        {calcResult && (
                            <div className="mt-4 p-4 bg-slate-100 dark:bg-slate-900 rounded">
                                {calcResult.estimate ? (
                                    <>
                                        <p><strong>Estimated:</strong> {calcResult.estimate.credits ?? 0} credits</p>
                                        <p><strong>Actual:</strong> {calcResult.actual?.credits ?? 0} credits</p>
                                        <p><strong>Delta:</strong> {calcResult.delta_credits ?? 0} credits</p>
                                    </>
                                ) : (
                                    <p className="text-red-500">Error: {JSON.stringify(calcResult)}</p>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Token Limits Tab */}
            {activeTab === "tokens" && !loading && (
                <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow">
                    <h2 className="text-lg font-semibold mb-4">Token Limits Configuration</h2>
                    <pre className="bg-slate-100 dark:bg-slate-900 p-4 rounded text-sm overflow-auto max-h-64">
                        {JSON.stringify(tokensConfig, null, 2)}
                    </pre>
                    <div className="mt-4 flex gap-2">
                        <input
                            placeholder="Change message..."
                            value={changeMsg}
                            onChange={e => setChangeMsg(e.target.value)}
                            className="flex-1 px-3 py-2 border rounded dark:bg-slate-700 dark:border-slate-600"
                        />
                        <button onClick={() => saveConfig("tokens", tokensConfig)} className="px-4 py-2 bg-admin-primary text-white rounded">
                            Save
                        </button>
                    </div>
                </div>
            )}

            {/* Transactions Tab */}
            {activeTab === "transactions" && !loading && (
                <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow overflow-x-auto">
                    <h2 className="text-lg font-semibold mb-4">Transaction Ledger</h2>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b dark:border-slate-700">
                                <th className="text-left py-2">ID</th>
                                <th className="text-left py-2">User</th>
                                <th className="text-left py-2">Action</th>
                                <th className="text-left py-2">Status</th>
                                <th className="text-right py-2">Est Credits</th>
                                <th className="text-right py-2">Act Credits</th>
                                <th className="text-right py-2">Delta</th>
                                <th className="text-left py-2">Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {transactions.map(tx => (
                                <tr key={tx.id} className="border-b dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700">
                                    <td className="py-2">{tx.id}</td>
                                    <td className="py-2">{tx.user_id}</td>
                                    <td className="py-2">{tx.action_type}</td>
                                    <td className="py-2">
                                        <span className={`px-2 py-1 rounded text-xs ${tx.status === "SETTLED" ? "bg-green-100 text-green-800" : tx.status === "PENDING" ? "bg-yellow-100 text-yellow-800" : "bg-red-100 text-red-800"}`}>
                                            {tx.status}
                                        </span>
                                    </td>
                                    <td className="py-2 text-right">{tx.estimated_credits}</td>
                                    <td className="py-2 text-right">{tx.actual_credits}</td>
                                    <td className="py-2 text-right">{tx.delta_credits}</td>
                                    <td className="py-2">{new Date(tx.created_at).toLocaleString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {transactions.length === 0 && <p className="text-slate-500 mt-4">No transactions found.</p>}
                </div>
            )}

            {/* Config History Tab */}
            {activeTab === "history" && !loading && (
                <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow">
                    <h2 className="text-lg font-semibold mb-4">Configuration History</h2>
                    <div className="space-y-4">
                        {history.map(ver => (
                            <div key={ver.id} className="border dark:border-slate-700 rounded p-4">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <p className="font-medium">v{ver.version} - {ver.change_msg}</p>
                                        <p className="text-xs text-slate-500">{new Date(ver.created_at).toLocaleString()}</p>
                                    </div>
                                    <button className="text-xs px-2 py-1 bg-slate-200 dark:bg-slate-700 rounded">Revert</button>
                                </div>
                                {ver.diff_json && Object.keys(ver.diff_json).length > 0 && (
                                    <pre className="mt-2 text-xs bg-slate-100 dark:bg-slate-900 p-2 rounded overflow-auto max-h-32">
                                        {JSON.stringify(ver.diff_json, null, 2)}
                                    </pre>
                                )}
                            </div>
                        ))}
                        {history.length === 0 && <p className="text-slate-500">No history found.</p>}
                    </div>
                </div>
            )}

            {/* Diagnostics Tab */}
            {activeTab === "diagnostics" && !loading && (
                <div className="space-y-6">
                    <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow">
                        <h2 className="text-lg font-semibold mb-4">User Credit Diagnostics</h2>
                        <div className="flex gap-4 mb-4">
                            <input
                                type="text"
                                placeholder="Email or User ID"
                                value={diagUserId}
                                onChange={e => setDiagUserId(e.target.value)}
                                className="px-3 py-2 border rounded dark:bg-slate-700 w-64"
                            />
                            <button onClick={checkUserCredits} className="px-4 py-2 bg-blue-600 text-white rounded">
                                Check Credits
                            </button>
                            <input
                                type="number"
                                placeholder="Amount"
                                value={seedAmount}
                                onChange={e => setSeedAmount(+e.target.value)}
                                className="px-3 py-2 border rounded dark:bg-slate-700 w-32"
                            />
                            <button onClick={seedCredits} className="px-4 py-2 bg-green-600 text-white rounded">
                                Seed Credits
                            </button>
                        </div>
                        {diagResult && (
                            <pre className="bg-slate-100 dark:bg-slate-900 p-4 rounded text-sm overflow-auto max-h-96">
                                {JSON.stringify(diagResult, null, 2)}
                            </pre>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
