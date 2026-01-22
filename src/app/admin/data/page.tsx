"use client";

import { useEffect, useMemo, useState } from "react";

export default function AdminDataPage() {
    const [tables, setTables] = useState<string[]>([]);
    const [selectedTable, setSelectedTable] = useState<string>("");
    const [rows, setRows] = useState<any[]>([]);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [filter, setFilter] = useState("");
    const [limit, setLimit] = useState(200);
    const [offset, setOffset] = useState(0);

    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    const getHeaders = () => {
        const token = localStorage.getItem("token");
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    useEffect(() => {
        const controller = new AbortController();
        const fetchTables = async () => {
            try {
                const res = await fetch(`${baseUrl}/api/v1/admin/db/tables`, { headers: getHeaders(), signal: controller.signal });
                if (!res.ok) throw new Error("Failed to load tables.");
                const data = await res.json();
                setTables(Array.isArray(data) ? data : []);
                if (Array.isArray(data) && data.length > 0) {
                    setSelectedTable(data[0]);
                }
            } catch (err) {
                if ((err as Error).name === "AbortError") return;
                console.error("Failed to fetch tables:", err);
                setErrorMessage("Unable to load table list.");
            } finally {
                setIsLoading(false);
            }
        };
        fetchTables();
        return () => controller.abort();
    }, [baseUrl]);

    useEffect(() => {
        if (!selectedTable) return;
        const controller = new AbortController();
        const fetchRows = async () => {
            try {
                const res = await fetch(`${baseUrl}/api/v1/admin/db/table/${encodeURIComponent(selectedTable)}?limit=${limit}&offset=${offset}`, { headers: getHeaders(), signal: controller.signal });
                if (!res.ok) throw new Error("Failed to load rows.");
                const data = await res.json();
                setRows(Array.isArray(data) ? data : []);
            } catch (err) {
                if ((err as Error).name === "AbortError") return;
                console.error("Failed to fetch rows:", err);
                setErrorMessage("Unable to load table data.");
            }
        };
        fetchRows();
        return () => controller.abort();
    }, [selectedTable, limit, offset, baseUrl]);

    const filteredRows = useMemo(() => {
        if (!filter.trim()) return rows;
        const needle = filter.trim().toLowerCase();
        return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(needle));
    }, [filter, rows]);

    if (isLoading) return <div className="p-8 text-slate-400">Loading data explorer...</div>;
    if (errorMessage) return <div className="p-8 text-rose-400">{errorMessage}</div>;

    const columns = filteredRows.length > 0 ? Object.keys(filteredRows[0]) : [];

    return (
        <div className="p-8 max-w-[1400px] mx-auto w-full flex flex-col gap-6">
            <header className="flex flex-col gap-2">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Data Explorer</h2>
                <p className="text-sm text-slate-400">Browse raw database tables with filters and pagination.</p>
            </header>
            <div className="flex flex-wrap items-center gap-4">
                <select
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-900 dark:text-white"
                    value={selectedTable}
                    onChange={(e) => {
                        setSelectedTable(e.target.value);
                        setOffset(0);
                    }}
                >
                    {tables.map((table) => (
                        <option key={table} value={table}>
                            {table}
                        </option>
                    ))}
                </select>
                <input
                    className="flex-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-900 dark:text-white placeholder:text-slate-600"
                    placeholder="Filter rows (JSON search)"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                />
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>Limit</span>
                    <input
                        className="w-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-900 dark:text-white"
                        type="number"
                        value={limit}
                        min={1}
                        max={2000}
                        onChange={(e) => setLimit(Number(e.target.value))}
                    />
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>Offset</span>
                    <input
                        className="w-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-900 dark:text-white"
                        type="number"
                        value={offset}
                        min={0}
                        onChange={(e) => setOffset(Number(e.target.value))}
                    />
                </div>
            </div>
            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full text-left">
                        <thead className="bg-slate-50 dark:bg-slate-900/50">
                            <tr>
                                {columns.map((col) => (
                                    <th key={col} className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                                        {col}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                            {filteredRows.map((row, idx) => (
                                <tr key={idx} className="hover:bg-slate-100 dark:hover:bg-slate-800/40 transition-colors">
                                    {columns.map((col) => (
                                        <td key={col} className="px-4 py-3 text-[11px] text-slate-600 dark:text-slate-300 whitespace-pre-wrap break-words">
                                            {typeof row[col] === "object" ? JSON.stringify(row[col]) : String(row[col] ?? "")}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                            {filteredRows.length === 0 && (
                                <tr>
                                    <td colSpan={Math.max(columns.length, 1)} className="px-4 py-6 text-center text-sm text-slate-500">
                                        No rows available.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}
